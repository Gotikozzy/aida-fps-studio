from __future__ import annotations

import hashlib
import json
import logging
import re
import stat
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import cast
from zipfile import BadZipFile, ZipFile

from PySide6.QtCore import QObject, QThread, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

SITE_URL = "https://detonandogueek.com.br"
AIDA_URL = f"{SITE_URL}/aida"
HELP_URL = f"{AIDA_URL}/ajuda"
UPDATE_URL = f"{AIDA_URL}/update.json"
MAX_MANIFEST_BYTES = 4096
UPDATE_TIMEOUT_MS = 5000
MAX_PACKAGE_BYTES = 1024 * 1024 * 1024
_VERSION = re.compile(r"(?:0|[1-9][0-9]{0,8})(?:\.(?:0|[1-9][0-9]{0,8})){2}")


def version_key(version: str) -> tuple[int, int, int]:
    if not isinstance(version, str) or _VERSION.fullmatch(version) is None:
        raise ValueError("Invalid stable version")
    return cast(tuple[int, int, int], tuple(map(int, version.split("."))))


@dataclass(frozen=True)
class UpdateRelease:
    version: str
    sha256: str | None = None
    size: int | None = None

    def __post_init__(self) -> None:
        version_key(self.version)

    @property
    def filename(self) -> str:
        return f"AIDA-FPS-Studio-{self.version}-windows-x64-setup.zip"

    @property
    def url(self) -> str:
        return f"{SITE_URL}/static/aida/{self.filename}"


def manifest_release(payload: bytes) -> UpdateRelease:
    if len(payload) > MAX_MANIFEST_BYTES:
        raise ValueError("Update manifest too large")
    document = json.loads(payload.decode("utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Invalid update manifest")
    version = document.get("version")
    version_key(version)
    digest, size = document.get("sha256"), document.get("size")
    if digest is not None and (not isinstance(digest, str)
                               or re.fullmatch(r"[a-fA-F0-9]{64}", digest) is None):
        raise ValueError("Invalid update digest")
    if size is not None and (type(size) is not int or not 0 < size <= MAX_PACKAGE_BYTES):
        raise ValueError("Invalid update size")
    return UpdateRelease(version, digest.lower() if digest else None, size)


def manifest_version(payload: bytes) -> str:
    return manifest_release(payload).version


class UpdateCheck(QObject):
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._network = QNetworkAccessManager(self)
        self._reply: QNetworkReply | None = None
        self._oversize = False
        self.release: UpdateRelease | None = None
        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.timeout.connect(self._abort)

    def start(self) -> None:
        if self._reply is not None:
            return
        request = QNetworkRequest(QUrl(UPDATE_URL))
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.ManualRedirectPolicy,
        )
        request.setRawHeader(b"Accept", b"application/json")
        request.setRawHeader(b"Cache-Control", b"no-cache")
        request.setAttribute(QNetworkRequest.Attribute.CacheLoadControlAttribute,
                             QNetworkRequest.CacheLoadControl.AlwaysNetwork)
        self._oversize = False
        self.release = None
        reply = self._network.get(request)
        self._reply = reply
        reply.setReadBufferSize(MAX_MANIFEST_BYTES + 1)
        reply.readyRead.connect(self._limit)
        reply.finished.connect(self._finish)
        self._timeout.start(UPDATE_TIMEOUT_MS)

    def _abort(self) -> None:
        if self._reply is not None:
            self._reply.abort()

    def _limit(self) -> None:
        if self._reply is not None and self._reply.bytesAvailable() > MAX_MANIFEST_BYTES:
            self._oversize = True
            self._abort()

    def _finish(self) -> None:
        reply, self._reply = self._reply, None
        self._timeout.stop()
        if reply is None:
            return
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        reply.deleteLater()
        if self._oversize:
            self.failed.emit("invalid")
        elif status == 404:
            self.failed.emit("unpublished")
        elif status != 200 or reply.error() != QNetworkReply.NetworkError.NoError:
            self.failed.emit("unreachable")
        else:
            try:
                self.release = manifest_release(bytes(reply.read(MAX_MANIFEST_BYTES + 1)))
            except (ValueError, RecursionError):
                self.failed.emit("invalid")
            else:
                self.succeeded.emit(self.release.version)


