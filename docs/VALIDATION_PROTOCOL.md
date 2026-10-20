# Validação da contagem e do índice de deposição

O sistema implementa uma medição reproduzível e um índice de triagem. Precisão contra
contagem humana e adequação agronômica ainda precisam de evidências independentes.
Não usar percentual fuzzy como taxa de acerto.

## Protocolo a registrar antes do ensaio

- Marca, modelo, lote e dimensões do papel; confirmar se é o mesmo papel hidrossensível
  amarelo/azul esperado pelo algoritmo. Outros materiais exigem validação própria.
- Cultura, alvo, estágio, posição/altura do coletor, equipamento, calda e condições.
- Celular, câmera, distância, iluminação, foco, compressão e orientação.
- Definição de mancha isolada, minúscula, unida, borda e sujeira; piso físico e limite
  de resolução. Uma mancha deve ser resolvível por imagem antes de ser contada.
- Perfil de avaliação: metas e justificativa para cobertura/densidade/uniformidade;
  separar parâmetros editoriais experimentais de parâmetros validados no ensaio.

## Referência humana

Use pelo menos dois avaliadores independentes em imagens reservadas. Registre as
divergências e a adjudicação, mantendo exemplos de cada classe. Ao comparar contagens,
use exatamente a mesma região interior e critérios de exclusão. Fotos do mesmo
cartão/coleta e suas cópias não devem aparecer em calibração e avaliação final.

Varie propositalmente perspectiva, rotação, celular, foco, sombra, densidade e
coalescência. Inclua imagens sem papel e situações em que a resposta correta seja
solicitar nova captura. Defina critérios de aceitação antes de observar o resultado.

## Relatório reproduzível de erro de contagem

Copie `validation-manifest.example.json`, preencha caminhos e contagens reais e
confirme a escala física somente após verificar o papel. Os caminhos das fotos
são relativos ao manifesto. O exemplo contém `null` para impedir seu uso como
verdade de referência sem edição.

```text
python scripts/evaluate_counts.py caminho/manifest.json --output artifacts/validation-report.json
```

O relatório contém MAE, RMSE, viés e diferença por imagem. Não calcula uma falsa
"precisão" por porcentagem de contagens: erros positivos/negativos podem se compensar.
Precisão/recall de detecção exigem correspondência por objeto e referência geométrica,
além da contagem total. A concordância humana deve aparecer junto dos resultados.

## Validação física e agronômica

Conferir calibração e área com referência conhecida; medir a repetibilidade com
fotografias repetidas do mesmo cartão. Diâmetro de mancha não deve ser relatado como
diâmetro original de gota sem calibração de espalhamento para papel/calda/condições.
O DV50 proxy das manchas não é medição validada do espectro do pulverizador.

Avalie o índice fuzzy separadamente com critérios definidos por profissional e pelo
ensaio: ele combina deposição no cartão, não comprova controle de praga/doença ou
eficácia em toda a cultura. Replicar cartões no dossel e condições reais é essencial.

Método e referências consultadas: [IMAGE_METHOD.md](IMAGE_METHOD.md).
