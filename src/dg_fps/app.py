from __future__ import annotations

import json
import logging
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from platformdirs import user_cache_path, user_data_path, user_log_path
from PySide6.QtCore import QTimer
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtWidgets import QApplication

from dg_fps import __version__


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "reason"):
            payload["reason"] = record.reason
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def main() -> int:
    log_path = user_log_path("AIDA FPS Studio", "DG")
    log_path.mkdir(parents=True, exist_ok=True)
    from logging.handlers import RotatingFileHandler

    handler = RotatingFileHandler(
        log_path / "aida-fps-studio.jsonl", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    application = QApplication(sys.argv)
    application.setApplicationName("AIDA FPS Studio")
    application.setApplicationVersion(__version__)
    application.setOrganizationName("DG")
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        from dg_fps.diagnostics import run_self_test

        return run_self_test(Path(sys.argv[2]))
    from dg_fps.ui.splash import StartupSplash

    application.setWindowIcon(QIcon(str(Path(__file__).parent / "assets/aida.ico")))
    screen = application.screenAt(QCursor.pos()) or application.primaryScreen()
    splash = StartupSplash(screen)
    splash.start()
    try:
        splash.report("Loading interface and media components...")
        from dg_fps.ui.main_window import FPSWindow
        from dg_fps.ui.theme import ANALYST_STYLE

        application.setStyleSheet(ANALYST_STYLE)
        splash.report("Reading preferences and cache paths...")
        data, cache, first_launch = _startup_storage()
        splash.report("Building the studio workspace...")
        window = FPSWindow(data, cache)
    except Exception:
        splash.close()
        logging.exception("startup_failed")
        raise

    def open_initial_view() -> None:
        if len(sys.argv) > 1 and Path(sys.argv[1]).is_file():
            source = Path(sys.argv[1])
            if source.suffix.lower() == ".aida":
                window._open_project(source)
            else:
                window.open_source(source)
        elif first_launch:
            window._show_preferences()
        QTimer.singleShot(0, window._start_update_check)

    splash.reveal_when_ready(window, lambda: QTimer.singleShot(0, open_initial_view))
    return application.exec()


def _startup_storage() -> tuple[Path, Path, bool]:
    data = user_data_path("AIDA FPS Studio", "DG")
    legacy = user_data_path("DG FPS", "DG")
    data.mkdir(parents=True, exist_ok=True)
    settings = data / "settings.json"
    if not settings.exists() and (legacy / "settings.json").is_file():
        shutil.copy2(legacy / "settings.json", settings)
    first_launch = not settings.exists()
    if first_launch and (legacy / "resultados").is_dir():
        settings.write_text(
            json.dumps({"legacy_results": str(legacy / "resultados")}), encoding="utf-8"
        )
    if (legacy / "resultados").is_dir():
        try:
            previous_settings = (
                json.loads(settings.read_text("utf-8")) if settings.is_file() else {}
            )
            if isinstance(previous_settings, dict) and "legacy_results" not in previous_settings:
                previous_settings["legacy_results"] = str(legacy / "resultados")
                settings.write_text(
                    json.dumps(previous_settings, ensure_ascii=False), encoding="utf-8"
                )
        except (OSError, ValueError):
            logging.exception("legacy_results_link_failed")
    cache = user_cache_path("DG FPS", "DG")
    if not cache.exists():
        cache = user_cache_path("AIDA FPS Studio", "DG")
    return data, cache, first_launch
