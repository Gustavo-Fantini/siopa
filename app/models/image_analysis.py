"""Auditable water-sensitive paper measurements, shared conceptually with offline JS.

Counts describe resolvable isolated stains. Physical units require an explicitly
confirmed collector size or manual scale. No model or database is loaded here.
"""
from __future__ import annotations

import base64
import math
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageOps
from loguru import logger

from app.core.config import settings
from app.core.exceptions import ImageProcessingError
from app.services.spray_quality import ENGINE_VERSION, evaluate_quality
from app.services.vision_features import extract_patch_features


def _option(options, camel, snake, default=None):
    return options.get(camel, options.get(snake, default))


def _positive(value, default=None):
    try:
        value = float(value)
        return value if math.isfinite(value) and value > 0 else default
    except (TypeError, ValueError):
        return default


def _polygon_area(points):
    points = np.asarray(points, dtype=np.float64)
    return abs(float(np.sum(points[:, 0] * np.roll(points[:, 1], -1) - points[:, 1] * np.roll(points[:, 0], -1)))) / 2


def _canonical_corners(points):
    """Order convex corners cyclically, placing a long edge on the horizontal axis."""
    points = np.asarray(points, dtype=np.float32)
    if points.shape != (4, 2) or not np.all(np.isfinite(points)):
        raise ImageProcessingError("Informe quatro cantos finitos do papel.")
    center = points.mean(axis=0)
    points = points[np.argsort(np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0]))]
    # Pick the upper/left corner then rotate if that edge is the short side.
    points = np.roll(points, -int(np.argmin(points.sum(axis=1))), axis=0)
    if np.linalg.norm(points[1] - points[0]) + np.linalg.norm(points[3] - points[2]) < np.linalg.norm(points[2] - points[1]) + np.linalg.norm(points[0] - points[3]):
        points = np.roll(points, -1, axis=0)
    if _polygon_area(points) < 16 or not cv2.isContourConvex(points):
        raise ImageProcessingError("Os cantos nao definem um papel valido.")
    return points


