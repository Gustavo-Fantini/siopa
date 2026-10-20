# Configuração do deploy EC2 no GitHub Actions

EC2 é opcional. Push, CI e geração do APK funcionam sem servidor, conta AWS ou
secrets de EC2. Um deploy ignorado não significa que o aplicativo foi hospedado.

## Habilitação explícita

Em **Settings → Secrets and variables → Actions → Variables**, cadastre a
variável **de repositório** `ENABLE_EC2_DEPLOY=true` somente quando o servidor e
os secrets estiverem preparados. Ausente ou desativada, a publicação é ignorada
com indicação explícita de que nenhuma implantação foi feita.

Não coloque esse controle apenas nas variáveis do environment `production`:
a decisão de iniciar o job ocorre antes de suas variáveis estarem disponíveis.
Não use a existência de um secret isolado como habilitação implícita.
[Referência de variáveis do GitHub](https://docs.github.com/en/actions/reference/workflows-and-actions/variables).

Com a variável habilitada, configuração ausente ou inválida deve **falhar** no
preflight. Não remova o erro com `continue-on-error` nem transforme falha de SSH
em publicação bem-sucedida.

## Secrets usados quando o deploy está habilitado

Cadastre em **Actions → Secrets**, no repositório ou no environment `production`
usado pelo job. Se houver aprovação/proteção do environment, ela também precisa
ser atendida. Os valores abaixo são exemplos, não credenciais válidas.

| Nome | Conteúdo |
| --- | --- |
| `EC2_HOST` | IP público ou DNS do servidor, sem `https://`, caminho ou porta embutida. |
| `EC2_PORT` | Porta SSH; se omitida, o padrão é `22`. Deve ser um inteiro entre 1 e 65535. |
| `EC2_USER` | Usuário Linux autorizado para a chave de deploy. |
| `EC2_PROJECT_DIR` | Diretório absoluto do projeto, sem espaços nem segmentos `..`, por exemplo `/srv/siopa`. |
| `EC2_SSH_KEY` | Conteúdo completo da chave privada dedicada, com suas quebras de linha. Sua pública deve estar no `authorized_keys` do usuário acima. |
| `EC2_KNOWN_HOSTS` | Entrada(s) de host key do servidor, verificadas por um canal confiável, para o mesmo host e porta. |

Use chave exclusiva para automação, sem reutilizar a chave pessoal de
administração. O cliente precisa autenticar sem interação; uma chave que exige
passphrase não funciona apenas por ter sido copiada para um arquivo, sem suporte
a agent/passphrase no workflow. Nunca publique chaves privadas no repositório,
na conversa ou nos logs. Ao girar a chave de acesso, atualize a pública autorizada
no servidor e o secret correspondente.

## Obter e verificar `EC2_KNOWN_HOSTS`

A chave pública do **servidor** é diferente da chave pública do **usuário de
deploy**. `EC2_KNOWN_HOSTS` fixa a identidade do servidor; `EC2_SSH_KEY` autentica
o usuário nele.

Pela console ou por uma sessão administrativa já confiável do servidor, obtenha
a chave pública de host e sua fingerprint. Para um servidor com host key Ed25519:

```bash
sudo cat /etc/ssh/ssh_host_ed25519_key.pub
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256
```

Monte a entrada `known_hosts` com o host usado em `EC2_HOST`: na porta 22,
`host tipo-da-chave chave-publica`; em porta personalizada,
`[host]:porta tipo-da-chave chave-publica`. Use somente valores obtidos e
confirmados por esse canal confiável.

Outra opção é coletar **localmente** uma candidata e comparar sua fingerprint
com a exibida pela console. Substitua host e porta pelos valores reais:

```bash
ssh-keyscan -T 10 -p 22 -t ed25519 app.seu-dominio.com > known_hosts.candidate
ssh-keygen -lf known_hosts.candidate -E sha256
```

Só copie o conteúdo de `known_hosts.candidate` para `EC2_KNOWN_HOSTS` depois de
confirmar a igualdade da fingerprint. A varredura usa a mesma porta do SSH.
`ssh-keyscan` sozinho não verifica a autenticidade da chave e não deve criar
confiança automaticamente dentro do job.
[Manual oficial OpenSSH](https://man.openbsd.org/ssh-keyscan.1).

Mudança de host key deve interromper a conexão. Confirme uma troca/recriação
legítima do servidor pela console antes de atualizar o pin; não desative
`StrictHostKeyChecking` para contornar o aviso.

## CI, commit e execução manual

O deploy automático considera o resultado bem-sucedido do workflow `CI` para
um push de `main` no próprio repositório e publica o **SHA exato aprovado**.
Um novo avanço de `main` não autoriza publicar um commit ainda não testado.
A execução manual também fica restrita a `main` e deve comprovar CI aprovado
para o SHA escolhido; ela não contorna o controle.
[Eventos de workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows).

## Diagnóstico

| Situação | Interpretação e ação |
| --- | --- |
| Deploy ignorado e `ENABLE_EC2_DEPLOY` ausente/desativada | Comportamento esperado quando EC2 não é usada; CI/APK continuam independentes. Nenhum site foi publicado por essa execução. |
| Preflight acusa configuração ausente | Cadastre os nomes indicados no escopo correto, ou mantenha o deploy desativado. Não imprima seus valores. |
| `Prepare SSH` falha com host/chave vazios | Causa confirmada na execução investigada em 20/10/2026: `EC2_HOST` e `EC2_SSH_KEY` estavam vazios. Segredo não cadastrado é entregue como string vazia. |
| Timeout ou conexão recusada | Confira DNS/IP, porta, serviço SSH e regras de rede para o runner. Liberar somente o IP do seu computador não libera o runner do GitHub. |
| Host key não corresponde | Confira host/porta e a identidade pela console; atualize o pin somente após validação. |
| Chave inválida ou `Permission denied (publickey)` | Confira formato/quebras de linha, requisito de passphrase, usuário e chave pública autorizada. |
| CI ainda não aprovado para o SHA | Aguarde ou corrija o CI desse commit; não publique outro SHA para obter um status verde. |

O status de preparação local valida configuração e formato. Somente uma conexão
real e as verificações de saúde posteriores comprovam um deploy no servidor.
