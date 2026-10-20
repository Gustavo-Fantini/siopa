import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from main import create_app
from app.api import routes_new


@pytest.fixture
def client():
    return TestClient(create_app())


def _image():
    stream = io.BytesIO()
    Image.new("RGB", (32, 24), "yellow").save(stream, format="PNG")
    return stream.getvalue()


def test_bootstrap_contains_complete_local_package_without_network(client, monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail("Bootstrap sem GPS não deve chamar provedores")
    monkeypatch.setattr(routes_new.environmental_service, "get_context", forbidden)
    response = client.get("/api/v1/offline/bootstrap")
    assert response.status_code == 200
    data = response.json()
    assert len(data["crops"]) >= 100
    assert {"arroz", "uva", "algodao", "cana"} <= {crop["key"] for crop in data["crops"]}
    assert data["environment"]["availability"] == "not_requested"
    assert data["capabilities"]["server_receives_photos_for_sync"] is False
    assert data["paper_defaults"]["paperSizeConfirmed"] is False
    assert data["quality_profiles"]["experimental-screening"]["confirmed"] is False
    assert "ADMIN_API_KEY" not in response.text


@pytest.mark.parametrize("params", [{"latitude": 0}, {"latitude": 91, "longitude": 0},
                                    {"latitude": "nan", "longitude": 0}])
def test_bootstrap_rejects_invalid_coordinates(client, params):
    assert client.get("/api/v1/offline/bootstrap", params=params).status_code in {400, 422}


def test_server_analysis_without_gps_is_calibrated_only_when_confirmed(client, monkeypatch):
    calls = []
    def analyze(path, options):
        calls.append(options)
        return {"total_droplets": 3, "calibration": {"valid": False},
                "quality": {"score": None, "status": "insufficient"}}
    async def forbidden(*args, **kwargs):
        pytest.fail("Foto sem GPS deve ser processada sem rede")
    monkeypatch.setattr(routes_new.droplet_analyzer, "process_image", analyze)
    monkeypatch.setattr(routes_new.environmental_service, "get_context", forbidden)
    response = client.post("/api/v1/analyze-image", files={"file": ("../card.png", _image(), "image/png")},
                           data={"crop_type": "uva", "target_problem": "alvo registrado"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert calls[0]["paperSizeConfirmed"] is False
    assert result["analysis"]["total_droplets"] == 3
    assert result["recommendations"]["dosage"]["recommended"] is None
    assert result["recommendations"]["crop"]["target_problem"] == "alvo registrado"
    assert not list(routes_new.Path(routes_new.settings.TEMP_UPLOAD_PATH).glob("*.png"))


def test_invalid_photo_and_profile_fail_before_processing(client, monkeypatch):
    monkeypatch.setattr(routes_new.droplet_analyzer, "process_image", lambda *a, **k: pytest.fail("Não analisar entrada inválida"))
    assert client.post("/api/v1/analyze-image", files={"file": ("file.png", b"not an image", "image/png")}).status_code == 400
    response = client.post("/api/v1/analyze-image", files={"file": ("file.png", _image(), "image/png")},
                           data={"quality_profile": '{"coverageMin":NaN}'})
    assert response.status_code == 400


def test_dataset_and_agrofit_writes_are_private_by_default(client):
    assert client.get("/api/v1/dataset/images").status_code == 403
    assert client.post("/api/v1/agrofit/sync").status_code == 403


def test_runtime_stats_do_not_invent_model_accuracy(client):
    data = client.get("/api/v1/system/stats").json()["stats"]
    assert data["models"]["measured_accuracy"] is None
    assert 0 <= data["system"]["uptime_seconds"] < 3600


def test_preview_is_explicit_simulation_without_pesticide(client):
    response = client.get("/api/v1/recommendations/preview", params={"crop_type": "arroz",
                          "coverage_percentage": 15, "density_per_cm2": 50, "cv_coefficient": 20})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "simulation"
    assert data["recommendations"]["quality"]["status"] == "simulated"
    assert data["recommendations"]["pesticide"]["name"] is None
