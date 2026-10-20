/* Local analysis, explicit context refresh, and private device history. */
"use strict";
const baseUrl = new URL("./", location.href);
const isNative = location.hostname === "appassets.androidplatform.net";
const $ = id => document.getElementById(id);
const state = { imageBlob: null, imageData: null, corners: [], catalog: [], snapshot: null, record: null, prompt: null, analyzing: false };
const profileFields = ["coverageMin", "coverageTarget", "coverageMax", "densityMin", "densityTarget", "densityMax", "uniformityCvMax"];
const text = (id, value) => { $(id).textContent = value; };
function message(value, error = false) { text("messageBox", value); $("messageBox").className = `message ${error ? "error" : "success"}`; $("messageBox").hidden = !value; }
function number(value, digits = 1, suffix = "") { return value !== null && value !== undefined && Number.isFinite(Number(value)) ? `${Number(value).toLocaleString("pt-BR", { maximumFractionDigits: digits })}${suffix}` : "Indisponível"; }
function metric(id, rows) {
  $(id).replaceChildren(...rows.map(([key, value]) => {
    const row = document.createElement("div"); row.className = "metric-row";
    const k = document.createElement("span"); k.className = "k"; k.textContent = key;
    const v = document.createElement("strong"); v.className = "v"; v.textContent = value; row.append(k, v); return row;
  }));
}
function date(value) { const d = new Date(value); return Number.isFinite(d.getTime()) ? d.toLocaleString("pt-BR") : "Data não informada"; }
function age(value) { const millis = Date.now() - new Date(value).getTime(); if (!Number.isFinite(millis)) return "idade desconhecida"; const hours = Math.max(0, Math.floor(millis / 3600000)); return hours < 1 ? "há menos de 1 h" : hours < 24 ? `há ${hours} h` : `há ${Math.floor(hours / 24)} dias`; }
function cropKey(crop) { return String(crop.key || crop.id || crop.crop_type || crop.slug || crop.name || ""); }
function cropName(crop) { return crop.name || crop.common_name || crop.display_name || cropKey(crop); }
function cropsFrom(payload) { const crops = Array.isArray(payload) ? payload : payload?.crops; return Array.isArray(crops) ? crops : crops && typeof crops === "object" ? Object.entries(crops).map(([key, crop]) => ({ key, ...crop })) : []; }
function renderCatalog(crops) {
  const previous = $("cropType").value, previousStage = $("growthStage").value, confirmed = $("profileConfirmed").checked;
  const previousProfile = Object.fromEntries(profileFields.map(key => [key, $(key).value])); state.catalog = crops;
  $("cropType").replaceChildren(...crops.map(crop => new Option(cropName(crop), cropKey(crop))));
  if (crops.some(c => cropKey(c) === previous)) $("cropType").value = previous;
  renderCrop();
  if (previous && previous === $("cropType").value) { $("growthStage").value = previousStage; for (const key of profileFields) $(key).value = previousProfile[key]; $("profileConfirmed").checked = confirmed; }
}
function renderCrop() {
  const crop = state.catalog.find(c => cropKey(c) === $("cropType").value);
  const stages = crop?.growth_stages || crop?.stages || [];
  const list = Array.isArray(stages) ? stages : Object.entries(stages).map(([key, value]) => ({ key, name: typeof value === "string" ? value : value.name || key }));
  $("growthStage").replaceChildren(new Option("Não informado", ""), ...list.map(stage => new Option(typeof stage === "string" ? stage.replaceAll("_", " ") : stage.name || stage.label || stage.key, typeof stage === "string" ? stage : stage.key || stage.id || stage.name)));
  text("cropGuide", crop ? [crop.scientific_name, crop.description, crop.category || crop.group].filter(v => typeof v === "string").join(" · ") || "Catálogo local disponível. Ajuste o perfil ao seu protocolo." : "Catálogo indisponível. Atualize os arquivos locais antes de sair ao campo.");
  $("cropGuidance").replaceChildren(...(crop?.sampling_guidance || []).map(item => { const li = document.createElement("li"); li.textContent = item; return li; }));
  const profile = state.snapshot?.quality_profiles?.[crop?.quality_profile_key] || crop?.quality_profile;
  if (profile) for (const key of profileFields) { const snake = key.replace(/[A-Z]/g, char => `_${char.toLowerCase()}`); const value = profile[key] ?? profile[snake]; if (value != null && Number.isFinite(Number(value))) $(key).value = value; }
  $("profileConfirmed").checked = false;
}
function contextOrigin(context) {
  const provenance = context?.provenance;
  if (typeof provenance === "string") return provenance;
  if (Array.isArray(provenance)) return provenance.map(p => typeof p === "string" ? p : p.source || p.provider || p.name).filter(Boolean).join(", ");
  if (provenance && typeof provenance === "object") return Object.entries(provenance).map(([key, value]) => `${key}: ${typeof value === "string" ? value : value?.source || value?.provider || JSON.stringify(value)}`).join("; ");
  return context?.weather?.current?.source || context?.weather?.source || context?.source || "Veja proveniência nos dados completos";
}
function renderContext() {
  const context = state.snapshot?.environment;
  const fetched = context?.fetched_at || state.snapshot?.generated_at;
  if (!context) { text("snapshotStatus", "Catálogo embarcado disponível. Sem contexto ambiental salvo para esta posição."); $("contextMetrics").replaceChildren(); metric("soilMetrics", [["Disponibilidade", "Sem consulta salva"]]); metric("terrainMetrics", [["Disponibilidade", "Sem consulta salva"]]); return; }
  const expired = context.stale === true || (context.expires_at && new Date(context.expires_at).getTime() < Date.now());
  const current = context.weather?.current || context.weather || {};
  const availability = context.availability;
  const status = typeof availability === "string" ? availability : availability ? JSON.stringify(availability) : "Consultar proveniência";
  text("snapshotStatus", `Contexto salvo em ${date(fetched)} (${age(fetched)}). ${expired ? "Validade vencida." : "Consulte a validade de cada fonte."} ${navigator.onLine ? "Conexão disponível; os valores são da consulta salva." : "Sem rede: esta é uma cópia salva."}`);
  const coordinates = context.coordinates || context.location || {};
  metric("contextMetrics", [["Disponibilidade", status], ["Origem", contextOrigin(context)], ["Temperatura salva", number(current.temperature ?? current.temp_c, 1, " °C")], ["Umidade salva", number(current.humidity, 0, "%")], ["Vento salvo", number(current.wind_speed ?? current.wind_kph, 1, " km/h")], ["Válido até", context.expires_at ? date(context.expires_at) : "Não informado"], ["Posição do contexto", coordinates.latitude !== undefined ? `${number(coordinates.latitude, 4)}, ${number(coordinates.longitude, 4)}` : "Veja dados completos"]]);
  const soil = context.soil || {}, terrain = context.terrain || {};
  const soilRows = [["Disponibilidade", soil.availability || "Indisponível"], ["pH estimado (0–5 cm)", number(soil.ph, 1)], ["Resolução", soil.resolution || "Não informada"], ["Fonte", contextOrigin(soil)], ["Consulta salva", soil.fetched_at ? `${date(soil.fetched_at)} (${age(soil.fetched_at)})` : "Sem consulta"], ["Referência temporal", soil.reference_period || "Não informada"], ["Validade do cache", soil.expires_at ? `${date(soil.expires_at)}${soil.stale || new Date(soil.expires_at).getTime() < Date.now() ? " · vencida" : ""}` : "Não informada"]];
  for (const property of Object.values(soil.properties || {})) for (const [depth, reading] of Object.entries(property.depths || {})) soilRows.push([`${property.label || "Propriedade"} · ${depth}`, `${number(reading.mean, 2, ` ${property.unit || ""}`)}${reading.q05 != null && reading.q95 != null ? ` (q05–q95: ${number(reading.q05, 2)}–${number(reading.q95, 2)})` : ""}`]);
  metric("soilMetrics", soilRows);
  metric("terrainMetrics", [["Disponibilidade", terrain.availability || "Indisponível"], ["Altitude estimada", number(terrain.elevation_m, 1, " m")], ["Declividade", number(terrain.slope_degrees, 1, "°")], ["Resolução", terrain.resolution || "Não informada"], ["Fonte", contextOrigin(terrain)], ["Consulta salva", terrain.fetched_at ? `${date(terrain.fetched_at)} (${age(terrain.fetched_at)})` : "Sem consulta"], ["Referência temporal", terrain.reference_period || "Não informada"], ["Validade do cache", terrain.expires_at ? `${date(terrain.expires_at)}${terrain.stale || new Date(terrain.expires_at).getTime() < Date.now() ? " · vencida" : ""}` : "Não informada"]]);
}
function updateConnection() { text("connectionStatus", navigator.onLine ? "Conexão disponível" : "Sem rede · análise local"); $("connectionStatus").className = `badge ${navigator.onLine ? "good" : "warn"}`; renderContext(); }
async function storageStatus() {
  try { await SiopaStore.open(); const persistent = await navigator.storage?.persisted?.(); const estimate = await navigator.storage?.estimate?.(); text("storageStatus", `${persistent ? "Proteção persistente concedida." : "Histórico local disponível; proteção persistente não confirmada."}${estimate?.usage ? ` Uso aproximado: ${number(estimate.usage / 1048576, 1)} MB.` : ""}`); }
  catch (error) { text("storageStatus", `Histórico indisponível: ${error.message}. Você ainda pode analisar e exportar.`); }
}
async function requestPersistence() { try { const granted = await navigator.storage?.persist?.(); message(granted ? "Proteção persistente concedida pelo navegador." : "O navegador não concedeu proteção persistente. Exporte amostras importantes."); await storageStatus(); } catch (error) { message(`Não foi possível solicitar proteção: ${error.message}`, true); } }
function coordinates() {
  const lat = $("latitude").value.trim(), lon = $("longitude").value.trim(); if (!lat && !lon) return null;
  const latitude = Number(lat), longitude = Number(lon);
  if (!lat || !lon || !Number.isFinite(latitude) || !Number.isFinite(longitude) || latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) throw new Error("Preencha ambas as coordenadas com valores válidos, ou deixe ambas vazias.");
  return { latitude, longitude };
}
function serverBase() {
  const supplied = $("serverUrl").value.trim();
  if (!supplied && isNative) throw new Error("Informe o endereço HTTPS do servidor para atualizar contexto. A análise local continua disponível.");
  const url = supplied ? new URL(supplied.endsWith("/") ? supplied : `${supplied}/`) : baseUrl;
  if (url.protocol !== "https:" && !(url.protocol === "http:" && ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname))) throw new Error("Use HTTPS no servidor de contexto (ou localhost para desenvolvimento).");
  if (url.username || url.password) throw new Error("O endereço do servidor não deve conter usuário ou senha.");
  return url;
}
async function syncContext(silent = false) {
  $("syncBtn").disabled = true;
  try {
    if (!navigator.onLine) throw new Error("Sem conexão. O catálogo e o contexto já salvos continuam disponíveis.");
    const url = new URL("api/v1/offline/bootstrap", serverBase());
    const coords = coordinates(); if (coords) for (const [key, value] of Object.entries(coords)) url.searchParams.set(key, String(value));
    const response = await fetch(url, { credentials: "omit", cache: "no-store", signal: AbortSignal.timeout(20000) });
    if (!response.ok) throw new Error(`Servidor respondeu HTTP ${response.status}.`);
    const snapshot = await response.json(); const crops = cropsFrom(snapshot);
    if (!snapshot.schema_version || !crops.length) throw new Error("Snapshot de contexto sem versão ou catálogo válido.");
    state.snapshot = snapshot;
    try { await SiopaStore.setMetadata("snapshot", snapshot); await SiopaStore.setMetadata("preferences", { serverUrl: $("serverUrl").value, coordinates: coords }); }
    catch (error) { if (!silent) message(`Contexto consultado, mas não salvo: ${error.message}`, true); renderCatalog(crops); renderContext(); return; }
    renderCatalog(crops); renderContext(); $("datasetTools").hidden = isNative || !snapshot.capabilities?.dataset_api;
    if (!silent) message("Catálogo e contexto atualizados no aparelho. Nenhuma foto foi enviada.");
  } catch (error) { if (!silent) message(`Atualização indisponível: ${error.message}`, true); }
  finally { $("syncBtn").disabled = false; }
}
async function loadImage(blob) {
  if (!blob) return;
  if (state.analyzing) { message("Aguarde o término da análise antes de trocar a imagem.", true); return; }
  if (!blob.size || blob.size > 25 * 1048576) { message("Escolha uma imagem com conteúdo e até 25 MB.", true); return; }
  try {
    let source;
    if (typeof createImageBitmap === "function") source = await createImageBitmap(blob, { imageOrientation: "from-image" });
    else source = await new Promise((resolve, reject) => { const url = URL.createObjectURL(blob); const img = new Image(); img.onload = () => { URL.revokeObjectURL(url); resolve(img); }; img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("Formato não suportado pelo aparelho.")); }; img.src = url; });
    const width = source.width || source.naturalWidth, height = source.height || source.naturalHeight;
    const scale = Math.min(1, 3000 / Math.max(width, height));
    const canvas = $("inputCanvas"); canvas.width = Math.max(1, Math.round(width * scale)); canvas.height = Math.max(1, Math.round(height * scale));
    const context = canvas.getContext("2d", { willReadFrequently: true }); context.drawImage(source, 0, 0, canvas.width, canvas.height); source.close?.();
    state.imageBlob = blob; state.imageData = context.getImageData(0, 0, canvas.width, canvas.height); state.corners = []; state.record = null;
    $("previewWrap").hidden = false; $("resultsSection").hidden = true;
    text("uploadName", `${blob.name || "Foto da amostra"} · ${number(blob.size / 1048576, 1)} MB · análise até 2.400 px`);
    drawInput(); message("");
  } catch (error) { message(`Não foi possível abrir a imagem: ${error.message}`, true); }
}
function drawInput() {
  if (!state.imageData) return;
  const ctx = $("inputCanvas").getContext("2d"); ctx.putImageData(state.imageData, 0, 0);
  if (state.corners.length) {
    ctx.lineWidth = Math.max(3, state.imageData.width / 250); ctx.strokeStyle = "#e24b29"; ctx.beginPath();
    state.corners.forEach((p, i) => { if (i) ctx.lineTo(p.x, p.y); else ctx.moveTo(p.x, p.y); }); if (state.corners.length === 4) ctx.closePath(); ctx.stroke();
    state.corners.forEach((p, i) => { ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(p.x, p.y, Math.max(10, state.imageData.width / 80), 0, Math.PI * 2); ctx.fill(); ctx.fillStyle = "#241f18"; ctx.font = `bold ${Math.max(15, state.imageData.width / 60)}px sans-serif`; ctx.fillText(String(i + 1), p.x + 8, p.y - 8); });
  }
  $("clearCornersBtn").hidden = !state.corners.length; text("cornerHint", state.corners.length === 4 ? "Quatro cantos marcados. Confira se o contorno acompanha a borda do papel." : `Toque nos quatro cantos, em sequência ao redor do papel (${state.corners.length}/4).`);
}
function analysisOptions() {
  if (!$("analysisForm").reportValidity()) throw new Error("Confira os campos destacados.");
  const width = Number($("paperWidth").value), height = Number($("paperHeight").value);
  if (width < height) throw new Error("Informe o lado maior na largura e o menor na altura.");
  if ($("manualCorners").checked && state.corners.length !== 4) throw new Error("Marque os quatro cantos ou desative a seleção manual.");
  const profile = { culture: $("cropType").value, stage: $("growthStage").value || null, mode: "screening", confirmed: $("profileConfirmed").checked };
  for (const key of profileFields) { profile[key] = Number($(key).value); if (!Number.isFinite(profile[key]) || profile[key] < 0) throw new Error("O perfil precisa de limites numéricos válidos."); }
  if (!(profile.coverageMin < profile.coverageTarget && profile.coverageTarget < profile.coverageMax && profile.coverageMax <= 100 && profile.densityMin < profile.densityTarget && profile.densityTarget < profile.densityMax && profile.uniformityCvMax > 0)) throw new Error("Use mínimo < alvo < máximo para cobertura e densidade, e CV máximo positivo.");
  return { paperWidthMm: width, paperHeightMm: height, paperSizeConfirmed: $("paperSizeConfirmed").checked, ...(state.corners.length === 4 && $("manualCorners").checked ? { paperCorners: state.corners } : {}), minStainDiameterMm: Number($("minStainDiameter").value), minComponentPixels: 9, analysisLongEdgePx: 2400, gridRows: 3, gridCols: 6, profile, includeOverlayPixels: true };
}
function workerAnalysis(imageData, options) {
  return new Promise((resolve, reject) => {
    let worker; try { worker = new Worker(new URL("static/analysis-worker.js", baseUrl)); } catch (error) { reject(error); return; }
    const id = crypto.randomUUID?.() || String(Date.now());
    const timer = setTimeout(() => { worker.terminate(); reject(new Error("A análise excedeu o tempo deste aparelho.")); }, 120000);
    const finish = () => { clearTimeout(timer); worker.terminate(); };
    worker.onmessage = event => { if (event.data.id !== id) return; finish(); if (event.data.error) reject(new Error(event.data.error.message)); else resolve(event.data.result); };
    worker.onerror = event => { finish(); reject(new Error(event.message || "Worker indisponível.")); };
    worker.postMessage({ id, imageData, options });
  });
}
async function analyze(event) {
  event.preventDefault(); if (state.analyzing) return;
  if (!state.imageData) { message("Fotografe ou escolha uma imagem antes de analisar.", true); return; }
  let options; try { options = analysisOptions(); } catch (error) { message(error.message, true); return; }
  const crop = $("cropType").value, selectedCropName = cropName(state.catalog.find(c => cropKey(c) === crop) || {}), imageBlob = state.imageBlob;
  state.analyzing = true; $("analyzeBtn").disabled = true; $("loadingBox").hidden = false; text("loadingText", "Separando manchas e calculando métricas. A foto não usa a conexão."); message("");
  try {
    let result, executionMode = "worker";
    try { result = await workerAnalysis(state.imageData, options); }
    catch (workerError) {
      executionMode = "main_thread";
      if (!globalThis.SiopaAnalysis?.analyzeImageData) throw new Error(`Motor local indisponível. Reabra o app com os arquivos atualizados. ${workerError.message}`);
      text("loadingText", "Executando o motor local no modo compatível com este aparelho…");
      await new Promise(resolve => setTimeout(resolve, 30)); result = await SiopaAnalysis.analyzeImageData(state.imageData, options);
    }
    const overlayBlob = await renderOverlay(result);
    const serializable = cleanResult(result);
    const cropData = state.catalog.find(c => cropKey(c) === crop);
    state.record = { id: crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`, createdAt: new Date().toISOString(), crop, cropName: selectedCropName, sampling_guidance: cropData?.sampling_guidance || [], sampling_sources: cropData?.sampling_sources || [], options, execution_mode: executionMode, imageBlob, imageName: imageBlob.name || "amostra.jpg", overlayBlob, result: serializable, environment: state.snapshot?.environment || null };
    renderResult(state.record);
    try { await SiopaStore.saveSample(state.record); text("saveStatus", "Foto, resultado e parâmetros salvos neste aparelho."); await renderHistory(); await storageStatus(); }
    catch (error) { text("saveStatus", `Não foi possível salvar o histórico: ${error.message}. Exporte esta amostra antes de sair.`); message("A análise terminou, mas não foi salva. Confira o armazenamento ou exporte a amostra.", true); }
  } catch (error) { message(`Falha na análise local: ${error.message}`, true); }
  finally { state.analyzing = false; $("analyzeBtn").disabled = false; $("loadingBox").hidden = true; if (state.pendingSync) { state.pendingSync = false; syncContext(true); } }
}
function cleanResult(result) { const copy = { ...result }; if (copy.overlay) { copy.overlay = { ...copy.overlay }; delete copy.overlay.rgba_data; } return copy; }
async function renderOverlay(result, blob) {
  const canvas = $("overlayCanvas"), overlay = result.overlay || {};
  if (blob) { const bitmap = await createImageBitmap(blob); canvas.width = bitmap.width; canvas.height = bitmap.height; canvas.getContext("2d").drawImage(bitmap, 0, 0); bitmap.close(); return blob; }
  canvas.width = overlay.width || 1; canvas.height = overlay.height || 1; const ctx = canvas.getContext("2d");
  if (overlay.rgba_data?.length === canvas.width * canvas.height * 4) ctx.putImageData(new ImageData(new Uint8ClampedArray(overlay.rgba_data), canvas.width, canvas.height), 0, 0);
  else { ctx.fillStyle = "#fff9db"; ctx.fillRect(0, 0, canvas.width, canvas.height); const colors = { valid: "#278544", coalesced: "#c26e0c", edge: "#1565bb", noise: "#777", tiny: "#999" }; for (const component of overlay.components || []) { const box = component.bbox; if (!box) continue; ctx.strokeStyle = colors[component.label] || "#777"; ctx.lineWidth = 2; ctx.strokeRect(...box); } }
  text("overlayLegend", `Verde: válida · laranja: unida · azul: borda · cinza: ruído/pequena. ${overlay.rgba_data ? "Imagem retificada com classificação." : "Máscara vetorial em coordenadas da análise."}`);
  return new Promise(resolve => canvas.toBlob(resolve, "image/png"));
}
function renderResult(record) {
  const result = record.result, quality = result.quality || {}, spatial = result.spatial_uniformity || {}, stain = result.stain_diameter || {};
  const statuses = { insufficient: "Calibração ou perfil insuficiente", provisional: "Triagem experimental", indicative: "Adequação ao perfil informado" };
  text("decisionTitle", statuses[quality.status] || "Leitura local concluída");
  text("decisionText", `${record.cropName || record.crop} · ${date(record.createdAt)}. ${result.calibration?.valid ? "Escala física disponível nesta leitura." : "Sem escala física válida: não interprete pixels como dimensões reais."}`);
  text("decisionBadge", quality.score == null ? "Sem índice" : `Índice ${number(quality.score, 1)}/100`); $("decisionBadge").className = `badge ${quality.status === "insufficient" ? "warn" : "neutral"}`;
  metric("analysisMetrics", [["Manchas válidas", number(result.valid_droplets ?? result.total_droplets, 0)], ["Manchas unidas", number(result.coalesced_droplets ?? result.double_droplets, 0)], ["Cobertura segmentada", number(result.coverage_percentage, 2, "%")], ["Densidade de manchas", number(result.density_per_cm2, 1, " /cm²")], ["Diâmetro mediano da mancha", number(stain.unit === "um" ? stain.median_um ?? stain.median : null, 1, " µm")], ["Piso configurado", `${number(record.options.minStainDiameterMm, 2)} mm`], ["Piso efetivamente resolúvel", number(result.effective_min_stain_diameter_mm, 3, " mm")], ["Estado da medida", String(result.measurement_status || "Veja observações")]]);
  const cells = Array.isArray(spatial.counts) ? spatial.counts.flat() : [];
  metric("qualityMetrics", [["CV espacial por células", number(spatial.cv_percent ?? spatial.cv_coefficient ?? spatial.cv, 1, "%")], ["Células com manchas", cells.length ? `${cells.filter(value => value > 0).length}/${cells.length}` : "Indisponível"], ["Índice fuzzy", quality.score == null ? "Indisponível" : `${number(quality.score, 1)}/100`], ["Natureza do perfil", record.options.profile?.confirmed ? "Informado pelo usuário" : "Triagem provisória"], ["Calibração", result.calibration?.source || "Indisponível"], ["Motor", result.engine_version || "Local"]]);
  const warnings = [...(Array.isArray(result.warnings) ? result.warnings : []), ...(record.sampling_guidance || []).map(item => `Plano de coleta (editorial): ${item}`), "O diâmetro da mancha não é o diâmetro da gota original; não há correção de espalhamento nesta leitura.", "Contexto ambiental salvo não representa condições em tempo real."];
  $("resultWarnings").replaceChildren(...warnings.map(warning => { const li = document.createElement("li"); li.textContent = typeof warning === "string" ? warning : warning.message || JSON.stringify(warning); return li; }));
  text("technicalJson", JSON.stringify({ result, options: record.options, context_at_analysis: record.environment }, null, 2));
  $("resultsSection").hidden = false; $("resultsSection").scrollIntoView({ behavior: "smooth", block: "start" });
}
async function renderHistory() {
  try {
    const samples = await SiopaStore.listSamples(); if (!samples.length) { $("historyList").textContent = "Nenhuma amostra salva neste aparelho."; return; }
    $("historyList").replaceChildren(...samples.map(sample => {
      const row = document.createElement("article"); row.className = "history-item";
      const description = document.createElement("div"), title = document.createElement("strong"), detail = document.createElement("p"); title.textContent = sample.cropName || sample.crop || "Amostra"; detail.className = "small-text"; detail.textContent = `${date(sample.createdAt)} · ${number(sample.result?.total_droplets, 0)} manchas · ${number(sample.result?.coverage_percentage, 1, "%")}`; description.append(title, detail);
      const actions = document.createElement("div"); actions.className = "history-actions";
      const open = document.createElement("button"); open.type = "button"; open.className = "action secondary"; open.textContent = "Abrir";
      open.onclick = async () => { if (state.analyzing) return; try { state.record = await SiopaStore.getSample(sample.id); await renderOverlay(state.record.result, state.record.overlayBlob); renderResult(state.record); text("saveStatus", "Amostra recuperada do histórico local."); } catch (error) { message(error.message, true); } };
      const remove = document.createElement("button"); remove.type = "button"; remove.className = "text-button danger"; remove.textContent = "Excluir"; remove.setAttribute("aria-label", `Excluir amostra de ${date(sample.createdAt)}`);
      remove.onclick = async () => { if (!confirm("Excluir a foto e o resultado desta amostra do aparelho?")) return; try { await SiopaStore.deleteSample(sample.id); if (state.record?.id === sample.id) { state.record = null; $("resultsSection").hidden = true; } await renderHistory(); await storageStatus(); } catch (error) { message(error.message, true); } };
      actions.append(open, remove); row.append(description, actions); return row;
    }));
  } catch (error) { text("historyList", `Histórico indisponível: ${error.message}`); }
}
async function exportResult() {
  if (!state.record) return;
  try {
    const toDataUrl = blob => new Promise((resolve, reject) => { if (!blob) { resolve(null); return; } const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = () => reject(reader.error); reader.readAsDataURL(blob); });
    const record = state.record; const payload = { schema_version: 1, ...record, imageBlob: undefined, overlayBlob: undefined, image_data_url: await toDataUrl(record.imageBlob), overlay_data_url: await toDataUrl(record.overlayBlob) };
    const json = JSON.stringify(payload);
    if (isNative && globalThis.SiopaAndroid?.saveExport) { SiopaAndroid.saveExport(`siopa-${record.id}.json`, json); message("Escolha no Android onde guardar a amostra exportada."); return; }
    const url = URL.createObjectURL(new Blob([json], { type: "application/json" })); const a = document.createElement("a"); a.href = url; a.download = `siopa-${record.id}.json`; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (error) { message(`Exportação indisponível: ${error.message}`, true); }
}
async function registerOffline() {
  if (isNative) { text("offlineStatus", "Motor e catálogo incluídos no APK"); $("offlineStatus").className = "badge good"; return; }
  if (!("serviceWorker" in navigator)) { text("offlineStatus", "Instalação offline indisponível neste navegador"); return; }
  try {
    await navigator.serviceWorker.register(new URL("service-worker.js", baseUrl), { scope: baseUrl.pathname });
    const registration = await Promise.race([navigator.serviceWorker.ready, new Promise((_, reject) => setTimeout(() => reject(new Error("O cache ainda não está completo. Reabra com conexão para concluir.")), 20000))]);
    const controller = navigator.serviceWorker.controller || registration.active; const channel = new MessageChannel();
    channel.port1.onmessage = event => { const ready = event.data?.ready; text("offlineStatus", ready ? "Arquivos prontos para uso offline" : "Preparando arquivos offline; mantenha esta tela aberta"); $("offlineStatus").className = `badge ${ready ? "good" : "warn"}`; };
    controller?.postMessage({ type: "CHECK_OFFLINE" }, [channel.port2]);
  } catch (error) { text("offlineStatus", `Instalação offline incompleta: ${error.message}`); $("offlineStatus").className = "badge warn"; }
}
async function init() {
  updateConnection(); text("engineVersion", `Motor ${globalThis.SiopaAnalysis?.ENGINE_VERSION || "indisponível"}`);
  try { const preferences = await SiopaStore.getMetadata("preferences"); if (preferences?.serverUrl) $("serverUrl").value = preferences.serverUrl; if (preferences?.coordinates) { $("latitude").value = preferences.coordinates.latitude; $("longitude").value = preferences.coordinates.longitude; } state.snapshot = await SiopaStore.getMetadata("snapshot"); } catch (error) { message(`Armazenamento local indisponível: ${error.message}`, true); }
  if (state.snapshot && cropsFrom(state.snapshot).length) renderCatalog(cropsFrom(state.snapshot));
  try {
    const response = await fetch(new URL("static/crops.json", baseUrl)); if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const bundled = await response.json(), crops = cropsFrom(bundled); if (!crops.length) throw new Error("Catálogo vazio");
    if (!state.snapshot || state.snapshot.catalog_source === "bundled") { state.snapshot = { ...bundled, generated_at: bundled.updated_at, catalog_source: "bundled", environment: null }; renderCatalog(crops); }
    try { await SiopaStore.setMetadata("bundled_catalog", bundled); if (state.snapshot.catalog_source === "bundled") await SiopaStore.setMetadata("snapshot", state.snapshot); } catch {}
  } catch (error) { if (!state.catalog.length) text("cropGuide", `Catálogo local indisponível: ${error.message}`); }
  $("datasetTools").hidden = isNative || !state.snapshot?.capabilities?.dataset_api;
  renderContext(); await Promise.allSettled([storageStatus(), renderHistory(), registerOffline()]);
  if (navigator.onLine && !isNative) syncContext(true);
}
$("analysisForm").addEventListener("submit", analyze);
$("imageFile").addEventListener("change", event => loadImage(event.target.files?.[0])); $("cameraFile").addEventListener("change", event => loadImage(event.target.files?.[0]));
$("cropType").addEventListener("change", renderCrop); $("syncBtn").addEventListener("click", () => syncContext()); $("persistBtn").addEventListener("click", requestPersistence); $("refreshHistoryBtn").addEventListener("click", renderHistory); $("exportResultBtn").addEventListener("click", exportResult);
$("locationBtn").addEventListener("click", () => {
  if (!navigator.geolocation) { message("Localização indisponível. Você pode informar coordenadas ou analisar sem posição.", true); return; }
  navigator.geolocation.getCurrentPosition(async position => {
    $("latitude").value = position.coords.latitude.toFixed(6); $("longitude").value = position.coords.longitude.toFixed(6);
    try { await SiopaStore.setMetadata("preferences", { serverUrl: $("serverUrl").value, coordinates: coordinates() }); } catch {}
    message(navigator.onLine ? "Posição preenchida. Atualizando contexto para consulta offline…" : "Posição salva. O contexto poderá ser atualizado quando a conexão voltar.");
    if (navigator.onLine) { if (state.analyzing) state.pendingSync = true; else syncContext(); }
  }, error => message(`Localização não obtida: ${error.message}. A análise funciona sem posição.`, true), { enableHighAccuracy: true, timeout: 15000, maximumAge: 300000 });
});
$("manualCorners").addEventListener("change", () => { $("cornerHint").hidden = !$("manualCorners").checked; $("inputCanvas").classList.toggle("select-corners", $("manualCorners").checked); });
$("clearCornersBtn").addEventListener("click", () => { state.corners = []; drawInput(); });
$("inputCanvas").addEventListener("pointerdown", event => { if (!$("manualCorners").checked || !state.imageData || state.analyzing || state.corners.length >= 4) return; event.preventDefault(); const rect = event.currentTarget.getBoundingClientRect(); state.corners.push({ x: (event.clientX - rect.left) * state.imageData.width / rect.width, y: (event.clientY - rect.top) * state.imageData.height / rect.height }); drawInput(); });
window.addEventListener("online", () => {
  updateConnection();
  const context = state.snapshot?.environment, expired = !context || context.stale || !context.expires_at || new Date(context.expires_at).getTime() < Date.now();
  if (expired && $("latitude").value && $("longitude").value && (!isNative || $("serverUrl").value)) { if (state.analyzing) state.pendingSync = true; else syncContext(true); }
});
window.addEventListener("offline", updateConnection);
window.addEventListener("beforeinstallprompt", event => { event.preventDefault(); state.prompt = event; $("installBtn").hidden = false; }); $("installBtn").addEventListener("click", async () => { if (!state.prompt) return; await state.prompt.prompt(); state.prompt = null; $("installBtn").hidden = true; });
init();
