#!/usr/bin/env python3
"""
Script para Upload em Lote de Imagens
Sistema Inteligente de Pulverização - TCC ETEC
"""

import requests
from pathlib import Path
import sys

def upload_images(image_folder: str, annotator_name: str = "Gustavo"):
    """
    Faz upload de todas as imagens de uma pasta
    
    Args:
        image_folder: Caminho da pasta com as imagens
        annotator_name: Nome do anotador
    """
    folder = Path(image_folder)
    
    if not folder.exists():
        print(f"❌ Pasta não encontrada: {folder}")
        return
    
    # Extensões suportadas
    extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
    images = []
    for ext in extensions:
        images.extend(folder.glob(f'*{ext}'))
        images.extend(folder.glob(f'*{ext.upper()}'))
    
    if not images:
        print(f"❌ Nenhuma imagem encontrada em: {folder}")
        return
    
    print(f"📤 UPLOAD DE IMAGENS")
    print(f"=" * 50)
    print(f"📁 Pasta: {folder}")
    print(f"🖼️  Total de imagens: {len(images)}")
    print(f"👤 Anotador: {annotator_name}")
    print()
    
    api_url = "http://127.0.0.1:8000/api/v1/dataset/upload"
    
    success_count = 0
    failed = []
    
    for i, image_path in enumerate(images, 1):
        print(f"[{i}/{len(images)}] Enviando: {image_path.name}...", end=" ")
        
        try:
            with open(image_path, 'rb') as f:
                files = {'file': (image_path.name, f, 'image/jpeg')}
                data = {
                    'original_filename': image_path.name,
                    'uploaded_by': annotator_name,
                    'notes': f'Upload em lote - Papel microporoso para TCC'
                }
                
                response = requests.post(api_url, files=files, data=data, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('status') == 'success':
                        print(f"✅ OK (ID: {result.get('image_id')})")
                        success_count += 1
                    else:
                        print(f"❌ Erro: {result.get('message')}")
                        failed.append(image_path.name)
                else:
                    print(f"❌ HTTP {response.status_code}")
                    failed.append(image_path.name)
                    
        except Exception as e:
            print(f"❌ Exceção: {e}")
            failed.append(image_path.name)
    
    print()
    print(f"=" * 50)
    print(f"✅ Sucesso: {success_count}/{len(images)}")
    
    if failed:
        print(f"❌ Falhas: {len(failed)}")
        for name in failed:
            print(f"   • {name}")
    else:
        print(f"🎉 TODAS AS IMAGENS ENVIADAS COM SUCESSO!")
    
    print()
    print(f"🎨 PRÓXIMOS PASSOS:")
    print(f"1. Acesse: http://127.0.0.1:8000/static/annotation.html")
    print(f"2. Anote as gotículas em cada imagem")
    print(f"3. Salve as anotações")
    print(f"4. Inicie o treinamento do ML")

def main():
    """Função principal"""
    if len(sys.argv) < 2:
        print("📤 UPLOAD EM LOTE DE IMAGENS")
        print("=" * 50)
        print()
        print("Uso:")
        print(f"  python {Path(__file__).name} <pasta_das_imagens> [nome_anotador]")
        print()
        print("Exemplo:")
        print(f'  python {Path(__file__).name} "C:\\Users\\usuario\\Desktop\\imagens_tcc" Gustavo')
        print()
        print("📋 Formatos suportados: JPG, PNG, BMP, TIFF")
        return 1
    
    image_folder = sys.argv[1]
    annotator_name = sys.argv[2] if len(sys.argv) > 2 else "Gustavo"
    
    try:
        upload_images(image_folder, annotator_name)
        return 0
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
