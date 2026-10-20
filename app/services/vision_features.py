"""Shared image features for droplet training and inference."""

from __future__ import annotations

from typing import List, Optional

import cv2
import numpy as np


FEATURE_NAMES: List[str] = [
    "gray_mean",
    "gray_std",
    "laplacian_var",
    "sobel_x_mean",
    "sobel_y_mean",
    "lab_l_mean",
    "lab_a_mean",
    "lab_b_mean",
    "hsv_h_mean",
    "hsv_s_mean",
    "hsv_v_mean",
    "foreground_area",
    "aspect_ratio",
    "solidity",
    "perimeter",
    "circularity",
    "bbox_fill_ratio",
    "center_background_delta",
]


def extract_patch_features(patch: np.ndarray) -> Optional[np.ndarray]:
    """Extract stable color, texture and morphology features from an image patch."""
    try:
        if patch is None or patch.size == 0:
            return None

        if patch.ndim == 2:
            gray = patch.astype(np.uint8)
            bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        else:
            bgr = patch.astype(np.uint8)
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

        lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

        gray_mean = float(np.mean(gray))
        gray_std = float(np.std(gray))
        laplacian_var = float(np.var(cv2.Laplacian(gray, cv2.CV_64F)))
        sobel_x_mean = float(np.mean(np.abs(cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3))))
        sobel_y_mean = float(np.mean(np.abs(cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3))))

        lab_means = [float(np.mean(lab[:, :, channel])) for channel in range(3)]
        hsv_means = [float(np.mean(hsv[:, :, channel])) for channel in range(3)]

        foreground_area = 0.0
        aspect_ratio = 1.0
        solidity = 0.0
        perimeter = 0.0
        circularity = 0.0
        bbox_fill_ratio = 0.0

        foreground = _foreground_mask(gray, lab)
        contours, _ = cv2.findContours(foreground, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            foreground_area = float(cv2.contourArea(largest_contour))
            if foreground_area > 0:
                rect = cv2.minAreaRect(largest_contour)
                width, height = rect[1]
                aspect_ratio = float(max(width, height) / max(min(width, height), 1.0))

                hull = cv2.convexHull(largest_contour)
                hull_area = float(cv2.contourArea(hull))
                solidity = foreground_area / max(hull_area, 1.0)

                perimeter = float(cv2.arcLength(largest_contour, True))
                circularity = float(4.0 * np.pi * foreground_area / (perimeter ** 2)) if perimeter > 0 else 0.0

                bbox_area = max(float(width), 1.0) * max(float(height), 1.0)
                bbox_fill_ratio = foreground_area / bbox_area if bbox_area > 0 else 0.0

        center_background_delta = _center_background_delta(lab)

        return np.array(
            [
                gray_mean,
                gray_std,
                laplacian_var,
                sobel_x_mean,
                sobel_y_mean,
                *lab_means,
                *hsv_means,
                foreground_area,
                aspect_ratio,
                solidity,
                perimeter,
                circularity,
                bbox_fill_ratio,
                center_background_delta,
            ],
            dtype=np.float32,
        )
    except Exception:
        return None


def _foreground_mask(gray: np.ndarray, lab: np.ndarray) -> np.ndarray:
    """Build a conservative foreground mask for droplet/dirt candidates."""
    b_inverse = 255 - lab[:, :, 2]
    _, gray_mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    _, blue_mask = cv2.threshold(b_inverse, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = cv2.bitwise_or(gray_mask, blue_mask)
    return cv2.morphologyEx(
        mask,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
        iterations=1,
    )


def _center_background_delta(lab: np.ndarray) -> float:
    """Compare the center color with the outer ring of the patch."""
    height, width = lab.shape[:2]
    if height < 5 or width < 5:
        return 0.0

    yy, xx = np.ogrid[:height, :width]
    center_x = (width - 1) / 2.0
    center_y = (height - 1) / 2.0
    distance = np.sqrt((xx - center_x) ** 2 + (yy - center_y) ** 2)
    max_radius = max(float(distance.max()), 1.0)

    center_mask = distance <= max_radius * 0.35
    ring_mask = distance >= max_radius * 0.72
    if not np.any(center_mask) or not np.any(ring_mask):
        return 0.0

    center_color = np.median(lab[center_mask].astype(np.float32), axis=0)
    ring_color = np.median(lab[ring_mask].astype(np.float32), axis=0)
    return float(np.linalg.norm(center_color - ring_color))
