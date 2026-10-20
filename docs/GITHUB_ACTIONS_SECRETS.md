# GitHub Actions: deploy EC2 descontinuado

Em **20/10/2026**, o usuário informou que excluiu a instância EC2. A automação
EC2 foi removida do projeto; não há workflow de deploy EC2 a habilitar.

Push, CI e geração do APK não exigem servidor, conta AWS, `ENABLE_EC2_DEPLOY`
ou secrets `EC2_*`. A configuração anterior desses valores não reativa uma
publicação. Esta mudança não altera contas ou secrets existentes.

O histórico Git preserva a configuração anterior e o diagnóstico de SSH. Ela
não representa um serviço atualmente hospedado nem uma etapa a seguir para
usar o aplicativo offline.

Para execução local ou uma futura publicação do backend, consulte
[DEPLOYMENT.md](DEPLOYMENT.md). Para o APK e uso sem rede, consulte
[MOBILE_OFFLINE.md](MOBILE_OFFLINE.md).