class DropletAnalyzer:
    """Deterministic stain segmentation and explicit calibration for phone photos."""

    def __init__(self):
        self.model = None
        self.model_loaded = False
        self.model_metadata = {}
        self.analysis_long_edge_px = max(512, int(settings.PAPER_ANALYSIS_LONG_EDGE_PX))
        self.paper_width_mm = max(settings.MICROPOROUS_PAPER_WIDTH_MM, settings.MICROPOROUS_PAPER_HEIGHT_MM)
        self.paper_height_mm = min(settings.MICROPOROUS_PAPER_WIDTH_MM, settings.MICROPOROUS_PAPER_HEIGHT_MM)
        self.paper_aspect_ratio = self.paper_width_mm / self.paper_height_mm
        self.border_margin_ratio = settings.PAPER_BORDER_MARGIN_RATIO
        self.min_droplet_radius_mm = settings.MIN_DROPLET_RADIUS_MM
        self.max_droplet_radius_mm = settings.MAX_DROPLET_RADIUS_MM

    def load_model(self):
        """Compatibility hook: measurements deliberately use the portable rules."""
        return False

    @staticmethod
    def _order_points(points):
        return _canonical_corners(points)

    @staticmethod
    def _resize_long_edge(image, target_long_edge):
        height, width = image.shape[:2]
        scale = min(1.0, float(target_long_edge) / max(height, width))
        resized = cv2.resize(image, (max(1, round(width * scale)), max(1, round(height * scale))), interpolation=cv2.INTER_AREA) if scale < 1 else image.copy()
        return resized, scale

    def _detect_paper_region(self, image_bgr, expected_aspect=None):
        """Find a complete warm collector; reject low-fill/background candidates."""
        small, scale = self._resize_long_edge(image_bgr, 640)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB).astype(np.int16)
        red, green, blue = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
        warm = ((red > 75) & (green > 55) & (red > blue * 1.25) & (green > blue * 1.10) & (red >= green * 0.85)).astype(np.uint8)
        warm = cv2.morphologyEx(warm, cv2.MORPH_CLOSE, np.ones((7, 7), dtype=np.uint8))
        count, labels, stats, _ = cv2.connectedComponentsWithStats(warm, 8)
        best, confidence, best_score = None, 0.0, 0.0
        total_area = small.shape[0] * small.shape[1]
        for component in range(1, count):
            area = int(stats[component, cv2.CC_STAT_AREA])
            if area < total_area * 0.04:
                continue
            component_mask = (labels == component).astype(np.uint8)
            contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            hull = cv2.convexHull(max(contours, key=cv2.contourArea)).reshape(-1, 2).astype(float).tolist()
            # Conservative quadrilateral simplification, identical to the portable engine.
            while len(hull) > 4:
                losses = [abs(np.cross(np.array(hull[i]) - hull[i - 1], np.array(hull[(i + 1) % len(hull)]) - hull[i - 1])) for i in range(len(hull))]
                hull.pop(int(np.argmin(losses)))
            if len(hull) != 4:
                continue
            corners = _canonical_corners(hull)
            polygon_area = _polygon_area(corners)
            fill = min(1.0, area / max(polygon_area, 1))
            sides = [float(np.linalg.norm(corners[(i + 1) % 4] - corners[i])) for i in range(4)]
            aspect = (sides[0] + sides[2]) / max(sides[1] + sides[3], 1)
            if min(sides) < 18 or not 1.3 <= aspect <= 5.5 or fill < 0.50:
                continue
            edge = any(point[0] <= 1 or point[1] <= 1 or point[0] >= small.shape[1] - 2 or point[1] >= small.shape[0] - 2 for point in corners)
            aspect_score = max(0.0, 1 - abs(math.log(aspect / (expected_aspect or self.paper_aspect_ratio))) / 1.4)
            quality = fill * 0.55 + aspect_score * 0.45 - (0.18 if edge else 0)
            score = quality * min(1, area / (total_area * 0.25))
            if quality >= 0.62 and score > best_score:
                best, confidence, best_score = corners / scale, quality, score
        return best, min(1.0, confidence)

    def preprocess_image(self, image, options=None):
        options = dict(options or {})
        if image is None or image.size == 0 or image.ndim != 3 or image.shape[2] != 3:
            raise ImageProcessingError("Imagem RGB/BGR invalida.")
        target = max(128, min(2400, int(_option(options, "analysisLongEdgePx", "analysis_long_edge_px", self.analysis_long_edge_px))))
        width_mm = _positive(_option(options, "paperWidthMm", "paper_width_mm", self.paper_width_mm))
        height_mm = _positive(_option(options, "paperHeightMm", "paper_height_mm", self.paper_height_mm))
        if width_mm is None or height_mm is None:
            raise ImageProcessingError("Dimensoes do papel devem ser finitas e positivas.")
        width_mm, height_mm = max(width_mm, height_mm), min(width_mm, height_mm)
        manual = _option(options, "paperCorners", "paper_corners")
        if manual is not None:
            manual = [[point["x"], point["y"]] if isinstance(point, dict) else point for point in manual]
            points, confidence = _canonical_corners(manual), 1.0
            if np.any(points[:, 0] < 0) or np.any(points[:, 1] < 0) or np.any(points[:, 0] >= image.shape[1]) or np.any(points[:, 1] >= image.shape[0]):
                raise ImageProcessingError("Os cantos devem ficar dentro da imagem.")
        else:
            points, confidence = self._detect_paper_region(image, width_mm / height_mm)
        confirmed = _option(options, "paperSizeConfirmed", "paper_size_confirmed", False) is True
        manual_scale_input = _option(options, "mmPerPixel", "mm_per_pixel")
        manual_scale = _positive(manual_scale_input)
        if manual_scale_input is not None and manual_scale is None:
            raise ImageProcessingError("Escala manual deve ser finita e positiva.")
        warnings = []
        if points is not None and (not manual_scale or confirmed):
            sides = [float(np.linalg.norm(points[(i + 1) % 4] - points[i])) for i in range(4)]
            natural_width = (sides[0] + sides[2]) / 2
            natural_height = (sides[1] + sides[3]) / 2
            # Do not invent physical aspect ratio until the user confirms paper dimensions.
            aspect = width_mm / height_mm if confirmed else natural_width / max(natural_height, 1)
            out_width = max(2, min(target, round(natural_width)))
            out_height = max(2, round(out_width / aspect))
            destination = np.array([[0, 0], [out_width - 1, 0], [out_width - 1, out_height - 1], [0, out_height - 1]], np.float32)
            matrix = cv2.getPerspectiveTransform(points.astype(np.float32), destination)
            roi = cv2.warpPerspective(image, matrix, (out_width, out_height), flags=cv2.INTER_LINEAR)
            mm_per_px = width_mm / out_width if confirmed else None
            source = "confirmed_paper_dimensions" if confirmed else "unconfirmed_paper"
        else:
            roi, resize_scale = self._resize_long_edge(image, target)
            mm_per_px = manual_scale / resize_scale if manual_scale else None
            source = "manual_scale" if manual_scale else "uncalibrated"
            if points is None:
                warnings.append("Papel nao identificado: selecione os quatro cantos e confirme suas dimensoes.")
        valid_scale = mm_per_px is not None
        if not valid_scale:
            warnings.append("Sem calibracao confirmada: apenas pixels, cobertura e contagem visual; sem mm, densidade ou qualidade conclusiva.")
        margin_ratio = max(0, min(.12, float(_option(options, "borderMarginRatio", "border_margin_ratio", self.border_margin_ratio))))
        metadata = {
            "original_shape": tuple(image.shape), "paper_detected": points is not None,
            "paper_confidence": round(confidence, 3), "paper_polygon": points.tolist() if points is not None else None,
            "paper_dimensions_mm": {"width": width_mm, "height": height_mm} if confirmed and points is not None else None,
            "analysis_shape": roi.shape[:2], "analysis_area_px": roi.shape[0] * roi.shape[1],
            "analysis_mm_per_px": mm_per_px, "scale_source": source,
            "border_margin_px": max(1, round(min(roi.shape[:2]) * margin_ratio)),
            "analysis_rgb": cv2.cvtColor(roi, cv2.COLOR_BGR2RGB), "analysis_bgr": roi,
            "analysis_gray": cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY), "options": options,
            "warnings": warnings,
            "calibration": {"valid": valid_scale, "confirmed": valid_scale, "source": source, "mm_per_px": mm_per_px, "paper_size_confirmed": confirmed, "paper_dimensions_mm": {"width": width_mm, "height": height_mm} if confirmed and points is not None else None},
        }
        return metadata["analysis_rgb"], metadata

    def segment_droplets(self, image_rgb, metadata):
        return self._segment_with_opencv(image_rgb, metadata)

    def _segment_with_opencv(self, image_rgb, metadata):
        # Purple/blue color change, excluding yellow shadows and neutral dark dirt.
        rgb = image_rgb.astype(np.float32)
        maximum, minimum = rgb.max(axis=2), rgb.min(axis=2)
        delta = maximum - minimum
        saturation = delta / np.maximum(maximum, 1)
        red, green, blue = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
        chromatic = np.maximum(blue - red, (red + blue) / 2 - green)
        mask = (saturation >= .12) & (chromatic >= 15) & (blue > green * 1.05) & (maximum > 25)
        metadata["segmentation_method"] = "blue_purple_chromatic_v1"
        return mask.astype(np.uint8)

    @staticmethod
    def _component_geometry(component, left, top):
        ys, xs = np.nonzero(component)
        area = len(xs)
        center = [float(xs.mean() + left), float(ys.mean() + top)]
        centered = np.array([xs - xs.mean(), ys - ys.mean()])
        covariance = centered @ centered.T / max(area, 1)
        eigenvalues = np.linalg.eigvalsh(covariance)
        aspect = math.sqrt((float(eigenvalues[1]) + .25) / (float(eigenvalues[0]) + .25))
        padded = np.pad(component, 1)
        boundary_edges = sum(np.count_nonzero(component & ~padded[1 + dy:1 + dy + component.shape[0], 1 + dx:1 + dx + component.shape[1]]) for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)])
        perimeter = boundary_edges * math.pi / 4
        contours, _ = cv2.findContours(component.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        hull = cv2.convexHull(max(contours, key=cv2.contourArea))
        hull_area = float(cv2.contourArea(hull))
        solidity = min(1.0, area / max(hull_area + perimeter / 2 + 1, 1))
        circularity = min(1.0, 4 * math.pi * area / max(perimeter ** 2, 1))
        distance = cv2.distanceTransform(np.pad(component.astype(np.uint8), 1), cv2.DIST_L2, 3)[1:-1, 1:-1]
        peak_mask = ((distance >= max(float(distance.max()) * .72, 1.5)) & component).astype(np.uint8)
        n, _, stats, _ = cv2.connectedComponentsWithStats(peak_mask, 8)
        peaks = sum(int(stats[index, cv2.CC_STAT_AREA]) >= 2 for index in range(1, n))
        return center, aspect, solidity, circularity, max(1, peaks)

    def analyze_droplets(self, mask, metadata):
        if mask is None or mask.size == 0:
            raise ImageProcessingError("Mascara vazia.")
        options = metadata.get("options", {})
        scale = metadata.get("analysis_mm_per_px")
        minimum_diameter = _positive(_option(options, "minStainDiameterMm", "min_stain_diameter_mm", getattr(settings, "MIN_STAIN_DIAMETER_MM", .10)), .10)
        min_pixels = max(4, int(_option(options, "minComponentPixels", "min_component_pixels", 9)))
        resolution_diameter_px = 2 * math.sqrt(min_pixels / math.pi)
        effective_minimum_mm = max(minimum_diameter, resolution_diameter_px * scale) if scale else None
        max_diameter = _positive(_option(options, "maxStainDiameterMm", "max_stain_diameter_mm", 2 * self.max_droplet_radius_mm), 2.5)
        height, width = mask.shape
        margin = min(int(metadata.get("border_margin_px", 1)), max(0, min(height, width) // 4))
        interior = np.zeros_like(mask, dtype=bool)
        interior[margin:height - margin or height, margin:width - margin or width] = True
        analysis_area = int(interior.sum())
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
        components, diameters, valid_centers = [], [], []
        grid_rows = max(1, min(12, int(_option(options, "gridRows", "grid_rows", 3))))
        grid_cols = max(1, min(12, int(_option(options, "gridCols", "grid_cols", 6))))
        grid = np.zeros((grid_rows, grid_cols), dtype=int)
        coverage_pixels = 0
        counts = {key: 0 for key in ("valid", "coalesced", "edge", "tiny", "noise")}
        overlay = metadata["analysis_bgr"].copy()
        palette = {"valid": (70, 210, 50), "coalesced": (30, 150, 255), "edge": (255, 190, 40), "tiny": (180, 180, 180), "noise": (130, 65, 200)}
        for index in range(1, count):
            left, top, component_width, component_height, area = map(int, stats[index])
            component = labels[top:top + component_height, left:left + component_width] == index
            if area < min_pixels:
                counts["tiny"] += 1
                continue
            coverage_pixels += int((component & interior[top:top + component_height, left:left + component_width]).sum())
            center, aspect, solidity, circularity, peaks = self._component_geometry(component, left, top)
            diameter_px = 2 * math.sqrt(area / math.pi)
            diameter_mm = diameter_px * scale if scale else None
            edge = left <= margin or top <= margin or left + component_width >= width - margin or top + component_height >= height - margin
            if diameter_mm is not None and diameter_mm < minimum_diameter:
                label = "tiny"
            elif edge:
                label = "edge"
            elif aspect > 4.0 or solidity < .40:
                label = "noise"
            elif peaks >= 2 or aspect > 1.8 or (solidity < .72 and circularity < .60) or (diameter_mm is not None and diameter_mm > max_diameter):
                label = "coalesced"
            else:
                label = "valid"
            counts[label] += 1
            record = {"label": label, "bbox": [left, top, component_width, component_height], "centroid": [round(value, 3) for value in center], "area_px": area, "diameter_px": round(diameter_px, 3), "stain_diameter_um": round(diameter_mm * 1000, 3) if diameter_mm else None, "aspect_ratio": round(aspect, 3), "solidity": round(solidity, 3), "circularity": round(circularity, 3), "peak_count": peaks}
            if len(components) < 5000:
                components.append(record)
            if label == "valid":
                diameters.append(diameter_mm * 1000 if diameter_mm else diameter_px)
                valid_centers.append(center)
                row = min(grid_rows - 1, max(0, int((center[1] - margin) * grid_rows / max(height - 2 * margin, 1))))
                col = min(grid_cols - 1, max(0, int((center[0] - margin) * grid_cols / max(width - 2 * margin, 1))))
                grid[row, col] += 1
            cv2.rectangle(overlay, (left, top), (left + component_width - 1, top + component_height - 1), palette[label], 1)
        density = counts["valid"] / (analysis_area * scale * scale / 100) if scale else None
        spatial_cv = float(np.std(grid) / np.mean(grid) * 100) if counts["valid"] else None
        diameter_cv = float(np.std(diameters) / np.mean(diameters) * 100) if diameters else None
        proxy_dv50 = self._volume_quantile(diameters, .5) if scale and diameters else None
        warnings = list(metadata.get("warnings", []))
        if counts["coalesced"]:
            warnings.append("Manchas coalescidas excluidas da contagem; gotas sobrepostas nao podem ser recuperadas com confianca.")
        if scale and minimum_diameter / scale < 3:
            warnings.append("Resolucao insuficiente para o limiar fisico escolhido: fotografe mais perto, sem zoom digital.")
        if scale and minimum_diameter < resolution_diameter_px * scale:
            warnings.append("O piso de pixels e maior que o limiar solicitado; o limiar efetivo exibido limita as menores manchas contaveis.")
        if len(components) >= 5000:
            warnings.append("Overlay limitado a 5000 componentes; contagens incluem todos.")
        warnings.append("Diametros sao de manchas; DV50 proxy pondera diametro da mancha ao cubo e nao mede gotas originais sem fator de espalhamento validado.")
        non_tiny = counts["valid"] + counts["coalesced"] + counts["edge"] + counts["noise"]
        result = {
            "engine_version": ENGINE_VERSION, "measurement_status": "calibrated" if scale else "uncalibrated",
            "total_droplets": counts["valid"], "valid_droplets": counts["valid"], "candidate_droplets": count - 1,
            "double_droplets": counts["coalesced"], "duplicated_droplets": counts["coalesced"], "coalesced_components": counts["coalesced"],
            "edge_droplets": counts["edge"], "rejected_noise": counts["noise"], "rejected_by_size": counts["tiny"], "estimated_total_impacts": None,
            "coverage_percentage": round(coverage_pixels / max(analysis_area, 1) * 100, 3), "coverage_method": "stained_pixels_in_inner_roi",
            "density_per_cm2": round(density, 3) if density is not None else None,
            "cv_coefficient": round(spatial_cv, 3) if spatial_cv is not None else None,
            "diameter_cv_coefficient": round(diameter_cv, 3) if diameter_cv is not None else None,
            "dv50_diameter": None, "dv50_proxy_um": round(proxy_dv50, 3) if proxy_dv50 else None,
            "droplet_class": "Nao determinada (manchas, sem fator de espalhamento)",
            "mean_diameter": round(float(np.mean(diameters)), 3) if scale and diameters else None,
            "min_diameter": round(min(diameters), 3) if scale and diameters else None, "max_diameter": round(max(diameters), 3) if scale and diameters else None,
            "stain_diameter": {"unit": "um" if scale else "px", "count": len(diameters), "mean": round(float(np.mean(diameters)), 3) if diameters else None, "median": round(float(np.median(diameters)), 3) if diameters else None, "volume_weighted_proxy_dv50_um": round(proxy_dv50, 3) if proxy_dv50 else None, "spread_factor_applied": False},
            "spatial_uniformity": {"cv": round(spatial_cv, 3) if spatial_cv is not None else None, "rows": grid_rows, "cols": grid_cols, "counts": grid.tolist(), "method": "population_CV_of_isolated_counts_in_equal_area_cells", "sample_scope": "one_collector"},
            "coalesced_fraction": counts["coalesced"] / max(non_tiny, 1),
            "paper_detected": metadata.get("paper_detected", False), "paper_confidence": metadata.get("paper_confidence", 0),
            "paper_dimensions_mm": metadata.get("paper_dimensions_mm"), "analysis_scale_mm_per_px": scale,
            "scale_source": metadata.get("scale_source"), "calibration": metadata["calibration"],
            "analysis_area_px": analysis_area, "min_stain_diameter_mm": minimum_diameter, "min_component_pixels": min_pixels,
            "effective_min_stain_diameter_mm": round(effective_minimum_mm, 6) if effective_minimum_mm is not None else None,
            "resolution_min_stain_diameter_px": round(resolution_diameter_px, 6),
            "overlay": {"width": width, "height": height, "paper_polygon": metadata.get("paper_polygon"), "components": components, "legend": {"valid": "Mancha isolada contada", "coalesced": "Coalescida: excluida", "edge": "Borda: excluida", "tiny": "Abaixo do limiar: excluida", "noise": "Artefato: excluido"}},
            "warnings": warnings,
        }
        if _option(options, "includeOverlayPixels", "include_overlay_pixels", True):
            ok, encoded = cv2.imencode(".png", overlay)
            if ok:
                result["overlay"]["image_data_url"] = "data:image/png;base64," + base64.b64encode(encoded.tobytes()).decode("ascii")
        profile = _option(options, "profile", "quality_profile", options.get("application_profile"))
        result["quality"] = evaluate_quality(result, profile)
        result["quality_score"] = result["quality"]["score"]
        result["quality_assessment"] = result["quality"]["label"]
        result["recommendations"] = warnings + ["Indice fuzzy experimental: " + result["quality"]["label"] + ". Nao representa probabilidade de eficacia."]
        return result

    @staticmethod
    def _volume_quantile(diameters, quantile):
        ordered = sorted(diameters)
        threshold = sum(value ** 3 for value in ordered) * quantile
        cumulative = 0
        for value in ordered:
            cumulative += value ** 3
            if cumulative >= threshold:
                return value
        return ordered[-1] if ordered else None

    def _extract_patch_features(self, patch):
        return extract_patch_features(patch)

    def _calculate_quality_score(self, coverage, cv, density, **kwargs):
        result = evaluate_quality({"coverage_percentage": coverage, "density_per_cm2": density, "spatial_uniformity": {"cv": cv}, "valid_droplets": 100, "coalesced_fraction": kwargs.get("double_ratio", 0), "calibration": {"valid": kwargs.get("paper_detected", True)}})
        return result["score"] or 0.0

    @staticmethod
    def _assess_quality(score):
        return "Excelente" if score >= 80 else "Boa" if score >= 60 else "Regular" if score >= 40 else "Inadequada"

    @staticmethod
    def _generate_recommendations(coverage, cv, density, **kwargs):
        messages = []
        if coverage < 10:
            messages.append("Cobertura baixa para o perfil experimental; conferir amostragem e protocolo.")
        if cv > 15:
            messages.append("Distribuicao espacial irregular; repetir a amostragem em outras posicoes.")
        if kwargs.get("double_ratio", 0) >= .12:
            messages.append("Manchas duplas/coalescidas limitam a contagem.")
        return messages or ["Conferir parametros ideais definidos no protocolo da cultura e do alvo."]

    def process_image(self, image_path: str, options: Optional[Dict] = None):
        started = time.perf_counter()
        try:
            # PIL applies all eight EXIF orientations exactly once, including mirrored photos.
            with Image.open(image_path) as source:
                oriented = ImageOps.exif_transpose(source).convert("RGB")
                if oriented.width * oriented.height > 80_000_000:
                    raise ImageProcessingError("Imagem excede 80 megapixels; reduza a resolucao.")
                image = cv2.cvtColor(np.asarray(oriented), cv2.COLOR_RGB2BGR)
            rgb, metadata = self.preprocess_image(image, options)
            result = self.analyze_droplets(self.segment_droplets(rgb, metadata), metadata)
            result["processing_time"] = round(time.perf_counter() - started, 3)
            result["orientation_applied"] = "EXIF transpose before analysis"
            return result
        except ImageProcessingError:
            raise
        except Exception as exc:
            logger.warning("Falha na analise de {}: {}", Path(image_path).name, exc)
            raise ImageProcessingError(f"Falha no processamento da imagem: {exc}") from exc


droplet_analyzer = DropletAnalyzer()
