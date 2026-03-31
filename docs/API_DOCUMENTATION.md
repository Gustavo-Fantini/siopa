# API do SIOPA

## Base
`/api/v1`

## Endpoints principais

### `GET /health`
Status rápido da aplicação.

### `GET /health/readiness`
Resumo de prontidão de deploy, storage, segurança e integrações.

### `GET /client/config`
Configuração pública consumida pela interface web/mobile.

### `GET /system/runtime`
Relatório operacional sem expor segredos.

### `POST /analyze-image`
Analisa uma imagem de papel hidrossensível.

Campos `multipart/form-data`:
- `file`
- `latitude`
- `longitude`
- `crop_type`
- `growth_stage` opcional
- `target_problem` opcional

### `POST /test-analysis`
Executa apenas a análise de imagem, sem fluxo completo.

### `GET /weather/{latitude}/{longitude}`
Clima atual.

### `GET /weather/forecast/{latitude}/{longitude}?days=3`
Previsão de curto prazo.

### `GET /agriculture/{crop_type}`
Informações agronômicas por cultura.

Parâmetros opcionais:
- `growth_stage`
- `latitude`
- `longitude`

### `GET /crop/{crop_type}`
Alias compatível com documentação externa.

### `GET /soil/{latitude}/{longitude}`
Informações de solo.

### `GET /recommendations/preview`
Simula recomendações com métricas informadas por query string.

### `GET /system/stats`
Estatísticas operacionais do sistema.

### `GET /statistics`
Alias compatível.

## Dataset e treinamento

### `POST /dataset/upload`
Envia imagem para o dataset.

### `GET /dataset/images`
Lista imagens com metadados completos para interface de anotação.

### `GET /dataset/image/{image_id}`
Retorna a imagem.

### `GET /dataset/image/{image_id}/annotations`
Lista anotações.

### `POST /dataset/image/{image_id}/annotations`
Salva ou substitui anotações.

### `GET /dataset/stats`
Resumo do dataset.

### `GET /dataset/export?format=coco`
Exportação do dataset.

### `POST /ml/train`
Inicia treinamento de modelo.

### `GET /ml/training/{session_id}/status`
Consulta progresso do treinamento.

## Resposta de erro
```json
{
  "error": true,
  "error_code": "VALIDATION_ERROR",
  "message": "Descrição do erro",
  "details": {},
  "timestamp": "2026-03-31T12:00:00",
  "path": "/api/v1/analyze-image"
}
```
