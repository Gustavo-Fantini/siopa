# SIOPA

Sistema Inteligente de Otimização da Pulverização Agrícola. Projeto de TCC da
ETEC Rodrigues de Abreu, com análise de papel hidrossensível e evolução para
Android e uso offline.

Autores acadêmicos: Caua Fernandes Jorge, Guilherme Cardoso Galelli, Gustavo Teodoro
Fantini e Jeferson Aguilar Junior. Contato operacional: Gustavo Teodoro Fantini.
Registros de autoria e direitos: [AUTHORS.md](AUTHORS.md), [LICENSE.md](LICENSE.md)
e [NOTICE.md](NOTICE.md).

## Aplicativo e análise local

- APK Android com câmera, galeria, GPS opcional e motor embarcado; funciona sem
  internet desde a instalação. Android 8/API 26 ou posterior e WebView atualizado.
- PWA com a mesma interface/motor; conclua o primeiro carregamento com conexão
  e aguarde a indicação de arquivos prontos para uso offline.
- Detecção/seleção do papel, correção de perspectiva e confirmação de dimensões,
  incluindo 76 × 26 e 76 × 25 mm. Nenhuma marca ou escala é confirmada automaticamente.
- Contagem de manchas isoladas resolvíveis; exclusão de coalescência, borda, ruído
  e manchas abaixo do piso configurado/efetivo. Overlay permite conferir classificações.
- Cobertura por pixels reais, densidade calibrada e uniformidade espacial por grade.
  O diâmetro informado é da mancha; não é automaticamente o da gota original.
- Índice fuzzy transparente de 0 a 100, com perfil ajustável e status experimental.
  Sem escala válida, medidas físicas e índice ficam nulos.
- Histórico local com foto, parâmetros, resultado, máscara, contexto e exportação.
  A jornada principal não transmite fotos ao servidor.
- Catálogo embarcado de 127 culturas, aliases, estágios genéricos e planos editoriais
  de coleta. Não contém receituários ou limiares validados para cada espécie.

O APK de desenvolvimento é gerado em `artifacts/siopa-3.0.0-debug.apk` nesta entrega;
o build reproduzível está em `mobile/android`. Instruções e verificação offline:
[docs/MOBILE_OFFLINE.md](docs/MOBILE_OFFLINE.md).

## Contexto com rede

Com posição autorizada e conexão, a aplicação baixa clima/previsão Open-Meteo,
propriedades regionais SoilGrids e elevação Copernicus GLO-90. Mostra fonte,
resolução, períodos, validade e indisponibilidade. Sem rede, usa a cópia salva
identificada como tal. Esses modelos não garantem dados exatos do talhão ao vivo.

O APK usa um servidor HTTPS configurável para atualização. Não inclui domínio público
fixo nem credenciais. Open-Meteo funciona sem chave para o protótipo não comercial;
endpoint e chave pagos podem ser configurados no servidor, conforme termos do provedor.
Fontes, licenças e limites: [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

## Backend e desenvolvimento

Python 3.11, FastAPI, SQLAlchemy, OpenCV/Pillow e clientes HTTP. O backend oferece
contexto e catálogo e mantém uma API opcional de análise com o motor Python.
Testes comparam as implementações Python e JavaScript nos cenários de referência.

```text
pip install -r requirements.txt
python start.py --host 0.0.0.0 --port 8000
```

Se `.env` ainda não existir, crie-o a partir de `.env.example`; preserve configurações
privadas existentes. Acesse `http://localhost:8000`. GPS e service worker no celular
exigem contexto seguro (HTTPS); HTTP de IP local não oferece todas as APIs do navegador.

```text
python -m pytest -q
python -m compileall main.py app tests scripts
python scripts/sync_crop_catalog.py
node mobile/tests/offline-browser.test.cjs
```

Teste do navegador requer Chromium/Edge; detalhes no guia mobile. No Windows desta
entrega foi provisionado um Python isolado em `.tools/python/python.exe`, sem
instalação global. `.tools` e artefatos de build ficam fora do Git.

O dataset/anotador/treinamento é interno: habilite `ENABLE_DATASET_API=True`, defina
`ADMIN_API_KEY` e use `X-API-Key`. O anotador recebe a chave em memória; CLIs aceitam
`SIOPA_ADMIN_API_KEY` ou `--api-key`. Somente imagens revisadas treinam. O classificador
de pesquisa não altera automaticamente o algoritmo embarcado.

Docker/EC2/Render continuam disponíveis. Ajuste HTTPS, hosts, CORS e persistência.
Para o APK, permita CORS da origem `https://appassets.androidplatform.net`.

## Método, evidências e continuidade

A contagem ainda precisa ser validada com fotos reais, papel identificado e
referência humana. O fuzzy mede aderência ao perfil informado; não significa taxa
de acerto nem eficácia biológica. Produto e dose dependem de cultura/alvo/bula e
não são deduzidos da cobertura de um cartão.

- [Método de imagem e fuzzy](docs/IMAGE_METHOD.md)
- [Protocolo de validação por humanos](docs/VALIDATION_PROTOCOL.md)
- [Entrega e verificações](docs/IMPLEMENTATION_2026-10-20.md)
- [API](docs/API_DOCUMENTATION.md)
- [Contexto técnico para próximas sessões](docs/PROJECT_CONTEXT.md)
- [Índice de funções e rotas](docs/FUNCTION_INDEX.md)
- [Deploy](docs/DEPLOYMENT.md), [EC2](docs/DEPLOYMENT_EC2.md) e [operação](docs/EC2_RUNBOOK.md)
