# Hospedagem EC2 descontinuada

O usuário informou em **20/10/2026** que excluiu a instância EC2 e que ela não
permanecerá ligada. A automação de deploy EC2 foi removida. Este documento
registra a descontinuação, sem indicar que exista um servidor público ativo.

Push, CI, geração do APK e análise offline continuam independentes de EC2.
Não é necessário cadastrar secrets EC2 ou habilitar uma flag de deploy para
continuar o desenvolvimento e usar o aplicativo.

`scripts/ec2/deploy.sh` e `deploy/bootstrap-ubuntu.sh` permanecem como referências
manuais genéricas. Não são executados automaticamente e sua presença não cria
nem mantém infraestrutura.

As instruções anteriores estão preservadas no histórico Git deste arquivo.
Para execução local ou uma futura publicação do backend, consulte
[DEPLOYMENT.md](DEPLOYMENT.md); para Android, [MOBILE_OFFLINE.md](MOBILE_OFFLINE.md).
