# Checklist final de apresentação e banca

## Infraestrutura
- Confirmar que o servidor sobe com `python start.py --host 0.0.0.0 --port 8000`.
- Validar `GET /health` e `GET /health/readiness`.
- Testar acesso pelo celular na mesma rede.
- Confirmar que `app.db` e modelos estão disponíveis no ambiente.
- Verificar se as chaves de API necessárias continuam válidas.

## Demonstração ao vivo
- Abrir a tela principal no celular.
- Enviar uma imagem real de papel hidrossensível.
- Mostrar análise, métricas e recomendação gerada.
- Abrir a interface de anotação e exibir o fluxo de dataset.
- Mostrar que o sistema roda centralizado no servidor.

## Narrativa acadêmica
- Apresentar o problema agrícola e a motivação.
- Explicar metodologia de visão computacional e recomendações.
- Mostrar arquitetura backend, mobile web e banco.
- Destacar ganhos de deploy, reprodutibilidade e escalabilidade.
- Explicitar limitações atuais e próximos passos de pesquisa.

## Evidências para levar
- Link do repositório GitHub publicado.
- `.env.production.local` configurado no servidor.
- `.env.backup.*.local` guardado como contingência privada.
- Backup do `app.db`.
- Imagens de teste para a demonstração.
- Slides com objetivos, método, resultados e conclusão.

## Pós-apresentação
- Registrar feedback da banca.
- Converter críticas em backlog técnico/científico.
- Planejar próximos experimentos e validações comparativas.
