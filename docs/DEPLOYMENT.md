# Deploy web/mobile do SIOPA

## Objetivo
Executar o sistema em um servidor único, deixando o celular apenas como cliente web.

## Estratégia recomendada
- Backend FastAPI servindo API e arquivos estáticos.
- Acesso mobile pelo navegador via mesma rede ou URL pública.
- PWA para instalação opcional na tela inicial.
- Banco via `DATABASE_URL` para SQLite ou PostgreSQL.

## Variáveis principais
- `HOST=0.0.0.0`
- `PORT=8000`
- `DEBUG=False`
- `DATABASE_URL=postgresql+psycopg2://usuario:senha@host:5432/siopa`
- `PUBLIC_BASE_URL=https://seu-dominio`
- `CORS_ORIGINS=["https://seu-dominio"]`
- `ALLOWED_HOSTS=["seu-dominio","localhost","127.0.0.1"]`
- `ROOT_PATH=` quando publicar na raiz, ou `/siopa` se ficar atrás de subcaminho.

## Execução local
```bash
python start.py --host 0.0.0.0 --port 8000
```

## Execução com Docker
```bash
docker build -t siopa .
docker run --rm -p 8000:8000 --env-file .env siopa
```

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
