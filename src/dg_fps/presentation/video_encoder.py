from __future__ import annotations

import io
from dataclasses import dataclass
from fractions import Fraction

import av
import numpy as np


class EncoderUnavailable(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class VideoEncoderSelection:
    stream: av.VideoStream
    codec: str
    description: str


def probe_nvenc(width: int, height: int) -> bool:
    """Exercise encoding and flush rather than trust a codec list."""
    if "h264_nvenc" not in av.codecs_available:
        return False
    try:
        with av.open(io.BytesIO(), "w", format="mp4") as output:
            stream = output.add_stream("h264_nvenc", rate=30)
            stream.width, stream.height, stream.pix_fmt = width, height, "yuv420p"
            frame = av.VideoFrame.from_ndarray(np.zeros((height, width, 3), np.uint8), "rgb24")
            for packet in stream.encode(frame):
                output.mux(packet)
            for packet in stream.encode():
                output.mux(packet)
        return True
    except (av.error.FFmpegError, ValueError):
        return False


def add_video_stream(
    container: av.OutputContainer,
    *,
    rate: Fraction | int,
    width: int,
    height: int,
    quality: int = 18,
    cpu_preset: str = "medium",
    mode: str = "cpu",
) -> VideoEncoderSelection:
    if mode not in {"cpu", "auto", "nvidia"}:
        raise ValueError("Modo de codificação inválido")
    accelerated = mode != "cpu" and probe_nvenc(width, height)
    if mode == "nvidia" and not accelerated:
        raise EncoderUnavailable("Codificação NVIDIA indisponível; usando CPU")
    codec = "h264_nvenc" if accelerated else "libopenh264"
    stream = container.add_stream(codec, rate=rate)
    stream.width, stream.height, stream.pix_fmt = width, height, "yuv420p"
    stream.time_base = Fraction(1, 90000)
    stream.codec_context.time_base = Fraction(1, 90000)
    normalized = str(max(0, min(51, quality)))
    if accelerated:
        stream.options = {"preset": "p5", "rc": "vbr", "cq": normalized, "b": "0"}
    else:
        # OpenH264 is BSD-licensed. Keep every output frame even when a scene
        # exceeds the bitrate target; export verification also checks the count.
        stream.bit_rate = max(2_000_000, round(width * height * float(rate) * 0.20))
        stream.codec_context.qmin = int(normalized)
        stream.codec_context.qmax = min(51, int(normalized) + 4)
        stream.options = {"rc_mode": "quality", "profile": "high", "allow_skip_frames": "0"}
    stream.codec_context.color_primaries = 1
    stream.codec_context.color_trc = 1
    stream.codec_context.colorspace = 1
    return VideoEncoderSelection(
        stream, codec, f"H.264 {'NVENC' if accelerated else 'CPU'} / BT.709"
    )
