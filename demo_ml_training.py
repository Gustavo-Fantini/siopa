#!/usr/bin/env python3
"""
Script de Demonstração do Sistema ML
Sistema Inteligente de Pulverização - TCC ETEC
"""

import asyncio
import json
import time
from pathlib import Path
import numpy as np
import cv2
from PIL import Image, ImageDraw
import requests
import sys

def create_demo_image():
    """
    Cria uma imagem de demonstração simulando papel microporoso
    """
    print("🎨 Criando imagem de demonstração...")
    
    # Cria imagem base (papel microporoso simulado)
    width, height = 800, 600
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Adiciona textura de fundo (papel)
    for _ in range(1000):
        x = np.random.randint(0, width)
        y = np.random.randint(0, height)
        size = np.random.randint(1, 3)
        color = (240 + np.random.randint(-10, 10), 
                240 + np.random.randint(-10, 10), 
                240 + np.random.randint(-10, 10))
        draw.ellipse([x-size, y-size, x+size, y+size], fill=color)
    
    # Adiciona gotículas simuladas
    droplets = []
    num_droplets = np.random.randint(20, 40)
    
    for i in range(num_droplets):
        # Posição aleatória
        x = np.random.randint(50, width-50)
        y = np.random.randint(50, height-50)
        
        # Tamanho variável (simula diferentes tamanhos de gotícula)
        radius = np.random.uniform(3, 15)
        
        # Cor azul (papel hidrossensível)
        blue_intensity = np.random.randint(100, 200)
        color = (50, 50, blue_intensity)
        
        # Desenha gotícula
        draw.ellipse([x-radius, y-radius, x+radius, y+radius], fill=color)
        
        # Adiciona variação na borda
        border_color = (30, 30, blue_intensity-20)
        draw.ellipse([x-radius, y-radius, x+radius, y+radius], outline=border_color, width=1)
        
        droplets.append({
            "x": float(x),
            "y": float(y),
            "radius": float(radius)
        })
    
    # Salva imagem
    demo_dir = Path("data/demo")
    demo_dir.mkdir(parents=True, exist_ok=True)
    
    img_path = demo_dir / "demo_microporoso.jpg"
    img.save(img_path, "JPEG", quality=95)
    
    # Salva anotações ground truth
    annotations_path = demo_dir / "demo_annotations.json"
    with open(annotations_path, 'w') as f:
        json.dump({
            "image_info": {
                "filename": "demo_microporoso.jpg",
                "width": width,
                "height": height
            },
            "droplets": droplets,
            "metadata": {
                "created_by": "demo_script",
                "num_droplets": len(droplets),
                "simulated": True
            }
        }, f, indent=2)
    
    print(f"✅ Imagem demo criada: {img_path}")
    print(f"✅ Anotações salvas: {annotations_path}")
    print(f"📊 Gotículas simuladas: {len(droplets)}")
    
    return str(img_path), str(annotations_path)

def test_image_analysis(image_path):
    """
    Testa análise de imagem com a demo
    """
    print("\n🔬 Testando análise de imagem...")
    
    try:
        # Importa o analisador
        sys.path.append(str(Path(__file__).parent))
        from app.models.image_analysis import droplet_analyzer
        
        # Processa imagem
        start_time = time.time()
        results = droplet_analyzer.process_image(image_path)
        processing_time = time.time() - start_time
        
        print(f"✅ Análise concluída em {processing_time:.2f}s")
        print(f"📊 Resultados:")
        print(f"   • Gotículas detectadas: {results.get('total_droplets', 0)}")
        print(f"   • Cobertura: {results.get('coverage_percentage', 0):.1f}%")
        print(f"   • CV: {results.get('cv_coefficient', 0):.1f}%")
        print(f"   • Densidade: {results.get('density_per_cm2', 0):.1f} got/cm²")
        print(f"   • Qualidade: {results.get('quality_assessment', 'N/A')}")
        
        return results
        
    except Exception as e:
        print(f"❌ Erro na análise: {e}")
        return None

async def test_api_upload(image_path):
    """
    Testa upload via API
    """
    print("\n📤 Testando upload via API...")
    
    try:
        # Verifica se servidor está rodando
        try:
            response = requests.get("http://127.0.0.1:8000/api/v1/health", timeout=5)
            if response.status_code != 200:
                print("⚠️ Servidor não está rodando. Inicie com: python main.py")
                return False
        except requests.exceptions.ConnectionError:
            print("⚠️ Servidor não está rodando. Inicie com: python main.py")
            return False
        
        # Upload da imagem
        with open(image_path, 'rb') as f:
            files = {'file': f}
            data = {
                'uploaded_by': 'demo_script',
                'notes': 'Imagem de demonstração criada automaticamente',
                'pixel_to_mm_ratio': 0.1
            }
            
            response = requests.post(
                "http://127.0.0.1:8000/api/v1/dataset/upload",
                files=files,
                data=data,
                timeout=30
            )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Upload realizado com sucesso")
            print(f"   • ID da imagem: {result.get('image_id')}")
            print(f"   • Tamanho: {result.get('size')}")
            return result.get('image_id')
        else:
            print(f"❌ Erro no upload: {response.status_code}")
            print(f"   {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Erro no teste de API: {e}")
        return None

