# SIOPA no celular e sem internet

A jornada principal processa a imagem no aparelho com `analysis-engine.js`. Não faz
upload da foto para analisar. O mesmo HTML/CSS/JavaScript atende ao site instalável
(PWA) e ao aplicativo Android; o build copia esses arquivos, sem manter outra UI.

## Uso no campo

1. Na PWA, abra o site por HTTPS com conexão uma primeira vez e aguarde
   **Arquivos prontos para uso offline**. O APK já inclui todos os arquivos necessários
   e pode abrir pela primeira vez em modo avião.
2. Toque em **Proteger dados offline** para solicitar armazenamento persistente.
   A concessão depende do navegador. Desinstalar o aplicativo, limpar seus dados ou
   limpar o armazenamento do site pode apagar o histórico. Exporte amostras importantes.
3. Abra a câmera traseira ou escolha uma imagem. A foto é decodificada com a orientação
   EXIF pelo navegador; a prévia é limitada a 3.000 px no lado maior, sem ampliar.
4. Informe e confirme as dimensões físicas do papel. Os valores iniciais 76 × 26 mm
   são editáveis e não constituem confirmação. Se necessário, marque os quatro cantos
   em sequência ao redor do papel; a detecção e a calibração precisam ser conferidas.
5. Defina o menor diâmetro de **mancha**, escolha cultura/estágio e analise.
   O processamento usa até 2.400 px no lado maior. O piso efetivo mostrado no resultado
   também depende da escala e do mínimo de pixels por componente. Não é microscopia.
6. Foto original, parâmetros, resultado, máscara e cópia do contexto são salvos no
   histórico local. As amostras podem ser abertas, excluídas ou exportadas com a foto
   em um arquivo JSON. O app não sincroniza as amostras com o servidor.

Sem calibração válida, as grandezas físicas e o índice ficam nulos. O perfil inicial
de triagem usa limites experimentais explícitos; o usuário pode editar os limites e
confirmá-los para seu protocolo. O índice fuzzy (0–100) é adequação ao perfil, **não é
probabilidade de acerto, eficácia biológica ou dose de produto**. O diâmetro da mancha
não é convertido no diâmetro original da gota. A uniformidade descreve células do
mesmo coletor, não comprova a uniformidade de todo o talhão.

O catálogo inclui culturas, estágios e planos editoriais de coleta por arquitetura.
Esses planos ajudam a registrar amostras e exigem validação de campo; não prescrevem
produto, bula, dose ou condições universais de pulverização.

## Contexto opcional e atualização

A posição é opcional. Ao tocar em **Usar minha localização**, o navegador/Android
solicita a permissão. Com conexão, o app consulta contexto para a posição; sem rede,
guarda a posição para uma consulta posterior. Também é possível preencher coordenadas.
O botão de atualização consulta somente catálogo e contexto, sem transmitir imagens.

Na PWA, o servidor padrão é a própria origem. No APK, informe o endereço HTTPS da
sua instalação em **Servidor de atualização**. Não há um servidor público fixo
embutido. O servidor deve permitir CORS para `https://appassets.androidplatform.net`
caso restrinja origens. O APK bloqueia tráfego HTTP; localhost HTTP é útil apenas
para desenvolvimento da PWA, não para a conexão do APK com outro computador.

O contrato esperado é `GET /api/v1/offline/bootstrap`, com `latitude` e `longitude`
opcionais, retornando:

```text
schema_version, generated_at, catalog_version, engine_version
crops[], quality_profiles{}, environment{}, paper_defaults{}, capabilities{}
```

`environment` contém `weather.current`, `soil`, `terrain`, disponibilidade,
proveniência, horários de consulta e vencimento. A tela mostra dados salvos, idade,
validade e fontes. Solo é previsão espacial (camadas/propriedades/intervalos), e
altitude vem de modelo de terreno; não são medições da parcela. Falhas de fontes
ficam indisponíveis, sem completar valores com clima inventado. Atribuições do
ISRIC/SoilGrids, Open-Meteo e Copernicus ficam junto aos dados.

Ao recuperar conexão com coordenadas guardadas e contexto vencido, o app tenta nova
consulta. Se uma análise estiver em execução, a atualização aguarda sua conclusão.
A foto permanece local. `navigator.onLine` indica conectividade do aparelho e não
garante que o servidor ou um provedor responderá.

## Contratos locais

| Arquivo | Contrato |
| --- | --- |
| `app/static/analysis-engine.js` | `SiopaAnalysis.analyzeImageData({width,height,data}, options)`; implementação determinística compartilhada conceitualmente com o motor Python. |
| `analysis-worker.js` | Recebe `{id,imageData,options}`; responde `{id,result,engineVersion}` ou `{id,error:{message,name}}`. |
| `app.js` | Prefere Worker; usa o mesmo motor na thread principal como compatibilidade. Registra `execution_mode` na amostra. |
| `offline-store.js` | IndexedDB `siopa-offline`, versão 1: `samples` (chave `id`) e `metadata` (chave `key`). |
| `service-worker.js` | Precache integral do shell, catálogo, motor, worker e armazenamento. Não intercepta nem cacheia `/api/`, POSTs ou fotos. |

