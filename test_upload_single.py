#!/usr/bin/env python3
"""
Script de teste para upload de uma única imagem
"""

import requests
from pathlib import Path
import sys

def test_upload(image_path: str):
    """
    Testa upload de uma imagem
    """
    image_file = Path(image_path)
    
    if not image_file.exists():
        print(f"❌ Arquivo não encontrado: {image_path}")
        return False
    
    print(f"🔍 Testando upload de: {image_file.name}")
    print(f"   Tamanho: {image_file.stat().st_size / 1024 / 1024:.2f} MB")
    
    api_url = "http://127.0.0.1:8000/api/v1/dataset/upload"
    
    try:
        with open(image_file, 'rb') as f:
            files = {'file': (image_file.name, f, 'image/png')}
            data = {
                'original_filename': image_file.name,
                'uploaded_by': 'Teste',
                'notes': 'Upload de teste'
            }
            
            print(f"\n📤 Enviando requisição...")
            response = requests.post(api_url, files=files, data=data, timeout=30)
            
            print(f"\n📊 Status Code: {response.status_code}")
            print(f"📋 Response:")
            print(response.text)
            
            if response.status_code == 200:
                result = response.json()
                print(f"\n✅ SUCESSO!")
                print(f"   ID: {result.get('image_id')}")
                print(f"   Filename: {result.get('filename')}")
                print(f"   Size: {result.get('size')}")
                return True
            else:
                print(f"\n❌ ERRO HTTP {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Detalhes: {error_data.get('detail', 'Sem detalhes')}")
                except:
                    pass
                return False
                
    except Exception as e:
        print(f"\n❌ Exceção: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Uso: python test_upload_single.py <caminho_da_imagem>")
        print("\nExemplo:")
        print('  python test_upload_single.py "C:\\Users\\gusta\\Desktop\\teste.png"')
        return 1
    
    image_path = sys.argv[1]
    success = test_upload(image_path)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
