# SIOPA

Sistema Inteligente de Otimizacao da Pulverizacao Agricola.

## Contexto academico
- Projeto de TCC da ETEC Rodrigues de Abreu.
- Autoria academica registrada: Caua Fernandes Jorge, Guilherme Cardoso Galelli, Gustavo Teodoro Fantini e Jeferson Aguilar Junior.
- Contato operacional atual do repositorio: Gustavo Teodoro Fantini.
- Objetivo tecnico atual: executar integralmente no servidor, com acesso mobile via navegador e base tecnica pronta para evolucao cientifica.

## Capacidades do projeto
- Analisa papel hidrossensivel com visao computacional.
- Detecta o retangulo amarelo/laranja, corrige perspectiva e calibra a escala em mm/px.
- Separa gotas validas, gotas duplas, marcas de borda e ruido antes do calculo final.
- Calcula cobertura, densidade, CV, DV50 e metricas correlatas.
- Integra clima, contexto regional por latitude/longitude, solo e base agronomica por bioma.
- Gera recomendacoes operacionais e de produto.
- Mantem fluxo de dataset, anotacao e treinamento.

## Stack atual
- `FastAPI` no backend HTTP.
- `SQLAlchemy` para persistencia.
- `OpenCV` e `Pillow` para analise de imagem.
- `PWA` mobile-first em `app/static/`, com frontend principal separado em `app.css` e `app.js`.
- `Docker` e `docker-compose` para deploy reproduzivel.
- `GitHub Actions` para validacao automatica basica e deploy de EC2.

## Execucao local
```bash
pip install -r requirements.txt
copy .env.example .env
python start.py --host 0.0.0.0 --port 8000
```

## Testes rapidos
```bash
python -m pytest -q
python -m compileall app tests
```

Depois acesse:
- `http://localhost:8000`
- `http://SEU_IP_LOCAL:8000` pelo celular na mesma rede

## Execucao com Docker Compose
```bash
docker compose up --build -d
```

Para usar PostgreSQL no mesmo ambiente:
```bash
docker compose --profile postgres up --build -d
```

## Deploy no Render
- O repositorio ja inclui `render.yaml` para deploy por Blueprint.
- Para manter `app.db`, `models` e `dataset`, use disco persistente no servico.
- O Blueprint atual ja monta o disco em `/app/data` e usa `DATABASE_URL=sqlite:////app/data/app.db`.
- Depois de criar o servico, preencha os segredos pendentes no painel do Render.
- Se quiser usar plano gratuito, nao conte com SQLite persistente; nesse caso, migre para Postgres.

## Deploy em EC2
- `docker-compose.prod.yml` sobe app + proxy reverso HTTPS.
- `deploy/Caddyfile` publica o dominio e encaminha trafego para o FastAPI.
- `scripts/ec2/deploy.sh` padroniza o deploy no servidor.
- `.github/workflows/deploy-ec2.yml` automatiza a atualizacao via GitHub Actions.
- Instrucoes completas: `docs/DEPLOYMENT_EC2.md`

## Endpoints operacionais
- `GET /health`
- `GET /health/readiness`
- `GET /api/v1/system/runtime`
- `GET /api/v1/client/config`

## Alinhamento para producao
- Use `.env.example` como base local e `.env.production.example` como base para o servidor.
- Troque `SECRET_KEY` antes de publicar.
- Defina `PUBLIC_BASE_URL`, `CORS_ORIGINS`, `ALLOWED_HOSTS` e `DOMAIN` corretamente.
- Ajuste `MICROPOROUS_PAPER_WIDTH_MM`, `MICROPOROUS_PAPER_HEIGHT_MM` e os limites de gotas se usar outro papel ou outro protocolo de leitura.
- Mantenha `.env`, bancos, logs e datasets fora do Git.
- Use `WORKERS` para ajustar concorrencia no servidor.
- Prefira `DATABASE_URL` com PostgreSQL em implantacoes publicas de maior escala.

## Documentacao
- `docs/API_DOCUMENTATION.md`
- `docs/DEPLOYMENT.md`
- `docs/DEPLOYMENT_EC2.md`
- `docs/EC2_RUNBOOK.md`
- `docs/GITHUB_ACTIONS_SECRETS.md`
- `docs/LGPD_OPERACIONAL.md`
- `docs/SCIENTIFIC_READINESS.md`
- `docs/PRESENTATION_CHECKLIST.md`

## Autoria e direitos
- Autoria e contato operacional: `AUTHORS.md`
- Status atual de direitos e licenciamento: `LICENSE.md`
- Avisos de atribuicao e cautelas de uso: `NOTICE.md`