Cada amostra registra `id`, `createdAt`, cultura, orientações editoriais/fontes,
opções de calibração/perfil, `imageBlob`, `overlayBlob`, `result`, `environment` e
`execution_mode`. Metadados guardam o catálogo embarcado, último snapshot recebido e
preferências de servidor/posição. Sem espaço ou sem IndexedDB, a análise ainda pode
ser exportada e a interface informa que não foi salva.

O overlay do motor usa `width`, `height`, `rgba_data` e componentes vetoriais
`{label,bbox,centroid,...}` em coordenadas retificadas. A matriz RGBA vira PNG local
para o histórico. Não é necessário reconstruir a imagem a partir de um servidor.

Ao publicar mudanças no shell, atualize `CACHE_NAME` no service worker para que
instalações existentes recebam o conjunto coerente de arquivos. O APK recebe novas
versões do motor/UI por um novo APK; catálogo/contexto podem ser atualizados pela API.

## Android

O projeto está em `mobile/android`. Requer Android 8.0/API 26 ou posterior e um
Android System WebView atualizado. Usa Java, Android Gradle Plugin 8.7.3, Gradle 8.9,
compile/target SDK 35 e AndroidX WebKit. Nenhum CDN é necessário em execução.

`WebViewAssetLoader` publica os arquivos embarcados em
`https://appassets.androidplatform.net/assets/siopa/index.html`. Esta origem HTTPS
permite IndexedDB, Worker e APIs de contexto seguro sem depender de um servidor
local. O APK não precisa de service worker para carregar seus próprios assets.

A ponte nativa oferece câmera/seleção de arquivo, permissão de posição e exportação
por `ACTION_CREATE_DOCUMENT`. Câmera grava em URI temporária do FileProvider privado;
a UI lê a foto e guarda seu Blob no histórico. A ponte de exportação só opera na
página local. Links HTTPS externos abrem no navegador, sem carregar uma UI remota no
WebView. Backup automático Android está desabilitado e o app não solicita permissão
ampla de acesso a arquivos.

### Build no Windows

Instale JDK 17 ou 21 e Android SDK (API 35 e Build Tools 34.0.0), conforme as licenças
dos fornecedores. Configure `JAVA_HOME` e `ANDROID_SDK_ROOT`.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File mobile/build-android.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File mobile/build-android.ps1 -Task lintDebug
```

`-ExecutionPolicy Bypass` se aplica somente a esse processo; não muda a política do
sistema. O script também reconhece runtimes provisionados em `.tools/android-build`
e SDK em `.tools/android-sdk`. Mantém caches Gradle, preferências Android e a chave
debug em `.tools/`, sem instalar runtimes globalmente.

```text
mobile/android/app/build/outputs/apk/debug/app-debug.apk
```

O APK é assinado com chave **debug** para instalação de desenvolvimento, não é uma
publicação em loja. A assinatura de produção deve usar chave própria fora do Git.
`syncWebAssets` roda no `preBuild` e exige os arquivos necessários em `app/static`.
Após mudar motor, catálogo ou UI, execute novo build; não edite os assets gerados.

### Build em Linux/macOS/CI

Com Java/Android SDK configurados e licenças aceitas:

```sh
sh mobile/build-android.sh
sh mobile/build-android.sh lintDebug
```

O Gradle Wrapper está incluído. Dependências são baixadas no primeiro build; o APK
resultante funciona offline. Para instalar em aparelho conectado com depuração USB:

```text
adb install -r mobile/android/app/build/outputs/apk/debug/app-debug.apk
```

## Verificação e limites

Teste de integração Chromium/Edge, sem pacotes Node externos:

```text
node mobile/tests/offline-browser.test.cjs
```

No Windows, pode definir `SIOPA_BROWSER` para o executável Chromium/Edge. O padrão é
Edge em `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`.
O teste cria servidor de arquivos e perfil temporários, bloqueia a rede via CDP,
executa análise real no Worker, verifica nulidade sem confirmação física, geometria
manual, índice provisório, histórico/Blobs, recarga e reabertura offline, fallback
na thread principal e ausência de uploads. Fixture de imagem/contexto é sintética.
Evidências locais ficam em `.tools/mobile-browser-test-result.json` e capturas PNG.

Nesta implementação foram feitos build debug real e teste de navegador. Esses
resultados não substituem ensaio em celulares, câmera/GPS reais, diferentes versões
de WebView, orientações EXIF e pressões de armazenamento. Não foi instalado em
aparelho físico nesta sessão; tampouco foi validada precisão científica nas fotos
reais. A PWA depende da conservação do armazenamento local; o APK depende do WebView
e dos assets embarcados. Sem rede, nenhum dos dois produz contexto ambiental atual.

Referências técnicas: [conteúdo local e WebViewAssetLoader](https://developer.android.com/develop/ui/views/layout/webapps/load-local-content),
[WebChromeClient e arquivos/câmera](https://developer.android.com/reference/android/webkit/WebChromeClient),
[Gradle/AGP 8.7](https://developer.android.com/build/releases/agp-8-7-0-release-notes),
[persistência de armazenamento](https://developer.mozilla.org/en-US/docs/Web/API/StorageManager/persist),
[service workers](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers).
