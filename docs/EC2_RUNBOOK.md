# Runbook EC2 encerrado

Em **20/10/2026**, o usuário informou a exclusão da instância EC2. O fluxo de
deploy EC2 foi descontinuado, e este runbook não é mais um procedimento ativo.
A configuração anterior pode ser consultada no histórico Git deste arquivo.

Não há etapa de EC2, cadastro de secrets ou conexão SSH para fazer push,
executar o CI, gerar o APK ou analisar imagens offline.

Os scripts `scripts/ec2/deploy.sh` e `deploy/bootstrap-ubuntu.sh` são mantidos
somente como referências manuais genéricas, sem execução automática. Nenhuma
infraestrutura, conta, credencial ou configuração privada é alterada por esta
atualização de documentação.

Execução local e publicação futura: [DEPLOYMENT.md](DEPLOYMENT.md).
Aplicativo e uso sem rede: [MOBILE_OFFLINE.md](MOBILE_OFFLINE.md).
