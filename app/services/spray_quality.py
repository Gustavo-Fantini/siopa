"""Transparent, configurable fuzzy screening of deposits on one collector.

This is an engineering screening index, not a probability of control, a product
recommendation or a universal agronomic standard. Keep in sync with analysis-engine.js.
"""
from __future__ import annotations

import math
from typing import Dict, Optional

ENGINE_VERSION = "3.0.0-offline"
SCREENING_PROFILE = {
    "id": "experimental-screening", "mode": "screening", "culture": "generic",
    "coverageMin": 5.0, "coverageTarget": 15.0, "coverageMax": 35.0,
    "densityMin": 10.0, "densityTarget": 50.0, "densityMax": 250.0,
    "uniformityCvMax": 50.0, "confirmed": False,
}


def _number(value) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _ramp(value: float, start: float, end: float) -> float:
    return max(0.0, min(1.0, (value - start) / max(end - start, 1e-9)))


def _members(value: float, low: float, target: float, high: float) -> Dict:
    return {
        "low": 1.0 - _ramp(value, low, target),
        "adequate": min(_ramp(value, low, target), 1.0 - _ramp(value, target, high)),
        "high": _ramp(value, target, high),
    }


def evaluate_quality(metrics: Dict, profile: Optional[Dict] = None) -> Dict:
    """Zero-order Sugeno rules with visible memberships, weights and evidence."""
    fields = ["coverageMin", "coverageTarget", "coverageMax", "densityMin", "densityTarget", "densityMax", "uniformityCvMax"]
    invalid_profile = profile is not None and not isinstance(profile, dict)
    requested = profile if isinstance(profile, dict) else {}
    fallback = requested.get("status") == "requires_local_calibration" and all(requested.get(key) is None for key in fields) and requested.get("confirmed") is not True
    chosen = dict(SCREENING_PROFILE)
    if requested and not fallback:
        chosen.update(profile)
    elif fallback:
        chosen.update({key: requested[key] for key in ("culture", "stage") if key in requested})
    evidence = {
        "coverage_percentage": _number(metrics.get("coverage_percentage")),
        "density_per_cm2": _number(metrics.get("density_per_cm2")),
        "spatial_cv": _number((metrics.get("spatial_uniformity") or {}).get("cv")),
        "coalesced_fraction": _number(metrics.get("coalesced_fraction")) or 0.0,
        "isolated_count": int(metrics.get("valid_droplets") or metrics.get("total_droplets") or 0),
    }
    base = {
        "score": None, "status": "insufficient", "label": "Dados insuficientes",
        "method": "Sugeno experimental; graus de pertinencia, nao probabilidade",
        "profile": chosen, "evidence": evidence, "memberships": {}, "rules": [],
        "profile_source": "experimental_fallback" if fallback else "user" if requested else "experimental_default",
        "limitations": [
            "Indice de deposito no papel; nao mede eficacia, dose, deriva ou residuos.",
            "Uma amostra nao representa a lavoura; repetir em posicoes e alturas do dossel.",
            "Metas do perfil sao parametros configuraveis, nao norma universal por cultura.",
        ],
    }
    if fallback:
        base["requested_profile"] = requested
        base["limitations"].append("Catalogo sem metas numericas: aplicado explicitamente o preset experimental de triagem, sem validacao por cultura.")
    if invalid_profile:
        base["reason"] = "Perfil invalido: esperado um objeto com parametros."
        return base
    calibration = metrics.get("calibration") or {}
    if not calibration.get("valid"):
        base["reason"] = "Confirme dimensoes do papel detectado ou uma escala manual antes de avaliar."
        return base
    numbers = {name: _number(chosen.get(name)) for name in fields}
    if (any(value is None for value in numbers.values())
            or not 0 <= numbers["coverageMin"] < numbers["coverageTarget"] < numbers["coverageMax"] <= 100
            or not 0 <= numbers["densityMin"] < numbers["densityTarget"] < numbers["densityMax"]
            or numbers["uniformityCvMax"] <= 0):
        base["reason"] = "Perfil invalido: informe limites minimo < alvo < maximo e CV positivo."
        return base
    if evidence["coverage_percentage"] is None or evidence["density_per_cm2"] is None:
        base["reason"] = "Cobertura e densidade calibrada sao necessarias."
        return base
    if evidence["isolated_count"] > 0 and evidence["spatial_cv"] is None:
        base["reason"] = "Uniformidade espacial indisponivel para esta amostra."
        return base

    coverage = _members(evidence["coverage_percentage"], numbers["coverageMin"], numbers["coverageTarget"], numbers["coverageMax"])
    density = _members(evidence["density_per_cm2"], numbers["densityMin"], numbers["densityTarget"], numbers["densityMax"])
    cv = evidence["spatial_cv"] if evidence["spatial_cv"] is not None else numbers["uniformityCvMax"] * 2
    uniform = 1.0 - _ramp(cv, numbers["uniformityCvMax"] * 0.5, numbers["uniformityCvMax"] * 2.0)
    merged = _ramp(evidence["coalesced_fraction"], 0.05, 0.35)
    good = min(coverage["adequate"], density["adequate"], uniform, 1.0 - merged)
    poor = max(coverage["low"], coverage["high"], density["low"], density["high"], 1.0 - uniform, merged)
    intermediate = max(0.0, 1.0 - max(good, poor))
    absent = 1.0 if evidence["isolated_count"] == 0 else 0.0
    rules = [
        {"id": "adequate_deposit", "activation": good, "consequent": 90.0},
        {"id": "limiting_factor", "activation": poor, "consequent": 20.0},
        {"id": "intermediate_deposit", "activation": intermediate, "consequent": 55.0},
        {"id": "no_isolated_stains", "activation": absent, "consequent": 0.0},
    ]
    denominator = sum(rule["activation"] for rule in rules)
    score = sum(rule["activation"] * rule["consequent"] for rule in rules) / max(denominator, 1e-9)
    if absent:
        score = 0.0
    base.update({
        "score": round(score, 2),
        "status": "indicative" if chosen.get("confirmed") is True else "provisional",
        "label": "Favoravel ao perfil" if score >= 75 else "Requer ajuste" if score >= 45 else "Limitado para o perfil",
        "memberships": {"coverage": coverage, "density": density, "spatial_uniformity": uniform, "coalescence": merged},
        "rules": rules,
    })
    if not chosen.get("confirmed"):
        base["limitations"].append("Perfil experimental nao confirmado; valores nao validados para cultura/alvo/estagio.")
    if evidence["isolated_count"] < 20:
        base["limitations"].append("Poucas manchas isoladas: densidade e uniformidade sao instaveis.")
    return base
