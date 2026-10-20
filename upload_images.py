#!/usr/bin/env python3
"""Upload em lote para o dataset privado, sem repetir extensões no Windows."""
import argparse
import mimetypes
import os
from pathlib import Path

import requests
from PIL import Image

DEFAULT_BASE_URL = 'http://127.0.0.1:8000'
SUPPORTED = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp'}


def _headers(api_key=None):
    key = api_key if api_key is not None else os.environ.get('SIOPA_ADMIN_API_KEY', '')
    return {'X-API-Key': key} if key else {}


def image_mime(path):
    """Use decoded image format, not a fixed MIME or a misleading extension."""
    with Image.open(path) as image:
        image.verify()
        return Image.MIME.get(image.format) or mimetypes.guess_type(str(path))[0] or 'application/octet-stream'


def list_images(folder):
    directory = Path(folder)
    if not directory.is_dir():
        return []
    # One directory traversal, one normalized resolved path per file. No lower/upper globs.
    unique = {}
    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() in SUPPORTED:
            unique[os.path.normcase(str(path.resolve()))] = path
    return sorted(unique.values(), key=lambda path: path.name.casefold())


def upload_images(image_folder, annotator_name='Gustavo', api_key=None, base_url=DEFAULT_BASE_URL):
    images = list_images(image_folder)
    if not images:
        print('Pasta inexistente ou sem imagens suportadas.')
        return False
    if not _headers(api_key):
        print('Defina SIOPA_ADMIN_API_KEY ou --api-key para acessar o dataset privado.')
        return False
    successful = 0
    for index, path in enumerate(images, 1):
        try:
            mime = image_mime(path)
            with path.open('rb') as stream:
                response = requests.post(f'{base_url.rstrip("/")}/api/v1/dataset/upload', headers=_headers(api_key),
                                         files={'file': (path.name, stream, mime)},
                                         data={'original_filename': path.name, 'uploaded_by': annotator_name, 'notes': 'Upload em lote'}, timeout=30)
            accepted = response.status_code == 200 and response.json().get('status') == 'success'
            if accepted:
                successful += 1
            print(f'[{index}/{len(images)}] {path.name}: {"enviada" if accepted else "falhou (HTTP " + str(response.status_code) + ")"}')
        except (OSError, requests.RequestException, ValueError):
            print(f'[{index}/{len(images)}] {path.name}: arquivo inválido ou envio não confirmado.')
    print(f'Enviadas: {successful}/{len(images)}. Anote, salve e revise antes do treino.')
    return successful == len(images)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image_folder')
    parser.add_argument('annotator_name', nargs='?', default='Gustavo')
    parser.add_argument('--api-key', default=None, help='Ou use SIOPA_ADMIN_API_KEY.')
    parser.add_argument('--base-url', default=DEFAULT_BASE_URL)
    arguments = parser.parse_args(argv)
    return 0 if upload_images(arguments.image_folder, arguments.annotator_name, arguments.api_key, arguments.base_url) else 1


if __name__ == '__main__':
    raise SystemExit(main())
