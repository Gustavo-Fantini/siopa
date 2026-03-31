# SIOPA

Sistema Inteligente de Otimização da Pulverização Agrícola.

## Contexto acadêmico
- Projeto de TCC da ETEC Rodrigues de Abreu.
- Autores: Cauã Fernandes Jorge, Guilherme Cardoso Galelli, Gustavo Teodoro Fantini e Jeferson Aguilar Junior.
- Objetivo atual: executar integralmente no servidor, com acesso mobile via navegador e base técnica pronta para iniciação científica.

## Capacidades do projeto
- Analisa papel hidrossensível com visão computacional.
- Calcula cobertura, densidade, CV, DV50 e métricas correlatas.
- Integra clima e contexto agronômico.
- Gera recomendações operacionais e de produto.
- Mantém fluxo de dataset, anotação e treinamento.

## Stack atual
- `FastAPI` no backend HTTP.
- `SQLAlchemy` para persistência.
- `OpenCV` e `Pillow` para análise de imagem.
- `PWA` mobile-first em `app/static/`.
- `Docker` e `docker-compose` para deploy reproduzível.
- `GitHub Actions` para validação automática básica.

## Execução local
```bash
pip install -r requirements.txt
copy .env.example .env
python start.py --host 0.0.0.0 --port 8000
```

Depois acesse:
- `http://localhost:8000`
- `http://SEU_IP_LOCAL:8000` pelo celular na mesma rede

## Execução com Docker Compose
```bash
docker compose up --build -d
```

Para usar PostgreSQL no mesmo ambiente:
```bash
docker compose --profile postgres up --build -d
```

## Endpoints operacionais
- `GET /health`
- `GET /health/readiness`
- `GET /api/v1/system/runtime`
- `GET /api/v1/client/config`

## Alinhamento para produção
- Use `.env.example` como base e troque `SECRET_KEY`.
- Defina `PUBLIC_BASE_URL`, `CORS_ORIGINS` e `ALLOWED_HOSTS` corretamente.
- Mantenha `.env`, `app.db`, logs e datasets fora do Git.
- Use `WORKERS` para ajustar concorrência no servidor.
- Prefira `DATABASE_URL` com PostgreSQL em implantação pública.

## Documentação
- `docs/API_DOCUMENTATION.md`
- `docs/DEPLOYMENT.md`
- `docs/SCIENTIFIC_READINESS.md`
