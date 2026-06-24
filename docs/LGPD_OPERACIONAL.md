# LGPD operacional

## Escopo deste documento
Este arquivo organiza exigencias tecnicas e operacionais para publicar o SIOPA com menos risco.
Ele nao substitui avaliacao juridica formal.

## Controlador
- nome: Gustavo Teodoro Fantini
- contato: gustavo.teodoro.fantini@gmail.com

## Pontos do sistema que podem tratar dados pessoais
- coordenadas geograficas enviadas pelo usuario
- imagens carregadas na analise, caso contenham informacoes identificaveis por uso indevido
- imagens e metadados do dataset
- logs tecnicos com IP, horario, status e erros

## Medidas minimas antes de abrir o sistema ao publico
1. publicar uma politica de privacidade acessivel no dominio final
2. definir base legal para cada fluxo de tratamento
3. registrar prazo de retencao para imagens, logs e anotacoes
4. limitar coleta ao minimo necessario para a funcionalidade
5. revisar quem pode acessar dataset, banco e logs
6. definir rotina de resposta a incidente e canal para titulares
7. evitar uso de imagens com pessoas, placas ou dados identificaveis

## Regras operacionais recomendadas
- nao reutilizar uploads de usuarios em treinamento sem base legal especifica
- separar ambiente de producao do ambiente de anotacao interna
- anonimizar ou excluir imagens quando nao forem mais necessarias
- manter credenciais apenas em `.env` no servidor
- registrar backups e restauracoes executadas no ambiente

## Checklist de publicacao
- `SECRET_KEY` trocada
- `CORS_ORIGINS` restrito ao dominio final
- `ALLOWED_HOSTS` restrito ao dominio final
- HTTPS ativo
- politica de privacidade publicada
- responsavel pelo atendimento de titulares definido
- rotina de exclusao e retencao documentada

## Pendencias que exigem decisao do proprietario
- prazo maximo de retencao para uploads de analise
- prazo maximo de retencao para dataset anotado
- definicao de compartilhamento com terceiros e provedores externos
- texto publico da politica de privacidade e dos termos de uso
