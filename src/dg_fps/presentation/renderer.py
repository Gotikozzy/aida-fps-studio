from __future__ import annotations

import av
import numpy as np
from numpy.typing import NDArray
from PySide6.QtGui import QImage


def qimage_to_video_frame(image: QImage) -> av.VideoFrame:
    """Copy directly into PyAV-owned planes while the QImage owner is alive."""
    converted = image.convertToFormat(QImage.Format.Format_RGB888)
    data = np.frombuffer(converted.constBits(), dtype=np.uint8).reshape(
        converted.height(), converted.bytesPerLine()
    )
    rgb = data[:, : converted.width() * 3].reshape(converted.height(), converted.width(), 3)
    return av.VideoFrame.from_ndarray(rgb, format="rgb24")


def qimage_to_rgb(image: QImage) -> NDArray[np.uint8]:
    converted = image.convertToFormat(QImage.Format.Format_RGB888)
    width = converted.width()
    height = converted.height()
    data = np.frombuffer(converted.bits(), dtype=np.uint8).reshape(height, converted.bytesPerLine())
    return data[:, : width * 3].reshape(height, width, 3).copy()
