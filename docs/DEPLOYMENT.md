# Deploy web/mobile do SIOPA

## Objetivo
Executar o sistema em um servidor único, deixando o celular apenas como cliente web.

## Estratégia recomendada
- Backend FastAPI servindo API e arquivos estáticos.
- Acesso mobile pelo navegador via mesma rede ou URL pública.
- PWA para instalação opcional na tela inicial.
- Banco via `DATABASE_URL` para SQLite ou PostgreSQL.
- Supervisão operacional com `GET /health/readiness` e `GET /api/v1/system/runtime`.

## Variáveis principais
- `ENVIRONMENT=production`
- `HOST=0.0.0.0`
- `PORT=8000`
- `WORKERS=2`
- `DEBUG=False`
- `DATABASE_URL=postgresql+psycopg2://usuario:senha@host:5432/siopa`
- `PUBLIC_BASE_URL=https://seu-dominio`
- `CORS_ORIGINS=["https://seu-dominio"]`
- `ALLOWED_HOSTS=["seu-dominio","localhost","127.0.0.1"]`
- `ROOT_PATH=` quando publicar na raiz, ou `/siopa` se ficar atrás de subcaminho.

## Execução local
```bash
python start.py --host 0.0.0.0 --port 8000 --workers 2
```

## Execução com Docker
```bash
docker build -t siopa .
docker run --rm -p 8000:8000 --env-file .env siopa
```

## Execução com Docker Compose
```bash
docker compose up --build -d
```

Com PostgreSQL no mesmo stack:
```bash
docker compose --profile postgres up --build -d
```

## Checklist mínimo de publicação
1. Copie `.env.example` para `.env`.
2. Se quiser reaproveitar as chaves atuais, use `.env.production.local` como base local privada.
3. Troque `SECRET_KEY`.
4. Ajuste `PUBLIC_BASE_URL`, `CORS_ORIGINS` e `ALLOWED_HOSTS`.
5. Confirme `GET /health/readiness`.
6. Valide `GET /api/v1/system/runtime`.
7. Ative HTTPS no proxy reverso.

## Uso no celular
- Conecte o celular na mesma rede do servidor.
- Descubra o IP local da máquina.
- Acesse `http://IP_DO_SERVIDOR:8000`.
- Instale o PWA pelo navegador, se desejar.

## Publicação
- Coloque um proxy reverso na frente do `uvicorn`.
- Ative HTTPS.
- Restrinja `CORS_ORIGINS` e `ALLOWED_HOSTS`.
- Revogue segredos antigos antes de publicar o repositório.
- Não suba `.env`, `app.db`, dataset bruto nem logs.
