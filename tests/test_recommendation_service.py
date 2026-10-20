from app.services.recommendation_service import PesticideRecommendationService


def test_deposition_never_infers_infestation_pesticide_or_dose():
    result = PesticideRecommendationService().build_recommendation(
        {"coverage_percentage": 2, "quality": {"score": 20, "status": "provisional"}},
        "arroz", target_problem="lagarta",
    )
    assert result["crop"]["target_problem"] == "lagarta"
    assert result["pesticide"]["name"] is None
    assert result["dosage"]["recommended"] is None
    assert result["confidence"] is None
    assert result["reasoning"]["synthetic_models_used"] is False
    assert result["application"]["weather_suitability"] == "unknown"


def test_stale_or_mock_weather_never_authorizes_application():
    service = PesticideRecommendationService()
    for extra in ({"stale": True}, {"source": "mock_data"}, {"availability": "unavailable"}):
        weather = {"temperature": 25, "humidity": 65, "wind_speed": 8,
                   "spray_conditions": {"overall_rating": "ideal"}, **extra}
        assert service._weather_suitability(weather) == "unknown"
