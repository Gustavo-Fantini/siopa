# API do SIOPA 3

Base: `/api/v1`. A jornada principal do celular executa o motor local; fotos não
são necessárias ao bootstrap. A API de análise continua disponível como alternativa.
Inventário completo de métodos/caminhos e localização no fonte:
[FUNCTION_INDEX.md](FUNCTION_INDEX.md#rotas-http).

## Bootstrap e contexto

`GET /api/v1/offline/bootstrap?latitude=-22.31&longitude=-49.06`

Latitude e longitude são opcionais, mas devem ser fornecidas juntas. Sem elas a
resposta inclui catálogo e capacidades, sem consultar serviços externos.

```text
schema_version: 1
generated_at, catalog_version, engine_version
crops[], sources[], stage_profiles{}, quality_profiles{}
paper_defaults: {paperWidthMm, paperHeightMm, paperSizeConfirmed:false, minStainDiameterMm}
environment: {weather, soil, terrain, provenance, coordinates,
              availability, fetched_at, expires_at, stale}
capabilities: {offline_analysis, offline_history, local_crop_catalog,
               dataset_api, pesticide_dosage_inference:false,
               server_receives_photos_for_sync:false}
```

`weather` contém `current`, `forecast`, `hourly` e metadata de origem/validade.
Solo contém propriedades/camadas/unidades e intervalos disponíveis. Terreno contém
`elevation_m`, resolução e `slope_degrees:null`. Campos indisponíveis permanecem
nulos. Data de consulta não equivale à data de medição/modelo.

Outras consultas públicas:

- `GET /api/v1/client/config`
- `GET /api/v1/crops`
- `GET /api/v1/environment/{latitude}/{longitude}`
- `GET /api/v1/weather/{latitude}/{longitude}`
- `GET /api/v1/weather/forecast/{latitude}/{longitude}?days=3` (1–7 dias)
- `GET /api/v1/agriculture/{crop_type}` e alias `/crop/{crop_type}`
- `GET /api/v1/soil/{latitude}/{longitude}`
- `GET /api/v1/agrofit/products` (busca de catálogo; não valida indicação/dose)

## Análise opcional no servidor

`POST /api/v1/analyze-image`, multipart/form-data:

| Campo | Regra |
| --- | --- |
| `file` | Imagem JPEG/PNG/WebP/BMP/TIFF válida; limites de bytes/pixels configurados. |
| `crop_type` | Chave ou alias do catálogo; padrão soja. |
| `growth_stage`, `target_problem` | Contexto opcional; alvo informado não é diagnóstico. |
| `latitude`, `longitude` | Opcionais em conjunto; ausência permite análise sem serviços externos. |
| `paper_width_mm`, `paper_height_mm` | Dimensões positivas; valores iniciais 76 e 26. |
| `paper_size_confirmed` | Padrão false. Sem confirmação não inventa escala física. |
| `min_stain_diameter_mm` | Piso configurável de mancha; padrão 0,10 mm. Resolução impõe piso efetivo. |
| `quality_profile` | JSON opcional com coverageMin/Target/Max, densityMin/Target/Max, uniformityCvMax e confirmed. |

Retorna `analysis`, `environment`, `weather`, `agriculture`, `recommendations` e
`metadata`. A foto temporária é excluída; esse endpoint não cria histórico/dataset
no servidor. CPU de imagem roda fora da thread do event loop.

`analysis` contém `valid_droplets`, coalescências/bordas/rejeições, cobertura,
densidade, `spatial_uniformity`, `calibration`, `quality`, diâmetros de manchas,
piso efetivo e overlay. Grandezas físicas podem ser `null`. `dv50_diameter` é
`null`; `dv50_proxy_um` é identificado como proxy de manchas, sem espalhamento.

`quality.score` é índice fuzzy, com regras/evidências. Status: `insufficient`,
`provisional` ou `indicative`; não expressa precisão ou eficácia.
`recommendations` é orientação de deposição/cultura, sem inferir infestação,
produto ou dose da foto. Esses campos permanecem nulos quando não comprovados.

`POST /api/v1/test-analysis` mantém compatibilidade para leitura sem confirmação
de escala. `GET /api/v1/recommendations/preview` é uma **simulação explícita** dos
parâmetros recebidos; não cria clima favorável nem valida o ensaio.

## Dataset, revisão e treinamento internos

Por padrão desativados. Habilitar `ENABLE_DATASET_API=True` e configurar uma
`ADMIN_API_KEY` não vazia. Cada requisição envia `X-API-Key`. Falta de habilitação
retorna 403; chave incorreta/ausente retorna 401. A chave não deve ir na URL.

- Upload/listagem/imagem: `/dataset/upload`, `/dataset/images`, `/dataset/image/{id}`.
- Anotações: GET/POST `/dataset/image/{id}/annotations`. POST substitui o conjunto,
  com validação prévia; `pixel_to_mm_ratio` opcional positivo vai na query.
- Revisão: PUT `/dataset/annotation/{id}/review`, formulário status=approved/rejected,
  reviewed_by e notes opcional. Todas aprovadas marcam a imagem validada.
- Modelos: GET/POST `/models`; treino JSON POST `/ml/train` ou formulário
  POST `/training/start`; GET `/training/sessions` e `/ml/training/{id}/status`.
- GET `/dataset/stats` e `/dataset/export?format=coco`.
- POST `/agrofit/sync` usa o mesmo controle de acesso.

Upload do dataset grava pixels RGB/PNG com EXIF aplicado e metadados removidos.
Anotações salvas ficam pendentes; treino e exportação usam dados revisados.
COCO usa caixas circulares; o formato `csv` legado retorna JSON tabular e YOLO
não está implementado. Treinamento é pesquisa separada do algoritmo mobile.

## Saúde, diagnóstico e erros

`GET /health`, `/health/readiness`, `/api/v1/health`, `/api/v1/system/runtime`,
`/api/v1/system/stats` e alias `/api/v1/statistics`. Estatísticas são somente do
processo atual; não incluem leituras privadas dos aparelhos ou acurácia inventada.

Erros usam status HTTP e envelope dos handlers com mensagem, código e path.
Entradas inválidas podem retornar 400/422; indisponibilidade de uma fonte ambiental
normalmente retorna contexto parcial/nulo com proveniência, preservando a análise.

Para o APK chamar servidor com CORS restrito, incluir a origem
`https://appassets.androidplatform.net`. Não embarcar segredos de provedores.