class UpdateDownload(QObject):
    """Stream the official, version-pinned ZIP and verify it before exposing it."""

    progress = Signal(int, int)
    succeeded = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, release: UpdateRelease, directory: Path, parent=None):
        super().__init__(parent)
        self.release = release
        self.directory = directory
        self._network = QNetworkAccessManager(self)
        self._reply: QNetworkReply | None = None
        self._digest = release.sha256
        self._hash = hashlib.sha256()
        self._count = 0
        self._stream = None
        self._part = directory / (release.filename + ".part")
        self._cancelled = False
        self._error = ""

    def start(self) -> None:
        if self._reply is not None:
            return
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            self._stream = self._part.open("xb")
        except OSError:
            self.failed.emit("storage")
            return
        self._request(self.release.url if self._digest else
                      self.release.url.removesuffix(".zip") + ".sha256", checksum=not self._digest)

    def _request(self, url: str, *, checksum: bool) -> None:
        request = QNetworkRequest(QUrl(url))
        request.setTransferTimeout(30_000)
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.SameOriginRedirectPolicy)
        request.setRawHeader(b"Cache-Control", b"no-cache")
        self._checksum_request = checksum
        reply = self._network.get(request)
        self._reply = reply
        reply.setReadBufferSize(1024 if checksum else 1024 * 1024)
        if checksum:
            reply.readyRead.connect(self._limit_checksum)
        else:
            reply.readyRead.connect(self._drain)
        reply.finished.connect(lambda: self._finish(reply))

    def _limit_checksum(self) -> None:
        if self._reply is not None and self._reply.bytesAvailable() > 512:
            self._error = "integrity"
            self._reply.abort()

    def cancel(self) -> None:
        self._cancelled = True
        if self._reply is not None:
            self._reply.abort()

    def _drain(self) -> None:
        reply = self._reply
        if reply is None or self._stream is None:
            return
        total = reply.header(QNetworkRequest.KnownHeaders.ContentLengthHeader)
        total = total if isinstance(total, int) and total > 0 else 0
        if total > MAX_PACKAGE_BYTES or (self.release.size and total
                                         and total != self.release.size):
            self._error = "integrity"
            reply.abort()
            return
        while reply.bytesAvailable():
            chunk = bytes(reply.read(1024 * 1024))
            if not chunk:
                break
            self._count += len(chunk)
            if self._count > MAX_PACKAGE_BYTES or (
                self.release.size and self._count > self.release.size
            ):
                self._error = "integrity"
                reply.abort()
                return
            try:
                self._stream.write(chunk)
            except OSError:
                self._error = "storage"
                reply.abort()
                return
            self._hash.update(chunk)
            self.progress.emit(self._count, self.release.size or total)

    def _discard(self) -> None:
        if self._stream is not None:
            try:
                self._stream.close()
            except OSError:
                logging.exception("update_partial_close_failed")
            self._stream = None
        try:
            self._part.unlink(missing_ok=True)
        except OSError:
            logging.exception("update_partial_cleanup_failed")

    def _finish(self, reply: QNetworkReply) -> None:
        if self._reply is not reply:
            return
        if not self._checksum_request and not self._error and not self._cancelled:
            self._drain()
        if self._reply is not reply:
            return
        self._reply = None
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        payload = bytes(reply.read(513)) if self._checksum_request else b""
        error = reply.error()
        reply.deleteLater()
        if (self._cancelled or self._error or status != 200
                or error != QNetworkReply.NetworkError.NoError):
            self._discard()
            if self._cancelled:
                self.cancelled.emit()
            else:
                self.failed.emit(self._error or "network")
            return
        if self._checksum_request:
            try:
                fields = payload.decode("ascii").strip().split()
                if not fields or re.fullmatch(r"[a-fA-F0-9]{64}", fields[0]) is None:
                    raise ValueError("Invalid checksum")
                if len(fields) > 2 or (len(fields) == 2
                                      and fields[1].lstrip("*") != self.release.filename):
                    raise ValueError("Checksum names another package")
                self._digest = fields[0].lower()
            except (UnicodeError, ValueError):
                self._discard()
                self.failed.emit("integrity")
                return
            self._request(self.release.url, checksum=False)
            return
        if (self._hash.hexdigest() != self._digest or self._count == 0
                or (self.release.size and self._count != self.release.size)):
            self._discard()
            self.failed.emit("integrity")
            return
        try:
            self._stream.close()
            self._stream = None
            target = self.directory / self.release.filename
            self._part.replace(target)
        except OSError:
            self._discard()
            self.failed.emit("storage")
            return
        logging.info("update_download_verified", extra={"reason": self.release.version})
        self.succeeded.emit(target)


def prepare_installer(package: Path, release: UpdateRelease, cancel: Event) -> Path:
    """Only the expected installer can leave the archive; no extractall/path trust."""
    expected = release.filename.removesuffix(".zip") + ".exe"
    target = package.parent / expected
    partial = target.with_suffix(".exe.part")
    try:
        with ZipFile(package) as archive:
            entries = archive.infolist()
            if len(entries) != 1:
                raise ValueError("Unexpected archive entries")
            info = entries[0]
            if (info.filename != expected or info.is_dir()
                    or stat.S_ISLNK(info.external_attr >> 16)
                    or not 0 < info.file_size <= MAX_PACKAGE_BYTES):
                raise ValueError("Invalid installer entry")
            with archive.open(info) as source, partial.open("xb") as output:
                written = 0
                while chunk := source.read(1024 * 1024):
                    if cancel.is_set():
                        raise InterruptedError("Update cancelled")
                    written += len(chunk)
                    if written > MAX_PACKAGE_BYTES:
                        raise ValueError("Installer too large")
                    output.write(chunk)
            with partial.open("rb") as stream:
                header = stream.read(64)
                if len(header) < 64 or header[:2] != b"MZ":
                    raise ValueError("Not a Windows executable")
                offset = struct.unpack_from("<I", header, 60)[0]
                if not 64 <= offset <= info.file_size - 4:
                    raise ValueError("Invalid PE header")
                stream.seek(offset)
                if stream.read(4) != b"PE\0\0":
                    raise ValueError("Not a Windows executable")
        if cancel.is_set():
            raise InterruptedError("Update cancelled")
        partial.replace(target)
        return target
    finally:
        partial.unlink(missing_ok=True)


class PrepareUpdate(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, package: Path, release: UpdateRelease, parent=None):
        super().__init__(parent)
        self.package, self.release = package, release
        self.cancel_event = Event()

    def run(self) -> None:
        try:
            installer = prepare_installer(self.package, self.release, self.cancel_event)
        except InterruptedError:
            self.failed.emit("cancelled")
        except (OSError, ValueError, RuntimeError, BadZipFile) as exc:
            logging.exception("update_preparation_failed")
            self.failed.emit(type(exc).__name__)
        else:
            self.succeeded.emit(installer)


def launch_installer(installer: Path, parent_pid: int) -> None:
    if not installer.is_absolute() or not installer.is_file() or installer.suffix != ".exe":
        raise OSError("Update installer unavailable")
    subprocess.Popen([str(installer), f"/UPDATEPID={parent_pid}"], close_fds=True)
