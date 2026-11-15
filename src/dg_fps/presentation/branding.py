from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter

BRAND_ACRONYM = "AIDA"
BRAND_NAME = "ANÁLISE DE FPS E CADÊNCIA VISUAL"
BRAND_SITE = "detonandogueek.com.br"


@lru_cache(maxsize=1)
def _brand_icon() -> QImage:
    return QImage(str(Path(__file__).resolve().parents[1] / "assets" / "aida.png"))


def draw_video_branding(
    painter: QPainter,
    canvas_width: int,
    *,
    x: float,
    y: float,
    background: bool = False,
    language: str = "pt",
    show_site: bool = True,
) -> float:
    scale = max(0.35, min(1.0, canvas_width / 1920.0))
    icon_size = 20.0 * scale
    text_x = x + icon_size + 7.0 * scale
    total_width = 570.0 * scale
    total_height = 54.0 * scale
    if background:
        painter.fillRect(
            QRectF(x - 8 * scale, y - 6 * scale, total_width, total_height + 12 * scale),
            QColor(8, 12, 18, 205),
        )
    baseline = y + 16 * scale
    icon = _brand_icon()
    if not icon.isNull():
        size = QSizeF(icon.size()).scaled(
            QSizeF(icon_size, icon_size), Qt.AspectRatioMode.KeepAspectRatio
        )
        painter.drawImage(
            QRectF(x, baseline - size.height() + 2 * scale, size.width(), size.height()),
            icon,
        )
    acronym_font = QFont("Segoe UI", max(7, round(14 * scale)), QFont.Weight.Bold)
    painter.setPen(QColor("#f8fafc"))
    painter.setFont(acronym_font)
    painter.drawText(QPointF(text_x, baseline), BRAND_ACRONYM)
    acronym_width = QFontMetricsF(acronym_font).horizontalAdvance(BRAND_ACRONYM)
    name_x = text_x + acronym_width + 18 * scale
    painter.setPen(QColor("#a8b3c4"))
    painter.setFont(QFont("Segoe UI", max(5, round(8 * scale))))
    name = "FPS & VISUAL CADENCE ANALYSIS" if language == "en" else BRAND_NAME
    painter.drawText(QPointF(name_x, baseline), name)
    painter.setPen(QColor("#f59e0b"))
    painter.setFont(QFont("Segoe UI", max(6, round(10 * scale))))
    if show_site:
        painter.drawText(
            QRectF(text_x, y + 23 * scale, 500 * scale, 18 * scale),
            BRAND_SITE,
        )
    return y + total_height