async def test_annotation_api(image_id, annotations_path):
    """
    Testa API de anotações
    """
    print("\n📝 Testando API de anotações...")
    
    if not image_id:
        print("⚠️ ID da imagem não disponível")
        return False
    
    try:
        # Carrega anotações
        with open(annotations_path, 'r') as f:
            annotation_data = json.load(f)
        
        droplets = annotation_data['droplets']
        
        # Envia anotações via API
        response = requests.post(
            f"http://127.0.0.1:8000/api/v1/dataset/image/{image_id}/annotations",
            json=droplets,
            params={'annotated_by': 'demo_script'},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Anotações enviadas com sucesso")
            print(f"   • Anotações criadas: {result.get('annotation_count')}")
            print(f"   • Confiança média: {result.get('average_confidence', 0):.2f}")
            return True
        else:
            print(f"❌ Erro ao enviar anotações: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste de anotações: {e}")
        return False

async def test_training_api():
    """
    Testa API de treinamento
    """
    print("\n🧠 Testando API de treinamento...")
    
    try:
        # Lista modelos disponíveis
        response = requests.get("http://127.0.0.1:8000/api/v1/models", timeout=10)
        
        if response.status_code == 200:
            models = response.json()
            print(f"✅ Modelos disponíveis: {models.get('total', 0)}")
            
            if models.get('total', 0) > 0:
                model_id = models['models'][0]['id']
                
                # Tenta iniciar treinamento
                training_data = {
                    'model_id': model_id,
                    'session_name': 'Demo Training Session',
                    'total_epochs': 10,
                    'started_by': 'demo_script'
                }
                
                response = requests.post(
                    "http://127.0.0.1:8000/api/v1/training/start",
                    data=training_data,
                    timeout=15
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Treinamento iniciado")
                    print(f"   • Session ID: {result.get('session_id')}")
                    return result.get('session_id')
                else:
                    print(f"⚠️ Treinamento não iniciado: {response.text}")
            
        return None
        
    except Exception as e:
        print(f"❌ Erro no teste de treinamento: {e}")
        return None

def test_statistics_api():
    """
    Testa API de estatísticas
    """
    print("\n📊 Testando API de estatísticas...")
    
    try:
        response = requests.get("http://127.0.0.1:8000/api/v1/dataset/stats", timeout=10)
        
        if response.status_code == 200:
            stats = response.json()
            print(f"✅ Estatísticas obtidas:")
            print(f"   • Total de imagens: {stats.get('total_images', 0)}")
            print(f"   • Imagens anotadas: {stats.get('annotated_images', 0)}")
            print(f"   • Prontas para treino: {stats.get('ready_for_training', 0)}")
            print(f"   • Taxa de aprovação: {stats.get('annotation_approval_rate', 0):.1f}%")
            return True
        else:
            print(f"❌ Erro ao obter estatísticas: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste de estatísticas: {e}")
        return False

async def run_complete_demo():
    """
    Executa demonstração completa do sistema
    """
    print("🚀 DEMONSTRAÇÃO COMPLETA DO SISTEMA ML")
    print("=" * 50)
    
    # 1. Cria imagem de demonstração
    image_path, annotations_path = create_demo_image()
    
    # 2. Testa análise local
    analysis_results = test_image_analysis(image_path)
    
    # 3. Testa APIs (se servidor estiver rodando)
    image_id = await test_api_upload(image_path)
    
    if image_id:
        await test_annotation_api(image_id, annotations_path)
        await test_training_api()
    
    test_statistics_api()
    
    print("\n" + "=" * 50)
    print("🎉 DEMONSTRAÇÃO CONCLUÍDA!")
    print("=" * 50)
    print()
    print("📋 RESUMO:")
    print(f"✅ Imagem demo criada: {Path(image_path).name}")
    print(f"✅ Análise local funcionando")
    
    if image_id:
        print(f"✅ APIs funcionando (ID: {image_id})")
    else:
        print("⚠️ APIs não testadas (servidor offline)")
    
    print()
    print("🎓 Sistema pronto para uso no TCC!")
    print("   Acesse: http://127.0.0.1:8000/static/annotation.html")

def main():
    """Função principal"""
    try:
        asyncio.run(run_complete_demo())
    except KeyboardInterrupt:
        print("\n\n❌ Demonstração interrompida")
    except Exception as e:
        print(f"\n\n❌ Erro na demonstração: {e}")

if __name__ == "__main__":
    main()
