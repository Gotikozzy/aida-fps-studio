"""Read back MP4 boundaries before publishing; no measurement or rendering changes."""

from __future__ import annotations

import os
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path

import av


class ExportVerificationError(RuntimeError):
    pass


def synchronize_file(path: Path) -> None:
    with path.open("r+b") as handle:
        handle.flush()
        os.fsync(handle.fileno())


def verify_mp4(
    path: Path,
    *,
    frames: int,
    last_pts: int,
    width: int,
    height: int,
    check_cancelled: Callable[[], None],
    expected_size: int | None = None,
    verify_tail: bool = True,
) -> int:
    """Check header/count and decode the first/last frame, rather than the entire video."""
    try:
        check_cancelled()
        size = path.stat().st_size
        if not path.is_file() or size <= 0 or (expected_size is not None and size != expected_size):
            raise ValueError("MP4 ausente, vazio ou com tamanho inesperado")
        with av.open(str(path), mode="r") as container:
            if "mp4" not in container.format.name or not container.streams.video:
                raise ValueError("Arquivo sem stream de vídeo MP4")
            stream = container.streams.video[0]
            if stream.frames != frames:
                raise ValueError(f"Contagem de frames incorreta: {stream.frames}/{frames}")
            if stream.codec_context.name != "h264":
                raise ValueError("Codec H.264 não confirmado")
            first = next(container.decode(video=0))
            if (first.width, first.height) != (width, height) or first.pts != 0:
                raise ValueError("Primeiro frame inválido")
            check_cancelled()
            if verify_tail:
                last_time = Fraction(last_pts, 90000)
                if stream.time_base is None:
                    raise ValueError("Base temporal ausente")
                container.seek(int(last_time / stream.time_base), stream=stream, backward=True)
                last = None
                for frame in container.decode(video=0):
                    check_cancelled()
                    if frame.pts is None or frame.time_base is None:
                        raise ValueError("Timestamp ausente no MP4")
                    last = frame.pts * frame.time_base
                    if last >= last_time:
                        break
                if last is None or abs(last - last_time) > max(
                    stream.time_base, Fraction(1, 90000)
                ):
                    raise ValueError("Último frame não confirmado")
        return size
    except (OSError, av.error.FFmpegError, ValueError, StopIteration) as exc:
        raise ExportVerificationError(f"Não foi possível validar o MP4 em {path}: {exc}") from exc
