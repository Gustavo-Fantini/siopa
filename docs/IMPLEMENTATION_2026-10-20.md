# Entrega técnica de 20/10/2026

Reestruturação do SIOPA para Android primeiro, medição local e funcionamento sem
internet. Arquivos privados existentes (`.env`, banco, imagens, modelos e logs)
foram preservados. Nenhum deploy ou publicação em loja foi feito.

## Implementado

- Motor Python e JavaScript determinístico: EXIF, orientação do papel/perspectiva,
  escala confirmada, contagem isolada, descarte separado de coalescência/borda/ruído,
  cobertura por pixels, CV espacial, métricas de manchas e piso efetivo de resolução.
- Fuzzy Sugeno com percentual, parâmetros, pertinências e regras visíveis. Estado
  experimental explícito; sem calibração física não retorna índice conclusivo.
- UI mobile com câmera/galeria, marcação manual de cantos, dimensões/perfil editáveis,
  overlay, IndexedDB, histórico e exportação da amostra. Foto não usa a rede.
- APK com UI/motor/catálogo embarcados, câmera, GPS opcional e exportação nativa;
  a PWA usa o mesmo conjunto de arquivos e cache integral.
- Catálogo local de 127 culturas com aliases, estágios genéricos e planos editoriais
  de coleta; sem simular limiares agronômicos por espécie ou receituários.
- Contexto Open-Meteo/SoilGrids/Copernicus com fonte, resolução, validade, incerteza
  e cache persistente; dados ausentes permanecem indisponíveis, sem mocks favoráveis.
- Recomendação de deposição substitui a predição sintética de produto/dose/infestação.
- Dataset interno protegido por chave, validação antes da substituição, revisão,
  escala persistida, normalização EXIF e correções de UI/CLI. Treino agrupa recortes
  por hash da imagem e não ativa modelo por uma accuracy artificialmente alta.
- Dependências HTTP atualizadas e verificadas; CI executa suíte completa. Compose/
  Docker corrigidos quanto à porta do healthcheck. Índice e contexto atualizados.

## Verificações realizadas

- **77 testes Python passaram**, incluindo comparação real Python/JS, fuzzy,
  catálogo/cache concorrente, API offline, privacidade das ferramentas, revisão,
  escala, EXIF e separação das imagens de treino. Testes isolam dados e credenciais.
- Compilação estática Python e `pip check` sem dependências incompatíveis.
- Teste real no Chromium/Edge: Worker sem rede, valores nulos sem escala, geometria
  confirmada, 24 manchas na fixture, índice provisório, duas amostras no IndexedDB,
  reload/reabertura offline e fallback local. Nenhum upload de foto no fluxo testado.
- Android `assembleDebug` e `lintDebug` concluídos; lint final sem ocorrências.
  APK verificado com `apksigner`; assinatura Android Debug.
- Conteúdo do APK comparado byte a byte com os assets atuais, incluindo 127 culturas.
- Consultas públicas reais em coordenada de teste de Bauru responderam para as três
  fontes; referência e limitações estão em [DATA_SOURCES.md](DATA_SOURCES.md).

Uma advertência de depreciação da integração TestClient/httpx foi emitida pela
dependência durante a suíte. O build SDK também informa diferença de versão do
formato de metadados. Nenhuma impediu as verificações acima.

## Artefatos locais

```text
artifacts/siopa-3.0.0-debug.apk
artifacts/apk-verification.json
artifacts/mobile-browser-test-result.json
artifacts/mobile-home.png
artifacts/mobile-result.png
```

O APK final tem 2.409.672 bytes. SHA-256:

```text
c54e842ccaaaba68ef3a02b586fcc2910591c5e74974b20f1a6ee216fb54cbbc
```

Os artefatos e runtimes em `.tools` ficam fora do Git; fonte, Gradle Wrapper,
scripts e documentação permitem repetir o build. APK debug é entrega de
desenvolvimento, sem assinatura de produção ou publicação em loja.

## O que continua dependendo de ensaio

Não houve instalação em aparelho Android físico. Câmera, GPS, versões de WebView,
desempenho e retenção precisam ser testados nos aparelhos escolhidos. Também não há
acurácia científica comprovada nas fotos reais: a execução dos seis conteúdos locais
não foi comparação com contagem humana.

O fuzzy é adequação experimental ao perfil, sem afirmar eficácia agronômica.
Catálogo/planos não equivalem a parâmetros validados para 127 culturas. Dados de solo
e elevação são modelos regionais; mesmo uma API paga não os transforma em medição
exata ao vivo. Marca/modelo do papel e protocolos ainda devem ser identificados.

Próxima evidência necessária: papel confirmado, fotos reais de diferentes aparelhos
e contagem humana independente, seguindo [VALIDATION_PROTOCOL.md](VALIDATION_PROTOCOL.md).
Ferramenta de comparação: `scripts/evaluate_counts.py`.
