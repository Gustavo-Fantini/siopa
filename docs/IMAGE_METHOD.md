# Método de imagem e índice experimental de deposição

Implementação em 20/10/2026; motor `3.0.0-offline`. Python e JavaScript usam o
mesmo método determinístico. O JavaScript não usa rede, CDN, serviço remoto,
OpenCV.js ou modelo. Opera sobre pixels já decodificados e orientados.

O usuário definiu Android primeiro e papel amarelo que marca azul, com dimensões
editáveis. Referências de fabricante consultadas em 20/10/2026 incluem
[SpotOn 25 × 76 mm](https://innoquestinc.com/product/paper/) e
[TeeJet 76 × 26 mm](https://www.teejet.com/es-mx/-/media/dam/agricultural/usa/sales-material/catalog/technical_information-m.pdf).
São exemplos, sem marca selecionada para o ensaio. Confirmar o cartão real antes
de calcular escala; não intercambiar fatores de espalhamento entre materiais.

## Grandezas e evidência primária

Cobertura é a fração de pixels classificados como mancha na área útil do coletor.
A definição por pixels está documentada pela [Embrapa Uva e Vinho, Circular Técnica
167, 2024](https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/1169076/1/CircTec-167.pdf).
A implementação não amplia raios, soma áreas circulares ou usa fator artificial
para aumentar a cobertura.

O diâmetro medido é o circular equivalente da **mancha** (`2 sqrt(A/pi)`), não o
diâmetro da gota antes de atingir o papel. A [USDA ARS, Hoffmann et al.,
2018](https://www.ars.usda.gov/research/publications/publication/?seqNo115=337949)
mostra que relações de espalhamento dependem da calda. A [Embrapa Meio Ambiente,
Circular Técnica 1, 1999](https://www.infoteca.cnptia.embrapa.br/handle/doc/13123)
também descreve a correção por espalhamento para estimar deposição a partir de
manchas. Por isso não são atribuídos diâmetros reais ou classes de gotas.

Sobreposição impede recuperar individualmente todas as gotas depositadas. O
[estudo original DepositScan, Zhu et al.,
2011](https://www.ars.usda.gov/ARSUserFiles/50820500/Publications/Zhu_2010_DepositScan.pdf)
discute a limitação em cobertura elevada. Aqui componentes com evidências de
coalescência são excluídos da contagem individual, embora seus pixels contribuam
para cobertura. Isso evita inventar impactos em componentes mesclados; não resolve
sobreposições que resultaram em manchas visualmente circulares.

Estas fontes sustentam definições e limitações. **Não validam este software,
seus limiares de segmentação, nem o escore fuzzy.**

## Aquisição e calibração

- Python usa Pillow `ImageOps.exif_transpose` antes de converter os pixels.
  `ImageData` no navegador deve ser produzido por um decoder que aplique EXIF;
  orientação não pode ser recuperada de um vetor RGBA sem os metadados do arquivo.
- Detecta uma região quente amarela/laranja, fecha pequenos buracos e aproxima o
  casco convexo por quatro cantos. A UI pode fornecer os cantos manualmente.
- Os cantos são ordenados ciclicamente; o lado longo segue o eixo horizontal de
  destino, inclusive quando o papel aparece vertical na fotografia.
- A perspectiva é retificada. O usuário precisa confirmar as dimensões reais
  (`paperSizeConfirmed=true`). Os números iniciais de 76×26 mm são apenas campos
  de formulário e não constituem calibração automática.
- Alternativamente `mmPerPixel` é uma escala manual por pixel **da imagem de
  entrada**, com ajuste se houver redução. Nesse modo não se aplica retificação
  automática, a menos que dimensões do papel também sejam confirmadas (estas
  passam a determinar a escala). Use uma imagem já recortada/ortogonal para a
  escala manual. Uma escala escalar não corrige perspectiva.
- Sem calibração, densidade/cm², diâmetros físicos e qualidade ficam `null`; ainda
  são exibidas contagem de manchas resolvíveis, diâmetros em pixels e cobertura.
- Não há ampliação artificial para produzir mais resolução: o destino não passa
  da extensão observada do papel, limitado pela aresta de análise configurada.
- A margem interna padrão de 2% é excluída da área útil. Cobertura e densidade usam
  exatamente essa mesma área; a grade divide essa área em células iguais.

## Segmentação e contagem auditável

A máscara identifica mudança azul/roxa cromática: saturação mínima 0,12,
contraste azul/roxo de 15 níveis, azul >1,05×verde e intensidade máxima >25.
Sombras amarelas e sujeira neutra escura não são tratadas automaticamente como
manchas azuis. Fotografias muito escuras, papel molhado, tinta ou objetos azuis
podem produzir erro e precisam de revisão do overlay.

Componentes de oito vizinhos abaixo de 9 pixels são excluídos como irresolvíveis.
O limiar físico mínimo padrão é 0,10 mm de diâmetro da mancha e pode ser alterado.
Esse número é uma escolha de triagem do software, **não limite universal de
visibilidade, deriva ou qualidade agronômica**. É emitido aviso se o limiar
selecionado representar menos de 3 pixels na imagem analisada.

O motor também retorna `effective_min_stain_diameter_mm`: o maior entre o limiar
físico solicitado e `2 sqrt(min_component_pixels/pi) × mm_per_px`. Com 9 pixels,
76 mm/1200 px implica piso de aproximadamente 0,214 mm; reduzir o campo para
0,10 mm não recupera detalhes inexistentes. O destino padrão passou a 2400 px
(sem ampliar além da extensão observada), com piso aproximado de 0,107 mm nesse
exemplo. A resolução efetiva real também depende do foco, lente e compressão.

A classificação usa área, segundo momento (alongamento), casco convexo,
circularidade discreta e lóbulos da transformada de distância. Borda, artefatos,
manchas abaixo do limiar e componentes coalescidos ficam fora da contagem válida.
É uma classificação conservadora de manchas; a quantidade de gotas físicas não
é demonstrável por esses componentes. Recortes de treinamento e artefatos sklearn
legados continuam em seu fluxo próprio; não são carregados por este motor.

O overlay inclui dimensões da imagem retificada, cantos na imagem de entrada e
componentes com bounding box, centro, classe, área e tamanho. Verde indica isolada
contada; laranja, coalescida; azul claro, borda; cinza, abaixo do limiar; roxo,
artefato. Componentes de menos de 9 pixels não têm caixas individuais. Há limite
de 5.000 componentes vetoriais no overlay e aviso; as contagens não são truncadas.
Python retorna PNG em `overlay.image_data_url`; JS retorna pixels retificados em
`overlay.rgba_data` se `includeOverlayPixels=true`.

## Métricas e compatibilidade

- `total_droplets`/`valid_droplets`: número de manchas isoladas aceitas.
- `coverage_percentage`: pixels de componentes resolvíveis dentro da área útil /
  pixels da área útil ×100; inclui partes de borda e coalescências e não aumenta
  quando o limiar físico de contagem muda.
- `density_per_cm2`: isoladas aceitas / área útil calibrada em cm².
- `cv_coefficient`: agora é o CV populacional das contagens por célula espacial
  (grade padrão 3×6), não o CV de diâmetros. Uma única amostra não mede a
  uniformidade de toda a área agrícola. Contagens baixas tornam esse CV instável.
- `diameter_cv_coefficient`: preserva separadamente a dispersão de diâmetros.
- `stain_diameter`: média/mediana de diâmetros de manchas, unidade explícita.
- `dv50_diameter`: `null`. O verdadeiro DV50 de gotas não é estimado sem relação
  de espalhamento validada. `dv50_proxy_um` é um **proxy de manchas**, obtido pelo
  primeiro diâmetro ordenado que acumula metade da soma dos cubos dos diâmetros.
  Não há interpolação ou afirmação de equivalência ao DV50 da pulverização.
- `estimated_total_impacts`: `null`, pois lóbulos não comprovam impactos reais.

## Fuzzy configurável e transparente

`evaluateQuality` / `evaluate_quality` implementam regras Sugeno de ordem zero.
O resultado é um **índice percentual de adequação ao perfil escolhido**, não
probabilidade de eficácia, autorização para aplicar, indicação de produto ou dose.
As pertinências e todas as ativações/regras são retornadas com as evidências.

O preset `experimental-screening` usa cobertura mínimo/alvo/máximo 5/15/35%,
densidade 10/50/250 manchas/cm² e parâmetro CV50. São referências de engenharia
para exercitar a triagem; não foram extraídas como norma para qualquer cultura.

Cobertura/densidade possuem pertinências triangulares de adequação e ombros baixo/
alto. Uniformidade decresce entre 0,5×CV e 2×CV do perfil; pertinência de
coalescência sobe entre frações 0,05 e 0,35. Regras usam min/max para combinar
adequação (consequente90), fator limitante (20), intermediário (55) e ausência de
manchas isoladas (0). A média ponderada de consequentes gera o índice; ausência
força zero. Os parâmetros e consequentes são explícitos e precisam de ensaio
antes de qualquer interpretação agronômica.

- Sem escala: `status=insufficient`, escore `null`.
- Perfil experimental/não confirmado: `provisional`.
- Perfil de protocolo confirmado: `indicative`; confirmação não valida o software.
- Perfil customizado inválido: `insufficient` com motivo, sem correção silenciosa.
- Catálogo com `status=requires_local_calibration` e todos os alvos ausentes:
  fallback **explícito** para o preset experimental (`experimental_fallback`),
  preservando `requested_profile`, cultura/estágio e aviso da falta de validação.

## Verificação e limites atuais

Testes sintéticos verificam contagem isolada, coalescência, borda, pontos minúsculos,
área de cobertura, escala, limiar físico, EXIF, orientação vertical, uniformidade
espacial, proxy cúbico e regras/perfis fuzzy. Um teste executa o mesmo fixture RGBA
em Python e Node e compara contagens, cobertura, densidade, grade, proxy e escore.
A paridade não implica resultados idênticos em todo limiar: interpolação da
perspectiva/redução é OpenCV em Python e bilinear no JS.

Ainda são necessários cartões anotados independentes, testes com diferentes
celulares/iluminações, protocolo óptico de referência, erros de contagem/cobertura,
repetibilidade, calibração da segmentação e validação dos perfis por contexto.
Nenhuma acurácia medida em campo é declarada por esta implementação.
