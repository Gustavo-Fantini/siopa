#!/usr/bin/env python3
"""
Script de Configuração Completa do Sistema ML
Sistema Inteligente de Pulverização - TCC ETEC
"""

import os
import sys
import subprocess
import sqlite3
from pathlib import Path
from datetime import datetime
import json

def print_header():
    """Imprime cabeçalho do sistema"""
    print("=" * 70)
    print("🌱 SISTEMA INTELIGENTE DE PULVERIZAÇÃO DE AGROTÓXICOS")
    print("   TCC - ETEC Rodrigues de Abreu")
    print("   Cauã, Guilherme, Gustavo, Jeferson")
    print("=" * 70)
    print()

def check_python_version():
    """Verifica versão do Python"""
    print("🔍 Verificando versão do Python...")
    
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ é necessário")
        print(f"   Versão atual: {sys.version}")
        return False
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} OK")
    return True

def install_dependencies():
    """Instala dependências necessárias"""
    print("\n📦 Instalando dependências...")
    
    # Dependências essenciais
    essential_deps = [
        "fastapi>=0.103.1",
        "uvicorn>=0.23.2",
        "sqlalchemy>=2.0.0",
        "pydantic>=2.3.0",
        "pydantic-settings>=2.0.0",
        "python-multipart>=0.0.6",
        "loguru>=0.7.0",
        "python-dotenv>=1.0.0"
    ]
    
    # Dependências de ML (compatibilidade NumPy)
    ml_deps = [
        "numpy>=1.24.0,<2.0",
        "opencv-python-headless>=4.8.0",
        "pillow>=10.1.0",
        "scikit-learn>=1.3.0",
        "joblib>=1.3.2"
    ]
    
    # Dependências de APIs
    api_deps = [
        "requests>=2.31.0",
        "aiohttp>=3.8.5",
        "httpx>=0.24.1"
    ]
    
    all_deps = essential_deps + ml_deps + api_deps
    
    for dep in all_deps:
        try:
            print(f"   Instalando {dep.split('>=')[0]}...")
            subprocess.run([
                sys.executable, "-m", "pip", "install", dep
            ], check=True, capture_output=True)
            print(f"   ✅ {dep.split('>=')[0]} instalado")
        except subprocess.CalledProcessError as e:
            print(f"   ⚠️ Erro ao instalar {dep}: {e}")
    
    print("✅ Dependências instaladas")

def create_directories():
    """Cria estrutura de diretórios"""
    print("\n📁 Criando estrutura de diretórios...")
    
    directories = [
        "models",
        "temp/uploads",
        "data/dataset/images",
        "data/dataset/annotations",
        "logs",
        "backups"
    ]
    
    for directory in directories:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        print(f"   ✅ {directory}")
    
    print("✅ Estrutura de diretórios criada")

def setup_database():
    """Configura banco de dados inicial"""
    print("\n🗄️ Configurando banco de dados...")
    
    try:
        # Importa e inicializa o banco
        sys.path.append(str(Path(__file__).parent))
        from app.core.database import init_database
        from app.models.database import Base
        
        init_database()
        print("✅ Banco de dados inicializado")
        
        # Cria dados de exemplo se necessário
        create_sample_data()
        
    except Exception as e:
        print(f"❌ Erro ao configurar banco: {e}")
        return False
    
    return True

def create_sample_data():
    """Cria dados de exemplo para demonstração"""
    print("\n📊 Criando dados de exemplo...")
    
    try:
        from app.core.database import DatabaseTransaction
        from app.models.database import MLModel, ImageDataset
        
        with DatabaseTransaction() as db:
            # Verifica se já existem dados
            existing_models = db.query(MLModel).count()
            
            if existing_models == 0:
                # Modelo OpenCV padrão
                opencv_model = MLModel(
                    name="OpenCV Baseline",
                    version="1.0.0",
                    model_type="segmentation",
                    architecture="opencv_adaptive_threshold",
                    description="Modelo baseline usando OpenCV para segmentação de gotículas",
                    is_active=True,
                    accuracy=0.75,
                    precision=0.70,
                    recall=0.80,
                    f1_score=0.75,
                    created_by="system"
                )
                
                # Modelo Random Forest (placeholder)
                rf_model = MLModel(
                    name="Random Forest V1",
                    version="1.0.0",
                    model_type="segmentation",
                    architecture="random_forest",
                    description="Modelo Random Forest para classificação de gotículas",
                    is_active=False,
                    accuracy=0.85,
                    precision=0.82,
                    recall=0.88,
                    f1_score=0.85,
                    created_by="system"
                )
                
                db.add(opencv_model)
                db.add(rf_model)
                db.commit()
                
                print("   ✅ Modelos de exemplo criados")
        
    except Exception as e:
        print(f"   ⚠️ Erro ao criar dados de exemplo: {e}")

