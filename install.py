"""
Script de instalação e configuração inicial do sistema
"""

import os
import sys
import subprocess
from pathlib import Path
import shutil

def check_python_version():
    """Verifica versão do Python"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ é necessário")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detectado")

def install_dependencies():
    """Instala dependências"""
    print("📦 Instalando dependências...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependências instaladas com sucesso")
    except subprocess.CalledProcessError:
        print("❌ Erro na instalação de dependências")
        sys.exit(1)

def create_directories():
    """Cria diretórios necessários"""
    directories = [
        "data/models",
        "data/temp", 
        "data/datasets",
        "logs"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"📁 Diretório criado: {directory}")

def setup_environment():
    """Configura arquivo .env"""
    env_example = Path(".env.example")
    env_file = Path(".env")
    
    if not env_file.exists() and env_example.exists():
        shutil.copy(env_example, env_file)
        print("✅ Arquivo .env criado a partir do .env.example")
        print("⚠️  Configure suas chaves de API no arquivo .env")
    else:
        print("ℹ️  Arquivo .env já existe")

def run_tests():
    """Executa testes básicos"""
    print("🧪 Executando testes...")
    try:
        subprocess.check_call([sys.executable, "-m", "pytest", "tests/", "-v"])
        print("✅ Todos os testes passaram")
    except subprocess.CalledProcessError:
        print("⚠️  Alguns testes falharam (normal na primeira instalação)")

def main():
    """Função principal de instalação"""
    print("🌱 Instalando Sistema Inteligente de Pulverização de Agrotóxicos")
    print("=" * 60)
    
    check_python_version()
    install_dependencies()
    create_directories()
    setup_environment()
    
    print("\n" + "=" * 60)
    print("✅ Instalação concluída!")
    print("\n📋 Próximos passos:")
    print("1. Configure as chaves de API no arquivo .env")
    print("2. Execute: python main.py")
    print("3. Acesse: http://localhost:8000")
    print("\n📚 Documentação: docs/API_DOCUMENTATION.md")

if __name__ == "__main__":
    main()
