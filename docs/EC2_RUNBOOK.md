# Runbook do deploy EC2 opcional

Este roteiro é para quem decidiu hospedar o backend numa instância existente
ou preparada por seu administrador. **EC2 não é requisito para push, CI ou APK**.
Sem hospedagem, mantenha `ENABLE_EC2_DEPLOY` ausente/desativada: o deploy é
ignorado explicitamente e a análise Android permanece local.

Os comandos abaixo são instruções para a operação futura autorizada. Alterar
este guia não cria servidor, DNS, credenciais ou publicação.

## 1. Preparar servidor e rede quando a hospedagem for desejada

Use Linux suportado pelo Docker, disco dimensionado para os dados e backups,
e endereço público/DNS estável. Exponha 80/443 ao tráfego do site; a porta 8000
permanece interna ao Compose.

Restrinja a porta SSH às origens autorizadas. Confira **também a origem de rede
do runner de deploy**: permitir somente o IP do computador administrativo não
permite automaticamente a entrada dos runners hospedados do GitHub. Prepare um
caminho autorizado para a automação, com saída conhecida ou conexão privada
quando aplicável, sem ampliar indiscriminadamente o acesso para corrigir timeout.
Se SSH usar porta personalizada, use-a no security group, firewall, cliente e
`EC2_PORT`.

Para DNS, um registro `A` deve apontar ao endereço público escolhido. Hostnames,
IPs e caminhos neste documento são placeholders; substitua-os antes de executar.

## 2. Acesso administrativo e bootstrap

Conecte com a chave administrativa já provisionada, verificando a identidade do
servidor por canal confiável:

```bash
ssh -p 22 -i sua-chave.pem ubuntu@SEU_ELASTIC_IP
```

Na sessão do servidor, instale Git e use o bootstrap se Docker/Compose ainda
precisarem de preparação:

```bash
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/Gustavo-Fantini/siopa.git /tmp/siopa-bootstrap
sudo DEPLOY_USER=ubuntu PROJECT_DIR=/srv/siopa bash /tmp/siopa-bootstrap/deploy/bootstrap-ubuntu.sh
```

Revise o script antes da execução e reconecte depois para aplicar o grupo
`docker`. Se o host já estiver preparado, não é necessário repetir o bootstrap.

## 3. Projeto, configuração e commit inicial

Clone apenas se o diretório ainda não contiver o projeto:

```bash
git clone https://github.com/Gustavo-Fantini/siopa.git /srv/siopa
cd /srv/siopa
cp .env.production.example .env
```

Não sobrescreva um `.env` existente. Configure nele domínio, `PUBLIC_BASE_URL`,
`SECRET_KEY` forte, `CORS_ORIGINS` e `ALLOWED_HOSTS`. Integrações com credenciais
são opcionais conforme uso; o cliente Open-Meteo aberto funciona sem chave,
respeitados os [termos das fontes](DATA_SOURCES.md).

Dataset/anotação/treino permanecem desativados por padrão. Caso sejam necessários,
configure o controle administrativo e as opções documentadas do projeto antes
de expô-los. `.env`, bancos, modelos, fotos e chaves não devem ser commitados.

Antes da primeira publicação manual, selecione o **SHA aprovado no CI** que
deseja instalar. A branch `main` pode ter avançado desde a aprovação: confira o
commit, não apenas o nome da branch. Preserve arquivos e dados locais; não use
reset ou limpeza destrutiva para contornar uma divergência sem revisão.

## 4. Primeira subida e verificação

Com o commit desejado e a configuração revisados:

```bash
cd /srv/siopa
git rev-parse HEAD
bash scripts/ec2/deploy.sh
docker compose -f docker-compose.prod.yml ps
curl --fail --show-error https://app.seu-dominio.com/health
curl --fail --show-error https://app.seu-dominio.com/health/readiness
```

Confira estado dos containers e conteúdo de prontidão, além do retorno HTTP.
A rota `/api/v1/system/runtime` também oferece diagnóstico; confira a prontidão
em `/health/readiness`. Uma imagem construída ou um comando finalizado sem erro
não basta para afirmar que o serviço público está saudável.

## 5. Chave de acesso de deploy e host key

Provisione por seu procedimento administrativo uma chave **dedicada à automação**
e autorize sua pública em `~/.ssh/authorized_keys` do usuário escolhido. Restrinja
permissões de `~/.ssh` e `authorized_keys` a 700/600. A privada usada pelo job
deve funcionar sem interação; uma passphrase exige suporte explícito a
agent/passphrase, não apenas copiar o arquivo.

Separadamente, obtenha a **host key do servidor** e a fingerprint pela console
ou sessão já confiável. Por exemplo, para Ed25519:

