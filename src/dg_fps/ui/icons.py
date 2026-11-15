"""Small monochrome transport icons, independent of the Windows light/dark theme."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF


def action_icon(kind: str) -> QIcon:
    """Consistent native outline icons; no font glyph or theme dependency."""
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(
        QPen(
            QColor("#e0e7f0"),
            1.7,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
    )
    p.setBrush(Qt.BrushStyle.NoBrush)
    if kind == "folder":
        p.drawPolyline(
            QPolygonF(
                [
                    QPointF(3, 19),
                    QPointF(3, 6),
                    QPointF(9, 6),
                    QPointF(11, 8),
                    QPointF(21, 8),
                    QPointF(21, 19),
                    QPointF(3, 19),
                ]
            )
        )
        p.drawLine(3, 11, 21, 11)
    elif kind in {"add", "close"}:
        if kind == "add":
            p.drawLine(5, 12, 19, 12)
            p.drawLine(12, 5, 12, 19)
        else:
            p.drawLine(6, 6, 18, 18)
            p.drawLine(6, 18, 18, 6)
    elif kind == "delete":
        p.drawRoundedRect(QRectF(6, 7, 12, 14), 2, 2)
        p.drawLine(4, 6, 20, 6)
        p.drawLine(9, 3, 15, 3)
        p.drawLine(10, 10, 10, 17)
        p.drawLine(14, 10, 14, 17)
    elif kind == "more":
        p.setBrush(QColor("#e0e7f0"))
        for x in (5, 12, 19):
            p.drawEllipse(QPointF(x, 12), 1, 1)
    elif kind == "analyze":
        p.drawPolyline(
            QPolygonF(
                [
                    QPointF(3, 14),
                    QPointF(7, 14),
                    QPointF(10, 6),
                    QPointF(14, 19),
                    QPointF(17, 10),
                    QPointF(21, 10),
                ]
            )
        )
    elif kind == "export":
        p.drawLine(12, 3, 12, 15)
        p.drawLine(7, 8, 12, 3)
        p.drawLine(12, 3, 17, 8)
        p.drawPolyline(
            QPolygonF([QPointF(4, 14), QPointF(4, 21), QPointF(20, 21), QPointF(20, 14)])
        )
    elif kind == "preview":
        p.drawRoundedRect(QRectF(3, 4, 18, 13), 2, 2)
        p.drawLine(8, 21, 16, 21)
        p.drawLine(12, 17, 12, 21)
        p.drawPolygon(QPolygonF([QPointF(10, 7), QPointF(16, 10.5), QPointF(10, 14)]))
    elif kind in {"in", "out", "range"}:
        if kind in {"in", "range"}:
            p.drawPolyline(
                QPolygonF([QPointF(8, 4), QPointF(4, 4), QPointF(4, 20), QPointF(8, 20)])
            )
        if kind in {"out", "range"}:
            p.drawPolyline(
                QPolygonF([QPointF(16, 4), QPointF(20, 4), QPointF(20, 20), QPointF(16, 20)])
            )
        p.drawLine(9, 12, 15, 12)
    elif kind in {"expand", "collapse"}:
        y1, y2 = (8, 15) if kind == "expand" else (15, 8)
        p.drawPolyline(QPolygonF([QPointF(6, y1), QPointF(12, y2), QPointF(18, y1)]))
    elif kind == "settings":
        for x, y in ((5, 8), (12, 16), (19, 10)):
            p.drawLine(x, 3, x, y - 2)
            p.drawLine(x, y + 2, x, 21)
            p.drawEllipse(QPointF(x, y), 2, 2)
    elif kind == "restore":
        p.drawArc(QRectF(5, 5, 15, 15), -60 * 16, 285 * 16)
        p.drawPolyline(QPolygonF([QPointF(3, 4), QPointF(3, 10), QPointF(9, 10)]))
    p.end()
    return QIcon(pixmap)


def icon_button(button, kind: str, label: str, *, show_text: bool = False) -> None:
    button.setIcon(action_icon(kind))
    button.setText(label if show_text else "")
    button.setToolTip(label)
    button.setAccessibleName(label)
    button.setMinimumSize(36, 32)
    button.setMaximumWidth(16777215 if show_text else 48)


def transport_icon(kind: str) -> QIcon:
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor("#e0e7f0")
    painter.setPen(QPen(color, 1.8))
    painter.setBrush(color)
    if kind == "pause":
        painter.drawRect(QRectF(6, 5, 4, 14))
        painter.drawRect(QRectF(14, 5, 4, 14))
    else:
        vertices = ((8, 4), (19, 12), (8, 20))
        if kind == "previous":
            vertices = ((17, 5), (7, 12), (17, 19))
            painter.drawLine(5, 5, 5, 19)
        elif kind == "next":
            vertices = ((7, 5), (17, 12), (7, 19))
            painter.drawLine(19, 5, 19, 19)
        painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in vertices]))
    painter.end()
    return QIcon(pixmap)
