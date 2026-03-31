#!/usr/bin/env python3
"""
Script para Iniciar Treinamento do Modelo ML
Sistema Inteligente de Pulverização - TCC ETEC
"""

import requests
import json
import time
from datetime import datetime

def check_dataset_ready():
    """
    Verifica se o dataset está pronto para treinamento
    """
    print("🔍 Verificando dataset...")
    
    try:
        response = requests.get("http://127.0.0.1:8000/api/v1/dataset/stats")
        
        if response.status_code != 200:
            print(f"❌ Erro ao verificar dataset: HTTP {response.status_code}")
            return False
        
        stats = response.json()
        
        total_images = stats.get('total_images', 0)
        annotated_images = stats.get('annotated_images', 0)
        total_annotations = stats.get('total_annotations', 0)
        
        print(f"📊 ESTATÍSTICAS DO DATASET:")
        print(f"   • Total de imagens: {total_images}")
        print(f"   • Imagens anotadas: {annotated_images}")
        print(f"   • Total de anotações: {total_annotations}")
        
        # Requisitos mínimos
        min_images = 5  # Ajustado para 5 imagens mínimas
        min_annotations = 50  # Ajustado para 50 anotações mínimas
        recommended_images = 10
        recommended_annotations = 100
        
        if annotated_images < min_images:
            print(f"\n❌ ATENÇÃO: Dataset insuficiente!")
            print(f"   Mínimo necessário: {min_images} imagens anotadas")
            print(f"   Atual: {annotated_images} imagens")
            print(f"\n   Por favor, anote mais imagens antes de treinar.")
            return False
        
        if annotated_images < recommended_images:
            print(f"\n⚠️ ATENÇÃO:")
            print(f"   Recomendado: pelo menos {recommended_images} imagens anotadas")
            print(f"   Atual: {annotated_images} imagens")
            print(f"   Com {annotated_images} imagens, o modelo pode ter qualidade limitada.")
            
            response = input(f"\n⚠️ Continuar mesmo assim? (s/n): ")
            if response.lower() not in ['s', 'sim', 'y', 'yes']:
                return False
        
        if total_annotations < min_annotations:
            print(f"\n⚠️ ATENÇÃO:")
            print(f"   Mínimo: {min_annotations} anotações")
            print(f"   Recomendado: {recommended_annotations}+ anotações")
            print(f"   Atual: {total_annotations} anotações")
            print(f"   Quanto mais anotações, melhor o modelo!")
            
            if total_annotations < min_annotations:
                response = input(f"\n⚠️ Continuar com poucas anotações? (s/n): ")
                if response.lower() not in ['s', 'sim', 'y', 'yes']:
                    return False
        
        print(f"\n✅ Dataset pronto para treinamento!")
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def start_training(
    model_name: str = "modelo_tcc_v1",
    algorithm: str = "random_forest",
    test_split: float = 0.2
):
    """
    Inicia o treinamento do modelo ML
    
    Args:
        model_name: Nome do modelo
        algorithm: Algoritmo (random_forest ou svm)
        test_split: Porcentagem para teste (0.2 = 20%)
    """
    print(f"\n🚀 INICIANDO TREINAMENTO")
    print(f"=" * 50)
    print(f"📝 Nome do modelo: {model_name}")
    print(f"🧠 Algoritmo: {algorithm.upper()}")
    print(f"📊 Split treino/teste: {int((1-test_split)*100)}% / {int(test_split*100)}%")
    print()
    
    training_config = {
        "model_name": model_name,
        "algorithm": algorithm,
        "test_split": test_split,
        "hyperparameters": {
            "n_estimators": 100,
            "max_depth": 20,
            "min_samples_split": 5
        } if algorithm == "random_forest" else {
            "kernel": "rbf",
            "C": 1.0,
            "gamma": "scale"
        }
    }
    
    try:
        print("📤 Enviando requisição de treinamento...")
        response = requests.post(
            "http://127.0.0.1:8000/api/v1/ml/train",
            json=training_config,
            timeout=300  # 5 minutos
        )
        
        if response.status_code != 200:
            print(f"❌ Erro: HTTP {response.status_code}")
            print(response.text)
            return False
        
        result = response.json()
        
        if result.get('status') == 'success':
            session_id = result.get('session_id')
            print(f"✅ Treinamento iniciado!")
            print(f"🔑 Session ID: {session_id}")
            print()
            
            # Monitora o progresso
            monitor_training(session_id)
            return True
        else:
            print(f"❌ Falha ao iniciar treinamento")
            print(f"   Mensagem: {result.get('message')}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"⏱️ Timeout - O treinamento pode estar em andamento")
        print(f"   Verifique o status em: http://127.0.0.1:8000/api/v1/ml/status")
        return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def monitor_training(session_id: str, check_interval: int = 5):
    """
    Monitora o progresso do treinamento
    
    Args:
        session_id: ID da sessão de treinamento
        check_interval: Intervalo de verificação em segundos
    """
    print(f"📊 MONITORANDO TREINAMENTO...")
    print(f"   (Atualizando a cada {check_interval}s)")
    print()
    
    start_time = time.time()
    last_status = None
    
    while True:
        try:
            response = requests.get(
                f"http://127.0.0.1:8000/api/v1/ml/training/{session_id}/status"
            )
            
            if response.status_code == 200:
                status = response.json()
                
                current_status = status.get('status')
                progress = status.get('progress', 0)
                
                if current_status != last_status:
                    elapsed = int(time.time() - start_time)
                    print(f"[{elapsed}s] Status: {current_status.upper()}")
                    last_status = current_status
                
                if current_status == 'completed':
                    print()
                    print(f"✅ TREINAMENTO CONCLUÍDO!")
                    print(f"=" * 50)
                    
                    # Exibe métricas
                    metrics = status.get('metrics', {})
                    if metrics:
                        print(f"📊 MÉTRICAS DO MODELO:")
                        print(f"   • Acurácia: {metrics.get('accuracy', 0):.2%}")
                        print(f"   • Precisão: {metrics.get('precision', 0):.2%}")
                        print(f"   • Recall: {metrics.get('recall', 0):.2%}")
                        print(f"   • F1-Score: {metrics.get('f1_score', 0):.2%}")
                    
                    model_id = status.get('model_id')
                    if model_id:
                        print(f"\n🎯 Modelo ID: {model_id}")
                        print(f"📁 Salvo em: data/models/")
                    
                    elapsed_total = int(time.time() - start_time)
                    print(f"\n⏱️ Tempo total: {elapsed_total}s")
                    break
                    
                elif current_status == 'failed':
                    print()
                    print(f"❌ TREINAMENTO FALHOU!")
                    error_msg = status.get('error_message', 'Erro desconhecido')
                    print(f"   Erro: {error_msg}")
                    break
                
                # Exibe progresso
                if progress > 0:
                    bar_length = 30
                    filled = int(bar_length * progress)
                    bar = '█' * filled + '░' * (bar_length - filled)
                    print(f"\r   Progresso: [{bar}] {progress:.1%}", end='', flush=True)
            
            time.sleep(check_interval)
            
        except KeyboardInterrupt:
            print(f"\n\n⚠️ Monitoramento interrompido pelo usuário")
            print(f"   O treinamento continua em background")
            break
        except Exception as e:
            print(f"\n❌ Erro ao monitorar: {e}")
            break

def main():
    """Função principal"""
    print("🧠 TREINAMENTO DE MODELO ML")
    print("=" * 50)
    print()
    
    # Verifica se o dataset está pronto
    if not check_dataset_ready():
        print(f"\n❌ Prepare o dataset antes de treinar:")
        print(f"   1. Acesse: http://127.0.0.1:8000/static/annotation.html")
        print(f"   2. Faça upload das imagens")
        print(f"   3. Anote as gotículas")
        print(f"   4. Execute este script novamente")
        return 1
    
    # Configuração do treinamento
    print(f"\n🔧 CONFIGURAÇÃO:")
    model_name = input(f"Nome do modelo [modelo_tcc_v1]: ").strip() or "modelo_tcc_v1"
    
    print(f"\nAlgoritmos disponíveis:")
    print(f"  1. Random Forest (recomendado)")
    print(f"  2. SVM")
    algorithm_choice = input(f"Escolha [1]: ").strip() or "1"
    algorithm = "random_forest" if algorithm_choice == "1" else "svm"
    
    # Inicia treinamento
    success = start_training(model_name, algorithm)
    
    if success:
        print(f"\n🎉 MODELO TREINADO COM SUCESSO!")
        print(f"\n📋 PRÓXIMOS PASSOS:")
        print(f"   1. Teste o modelo com novas imagens")
        print(f"   2. Avalie as métricas de performance")
        print(f"   3. Se necessário, treine novamente com mais dados")
        return 0
    else:
        print(f"\n❌ Falha no treinamento")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