```bash
sudo cat /etc/ssh/ssh_host_ed25519_key.pub
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256
```

Use a pública para montar `EC2_KNOWN_HOSTS` com o host exato do deploy. O formato
é `host tipo chave` na porta 22, ou `[host]:porta tipo chave` em porta personalizada.
Se preferir uma coleta local com `ssh-keyscan -T 10 -p PORTA`, **compare antes**
a fingerprint com a console; a coleta por rede sozinha não autentica o host.
O passo a passo está em [GITHUB_ACTIONS_SECRETS.md](GITHUB_ACTIONS_SECRETS.md).

Ao recriar a instância ou trocar sua host key, o pin anterior deve fazer a
conexão falhar. Valide a mudança pela console antes de atualizá-lo; não desative
a verificação de identidade para obter um status verde.

## 6. Secrets e habilitação no GitHub

Configure os secrets no repositório ou no environment `production` utilizado
pelo job:

| Nome | Exemplo/instrução |
| --- | --- |
| `EC2_HOST` | Host ou IP, sem protocolo, porta ou caminho. |
| `EC2_PORT` | Opcional; padrão 22, ou a porta SSH configurada. |
| `EC2_USER` | Usuário Linux com a pública de deploy autorizada. |
| `EC2_PROJECT_DIR` | Diretório absoluto, por exemplo `/srv/siopa`. |
| `EC2_SSH_KEY` | Privada dedicada completa, preservando quebras de linha. |
| `EC2_KNOWN_HOSTS` | Entrada(s) de host key verificadas para o host/porta usados. |

Depois, em Settings → Secrets and variables → Actions → Variables, defina
**no repositório** `ENABLE_EC2_DEPLOY=true`. Não dependa de uma variável existente
somente no environment para decidir o início do job.

Se a flag estiver desativada, nenhuma implantação é tentada. Se estiver
habilitada e a configuração for incompleta/inválida, o preflight deve falhar
identificando os nomes faltantes, sem mostrar valores. A flag não substitui as
proteções e aprovações do environment.

## 7. Verificar a atualização automática ou manual

O fluxo automático é: push em `main` → CI aprovado para o mesmo SHA → gate de
EC2 habilitado → validações SSH → publicação do **SHA exato** → verificação do
serviço. O servidor não deve fazer um `git pull main` indiscriminado para
instalar um commit mais novo sem CI.

O acionamento manual fica restrito a `main` e deve comprovar aprovação de CI
para o SHA escolhido. Não o use para contornar testes pendentes/falhos.

Após uma execução real de deploy, compare o SHA indicado no workflow com:

```bash
cd /srv/siopa
git rev-parse HEAD
docker compose -f docker-compose.prod.yml ps
```

Confira também HTTPS e prontidão. Um job ignorado não publicou o aplicativo;
desativar novos deploys também não desliga uma instância já em funcionamento.

## 8. Diagnosticar falhas sem esconder o resultado

Na execução investigada em **20/10/2026**, o CI/backend passou e `Prepare SSH`
falhou com `EC2_HOST` e `EC2_SSH_KEY` vazios. O erro refletia configuração EC2
ausente. Quem trabalha apenas no código/Android pode deixar EC2 desativada.

- **Configuração ausente com gate habilitado:** confira os nomes e o escopo dos
  secrets; mantenha a falha até corrigir ou desative explicitamente o deploy.
- **Timeout/conexão recusada:** confira DNS, porta, daemon SSH e acesso de rede
  do runner; a regra do seu computador não cobre automaticamente o runner.
- **Host key divergente:** verifique identidade pela console, incluindo host e
  porta, antes de qualquer atualização do pin.
- **Chave inválida/autenticação negada:** confira formato, quebras de linha,
  passphrase, usuário e pública autorizada.
- **CI não aprovado para o SHA:** aguarde ou corrija o CI desse commit.
- **SSH funciona, aplicação falha:** examine build, configuração, containers e
  prontidão. Não use `continue-on-error` para declarar a publicação concluída.

Validar YAML, parâmetros ou formato da chave localmente não comprova acesso ao
servidor. Os três resultados a distinguir são: deploy ignorado, tentativa falha
e commit confirmado no servidor com serviço saudável.

## 9. Operação e backup

Mantenha domínio/HTTPS válidos, segredo forte, origens restritas e um caminho de
SSH autorizado para administração e runner. Preserve volumes de dados, logs e
certificados e faça backup antes de alterações relevantes. Não compartilhe
chaves ou `.env` nos logs de diagnóstico. Consulte também
[DEPLOYMENT_EC2.md](DEPLOYMENT_EC2.md) e a política operacional do projeto.