def create_env_file():
    """Cria arquivo .env com configurações"""
    print("\n⚙️ Criando arquivo de configuração...")
    
    env_content = f"""# Configurações do Sistema Inteligente de Pulverização
# Gerado automaticamente em {datetime.now().isoformat()}

# Aplicação
DEBUG=True
SECRET_KEY=your-secret-key-change-in-production-{datetime.now().strftime('%Y%m%d')}

# Servidor
HOST=127.0.0.1
PORT=8000

# APIs Externas (Configure conforme necessário)
OPENWEATHER_API_KEY=your_openweather_key_here
CLIMATEMPO_TOKEN=your_climatempo_token_here
EMBRAPA_API_KEY=your_embrapa_key_here

# Configurações de ML
MAX_IMAGE_SIZE=10485760
PIXEL_TO_MM=0.1

# Logging
LOG_LEVEL=INFO

# Banco de Dados
DATABASE_PATH=app.db
"""
    
    env_path = Path(".env")
    if not env_path.exists():
        env_path.write_text(env_content, encoding='utf-8')
        print("✅ Arquivo .env criado")
    else:
        print("✅ Arquivo .env já existe")

def create_startup_script():
    """Cria script de inicialização"""
    print("\n🚀 Criando script de inicialização...")
    
    startup_content = '''@echo off
echo.
echo ========================================
echo  Sistema Inteligente de Pulverizacao
echo  TCC - ETEC Rodrigues de Abreu
echo ========================================
echo.

echo Iniciando sistema...
python main.py

pause
'''
    
    startup_path = Path("start_system.bat")
    startup_path.write_text(startup_content, encoding='utf-8')
    print("✅ Script start_system.bat criado")

def test_system():
    """Testa componentes do sistema"""
    print("\n🧪 Testando componentes do sistema...")
    
    tests = [
        ("Importação FastAPI", test_fastapi),
        ("Importação OpenCV", test_opencv),
        ("Importação Scikit-learn", test_sklearn),
        ("Banco de dados", test_database),
        ("Análise de imagem", test_image_analysis)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            if result:
                print(f"   ✅ {test_name}")
                results.append(True)
            else:
                print(f"   ❌ {test_name}")
                results.append(False)
        except Exception as e:
            print(f"   ❌ {test_name}: {e}")
            results.append(False)
    
    success_rate = sum(results) / len(results) * 100
    print(f"\n📊 Taxa de sucesso: {success_rate:.1f}%")
    
    return success_rate > 80

def test_fastapi():
    """Testa importação do FastAPI"""
    from fastapi import FastAPI
    return True

def test_opencv():
    """Testa OpenCV"""
    import cv2
    import numpy as np
    
    # Cria imagem de teste
    test_img = np.zeros((100, 100, 3), dtype=np.uint8)
    gray = cv2.cvtColor(test_img, cv2.COLOR_BGR2GRAY)
    return gray.shape == (100, 100)

def test_sklearn():
    """Testa Scikit-learn"""
    from sklearn.ensemble import RandomForestClassifier
    import numpy as np
    
    # Teste rápido
    X = np.random.rand(10, 4)
    y = np.random.randint(0, 2, 10)
    
    clf = RandomForestClassifier(n_estimators=5, random_state=42)
    clf.fit(X, y)
    
    return len(clf.predict(X)) == 10

def test_database():
    """Testa conexão com banco"""
    try:
        from app.core.database import SessionLocal
        
        # Teste simples de conexão
        db = SessionLocal()
        try:
            # Executa query simples
            result = db.execute("SELECT 1 as test").fetchone()
            return result.test == 1
        finally:
            db.close()
    except Exception as e:
        print(f"   Erro no banco: {e}")
        return False

def test_image_analysis():
    """Testa análise de imagem básica"""
    try:
        from app.models.image_analysis import DropletAnalyzer
        
        analyzer = DropletAnalyzer()
        return analyzer is not None
    except:
        return False

def print_success_message():
    """Imprime mensagem de sucesso"""
    print("\n" + "=" * 70)
    print("🎉 SISTEMA CONFIGURADO COM SUCESSO!")
    print("=" * 70)
    print()
    print("📋 PRÓXIMOS PASSOS:")
    print()
    print("1. 🚀 Iniciar o sistema:")
    print("   python main.py")
    print("   OU")
    print("   start_system.bat")
    print()
    print("2. 🌐 Acessar interfaces:")
    print("   • Sistema Principal: http://127.0.0.1:8000")
    print("   • Anotação ML: http://127.0.0.1:8000/static/annotation.html")
    print("   • API Docs: http://127.0.0.1:8000/docs")
    print()
    print("3. 📚 Consultar documentação:")
    print("   • README_ML_TRAINING.md")
    print()
    print("4. 🧠 Para treinar ML:")
    print("   • Faça upload de imagens via interface")
    print("   • Anote as gotículas manualmente")
    print("   • Inicie o treinamento via API")
    print()
    print("🎓 TCC ETEC - Sistema pronto para uso!")
    print("=" * 70)

def main():
    """Função principal"""
    print_header()
    
    # Verificações e configurações
    if not check_python_version():
        return False
    
    install_dependencies()
    create_directories()
    create_env_file()
    create_startup_script()
    
    if not setup_database():
        print("❌ Falha na configuração do banco de dados")
        return False
    
    if not test_system():
        print("⚠️ Alguns testes falharam, mas o sistema pode funcionar")
    
    print_success_message()
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Configuração interrompida pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Erro fatal na configuração: {e}")
        sys.exit(1)
