# Contexto de trabalho do SIOPA

Este repositório contém o SIOPA, TCC de ensino médio técnico apresentado na
ETEC Rodrigues de Abreu. O usuário pretende desenvolver o projeto continuamente
por pelo menos o próximo ano, conforme conversa de 20/10/2026.

Direção confirmada: **Android primeiro**, análise da foto inteiramente offline,
catálogo no aparelho e sincronização opcional de contexto por GPS/rede. Papel
hidrossensível amarelo que marca azul; dimensões editáveis, incluindo 76 × 26 e
76 × 25 mm. Marca/modelo não definidos; não presumir fator de espalhamento.

Hospedagem: o usuário informou em 20/10/2026 que excluiu a instância EC2 e não
vai mantê-la ligada. A automação EC2 foi removida. Não reintroduza esse deploy
nem presuma servidor ativo; o desenvolvimento Android/offline segue independente.

## Retomada de contexto

- Leia [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md) para conhecer arquitetura,
  jornadas, persistência, integrações, estado observado e limitações conhecidas.
- Consulte [docs/FUNCTION_INDEX.md](docs/FUNCTION_INDEX.md) para localizar classes,
  funções e rotas. O índice é textual e representa a data registrada no documento.
- Confira o código e `git status` antes de trabalhar: esses documentos são um mapa,
  e a implementação atual é a fonte de verdade.
- Atualize o contexto quando uma mudança importante tornar suas informações
  desatualizadas. Registre decisões técnicas e evidências para permitir continuidade
  entre sessões; não dependa apenas do histórico da conversa.

## Cuidados específicos do projeto

- Preserve alterações locais preexistentes. A leitura inicial encontrou trabalho
  em andamento em visão, treinamento, anotação e AGROFIT.
- Preserve a autoria acadêmica registrada em `AUTHORS.md`, `LICENSE.md` e `NOTICE.md`.
- Trate `.env`, bancos, datasets, modelos e logs como artefatos privados. Não copie
  credenciais ou dados pessoais para documentação, respostas ou commits.
- Considere os efeitos de executar/importar o código: `Settings()` cria diretórios;
  o startup cria/migra o banco;
  setup/demo/upload/treinamento podem alterar dados ou chamar serviços externos.
- Diferencie observações, dados externos, perfis estimados e exemplos sintéticos.
  Diferencie também classificação de recortes, segmentação OpenCV e modelos de
  recomendação: são fluxos distintos. O recomendador atual não treina modelos
  sintéticos nem infere produto/dose. O classificador de pesquisa não altera
  automaticamente o motor offline determinístico.
- Ao alterar métricas físicas, explicite unidades e método; ao alterar features,
  confira compatibilidade entre anotações, treinamento, artefatos e inferência.

## Execução e verificações de referência

O projeto documenta Python 3.10/3.11; Docker e CI usam Python 3.11.

```text
pip install -r requirements.txt
python start.py --host 0.0.0.0 --port 8000
python -m pytest -q
python -m compileall main.py app tests
python scripts/sync_crop_catalog.py
node mobile/tests/offline-browser.test.cjs
```

Use configuração e dados de teste isolados quando a verificação puder modificar
os artefatos existentes. A disponibilidade de Python deve ser conferida a cada
ambiente. A leitura inicial não executou testes; a reestruturação posterior tem
verificações registradas em `docs/IMPLEMENTATION_2026-10-20.md`.
