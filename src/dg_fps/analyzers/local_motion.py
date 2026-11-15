"""Local, bidirectionally checked motion evidence; no frame-rate or cause decisions."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class LocalMotion:
    supported: NDArray[np.bool_]
    magnitude: float
    confidence: float
    alignment_gain: float
    noise_floor: float
    regions: list[dict[str, float | int]]
    total_regions: int


def motion_occupancy(supported: NDArray[np.bool_]) -> dict:
    """All validated pixels, independent of the bounded visual witness sample."""
    height, width = supported.shape
    cells = []
    for y in range(6):
        for x in range(8):
            count = int(
                supported[
                    y * height // 6 : (y + 1) * height // 6, x * width // 8 : (x + 1) * width // 8
                ].sum()
            )
            if count >= 12:
                cells.append([x, y])
    return {
        "grid": [8, 6],
        "cells": cells,
        "minimum_support": 12,
        "origin": "full_validated_motion_mask",
        "version": "1.0.0",
    }


def validate_motion(
    previous_rgb: NDArray[np.uint8],
    current_rgb: NDArray[np.uint8],
    forward: NDArray[np.float32],
    backward: NDArray[np.float32],
) -> LocalMotion:
    return validate_luma_motion(
        motion_luma(previous_rgb), motion_luma(current_rgb), forward, backward
    )


def motion_luma(rgb: NDArray[np.uint8]) -> NDArray[np.uint8]:
    return cv2.GaussianBlur(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), (3, 3), 0.7)


def validate_luma_motion(
    previous: NDArray[np.uint8],
    current: NDArray[np.uint8],
    forward: NDArray[np.float32],
    backward: NDArray[np.float32],
) -> LocalMotion:
    a, b = previous.astype(np.float32), current.astype(np.float32)
    height, width = a.shape
    yy, xx = np.indices(a.shape, dtype=np.float32)
    mx, my = xx + forward[:, :, 0], yy + forward[:, :, 1]
    magnitude = np.linalg.norm(forward, axis=2)
    reverse = cv2.remap(backward, mx, my, cv2.INTER_LINEAR)
    error = np.linalg.norm(forward + reverse, axis=2)
    gradient = cv2.magnitude(cv2.Sobel(a, cv2.CV_32F, 1, 0), cv2.Sobel(a, cv2.CV_32F, 0, 1))
    texture = gradient > 4
    moving = texture & (magnitude >= 0.06)
    valid = (
        moving
        & (mx >= 1)
        & (my >= 1)
        & (mx < width - 2)
        & (my < height - 2)
        & np.isfinite(error)
        & (error <= np.maximum(0.35, magnitude * 0.25))
    )
    baseline = np.abs(b - a)
    # Symmetric midpoint warp avoids penalizing genuine subpixel motion for the
    # extra interpolation blur of a one-sided reconstruction.
    residual = np.abs(
        cv2.remap(b, xx + forward[:, :, 0] / 2, yy + forward[:, :, 1] / 2, cv2.INTER_LINEAR)
        - cv2.remap(a, xx - forward[:, :, 0] / 2, yy - forward[:, :, 1] / 2, cv2.INTER_LINEAR)
    )
    stationary = baseline[texture & (magnitude < 0.06)]
    # Bounded noise estimate: it cannot grow with scene motion and erase real updates.
    noise = min(
        2.0,
        max(0.35, float(np.percentile(stationary, 75)) * 1.5 if stationary.size >= 32 else 0.35),
    )
    accepted = np.zeros(a.shape, dtype=bool)
    regions: list[dict[str, float | int]] = []
    gains: list[float] = []
    block = 16
    tops, lefts = np.arange(0, height, block), np.arange(0, width, block)
    # Integer counts include partial edge tiles. Keep the subsequent floating-point
    # operations on the original tile slices, visited in the original row-major order.
    counts = np.add.reduceat(np.add.reduceat(valid, tops, axis=0), lefts, axis=1)
    candidates = np.add.reduceat(np.add.reduceat(moving, tops, axis=0), lefts, axis=1)
    eligible = (counts >= 12) & (counts / np.maximum(1, candidates) >= 0.60)
    for row, col in np.argwhere(eligible):
        top, left = int(tops[row]), int(lefts[col])
        rows, cols = slice(top, top + block), slice(left, left + block)
        mask = valid[rows, cols]
        vectors = forward[rows, cols][mask]
        center = np.median(vectors, axis=0)
        lengths = np.linalg.norm(vectors, axis=1)
        cosine = (vectors @ center) / np.maximum(lengths * np.linalg.norm(center), 1e-6)
        coherent = float((cosine >= 0.75).mean())
        if float(np.linalg.norm(center)) < 0.08 or coherent < 0.65:
            continue
        original = float(baseline[rows, cols][mask].mean())
        aligned = float(residual[rows, cols][mask].mean())
        gain = (original - aligned) / max(original, 1e-6)
        if original < noise or gain < 0.12 or original - aligned < max(0.35, noise * 0.5):
            continue
        accepted[rows, cols] = mask
        gains.append(gain)
        regions.append(
            {
                "x": left,
                "y": top,
                "width": min(block, width - left),
                "height": min(block, height - top),
                "support": int(counts[row, col]),
                "alignment_gain": gain,
                "alignment_improvement_luma": original - aligned,
                "local_coherence": coherent,
                "fb_error_px": float(np.median(error[rows, cols][mask])),
            }
        )
    confidence = float(accepted.sum() / max(1, moving.sum()))
    total_regions = len(regions)
    # Keep evidence bounded for long captures. Metrics use the complete mask;
    # the retained/displayed witnesses are a deterministic spatial sample.
    if len(regions) > 32:
        regions = [regions[int(index)] for index in np.linspace(0, len(regions) - 1, 32)]
    return LocalMotion(
        accepted,
        float(np.percentile(magnitude[accepted], 75)) if accepted.any() else 0.0,
        confidence,
        max(gains, default=0.0),
        noise,
        regions,
        total_regions,
    )


def textured_signal(rgb: NDArray[np.uint8]) -> str:
    return textured_luma(motion_luma(rgb))


def textured_luma(gray: NDArray[np.uint8]) -> str:
    gradient = cv2.magnitude(cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1))
    # A small textured region can be observable even on an otherwise black screen.
    for top in range(0, gray.shape[0], 32):
        for left in range(0, gray.shape[1], 32):
            patch = gray[top : top + 32, left : left + 32]
            support = gradient[top : top + 32, left : left + 32]
            if np.count_nonzero(support > 4) >= 24 and np.ptp(patch) >= 4:
                return "observable"
    return "dark_unobservable" if float(np.percentile(gray, 99)) < 16 else "low_texture"
