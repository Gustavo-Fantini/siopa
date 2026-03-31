# Prontidão para iniciação científica

## Objetivo
Deixar o SIOPA apresentável como projeto acadêmico, reproduzível tecnicamente e sustentável para evolução experimental.

## Pilares já alinhados
- Execução centralizada no servidor, com acesso mobile via navegador.
- Ambiente parametrizado por `.env`.
- Deploy reproduzível com `Dockerfile` e `docker-compose.yml`.
- Saúde operacional com `GET /health`, `GET /health/readiness` e `GET /api/v1/system/runtime`.
- Publicação limpa no GitHub, sem expor `.env` nem `app.db`.

## Próximos cuidados para banca e pesquisa
- Documentar hipóteses experimentais e métricas-alvo.
- Versionar datasets derivados sem expor dados sensíveis ou excessivos.
- Registrar datas, parâmetros e origem de cada treinamento.
- Padronizar critérios de anotação para reduzir viés entre avaliadores.
- Separar ambiente de produção, validação e experimentação.

## Checklist técnico
- `SECRET_KEY` exclusivo por ambiente.
- `DATABASE_URL` explícita para cada cenário.
- `CORS_ORIGINS` e `ALLOWED_HOSTS` restritos.
- Rotina de backup para `app.db` e modelos treinados.
- Estratégia de retenção para `logs/`.
- Evidência de testes automatizados no GitHub Actions.

## Checklist científico
- Definir protocolo de coleta das imagens.
- Definir método de validação cruzada.
- Registrar limitações do modelo atual.
- Explicar baseline, variações testadas e critérios de comparação.
- Salvar versão do conjunto de treino usado em cada experimento.
