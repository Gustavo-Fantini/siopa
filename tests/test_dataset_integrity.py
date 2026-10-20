"""Private dataset requests use an isolated SQLite connection, never app.db."""
import math
from io import BytesIO
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import dataset_routes
from app.core.config import settings
from app.core.database import get_db
from app.models.database import Base, ImageAnnotation, ImageDataset, get_training_ready_images


@pytest.fixture
def dataset(tmp_path, monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    path = tmp_path / 'card.png'
    Image.new('RGB', (100, 80), 'yellow').save(path)
    with factory() as session:
        image = ImageDataset(filename='card.png', original_filename='<img src=x onerror=alert(1)>.png', file_path=str(path), file_size=path.stat().st_size, image_width=100, image_height=80, image_format='PNG', pixel_to_mm_ratio=.01, is_annotated=True, is_validated=False)
        session.add(image)
        session.flush()
        session.add_all([ImageAnnotation(image_id=image.id, x=x, y=20, radius=3, area_pixels=math.pi*9, confidence=1, annotated_by='fixture', annotation_type='droplet', review_status='pending') for x in (20, 60)])
        session.commit()
        image_id = image.id
    monkeypatch.setattr(settings, 'ENABLE_DATASET_API', True)
    monkeypatch.setattr(settings, 'ADMIN_API_KEY', 'private-test-key')
    app = FastAPI()
    app.include_router(dataset_routes.router, prefix='/api/v1')
    def isolated_db():
        with factory() as session:
            yield session
    app.dependency_overrides[get_db] = isolated_db
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, factory=factory, image_id=image_id, headers={'X-API-Key': 'private-test-key'})
    engine.dispose()


def _annotations(dataset):
    response = dataset.client.get(f'/api/v1/dataset/image/{dataset.image_id}/annotations', headers=dataset.headers)
    assert response.status_code == 200
    return response.json()['annotations']


def _save(dataset, annotations, **query):
    return dataset.client.post(f'/api/v1/dataset/image/{dataset.image_id}/annotations', headers=dataset.headers, json=annotations, params=query)


def _review(dataset, annotation_id, status):
    return dataset.client.put(f'/api/v1/dataset/annotation/{annotation_id}/review', headers=dataset.headers, data={'status': status, 'reviewed_by': 'reviewer', 'notes': 'checked'})


def test_private_dataset_and_image_require_header_and_enabled_server(dataset, monkeypatch):
    endpoint = f'/api/v1/dataset/image/{dataset.image_id}'
    assert dataset.client.get('/api/v1/dataset/images').status_code == 401
    assert dataset.client.get(endpoint).status_code == 401
    assert dataset.client.get(endpoint, headers={'X-API-Key': 'incorrect'}).status_code == 401
    response = dataset.client.get(endpoint, headers=dataset.headers)
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('image/')
    monkeypatch.setattr(settings, 'ENABLE_DATASET_API', False)
    assert dataset.client.get(endpoint, headers=dataset.headers).status_code == 403


def test_upload_normalizes_phone_exif_and_strips_metadata(dataset, tmp_path, monkeypatch):
    incoming = tmp_path / "incoming"
    monkeypatch.setattr(settings, 'DATASET_PATH', str(incoming))
    photo = Image.new('RGB', (63, 31), 'yellow')
    exif = Image.Exif()
    exif[274] = 6
    stream = BytesIO()
    photo.save(stream, format='JPEG', exif=exif)
    response = dataset.client.post('/api/v1/dataset/upload', headers=dataset.headers,
                                   files={'file': ('camera.jpg', stream.getvalue(), 'image/jpeg')})
    assert response.status_code == 200, response.text
    with dataset.factory() as session:
        entry = session.get(ImageDataset, response.json()['image_id'])
        assert (entry.image_width, entry.image_height) == (31, 63)
        with Image.open(entry.file_path) as saved:
            assert saved.size == (31, 63)
            assert saved.format == 'PNG'
            assert not saved.getexif()


def test_invalid_upload_leaves_no_orphan_file(dataset, tmp_path, monkeypatch):
    incoming = tmp_path / "incoming"
    monkeypatch.setattr(settings, 'DATASET_PATH', str(incoming))
    response = dataset.client.post('/api/v1/dataset/upload', headers=dataset.headers,
                                   files={'file': ('camera.jpg', b'not a photo', 'image/jpeg')})
    assert response.status_code == 400
    assert not incoming.exists() or not list(incoming.iterdir())


