# Deploy EC2 opcional com domínio público

EC2 é uma opção de hospedagem do backend com HTTPS. **Push, CI e geração do APK
não dependem de EC2**. A análise no Android continua local; cadastrar código no
GitHub ou obter CI aprovado não comprova que exista um servidor publicado.

Sem a variável de repositório `ENABLE_EC2_DEPLOY=true`, o deploy é explicitamente
ignorado. Não é necessário criar infraestrutura ou preencher secrets apenas
para manter o repositório, testar o projeto ou compilar o app.

## Componentes

| Arquivo | Função |
| --- | --- |
| `docker-compose.prod.yml` | Aplicação e proxy Caddy, com volumes persistentes. |
| `deploy/Caddyfile` | HTTPS e encaminhamento para `app:8000`. |
| `deploy/bootstrap-ubuntu.sh` | Preparação opcional do servidor Ubuntu. |
| `scripts/ec2/deploy.sh` | Validação da configuração e atualização da stack no servidor. |
| `.github/workflows/deploy-ec2.yml` | Deploy habilitado explicitamente, vinculado a CI e commit aprovado. |
| `.env.production.example` | Modelo de configuração local ao servidor, sem credenciais reais. |

## Preparação quando houver um servidor

1. Prepare Linux, Docker Engine e Compose, armazenamento e acesso administrativo.
2. Configure DNS para o endereço público da instância e mantenha Caddy em 80/443.
3. Clone o repositório no diretório de deploy e selecione um commit aprovado no CI.
4. Copie `.env.production.example` para `.env` **no servidor** e ajuste domínio,
   `PUBLIC_BASE_URL`, `SECRET_KEY`, `CORS_ORIGINS` e `ALLOWED_HOSTS`.
5. Configure integrações opcionais conforme necessidade. O clima aberto não exige
   contratar um provedor; observe as condições de uso em [DATA_SOURCES.md](DATA_SOURCES.md).
6. Execute `bash scripts/ec2/deploy.sh` e confira a saúde e o SHA publicado.

Verifique `https://SEU-DOMINIO/health` e `/health/readiness`, incluindo o conteúdo
da resposta. HTTP 200 isolado não comprova prontidão de todas as dependências.
O roteiro detalhado está em [EC2_RUNBOOK.md](EC2_RUNBOOK.md).

## Configuração do GitHub Actions

Somente após a preparação, cadastre os secrets `EC2_HOST`, `EC2_USER`,
`EC2_PROJECT_DIR`, `EC2_SSH_KEY` e **`EC2_KNOWN_HOSTS`**. `EC2_PORT` permite porta
personalizada; se ausente, usa 22. O host não deve conter protocolo ou caminho.
Os secrets podem pertencer ao repositório ou ao environment `production` usado
pelo job.

Verifique a host key pela console/sessão administrativa confiável antes de
preencher `EC2_KNOWN_HOSTS`. A chave de host identifica o servidor; a chave de
deploy autentica o usuário. Não crie confiança com uma varredura não verificada
durante o workflow. Os formatos e a comparação de fingerprint estão em
[GITHUB_ACTIONS_SECRETS.md](GITHUB_ACTIONS_SECRETS.md).

Cadastre então a variável **de repositório** `ENABLE_EC2_DEPLOY=true` em
Settings → Secrets and variables → Actions → Variables. Habilitado o deploy,
secrets ausentes ou inválidos devem causar falha de preflight, com os nomes
necessários e sem expor valores.

## Fluxo automático e manual

1. O push de `main` executa o CI normalmente, com ou sem EC2.
2. O workflow de deploy considera a conclusão bem-sucedida do CI para esse push,
   no próprio repositório, e verifica a habilitação explícita.
3. O preflight valida os parâmetros e a chave/pin usados no SSH.
4. O servidor recebe o **SHA exato aprovado**, busca o commit e o seleciona para
   a atualização. Não avança livremente para um `main` mais recente sem CI.
5. A stack é atualizada e seu estado é verificado. Ignore nenhum erro de SSH,
   build ou verificação de saúde para apresentar a publicação como concluída.

O acionamento manual também é restrito a `main` e precisa comprovar CI aprovado
para o SHA escolhido. Ele não serve para contornar um teste pendente ou falho.
Desativar a variável impede novos deploys; não desliga uma instância existente.

## Rede e identidade do servidor

- O runner precisa alcançar o serviço SSH no host e na **mesma porta** configurada
  em `EC2_PORT`. Uma regra que permite apenas o IP do seu computador não permite
  automaticamente o acesso do runner do GitHub.
- Defina um caminho de rede autorizado para a automação, por exemplo um runner
  com saída conhecida ou conexão privada já configurada. Não amplie o acesso
  indiscriminadamente para contornar um timeout.
- Mantenha a porta 8000 interna ao Compose; exponha 80/443 para o site e restrinja
  SSH às origens administrativas e de automação autorizadas.
- Se a host key mudar, confirme pela console antes de atualizar o pin. Uma
  divergência deve falhar, sem desativar a verificação de identidade.

## Diagnóstico e confirmação

Na falha de `Prepare SSH` investigada em **20/10/2026**, `EC2_HOST` e
`EC2_SSH_KEY` estavam vazios. Isso indicou configuração de deploy ausente;
o CI/backend havia passado. O gate explícito permite deixar EC2 desativada
enquanto o trabalho no código e no Android continua.

Deploy **ignorado**, **tentativa falha** e **servidor atualizado e saudável**
são resultados diferentes. Confira o resumo do workflow, o SHA no servidor,
containers e endpoints. Validação local de YAML ou chave não comprova acesso ao
servidor nem publica o aplicativo.

## Operação e backup

Dados e logs usam `siopa_data`/`siopa_logs`; certificados usam `caddy_data`.
Preserve os volumes e faça backup antes de alterações relevantes. `.env`, chaves,
modelos e dados privados não pertencem ao repositório. Uma conexão SSH funcional
não substitui política de backup, controle de acesso e retenção.
