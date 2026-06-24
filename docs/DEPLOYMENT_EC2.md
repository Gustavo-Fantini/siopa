# Deploy EC2 com dominio publico

## Objetivo
- publicar o SIOPA em uma instancia EC2 com HTTPS
- manter atualizacao automatica a partir do GitHub
- preservar dados do app e certificados entre deploys

## Arquivos adicionados para producao
- `docker-compose.prod.yml`: stack de producao com app + Caddy
- `deploy/Caddyfile`: proxy reverso com HTTPS automatico
- `deploy/bootstrap-ubuntu.sh`: prepara Ubuntu com Docker oficial
- `scripts/ec2/deploy.sh`: rotina padrao de deploy no servidor
- `.github/workflows/deploy-ec2.yml`: atualizacao automatica a cada push em `main`
- `.env.production.example`: base para o `.env` do servidor
- `docs/EC2_RUNBOOK.md`: passo a passo operacional completo
- `docs/GITHUB_ACTIONS_SECRETS.md`: modelo pronto dos secrets

## Arquitetura recomendada
1. EC2 Linux com IP estatico
2. DNS publico apontando para o IP da instancia
3. Docker Engine + Docker Compose plugin instalados no host
4. Stack em `docker-compose.prod.yml`
5. Caddy recebendo trafego em 80/443 e encaminhando para o FastAPI em `app:8000`

## Primeira subida no servidor
1. clone o repositorio na EC2
2. copie `.env.production.example` para `.env`
3. ajuste `DOMAIN`, `PUBLIC_BASE_URL`, `SECRET_KEY`, `CORS_ORIGINS`, `ALLOWED_HOSTS` e chaves de integracao
4. execute `bash scripts/ec2/deploy.sh`
5. valide:
   - `https://SEU-DOMINIO/health`
   - `https://SEU-DOMINIO/health/readiness`
   - `https://SEU-DOMINIO/api/v1/system/runtime`

## Segredos necessarios no GitHub Actions
- `EC2_HOST`: IP publico ou DNS da instancia
- `EC2_PORT`: porta SSH, normalmente `22`
- `EC2_USER`: usuario Linux do servidor
- `EC2_SSH_KEY`: chave privada usada pelo GitHub Actions
- `EC2_PROJECT_DIR`: diretorio do projeto no servidor, ex. `/srv/siopa`

## Fluxo automatico de atualizacao
1. voce faz push na branch `main`
2. o workflow `Deploy EC2` abre uma sessao SSH no servidor
3. o servidor executa `git fetch`, `git checkout`, `git pull --ff-only`
4. o script `scripts/ec2/deploy.sh` reconstrui e sobe a stack

## Publicacao segura
- mantenha o repositorio com `.env` apenas no servidor
- restrinja `ALLOWED_HOSTS` e `CORS_ORIGINS` ao dominio final
- troque `SECRET_KEY` antes da publicacao
- deixe a porta `8000` apenas na rede interna do compose
- exponha para a internet apenas `80` e `443`
- limite o acesso SSH a IPs administrativos sempre que possivel

## Operacao e backup
- dados do app ficam no volume `siopa_data`
- logs ficam no volume `siopa_logs`
- certificados HTTPS ficam em `caddy_data`
- antes de alteracoes maiores, gere backup dos volumes persistentes

## Guias complementares
- bootstrap e primeira subida: `docs/EC2_RUNBOOK.md`
- cadastro de secrets do GitHub: `docs/GITHUB_ACTIONS_SECRETS.md`