@pytest.mark.parametrize('bad', [
    {'x': -1, 'y': 1, 'radius': 2}, {'x': 1, 'y': 1, 'radius': -2},
    {'x': 1, 'y': 1, 'radius': 2, 'confidence': -0.1},
    {'x': 1, 'y': 1, 'radius': 2, 'annotation_type': '<script>'},
    {'x': 1, 'y': 1, 'radius': 2, 'diameter_mm': -1},
])
def test_invalid_replacement_never_deletes_existing_annotations(dataset, bad):
    before = _annotations(dataset)
    response = _save(dataset, [{'x': 10, 'y': 10, 'radius': 2}, bad])
    assert response.status_code == 422, response.text
    assert _annotations(dataset) == before


@pytest.mark.parametrize('scale', [-1, 0, 'nan', 'inf'])
def test_invalid_scale_preserves_annotations_and_saved_calibration(dataset, scale):
    before = _annotations(dataset)
    response = _save(dataset, [{'x': 10, 'y': 10, 'radius': 2}], pixel_to_mm_ratio=scale)
    assert response.status_code == 422, response.text
    assert _annotations(dataset) == before
    with dataset.factory() as session:
        assert session.get(ImageDataset, dataset.image_id).pixel_to_mm_ratio == .01


def test_save_preserves_zero_confidence_scale_and_pending_review(dataset):
    old = _annotations(dataset)
    for annotation in old:
        assert _review(dataset, annotation['id'], 'approved').status_code == 200
    response = _save(dataset, [{'x': 20, 'y': 30, 'radius': 4, 'confidence': 0, 'diameter_mm': .16}], pixel_to_mm_ratio=.02)
    assert response.status_code == 200, response.text
    assert response.json()['average_confidence'] == 0
    current = _annotations(dataset)
    assert len(current) == 1
    assert current[0]['confidence'] == 0
    assert current[0]['review_status'] == 'pending'
    with dataset.factory() as session:
        image = session.get(ImageDataset, dataset.image_id)
        assert image.pixel_to_mm_ratio == .02
        assert image.is_annotated is True
        assert image.is_validated is False
        assert get_training_ready_images(session) == []


def test_review_validates_only_after_all_annotations_approved(dataset):
    first, second = _annotations(dataset)
    assert _review(dataset, first['id'], 'approved').status_code == 200
    with dataset.factory() as session:
        assert session.get(ImageDataset, dataset.image_id).is_validated is False
        assert not get_training_ready_images(session)
    assert _review(dataset, second['id'], 'approved').status_code == 200
    with dataset.factory() as session:
        assert session.get(ImageDataset, dataset.image_id).is_validated is True
        assert len(get_training_ready_images(session)) == 1
    assert _review(dataset, first['id'], 'rejected').status_code == 200
    with dataset.factory() as session:
        assert session.get(ImageDataset, dataset.image_id).is_validated is False
        assert not get_training_ready_images(session)


def test_unknown_review_status_does_not_change_pending_annotation(dataset):
    first = _annotations(dataset)[0]
    assert _review(dataset, first['id'], 'anything').status_code == 422
    assert _annotations(dataset)[0]['review_status'] == 'pending'


def test_training_cli_failure_is_not_reported_as_success(monkeypatch, capsys):
    import train_model
    token = 'do-not-print-private-token'
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(status_code=200, json=lambda: {'status': 'success', 'session_id': 7})
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(status_code=200, json=lambda: {'status': 'failed'})
    monkeypatch.setattr(train_model.requests, 'post', post)
    monkeypatch.setattr(train_model.requests, 'get', get)
    assert train_model.start_training(api_key=token) is False
    assert token not in capsys.readouterr().out
    assert all(call[1]['headers']['X-API-Key'] == token and token not in call[0] for call in calls)


def test_upload_clients_use_real_mime_single_case_insensitive_listing_and_private_header(tmp_path, monkeypatch, capsys):
    import upload_images
    import test_upload_single
    png = tmp_path / 'Card.PNG'
    jpeg = tmp_path / 'Photo.JpG'
    Image.new('RGB', (8, 8), 'yellow').save(png, format='PNG')
    Image.new('RGB', (8, 8), 'yellow').save(jpeg, format='JPEG')
    assert len(upload_images.list_images(tmp_path)) == 2
    assert upload_images.image_mime(png) == 'image/png'
    assert upload_images.image_mime(jpeg) == 'image/jpeg'
    sent = []
    def post(url, **kwargs):
        sent.append((url, kwargs['files']['file'][2], kwargs['headers']))
        return SimpleNamespace(status_code=200, json=lambda: {'status': 'success', 'image_id': 9})
    monkeypatch.setenv('SIOPA_ADMIN_API_KEY', 'client-private-key')
    monkeypatch.setattr(upload_images.requests, 'post', post)
    assert upload_images.upload_images(tmp_path)
    assert test_upload_single.test_upload(png)
    assert len(sent) == 3
    assert {call[1] for call in sent} == {'image/png', 'image/jpeg'}
    assert all(call[2]['X-API-Key'] == 'client-private-key' for call in sent)
    assert 'client-private-key' not in capsys.readouterr().out
