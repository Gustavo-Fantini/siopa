# GitHub Actions secrets

## Secrets obrigatorios

```text
EC2_HOST=app.seu-dominio.com
EC2_PORT=22
EC2_USER=ubuntu
EC2_PROJECT_DIR=/srv/siopa
EC2_SSH_KEY=-----BEGIN OPENSSH PRIVATE KEY-----
<sua-chave-aqui>
-----END OPENSSH PRIVATE KEY-----
```

## Como preencher
- `EC2_HOST`: dominio do app ou Elastic IP da instancia
- `EC2_PORT`: porta SSH da instancia
- `EC2_USER`: usuario Linux usado no SSH
- `EC2_PROJECT_DIR`: diretorio onde o repositorio fica no servidor
- `EC2_SSH_KEY`: chave privada correspondente a chave publica autorizada em `~/.ssh/authorized_keys`

## Observacoes
- use uma chave exclusiva para o GitHub Actions
- nao reutilize sua chave pessoal de administracao
- se girar a chave, atualize `authorized_keys` na EC2 e o secret no GitHub
