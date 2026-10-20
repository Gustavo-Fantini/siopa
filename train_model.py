#!/usr/bin/env python3
"""CLI autenticado para treino de recortes revisados do dataset privado."""
import argparse
import os
import time

import requests

DEFAULT_BASE_URL = 'http://127.0.0.1:8000'


def _headers(api_key=None):
    key = api_key if api_key is not None else os.environ.get('SIOPA_ADMIN_API_KEY', '')
    return {'X-API-Key': key} if key else {}


def check_dataset_ready(api_key=None, base_url=DEFAULT_BASE_URL, min_images=5):
    try:
        response = requests.get(f'{base_url.rstrip("/")}/api/v1/dataset/stats', headers=_headers(api_key), timeout=15)
        if response.status_code != 200:
            print(f'Falha ao verificar dataset: HTTP {response.status_code}. Confira a habilitação e a chave de acesso.')
            return False
        stats = response.json()
        ready = int(stats.get('ready_for_training', 0))
        print(f'Imagens anotadas: {stats.get("annotated_images", 0)}; revisadas para treino: {ready}; anotações: {stats.get("total_annotations", 0)}.')
        if ready < min_images:
            print(f'São necessárias pelo menos {min_images} imagens revisadas. Salve e aprove as anotações no anotador antes de treinar.')
            return False
        print('Pré-requisito de revisão atendido. O servidor ainda verificará classes, arquivos e divisão por imagem.')
        return True
    except (requests.RequestException, ValueError, TypeError):
        print('Não foi possível consultar as estatísticas do dataset privado.')
        return False


def monitor_training(session_id, check_interval=5, api_key=None, base_url=DEFAULT_BASE_URL):
    """Return True only after a completed session, never after failure/interruption."""
    previous = None
    while True:
        try:
            response = requests.get(f'{base_url.rstrip("/")}/api/v1/ml/training/{session_id}/status', headers=_headers(api_key), timeout=15)
            if response.status_code != 200:
                print(f'Falha ao consultar sessão: HTTP {response.status_code}.')
                return False
            status = response.json()
            current = status.get('status')
            if current != previous:
                print(f'Status: {current or "desconhecido"}')
                previous = current
            if current == 'completed':
                print('Treinamento concluído pelo servidor.')
                for name, value in (status.get('metrics') or {}).items():
                    if isinstance(value, (int, float)):
                        print(f'{name}: {value:.4f}')
                return True
            if current in {'failed', 'cancelled', 'canceled'}:
                print('Treinamento não concluído. Consulte o registro da sessão no servidor.')
                return False
            progress = status.get('progress')
            if isinstance(progress, (int, float)):
                print(f'Progresso informado: {max(0, min(100, progress)):.0f}%')
            time.sleep(check_interval)
        except KeyboardInterrupt:
            print('Monitoramento interrompido. A execução no servidor pode continuar; conclusão não confirmada.')
            return False
        except (requests.RequestException, ValueError, TypeError):
            print('Não foi possível acompanhar a sessão; conclusão não confirmada.')
            return False


def start_training(model_name='modelo_tcc_v1', algorithm='random_forest', test_split=.2, api_key=None, base_url=DEFAULT_BASE_URL):
    try:
        response = requests.post(f'{base_url.rstrip("/")}/api/v1/ml/train', headers=_headers(api_key),
                                 json={'model_name': model_name, 'algorithm': algorithm, 'test_split': test_split}, timeout=30)
        if response.status_code != 200:
            print(f'Falha ao iniciar treinamento: HTTP {response.status_code}.')
            return False
        result = response.json()
        if result.get('status') != 'success' or result.get('session_id') is None:
            print('O servidor não confirmou o início do treinamento.')
            return False
        print(f'Sessão iniciada: {result["session_id"]}.')
        return monitor_training(result['session_id'], api_key=api_key, base_url=base_url)
    except (requests.RequestException, ValueError, TypeError):
        print('Não foi possível iniciar o treinamento.')
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-key', default=None, help='Chave privada; também pode usar SIOPA_ADMIN_API_KEY.')
    parser.add_argument('--base-url', default=DEFAULT_BASE_URL)
    parser.add_argument('--model-name', default='modelo_tcc_v1')
    parser.add_argument('--algorithm', choices=['random_forest', 'svm'], default='random_forest')
    parser.add_argument('--test-split', type=float, default=.2)
    arguments = parser.parse_args(argv)
    if not 0 < arguments.test_split < 1:
        parser.error('--test-split precisa ficar entre 0 e 1.')
    if not _headers(arguments.api_key):
        print('Defina SIOPA_ADMIN_API_KEY ou --api-key para acessar o dataset privado.')
        return 1
    if not check_dataset_ready(arguments.api_key, arguments.base_url):
        return 1
    success = start_training(arguments.model_name, arguments.algorithm, arguments.test_split, arguments.api_key, arguments.base_url)
    print('Modelo treinado com sucesso.' if success else 'Treinamento sem conclusão bem-sucedida confirmada.')
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
