#!/usr/bin/env python3
"""Cliente manual autenticado de upload individual; não integra a suíte pytest."""
import argparse
from pathlib import Path

import requests
from upload_images import DEFAULT_BASE_URL, _headers, image_mime


def test_upload(image_path, api_key=None, base_url=DEFAULT_BASE_URL):
    path = Path(image_path)
    if not path.is_file():
        print('Arquivo não encontrado.')
        return False
    if not _headers(api_key):
        print('Defina SIOPA_ADMIN_API_KEY ou --api-key para acessar o dataset privado.')
        return False
    try:
        mime = image_mime(path)
        with path.open('rb') as stream:
            response = requests.post(f'{base_url.rstrip("/")}/api/v1/dataset/upload', headers=_headers(api_key),
                                     files={'file': (path.name, stream, mime)},
                                     data={'original_filename': path.name, 'uploaded_by': 'Teste', 'notes': 'Upload individual'}, timeout=30)
        if response.status_code != 200:
            print(f'Upload não confirmado: HTTP {response.status_code}.')
            return False
        data = response.json()
        if data.get('status') != 'success':
            print('O servidor não confirmou o upload.')
            return False
        print(f'Imagem enviada; ID {data.get("image_id")}.')
        return True
    except (OSError, requests.RequestException, ValueError):
        print('Arquivo inválido ou envio não confirmado.')
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image_path')
    parser.add_argument('--api-key', default=None, help='Ou use SIOPA_ADMIN_API_KEY.')
    parser.add_argument('--base-url', default=DEFAULT_BASE_URL)
    arguments = parser.parse_args(argv)
    return 0 if test_upload(arguments.image_path, arguments.api_key, arguments.base_url) else 1


if __name__ == '__main__':
    raise SystemExit(main())
