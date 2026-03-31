# SIOPA

Sistema Inteligente de Otimização da Pulverização Agrícola.

## Contexto acadêmico
- Projeto de TCC da ETEC Rodrigues de Abreu.
- Autores: Cauã Fernandes Jorge, Guilherme Cardoso Galelli, Gustavo Teodoro Fantini e Jeferson Aguilar Junior.
- Objetivo atual: deixar a plataforma pronta para execução em servidor, acesso mobile e expansão para iniciação científica.

## O que o projeto faz
- Analisa papel hidrossensível com visão computacional.
- Calcula métricas como cobertura, densidade, CV e DV50.
- Integra clima e contexto agronômico.
- Gera recomendação operacional e de produto.
- Mantém fluxo de dataset, anotação e treinamento.

## Arquitetura atual
- `main.py`: aplicação FastAPI.
- `app/api/`: rotas HTTP.
- `app/models/`: análise de imagem e modelos SQLAlchemy.
- `app/services/`: clima, agricultura, recomendação e treinamento.
- `app/static/`: interface web principal, anotação, PWA e assets.
- `docs/`: documentação de API e deploy.

## Melhorias aplicadas nesta revisão
- Execução preparada para servidor com `HOST=0.0.0.0`, proxy headers e `ROOT_PATH`.
- Banco desacoplado de SQLite fixo via `DATABASE_URL`.
- Interface web refeita para uso mobile-first.
- Interface de anotação refeita com suporte a pointer/touch.
- PWA adicionada com `manifest.webmanifest` e `service-worker.js`.
- Dockerfile e documentação de deploy adicionados.
- `.gitignore` e `.dockerignore` criados.
- Endpoints de clima, solo, preview e aliases padronizados.

## Execução local
```bash
pip install -r requirements.txt
python start.py --host 0.0.0.0 --port 8000
```

Depois acesse:
- `http://localhost:8000`
- `http://SEU_IP_LOCAL:8000` pelo celular na mesma rede

## Variáveis importantes
Crie um `.env` a partir de `.env.example`.

Campos principais:
- `HOST`
- `PORT`
- `DEBUG`
- `DATABASE_URL`
- `PUBLIC_BASE_URL`
- `CORS_ORIGINS`
- `ALLOWED_HOSTS`
- `ROOT_PATH`

## Deploy com Docker
```bash
docker build -t siopa .
docker run --rm -p 8000:8000 --env-file .env siopa
```

## Observações de segurança
- Não publique `.env` real.
- Revogue chaves antigas antes de abrir o repositório.
- Remova artefatos já versionados com `git rm --cached` antes de publicar.

## Documentação adicional
- `docs/API_DOCUMENTATION.md`
- `docs/DEPLOYMENT.md`
