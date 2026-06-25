"""
Computer vision pipeline for droplet analysis on water-sensitive paper.

The analyzer now prioritizes:
- detecting the yellow/orange microporous paper region
- rectifying perspective before any droplet measurement
- calibrating mm/px from the known paper size
- filtering noise, edge hits and merged/double droplets
- optionally reusing the trained classical ML model as a contour classifier
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from loguru import logger

from app.core.config import settings
from app.core.exceptions import ImageProcessingError


class DropletAnalyzer:
    """Analyze droplet deposition on water-sensitive paper."""

    def __init__(self):
        self.model = None
        self.model_loaded = False
        self.model_metadata: Dict = {}

        self.analysis_long_edge_px = max(512, int(settings.PAPER_ANALYSIS_LONG_EDGE_PX))
        self.paper_width_mm = max(
            float(settings.MICROPOROUS_PAPER_WIDTH_MM),
            float(settings.MICROPOROUS_PAPER_HEIGHT_MM),
        )
        self.paper_height_mm = min(
            float(settings.MICROPOROUS_PAPER_WIDTH_MM),
            float(settings.MICROPOROUS_PAPER_HEIGHT_MM),
        )
        self.paper_aspect_ratio = self.paper_width_mm / max(self.paper_height_mm, 1e-6)
        self.border_margin_ratio = max(0.0, min(float(settings.PAPER_BORDER_MARGIN_RATIO), 0.15))
        self.min_droplet_radius_mm = max(0.005, float(settings.MIN_DROPLET_RADIUS_MM))
        self.max_droplet_radius_mm = max(self.min_droplet_radius_mm, float(settings.MAX_DROPLET_RADIUS_MM))
        self.protection_radius_factor = 2.0

        self.quality_thresholds = {
            "min_coverage": 10.0,
            "max_cv": 15.0,
            "min_density": 20,
            "max_density": 200,
        }

    def load_model(self) -> bool:
        """Load the best active local classifier trained by the annotation flow."""
        try:
            from app.services.ml_training import load_active_model

            loaded = load_active_model("segmentation")
            if not loaded or not loaded.get("model"):
                logger.info("Nenhum modelo treinado ativo encontrado; usando apenas regras geometricas.")
                self.model = None
                self.model_loaded = False
                self.model_metadata = {}
                return False

            self.model = loaded["model"]
            self.model_metadata = loaded.get("metadata", {}) or {}
            self.model_loaded = True
            logger.info(
                "Modelo classico ativo carregado para apoio a filtragem de gotas: {}",
                self.model_metadata.get("name", "sem_nome"),
            )
            return True
        except Exception as exc:
            logger.warning(f"Falha ao carregar modelo treinado ativo ({exc}). Seguindo sem ML auxiliar.")
            self.model = None
            self.model_loaded = False
            self.model_metadata = {}
            return False

    def preprocess_image(self, image: np.ndarray) -> Tuple[np.ndarray, Dict]:
        """Detect paper, rectify it and prepare a normalized ROI for analysis."""
        try:
            if image is None or image.size == 0:
                raise ImageProcessingError("Imagem vazia ou invalida recebida para pre-processamento")

            original_shape = tuple(int(value) for value in image.shape)
            paper_points, paper_confidence = self._detect_paper_region(image)

            if paper_points is not None:
                paper_bgr = self._warp_paper_region(image, paper_points)
                mm_per_px = self.paper_width_mm / float(paper_bgr.shape[1])
                metadata = {
                    "original_shape": original_shape,
                    "paper_detected": True,
                    "paper_confidence": round(float(paper_confidence), 3),
                    "paper_polygon": np.round(paper_points, 2).tolist(),
                    "paper_dimensions_mm": {
                        "width": round(self.paper_width_mm, 2),
                        "height": round(self.paper_height_mm, 2),
                    },
                    "analysis_shape": (int(paper_bgr.shape[0]), int(paper_bgr.shape[1])),
                    "analysis_area_px": int(paper_bgr.shape[0] * paper_bgr.shape[1]),
                    "analysis_mm_per_px": float(mm_per_px),
                    "scale_source": "paper_rectification",
                    "fallback_pixel_to_mm": float(settings.PIXEL_TO_MM),
                }
            else:
                paper_bgr, resize_scale = self._resize_long_edge(image, self.analysis_long_edge_px)
                mm_per_px = float(settings.PIXEL_TO_MM) / max(resize_scale, 1e-6)
                metadata = {
                    "original_shape": original_shape,
                    "paper_detected": False,
                    "paper_confidence": 0.0,
                    "paper_polygon": None,
                    "paper_dimensions_mm": {
                        "width": round(float(paper_bgr.shape[1]) * mm_per_px, 2),
                        "height": round(float(paper_bgr.shape[0]) * mm_per_px, 2),
                    },
                    "analysis_shape": (int(paper_bgr.shape[0]), int(paper_bgr.shape[1])),
                    "analysis_area_px": int(paper_bgr.shape[0] * paper_bgr.shape[1]),
                    "analysis_mm_per_px": float(mm_per_px),
                    "scale_source": "fallback_pixel_to_mm",
                    "fallback_pixel_to_mm": float(settings.PIXEL_TO_MM),
                }

            analysis_rgb = cv2.cvtColor(paper_bgr, cv2.COLOR_BGR2RGB)
            enhanced_rgb = self._enhance_contrast(analysis_rgb)
            metadata["border_margin_px"] = max(
                2,
                int(round(min(enhanced_rgb.shape[:2]) * self.border_margin_ratio)),
            )
            metadata["analysis_rgb"] = enhanced_rgb
            metadata["analysis_gray"] = cv2.cvtColor(enhanced_rgb, cv2.COLOR_RGB2GRAY)
            return enhanced_rgb, metadata
        except Exception as exc:
            logger.error(f"Erro no pre-processamento: {exc}")
            raise ImageProcessingError(f"Falha no pre-processamento da imagem: {exc}")

    def _enhance_contrast(self, image_rgb: np.ndarray) -> np.ndarray:
        """Improve local contrast without destroying droplet edges."""
        try:
            lab = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            l_channel = clahe.apply(l_channel)
            enhanced = cv2.merge((l_channel, a_channel, b_channel))
            enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2RGB)

            blurred = cv2.GaussianBlur(enhanced, (0, 0), 1.2)
            sharpened = cv2.addWeighted(enhanced, 1.15, blurred, -0.15, 0)
            return sharpened
        except Exception as exc:
            logger.warning(f"Falha ao melhorar contraste ({exc}); usando ROI original.")
            return image_rgb

    def _detect_paper_region(self, image_bgr: np.ndarray) -> Tuple[Optional[np.ndarray], float]:
        """Find the most likely yellow/orange paper rectangle."""
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)

        warm_hsv_mask = cv2.inRange(
            hsv,
            np.array([5, 35, 55], dtype=np.uint8),
            np.array([45, 255, 255], dtype=np.uint8),
        )

        b_channel = lab[:, :, 2]
        dynamic_b_threshold = int(max(140, min(220, np.percentile(b_channel, 72))))
        _, warm_lab_mask = cv2.threshold(b_channel, dynamic_b_threshold, 255, cv2.THRESH_BINARY)

        combined = cv2.bitwise_or(warm_hsv_mask, warm_lab_mask)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel, iterations=2)
        combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel, iterations=1)
        combined = cv2.dilate(combined, kernel, iterations=1)

        contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None, 0.0

        image_area = float(image_bgr.shape[0] * image_bgr.shape[1])
        best_points = None
        best_score = 0.0

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < image_area * 0.03:
                continue

            rect = cv2.minAreaRect(contour)
            width, height = rect[1]
            if width < 20 or height < 20:
                continue

            rect_area = max(width * height, 1.0)
            fill_ratio = float(area / rect_area)
            long_side = max(width, height)
            short_side = max(min(width, height), 1.0)
            aspect_ratio = float(long_side / short_side)
            aspect_score = 1.0 - min(abs(aspect_ratio - self.paper_aspect_ratio) / self.paper_aspect_ratio, 1.0)
            area_score = min(area / max(image_area * 0.18, 1.0), 1.2)
            rectangularity_score = max(0.0, min(fill_ratio / 0.85, 1.0))

            epsilon = 0.03 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            if len(approx) == 4:
                points = approx.reshape(4, 2).astype(np.float32)
                quadrilateral_bonus = 0.2
            else:
                points = cv2.boxPoints(rect).astype(np.float32)
                quadrilateral_bonus = 0.0

            score = (aspect_score * 3.0) + (rectangularity_score * 2.0) + (area_score * 2.0) + quadrilateral_bonus
            if score > best_score:
                best_score = score
                best_points = points

        if best_points is None:
            return None, 0.0

        confidence = max(0.0, min(best_score / 6.2, 1.0))
        return best_points, confidence

    def _warp_paper_region(self, image_bgr: np.ndarray, points: np.ndarray) -> np.ndarray:
        """Rectify the detected paper into a fixed physical aspect ratio."""
        ordered = self._order_points(points)
        target_height = max(64, int(round(self.analysis_long_edge_px / self.paper_aspect_ratio)))
        target_width = int(self.analysis_long_edge_px)
        destination = np.array(
            [
                [0, 0],
                [target_width - 1, 0],
                [target_width - 1, target_height - 1],
                [0, target_height - 1],
            ],
            dtype=np.float32,
        )
        matrix = cv2.getPerspectiveTransform(ordered, destination)
        return cv2.warpPerspective(
            image_bgr,
            matrix,
            (target_width, target_height),
            flags=cv2.INTER_LANCZOS4,
            borderMode=cv2.BORDER_REPLICATE,
        )

    @staticmethod
    def _order_points(points: np.ndarray) -> np.ndarray:
        """Return points ordered as tl, tr, br, bl."""
        pts = np.asarray(points, dtype=np.float32)
        if pts.shape != (4, 2):
            raise ImageProcessingError("Poligono do papel microporoso invalido")

        ordered = np.zeros((4, 2), dtype=np.float32)
        point_sum = pts.sum(axis=1)
        point_diff = np.diff(pts, axis=1).reshape(-1)

        ordered[0] = pts[np.argmin(point_sum)]
        ordered[2] = pts[np.argmax(point_sum)]
        ordered[1] = pts[np.argmin(point_diff)]
        ordered[3] = pts[np.argmax(point_diff)]
        return ordered

    @staticmethod
    def _resize_long_edge(image: np.ndarray, target_long_edge: int) -> Tuple[np.ndarray, float]:
        """Resize an image so the longest side matches the target."""
        height, width = image.shape[:2]
        current_long_edge = max(height, width)
        scale = float(target_long_edge) / max(float(current_long_edge), 1.0)
        new_size = (max(1, int(round(width * scale))), max(1, int(round(height * scale))))
        resized = cv2.resize(image, new_size, interpolation=cv2.INTER_LANCZOS4)
        return resized, scale

    def segment_droplets(self, image_rgb: np.ndarray, metadata: Dict) -> np.ndarray:
        """Segment droplets inside the normalized paper ROI."""
        try:
            return self._segment_with_opencv(image_rgb, metadata)
        except Exception as exc:
            logger.error(f"Erro na segmentacao: {exc}")
            raise ImageProcessingError(f"Falha na segmentacao de goticulas: {exc}")

    def _segment_with_opencv(self, image_rgb: np.ndarray, metadata: Dict) -> np.ndarray:
        """Color and morphology based droplet segmentation."""
        rgb_uint8 = image_rgb.astype(np.uint8)
        gray = cv2.cvtColor(rgb_uint8, cv2.COLOR_RGB2GRAY)
        lab = cv2.cvtColor(rgb_uint8, cv2.COLOR_RGB2LAB)
        hsv = cv2.cvtColor(rgb_uint8, cv2.COLOR_RGB2HSV)
        lab_float = lab.astype(np.float32)
        paper_median_lab = np.median(lab_float.reshape(-1, 3), axis=0)
        color_distance = np.linalg.norm(lab_float - paper_median_lab, axis=2)

        b_inverse = 255 - lab[:, :, 2]
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        b_inverse = clahe.apply(b_inverse)

        blackhat = cv2.morphologyEx(
            gray,
            cv2.MORPH_BLACKHAT,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)),
        )
        blue_dominance = np.clip(
            rgb_uint8[:, :, 2].astype(np.int16) - rgb_uint8[:, :, 0].astype(np.int16) + 32,
            0,
            255,
        ).astype(np.uint8)

        response = cv2.addWeighted(b_inverse, 0.55, blackhat, 0.45, 0)
        response = cv2.max(response, blue_dominance)
        response = cv2.GaussianBlur(response, (5, 5), 0)

        _, otsu_mask = cv2.threshold(response, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        blue_hue_mask = cv2.inRange(
            hsv,
            np.array([90, 10, 10], dtype=np.uint8),
            np.array([175, 255, 235], dtype=np.uint8),
        )
        warm_background_mask = cv2.inRange(
            hsv,
            np.array([5, 20, 70], dtype=np.uint8),
            np.array([50, 255, 255], dtype=np.uint8),
        )
        distance_mask = (color_distance >= max(18.0, np.percentile(color_distance, 95))).astype(np.uint8) * 255
        dark_mask = cv2.threshold(
            gray,
            int(max(20, min(190, np.percentile(gray, 20)))),
            255,
            cv2.THRESH_BINARY_INV,
        )[1]
        blue_intensity_mask = (b_inverse >= max(25.0, np.percentile(b_inverse, 94))).astype(np.uint8) * 255

        combined = cv2.bitwise_or(otsu_mask, blue_hue_mask)
        combined = cv2.bitwise_or(combined, blue_intensity_mask)
        combined = cv2.bitwise_and(combined, distance_mask)
        combined = cv2.bitwise_and(combined, cv2.bitwise_or(cv2.bitwise_not(warm_background_mask), dark_mask))
        combined = cv2.morphologyEx(
            combined,
            cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
            iterations=1,
        )
        combined = cv2.morphologyEx(
            combined,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
            iterations=1,
        )
        combined = cv2.medianBlur(combined, 3)

        border_margin = int(metadata.get("border_margin_px", 2))
        if border_margin > 0:
            combined[:border_margin, :] = 0
            combined[-border_margin:, :] = 0
            combined[:, :border_margin] = 0
            combined[:, -border_margin:] = 0

        component_count, labels, stats, _ = cv2.connectedComponentsWithStats(combined, connectivity=8)
        cleaned = np.zeros_like(combined)
        max_component_area = combined.shape[0] * combined.shape[1] * 0.08
        for component_id in range(1, component_count):
            area = stats[component_id, cv2.CC_STAT_AREA]
            if 4 <= area <= max_component_area:
                cleaned[labels == component_id] = 255

        metadata["droplet_response_map"] = response
        return (cleaned > 0).astype(np.uint8)

    def analyze_droplets(self, mask: np.ndarray, metadata: Dict) -> Dict:
        """Quantify valid droplets, doubles and noise within the paper ROI."""
        try:
            if mask is None or mask.size == 0:
                raise ImageProcessingError("Mascara binaria vazia recebida para analise")

            if not self.model_loaded:
                self.load_model()

            contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            response_map = metadata.get("droplet_response_map")
            gray_image = metadata.get("analysis_gray")
            mm_per_px = float(metadata.get("analysis_mm_per_px", settings.PIXEL_TO_MM))
            border_margin = int(metadata.get("border_margin_px", 2))
            image_h, image_w = mask.shape[:2]
            paper_area = max(int(metadata.get("analysis_area_px", image_h * image_w)), 1)

            valid_candidates: List[Dict] = []
            double_candidates: List[Dict] = []
            edge_candidates: List[Dict] = []
            rejected_noise = 0
            rejected_size = 0
            candidate_count = 0

            for contour in contours:
                candidate = self._describe_candidate(
                    contour=contour,
                    gray_image=gray_image,
                    response_map=response_map,
                    mask_shape=mask.shape,
                    mm_per_px=mm_per_px,
                    border_margin=border_margin,
                )
                if candidate is None:
                    continue

                candidate_count += 1
                label = self._classify_candidate(candidate)
                if label == "valid":
                    valid_candidates.append(candidate)
                elif label == "double":
                    double_candidates.append(candidate)
                elif label == "edge":
                    edge_candidates.append(candidate)
                elif label == "size":
                    rejected_size += 1
                else:
                    rejected_noise += 1

            accepted_for_coverage = valid_candidates + double_candidates
            total_valid_droplets = len(valid_candidates)
            double_droplets = len(double_candidates)
            edge_droplets = len(edge_candidates)
            duplicated_count = double_droplets

            protection_mask = np.zeros(mask.shape, dtype=np.uint8)
            theoretical_protection_area = 0.0
            coverage_contours = [candidate["contour"] for candidate in accepted_for_coverage]

            for candidate in accepted_for_coverage:
                cx, cy = candidate["centroid"]
                protection_radius = max(candidate["equivalent_radius_px"] * self.protection_radius_factor, 1.0)
                cv2.circle(protection_mask, (int(round(cx)), int(round(cy))), int(round(protection_radius)), 1, -1)
                theoretical_protection_area += np.pi * (protection_radius ** 2)

            if coverage_contours:
                raw_coverage_mask = np.zeros(mask.shape, dtype=np.uint8)
                cv2.drawContours(raw_coverage_mask, coverage_contours, -1, 1, thickness=-1)
                segmented_coverage_area = int(np.count_nonzero(raw_coverage_mask))
            else:
                segmented_coverage_area = 0

            protection_area_mask = int(np.count_nonzero(protection_mask))
            effective_protection_area = max(segmented_coverage_area, protection_area_mask, int(theoretical_protection_area))
            coverage_percentage = (effective_protection_area / paper_area) * 100.0
            coverage_percentage *= float(getattr(settings, "DROPLET_COVERAGE_SCALE", 1.0))
            coverage_percentage = max(0.0, min(100.0, coverage_percentage))

            area_cm2 = (paper_area * mm_per_px * mm_per_px) / 100.0
            density_per_cm2 = total_valid_droplets / area_cm2 if area_cm2 > 0 else 0.0

            diameters_um = [candidate["diameter_um"] for candidate in valid_candidates]
            if not diameters_um:
                diameters_um = [candidate["diameter_um"] for candidate in accepted_for_coverage]

            if len(diameters_um) > 1:
                mean_diameter = float(np.mean(diameters_um))
                std_diameter = float(np.std(diameters_um))
                cv_coefficient = (std_diameter / mean_diameter) * 100.0 if mean_diameter > 0 else 0.0
            else:
                mean_diameter = float(diameters_um[0]) if diameters_um else 0.0
                cv_coefficient = 0.0

            dv50 = float(np.median(diameters_um)) if diameters_um else 0.0
            droplet_class = self._classify_droplet_size(dv50)

            effective_candidates = max(candidate_count, 1)
            double_ratio = double_droplets / effective_candidates
            edge_ratio = edge_droplets / effective_candidates
            scale_confidence = float(metadata.get("paper_confidence", 0.0)) if metadata.get("paper_detected") else 0.0

            quality_score = self._calculate_quality_score(
                coverage_percentage,
                cv_coefficient,
                density_per_cm2,
                double_ratio=double_ratio,
                edge_ratio=edge_ratio,
                paper_detected=bool(metadata.get("paper_detected")),
                scale_confidence=scale_confidence,
            )

            estimated_total_impacts = total_valid_droplets + sum(candidate["peak_count"] for candidate in double_candidates)

            results = {
                "total_droplets": total_valid_droplets,
                "valid_droplets": total_valid_droplets,
                "candidate_droplets": candidate_count,
                "duplicated_droplets": duplicated_count,
                "double_droplets": double_droplets,
                "edge_droplets": edge_droplets,
                "rejected_noise": rejected_noise,
                "rejected_by_size": rejected_size,
                "estimated_total_impacts": int(estimated_total_impacts),
                "coverage_percentage": round(coverage_percentage, 2),
                "density_per_cm2": round(density_per_cm2, 2),
                "cv_coefficient": round(cv_coefficient, 2),
                "dv50_diameter": round(dv50, 2),
                "droplet_class": droplet_class,
                "mean_diameter": round(mean_diameter, 2),
                "min_diameter": round(float(np.min(diameters_um)), 2) if diameters_um else 0,
                "max_diameter": round(float(np.max(diameters_um)), 2) if diameters_um else 0,
                "quality_score": quality_score,
                "quality_assessment": self._assess_quality(quality_score),
                "paper_detected": bool(metadata.get("paper_detected")),
                "paper_confidence": round(scale_confidence, 3),
                "paper_dimensions_mm": metadata.get("paper_dimensions_mm"),
                "analysis_scale_mm_per_px": round(mm_per_px, 6),
                "scale_source": metadata.get("scale_source", "unknown"),
                "recommendations": self._generate_recommendations(
                    coverage_percentage,
                    cv_coefficient,
                    density_per_cm2,
                    double_ratio=double_ratio,
                    paper_detected=bool(metadata.get("paper_detected")),
                    edge_ratio=edge_ratio,
                ),
            }

            logger.info(
                "Analise concluida: {} gotas validas, {} duplas, {} rejeitadas por ruido",
                total_valid_droplets,
                double_droplets,
                rejected_noise,
            )
            return results
        except Exception as exc:
            logger.error(f"Erro na analise de goticulas: {exc}")
            raise ImageProcessingError(f"Falha na analise quantitativa: {exc}")

    def _describe_candidate(
        self,
        contour: np.ndarray,
        gray_image: np.ndarray,
        response_map: Optional[np.ndarray],
        mask_shape: Tuple[int, int],
        mm_per_px: float,
        border_margin: int,
    ) -> Optional[Dict]:
        """Extract geometry, intensity and peak statistics for one contour."""
        area_px = float(cv2.contourArea(contour))
        if area_px <= 0:
            return None

        perimeter = float(cv2.arcLength(contour, True))
        equivalent_radius_px = float(np.sqrt(area_px / np.pi))
        radius_mm = equivalent_radius_px * mm_per_px
        diameter_um = (equivalent_radius_px * 2.0) * mm_per_px * 1000.0

        x, y, width, height = cv2.boundingRect(contour)
        aspect_ratio = float(max(width, height) / max(min(width, height), 1))

        hull = cv2.convexHull(contour)
        hull_area = float(cv2.contourArea(hull))
        solidity = area_px / max(hull_area, 1.0)
        circularity = (4.0 * np.pi * area_px / (perimeter ** 2)) if perimeter > 0 else 0.0

        moments = cv2.moments(contour)
        if moments["m00"] <= 0:
            return None
        centroid = (moments["m10"] / moments["m00"], moments["m01"] / moments["m00"])

        component_mask = np.zeros(mask_shape, dtype=np.uint8)
        cv2.drawContours(component_mask, [contour], -1, 255, thickness=-1)
        local_response = float(cv2.mean(response_map, mask=component_mask)[0]) if response_map is not None else 0.0
        ml_probability = self._predict_candidate_probability(gray_image, x, y, width, height)

        peak_count = self._count_component_peaks(contour, mask_shape)
        edge_contact = bool(
            x <= border_margin
            or y <= border_margin
            or (x + width) >= (mask_shape[1] - border_margin)
            or (y + height) >= (mask_shape[0] - border_margin)
        )

        return {
            "contour": contour,
            "area_px": area_px,
            "perimeter_px": perimeter,
            "equivalent_radius_px": equivalent_radius_px,
            "radius_mm": radius_mm,
            "diameter_um": diameter_um,
            "aspect_ratio": aspect_ratio,
            "solidity": solidity,
            "circularity": circularity,
            "bbox": (x, y, width, height),
            "centroid": centroid,
            "response_score": local_response,
            "peak_count": peak_count,
            "edge_contact": edge_contact,
            "ml_probability": ml_probability,
        }

    def _classify_candidate(self, candidate: Dict) -> str:
        """Label a contour as valid droplet, double, edge or noise."""
        radius_mm = candidate["radius_mm"]
        if radius_mm < self.min_droplet_radius_mm or radius_mm > self.max_droplet_radius_mm:
            return "size"

        circularity = candidate["circularity"]
        solidity = candidate["solidity"]
        aspect_ratio = candidate["aspect_ratio"]
        peak_count = candidate["peak_count"]
        ml_probability = candidate.get("ml_probability")

        if aspect_ratio > 4.0 or solidity < 0.32 or circularity < 0.08:
            return "noise"

        if ml_probability is not None and ml_probability < 0.25 and (circularity < 0.65 or solidity < 0.8):
            return "noise"

        if candidate["edge_contact"]:
            return "edge"

        if peak_count >= 2 and (aspect_ratio > 1.15 or circularity < 0.8 or solidity < 0.95):
            return "double"

        if aspect_ratio > 1.75 and circularity < 0.72:
            return "double"

        if circularity < 0.28 and solidity < 0.74:
            return "noise"

        if ml_probability is not None and ml_probability < 0.45 and circularity < 0.55:
            return "noise"

        return "valid"

    def _count_component_peaks(self, contour: np.ndarray, mask_shape: Tuple[int, int]) -> int:
        """Estimate how many droplet lobes exist inside a merged component."""
        component_mask = np.zeros(mask_shape, dtype=np.uint8)
        cv2.drawContours(component_mask, [contour], -1, 255, thickness=-1)
        distance = cv2.distanceTransform(component_mask, cv2.DIST_L2, 5)
        max_distance = float(distance.max())
        if max_distance <= 0:
            return 0

        peak_threshold = max(max_distance * 0.62, 1.5)
        peak_mask = (distance >= peak_threshold).astype(np.uint8)
        peak_mask = cv2.morphologyEx(
            peak_mask,
            cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
            iterations=1,
        )
        components, _ = cv2.connectedComponents(peak_mask)
        return max(1, components - 1)

    def _predict_candidate_probability(
        self,
        gray_image: Optional[np.ndarray],
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> Optional[float]:
        """Use the trained classical model, when available, to score a contour patch."""
        if not self.model_loaded or self.model is None or gray_image is None:
            return None

        margin = 6
        x1 = max(0, x - margin)
        y1 = max(0, y - margin)
        x2 = min(gray_image.shape[1], x + width + margin)
        y2 = min(gray_image.shape[0], y + height + margin)
        patch = gray_image[y1:y2, x1:x2]
        features = self._extract_patch_features(patch)
        if features is None:
            return None

        try:
            feature_row = features.reshape(1, -1)
            estimator = self.model
            if isinstance(self.model, dict) and "model" in self.model:
                scaler = self.model.get("scaler")
                if scaler is not None:
                    feature_row = scaler.transform(feature_row)
                estimator = self.model["model"]

            expected_features = getattr(estimator, "n_features_in_", None)
            if expected_features is not None and int(expected_features) != feature_row.shape[1]:
                return None

            if hasattr(estimator, "predict_proba"):
                probabilities = estimator.predict_proba(feature_row)
                if probabilities.shape[1] > 1:
                    return float(probabilities[0][1])
                return float(probabilities[0][0])

            prediction = estimator.predict(feature_row)
            return float(prediction[0])
        except Exception as exc:
            logger.debug(f"Falha ao aplicar classificador auxiliar na gota candidata: {exc}")
            return None

    def _extract_patch_features(self, patch: np.ndarray) -> Optional[np.ndarray]:
        """Mirror the features used by the training pipeline."""
        try:
            if patch is None or patch.size == 0:
                return None

            intensity_mean = np.mean(patch)
            intensity_std = np.std(patch)
            laplacian = cv2.Laplacian(patch, cv2.CV_64F)
            laplacian_var = np.var(laplacian)
            sobel_x = cv2.Sobel(patch, cv2.CV_64F, 1, 0, ksize=3)
            sobel_y = cv2.Sobel(patch, cv2.CV_64F, 0, 1, ksize=3)
            sobel_x_mean = np.mean(np.abs(sobel_x))
            sobel_y_mean = np.mean(np.abs(sobel_y))

            _, binary = cv2.threshold(patch, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if contours:
                largest = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(largest)
                rect = cv2.minAreaRect(largest)
                width, height = rect[1]
                aspect_ratio = max(width, height) / max(min(width, height), 1.0)
                hull = cv2.convexHull(largest)
                hull_area = cv2.contourArea(hull)
                solidity = area / max(hull_area, 1.0)
                perimeter = cv2.arcLength(largest, True)
                circularity = 4.0 * np.pi * area / (perimeter ** 2) if perimeter > 0 else 0.0
                bbox_area = max(width, 1.0) * max(height, 1.0)
                bbox_fill_ratio = area / bbox_area if bbox_area > 0 else 0.0
            else:
                area = 0.0
                aspect_ratio = 1.0
                solidity = 0.0
                perimeter = 0.0
                circularity = 0.0
                bbox_fill_ratio = 0.0

            return np.array(
                [
                    intensity_mean,
                    intensity_std,
                    laplacian_var,
                    sobel_x_mean,
                    sobel_y_mean,
                    area,
                    aspect_ratio,
                    solidity,
                    perimeter,
                    circularity,
                    bbox_fill_ratio,
                ],
                dtype=np.float32,
            )
        except Exception as exc:
            logger.debug(f"Nao foi possivel extrair features do patch candidato: {exc}")
            return None

    def _classify_droplet_size(self, dv50: float) -> str:
        """Map DV50 in microns to a spray quality class."""
        if dv50 <= 0:
            return "Indefinida"
        if 80 <= dv50 < 190:
            return "Muito fina"
        if 190 <= dv50 < 280:
            return "Fina"
        if 280 <= dv50 < 330:
            return "Media"
        if 330 <= dv50 < 400:
            return "Grossa"
        if dv50 >= 400:
            return "Extremamente grossa"
        return "Ultrafina"

    def _calculate_quality_score(
        self,
        coverage: float,
        cv: float,
        density: float,
        double_ratio: float = 0.0,
        edge_ratio: float = 0.0,
        paper_detected: bool = True,
        scale_confidence: float = 1.0,
    ) -> float:
        """Score the spray quality from 0 to 100."""
        try:
            cov_opt_low, cov_opt_high = 10.0, 30.0
            cov_min, cov_max = 3.0, 50.0

            if coverage <= cov_min or coverage >= cov_max:
                coverage_score = 0.0
            elif cov_opt_low <= coverage <= cov_opt_high:
                coverage_score = 40.0
            elif coverage < cov_opt_low:
                coverage_score = 40.0 * (coverage - cov_min) / (cov_opt_low - cov_min)
            else:
                coverage_score = 40.0 * (cov_max - coverage) / (cov_max - cov_opt_high)
            coverage_score = max(0.0, min(40.0, coverage_score))

            if cv <= 20.0:
                cv_score = 30.0
            elif cv >= 60.0:
                cv_score = 0.0
            else:
                cv_score = 30.0 * (60.0 - cv) / (60.0 - 20.0)
            cv_score = max(0.0, min(30.0, cv_score))

            dens_opt_low, dens_opt_high = 20.0, 150.0
            dens_min, dens_max = 5.0, 250.0

            if density <= dens_min or density >= dens_max:
                density_score = 0.0
            elif dens_opt_low <= density <= dens_opt_high:
                density_score = 30.0
            elif density < dens_opt_low:
                density_score = 30.0 * (density - dens_min) / (dens_opt_low - dens_min)
            else:
                density_score = 30.0 * (dens_max - density) / (dens_max - dens_opt_high)
            density_score = max(0.0, min(30.0, density_score))

            total_score = coverage_score + cv_score + density_score
            total_score -= min(18.0, max(0.0, double_ratio) * 30.0)
            total_score -= min(8.0, max(0.0, edge_ratio) * 16.0)
            if not paper_detected:
                total_score -= 8.0
            total_score -= max(0.0, (1.0 - max(0.0, min(scale_confidence, 1.0))) * 4.0)
            return round(min(100.0, max(0.0, total_score)), 2)
        except Exception as exc:
            logger.warning(f"Erro no calculo de qualidade: {exc}")
            return 0.0

    def _assess_quality(self, score: float) -> str:
        """Return a human-readable quality bucket."""
        if score >= 80:
            return "Excelente"
        if score >= 60:
            return "Boa"
        if score >= 40:
            return "Regular"
        return "Inadequada"

    def _generate_recommendations(
        self,
        coverage: float,
        cv: float,
        density: float,
        double_ratio: float = 0.0,
        paper_detected: bool = True,
        edge_ratio: float = 0.0,
    ) -> List[str]:
        """Generate operational recommendations from the image analysis."""
        recommendations: List[str] = []

        if not paper_detected:
            recommendations.append(
                "O papel microporoso nao foi identificado com alta confianca; fotografe o retangulo amarelo/laranja ocupando mais area da imagem."
            )

        if coverage < 5.0:
            recommendations.append("Cobertura muito baixa - revisar volume de calda, altura da barra e velocidade de aplicacao")
        elif coverage < self.quality_thresholds["min_coverage"]:
            recommendations.append("Cobertura moderada - avaliar ajuste de volume ou escolha de bicos conforme o alvo")

        if cv > self.quality_thresholds["max_cv"]:
            recommendations.append("Distribuicao irregular - revisar pressao, uniformidade dos bicos e estabilidade da aplicacao")

        if density < self.quality_thresholds["min_density"]:
            recommendations.append("Densidade de gotas baixa - reduzir altura de aplicacao ou aumentar pressao")
        elif density > self.quality_thresholds["max_density"]:
            recommendations.append("Densidade muito alta - verificar excesso de volume ou risco de coalescencia")

        if double_ratio >= 0.12:
            recommendations.append("Ha muitas gotas duplas/mescladas - reduzir excesso de deposicao e revisar espectro de gotas")

        if edge_ratio >= 0.1:
            recommendations.append("Muitas marcas tocaram a borda do papel - reposicione e enquadre melhor a amostra")

        if not recommendations:
            recommendations.append("Aplicacao dentro dos parametros ideais para a amostra analisada")

        return recommendations

    def process_image(self, image_path: str) -> Dict:
        """Run the full image processing pipeline."""
        try:
            start_time = time.time()
            image = cv2.imread(image_path)
            if image is None:
                raise ImageProcessingError(f"Nao foi possivel carregar a imagem: {image_path}")

            logger.info(f"Processando imagem: {Path(image_path).name}")
            processed_image, metadata = self.preprocess_image(image)
            mask = self.segment_droplets(processed_image, metadata)
            analysis_results = self.analyze_droplets(mask, metadata)
            analysis_results["processing_time"] = round(time.time() - start_time, 3)
            return analysis_results
        except Exception as exc:
            logger.error(f"Erro no processamento da imagem: {exc}")
            raise ImageProcessingError(f"Falha no processamento: {exc}")


# Global singleton used by the API routes.
droplet_analyzer = DropletAnalyzer()
