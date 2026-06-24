# EC2 runbook

## Escopo
Este runbook deixa a instancia pronta para receber o SIOPA com:
- dominio publico
- HTTPS automatico
- deploy por GitHub Actions
- stack Docker reproduzivel

## 1. AWS antes do login no servidor

### EC2
- Ubuntu LTS atual suportado pelo Docker
- tipo inicial sugerido: `t3.small` ou superior
- disco EBS com espaco suficiente para dataset, logs e banco

### Elastic IP
- aloque um Elastic IP
- associe o Elastic IP a instancia

### Security group
- `22/tcp` liberado apenas para seu IP administrativo
- `80/tcp` liberado para `0.0.0.0/0`
- `443/tcp` liberado para `0.0.0.0/0`

## 2. DNS publico
- crie um registro `A` apontando o subdominio do app para o Elastic IP
- exemplo: `app.seu-dominio.com -> 203.0.113.10`

## 3. Login e bootstrap

Conecte por SSH:

```bash
ssh -i sua-chave.pem ubuntu@SEU_ELASTIC_IP
```

No servidor, execute:

```bash
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/Gustavo-Fantini/siopa.git /tmp/siopa-bootstrap
sudo DEPLOY_USER=ubuntu PROJECT_DIR=/srv/siopa bash /tmp/siopa-bootstrap/deploy/bootstrap-ubuntu.sh
```

Depois reconecte na sessao SSH para o grupo `docker` ser aplicado.

## 4. Preparar o projeto no servidor

```bash
git clone https://github.com/Gustavo-Fantini/siopa.git /srv/siopa
cd /srv/siopa
cp .env.production.example .env
```

Gere uma `SECRET_KEY` forte:

```bash
openssl rand -hex 32
```

Edite `.env` e preencha pelo menos:
- `DOMAIN=app.seu-dominio.com`
- `PUBLIC_BASE_URL=https://app.seu-dominio.com`
- `SECRET_KEY=<valor-gerado>`
- `CORS_ORIGINS=["https://app.seu-dominio.com"]`
- `ALLOWED_HOSTS=["app.seu-dominio.com"]`
- chaves reais de clima e integracoes, se usadas

## 5. Primeiro deploy

```bash
cd /srv/siopa
chmod +x scripts/ec2/deploy.sh
bash scripts/ec2/deploy.sh
```

Validacoes:

```bash
docker compose -f docker-compose.prod.yml ps
curl -I https://app.seu-dominio.com/health
curl https://app.seu-dominio.com/health/readiness
curl https://app.seu-dominio.com/api/v1/system/runtime
```

## 6. Segredos do GitHub Actions

Cadastre no repositorio:
- `EC2_HOST=app.seu-dominio.com` ou o Elastic IP
- `EC2_PORT=22`
- `EC2_USER=ubuntu`
- `EC2_PROJECT_DIR=/srv/siopa`
- `EC2_SSH_KEY=<conteudo da chave privada>`

## 7. Configurar a chave SSH do deploy

Na sua maquina local, gere uma chave dedicada:

```bash
ssh-keygen -t ed25519 -C "github-actions-siopa" -f ./siopa-ec2-ed25519
```

Adicione a chave publica no servidor:

```bash
mkdir -p ~/.ssh
cat siopa-ec2-ed25519.pub >> ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

Coloque o conteudo de `siopa-ec2-ed25519` em `EC2_SSH_KEY`.

## 8. Teste do fluxo automatico
- faca um commit em `main`
- confirme a execucao do workflow `Deploy EC2`
- confirme no servidor:

```bash
cd /srv/siopa
git rev-parse HEAD
docker compose -f docker-compose.prod.yml ps
```

## 9. Checklist de fechamento
- dominio resolvendo para o Elastic IP
- `https://app.seu-dominio.com` abrindo sem aviso de certificado
- `health` e `readiness` respondendo
- `.env` presente apenas no servidor
- `SECRET_KEY` trocada
- GitHub Actions com secrets preenchidos
- SSH restrito ao seu IP no security group
