# Deploy web/mobile do SIOPA

## Objetivo
Publicar o servidor de contexto/catálogo e a PWA. A jornada principal já processa
imagens no aparelho e guarda histórico offline; o APK inclui os arquivos locais.
Consulte `docs/MOBILE_OFFLINE.md` antes de configurar o cliente Android.

## Estratégia recomendada
- Backend FastAPI servindo API e arquivos estáticos.
- Acesso mobile por HTTPS para GPS e service worker; APK usa servidor HTTPS configurável.
- PWA para instalação opcional na tela inicial.
- Banco via `DATABASE_URL` para SQLite ou PostgreSQL.
- Se restringir CORS, permitir também `https://appassets.androidplatform.net` para o APK.
- Dataset/anotação/treinamento ficam desativados por padrão; habilitar flag e chave
  administrativa somente quando for utilizar as ferramentas internas.
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

## Deploy no Render

### Situação atual do projeto
- O projeto está apto para Render com `render.yaml`.
- O arquivo `render.yaml` usa runtime Docker, `healthCheckPath: /health` e disco persistente em `/app/data`.
- O SQLite foi configurado para `sqlite:////app/data/app.db`, preservando seu `app.db` entre deploys.

### Observação crítica
- Se você subir em um serviço sem disco persistente, o conteúdo de `app.db`, `models`, `dataset` e uploads pode ser perdido em restart ou novo deploy.
- Para manter o fluxo atual com SQLite, use um plano com disk.
- Se quiser usar Render sem disk, o caminho correto é migrar `DATABASE_URL` para Postgres.

### Passo a passo
1. No Render, escolha `New +` → `Blueprint`.
2. Aponte para este repositório.
3. Confirme o serviço `siopa` definido em `render.yaml`.
4. Preencha `PUBLIC_BASE_URL` com a URL pública do serviço Render.
5. Preencha as chaves `OPENWEATHER_API_KEY`, `WEATHERAPI_KEY`, `AGRO_API_TOKEN` e demais integrações necessárias.
6. Faça o primeiro deploy.
7. Valide `https://SEU-SERVICO.onrender.com/health`.
8. Valide `https://SEU-SERVICO.onrender.com/health/readiness`.

### Ajustes recomendados após subir
- Trocar `CORS_ORIGINS=["*"]` por sua URL pública real.
- Trocar `ALLOWED_HOSTS=["*"]` pelo host do Render e seu domínio final.
- Exportar backup periódico do `app.db`.

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
