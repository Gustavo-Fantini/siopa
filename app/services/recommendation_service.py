"""Auditable deposition advice, without synthetic pesticide/dose predictions."""

from datetime import datetime, timezone
from typing import Dict, Optional

from app.services.crop_catalog import crop_catalog


class PesticideRecommendationService:
    """Compatibility entry point for local spray-test recommendations."""

    def build_recommendation(
        self, analysis_results: Dict, crop_type: str,
        growth_stage: Optional[str] = None, target_problem: Optional[str] = None,
        weather_data: Optional[Dict] = None, crop_info: Optional[Dict] = None,
        soil_info: Optional[Dict] = None,
    ) -> Dict:
        crop = crop_info or crop_catalog.get_crop(crop_type)
        weather = weather_data or {}
        quality = analysis_results.get("quality") or {}
        calibration = analysis_results.get("calibration") or {}
        name = (crop or {}).get("name", crop_type)
        notes = list(analysis_results.get("recommendations") or [])
        notes.extend((crop or {}).get("sampling_guidance") or [])
        if not crop:
            notes.append("Cultura ausente do catálogo local; selecione uma referência validada.")
        notes.append(
            f"Para {name}, compare cartões colocados nos estratos e alvos do mesmo ensaio; "
            "um único cartão não representa toda a área pulverizada."
        )
        if not calibration.get("valid") or not calibration.get("confirmed"):
            notes.append("Confirme as dimensões do cartão e a delimitação do papel antes de interpretar medidas físicas.")
        if quality.get("status") != "validated":
            notes.append(
                "O percentual fuzzy expressa aderência ao perfil informado; não é probabilidade "
                "de acerto da contagem nem comprovação de eficácia agronômica."
            )
        if target_problem:
            notes.append("O alvo foi registrado como contexto. A imagem do cartão não confirma sua presença na cultura.")
        suitability = self._weather_suitability(weather)
        if suitability == "unknown":
            notes.append("Condições atuais de aplicação não avaliadas: clima recente e identificável indisponível.")
        elif suitability in {"poor", "caution"}:
            notes.extend((weather.get("spray_conditions") or {}).get("recommendations") or [])
        if weather.get("stale"):
            notes.append("O clima exibido é um registro em cache; atualize antes de decidir uma nova aplicação.")
        notes.append(
            "Produto, dose e intervalo dependem de alvo confirmado, cultura, bula/registro vigente "
            "e protocolo de aplicação; não são deduzidos pela cobertura do cartão."
        )
        return {
            "status": "deposition_advice", "mode": "local_rules",
            "crop": {"key": (crop or {}).get("key", crop_type), "name": name,
                     "growth_stage": growth_stage, "target_problem": target_problem},
            "quality": quality,
            "pesticide": {"name": None, "active_ingredient": None, "concentration": None,
                          "status": "requires_verified_crop_target_and_label", "agrofit_candidates": []},
            "dosage": {"recommended": None, "unit": None, "range": None, "status": "requires_product_label"},
            "application": {"timing": None, "weather_suitability": suitability,
                            "weather_source": weather.get("source"),
                            "observed_at": weather.get("observed_at") or weather.get("timestamp"),
                            "stale": bool(weather.get("stale"))},
            "confidence": None,
            "recommendations": list(dict.fromkeys(str(item) for item in notes if item)),
            "reasoning": {"method": "measured_deposition_and_explicit_profile",
                          "profile": quality.get("profile") or {}, "evidence": quality.get("evidence", []),
                          "inferred_infestation": False, "synthetic_models_used": False},
            "context": {"soil": soil_info or {}, "weather_availability": weather.get("availability", "unavailable")},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _weather_suitability(weather: Dict) -> str:
        if (weather.get("availability") not in {"available", "partial"}
                or not weather.get("source") or weather.get("source") == "mock_data" or weather.get("stale")):
            return "unknown"
        if any(weather.get(field) is None for field in ("temperature", "humidity", "wind_speed")):
            return "unknown"
        rating = (weather.get("spray_conditions") or {}).get("overall_rating", "unknown")
        return rating if rating in {"ideal", "good", "caution", "poor"} else "unknown"

    async def get_pesticide_recommendation(
        self, analysis_results: Dict, latitude: Optional[float], longitude: Optional[float],
        crop_type: str, growth_stage: Optional[str] = None, target_problem: Optional[str] = None,
        weather_data: Optional[Dict] = None, crop_info: Optional[Dict] = None,
        soil_info: Optional[Dict] = None,
    ) -> Dict:
        """Old API entry point; the orchestrator supplies fetched context once."""
        return self.build_recommendation(
            analysis_results, crop_type, growth_stage, target_problem,
            weather_data, crop_info, soil_info,
        )


recommendation_service = PesticideRecommendationService()
