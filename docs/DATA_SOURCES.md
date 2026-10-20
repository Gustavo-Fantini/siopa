# Fontes de dados ambientais e catálogo agrícola

Pesquisa e implementação: **20/10/2026**. Foram consultadas fontes primárias dos
próprios provedores. Documentação acessível não garante disponibilidade da API.
Uma resposta obtida por latitude/longitude representa uma grade regional;
não equivale a medição exata no talhão. Datas de consulta, referência dos dados
e expiração de cache são informações diferentes.

## Clima: Open-Meteo

- [Documentação Forecast API](https://open-meteo.com/en/docs): condições atuais
  são estimativas de modelo, com passos de 15 minutos; vento é a 10 m e
  temperatura/umidade a 2 m. A seleção automática pode combinar modelos,
  com grade variável por região; não inventamos resolução numérica fixa.
- [Licença](https://open-meteo.com/en/licence): dados CC BY 4.0; atribuir
  Open-Meteo junto à apresentação dos dados. A implementação normaliza nomes,
  unidades e agrega o resumo diário a partir das horas, alterações do SIOPA.
- [Termos do endpoint gratuito](https://open-meteo.com/en/terms): uso não
  comercial; limites publicados de 600 chamadas/minuto, 5.000/hora e
  10.000/dia. Uso comercial exige verificar plano/contrato. Nenhum plano foi
  contratado. Os termos podem mudar e devem ser revistos antes da publicação.

`WeatherService` faz uma consulta de atual + sete dias horários e compartilha o
snapshot entre chamadas. Campo `pressure` é pressão de superfície no Open-Meteo,
não pressão da bomba. Precipitação atual e horária carregam seu intervalo de
acumulação; um resumo diário não define uma janela de aplicação. Vento de modelo
a 10 m não substitui anemômetro na altura de operação.

Configuração: `OPEN_METEO_API_URL`, `OPEN_METEO_API_KEY` opcional,
`ENVIRONMENT_CACHE_PATH`, `ENVIRONMENT_CACHE_TTL_SECONDS`. Uma chave configurada
com o domínio público seleciona o domínio `customer-api`; isso apenas prepara
o cliente para um contrato existente. Sem chave, funciona o endpoint aberto.
Se a fonte principal falha, os clientes já existentes WeatherAPI/OpenWeather/
Agromonitoring/Climatempo são tentados somente quando configurados; termos
e cobertura desses provedores continuam sujeitos aos respectivos contratos.

Não há clima ou previsão sintética no fallback. Sem fonte nem snapshot útil,
os números são `null`, a lista de previsão fica vazia e a disponibilidade é
`unavailable`. A triagem `spray_conditions` é referência genérica do aplicativo,
sem validação por produto/cultura; não autoriza aplicação.

## Solo: ISRIC SoilGrids

- [Documentação e contrato REST](https://rest.isric.org/soilgrids/v2.0/docs),
  [OpenAPI](https://rest.isric.org/soilgrids/v2.0/openapi.json).
- [Propriedades e conversão de unidades](https://docs.isric.org/globaldata/soilgrids/SoilGrids_faqs_01.html).
  As respostas inteiras são divididas pelo fator oficial: pH/10,
  carbono orgânico/10 para g/kg e areia/argila/silte/10 para porcentagem.
- [FAQ sobre período dos dados](https://docs.isric.org/globaldata/soilgrids/SoilGrids_faqs_04.html):
  não existe um ano único das observações de solo usadas no produto.
- [Produto e licença](https://isric.org/explore/soilgrids)
  e [política de dados](https://www.isric.org/about/data-policy): atribuir ISRIC;
  produtos SoilGrids distribuídos sob CC BY 4.0, observadas as condições da fonte.
- [Entrada oficial REST](https://rest.isric.org/): beta sem garantia de uptime,
  uso justo de **cinco chamadas/minuto**.

A página oficial do produto consultada em 20/10/2026 informa que o REST está
**temporariamente pausado, sem prazo de retorno**. O Swagger acessível não
comprova que uma consulta de propriedades funciona. Esta integração é de melhor
esforço e deve apresentar ausência enquanto o serviço não responder.

Na verificação real desta implementação, às **20:02 UTC de 20/10/2026**
(21:02 em Lisboa), uma consulta pública de exemplo em Bauru (-22,31; -49,06)
retornou as cinco propriedades solicitadas. Portanto o aviso estático do site e
o comportamento observado naquele instante divergem; nenhum dos dois garante
uptime futuro. Open-Meteo respondeu HTTP 200, com referência meteorológica
20:00 UTC, sete dias/168 horas; a elevação GLO-90 também foi recebida.
Não foram usadas credenciais nem a localização do usuário nessa verificação.

Uma consulta pede média e quantis Q0.05/Q0.95 de pH em água, carbono orgânico e
frações de textura nas profundidades 0–5 e 5–15 cm. Resolução: 250 m.
Preservamos quantis; dados ausentes não são transformados em zero. Não inferimos
classe brasileira de solo, minerais, fertilidade, drenagem ou umidade atual.
`observed_at=null` é deliberado: não existe coleta local datada nessa resposta.

O limitador protege cinco requisições por minuto **por processo**. Workers/réplicas
na mesma saída de rede precisam de orçamento compartilhado antes de escalar.
Não esperamos em fila longa: limite local, erro, timeout ou pixel sem valores
produzem indisponibilidade explícita, ou snapshot antigo identificado.
`SOILGRIDS_API_URL` permite configurar endpoint compatível.

## Relevo: Open-Meteo / Copernicus DEM

[Elevation API](https://open-meteo.com/en/docs/elevation-api) documenta o
Copernicus DEM GLO-90, edição 2021, resolução 90 m, endpoint `/v1/elevation`.
Atribuir Open-Meteo e Copernicus; a documentação aponta a licença do DEM e
o identificador [10.5270/ESA-c5d3d65](https://doi.org/10.5270/ESA-c5d3d65).
Os termos de acesso do Open-Meteo também se aplicam. É modelo de superfície;
um valor de elevação não resolve declividade, microrelevo ou drenagem.
`slope_degrees=null` evita criar uma declividade sem levantamento/malha adequados.
O cliente usa o domínio configurado para Open-Meteo e a chave opcional.

## Catálogo local e orientação conservadora

[FAO Caliper/WCA](https://www.fao.org/statistics/caliper/classifications/wca/en)
mantém listas agrícolas com nomes botânicos e correspondências classificatórias.
Também foi consultado o [apêndice botânico histórico da FAO](https://www.fao.org/4/a0135e/A0135E10.htm)
e o [USDA ARS GRIN-Global](https://npgsweb.ars-grin.gov/gringlobal/sitemap),
cuja [base taxonômica](https://npgstest.ars-grin.gov/gringlobal/taxon/abouttaxonomy?chapter=basis)
explica atualização e sinonímia. O download do manual WCA vinculado no Caliper
retornou HTTP 403 durante a pesquisa; não foi usado como se tivesse sido lido.

`app/data/crops.json` contém 127 identidades de culturas e aliases editoriais em
português/inglês. Os nomes são referências informativas, não uma resolução
taxonômica completa: banana, cana, inhame e outros grupos comerciais podem
abranger várias espécies/híbridos. A existência de uma entrada não comprova
cultivo em todo país nem registro de um produto fitossanitário. Não foi
realizada auditoria individual de todos os nomes no GRIN. Os registros indicam
`taxonomy_status=informational_reference`, sem alegação de aceitação taxonômica.

Os [quatro estágios gerais da FAO](https://www.fao.org/4/S2022E/s2022e07.htm)
servem de referência para navegação em cultivos anuais. Perenes usam rótulos
editoriais gerais. Não fornecemos dias, escala BBCH, pragas/doenças, janelas
de plantio ou exigências ambientais específicas sem fonte individual.
O catálogo não reproduz tabelas extensas de texto das publicações; conferir
licença da publicação de origem ao reutilizar conteúdo adicional FAO/USDA.

As [orientações FAO para uso/aplicação](https://www.fao.org/pest-and-pesticide-management/pesticide-risk-reduction/code-conduct/use/en/)
fundamentam a necessidade de equipamento, calibração e contexto. Nenhuma fonte
consultada estabeleceu limiar universal de cobertura/densidade/CV por cultura
que justificasse os números anteriormente presumidos pelo aplicativo.
Por isso todos os perfis novos têm `confirmed=false`, limiares numéricos `null`
e `status=requires_local_calibration`. Valores experimentais definidos pelo
usuário devem carregar protocolo e validação próprios. Não há doses no catálogo.

## Snapshot offline e datas

O cache JSON é criado somente quando usado, com gravação atômica, versão,
`fetched_at` UTC, `expires_at`, origem e valores normalizados. O TTL de clima usa
a configuração (padrão 3.600 s); solo e relevo têm TTL independente de 30 dias.
A expiração agregada é a menor dos componentes. O instante original do clima é
preservado em `timestamp`, além da data de busca. Uma referência meteorológica
mais antiga que `max(1 hora, 2 × TTL)` ou sem fuso/data conhecida não é tratada
como condição atual, mesmo que a transferência tenha acabado de ocorrer.

Após falha preservamos snapshot anterior sem renovar sua data/validade e
marcamos `stale` quando expirado. A repetição de falhas recebe backoff persistente
de cinco minutos para clima e dez para solo/relevo; um erro não apaga último
sucesso. `force_refresh=true` tenta nova consulta respeitando o limite SoilGrids.
Um snapshot expirado pode ser lido para contexto, não confirmar clima atual.
Sem snapshot disponível, a interface deve mostrar ausência, nunca simulação.

Cache é local ao servidor, contém coordenadas e deve seguir a retenção e acesso
do projeto. Não substitui o armazenamento offline do navegador. Processos
concorrentes compartilham arquivos atomicamente, mas locks e rate limit são
locais ao processo; não constituem infraestrutura distribuída.
