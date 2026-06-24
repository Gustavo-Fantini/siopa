const fallbackCrops = [
    { key: "soja", name: "Soja", growth_stages: ["germinacao", "vegetativo", "floracao", "enchimento_graos", "maturacao"] },
    { key: "milho", name: "Milho", growth_stages: ["germinacao", "vegetativo", "pendoamento", "espigamento", "maturacao"] },
    { key: "algodao", name: "Algodao", growth_stages: ["germinacao", "vegetativo", "floracao", "frutificacao", "abertura_capulhos"] },
    { key: "cana", name: "Cana-de-acucar", growth_stages: ["brotacao", "perfilhamento", "crescimento", "maturacao"] },
];

const state = {
    config: null,
    deferredPrompt: null,
    previewUrl: null,
};

const elements = {
    analyzeBtn: document.getElementById("analyzeBtn"),
    appVersion: document.getElementById("appVersion"),
    cropPreviewCard: document.getElementById("cropPreviewCard"),
    cropPreviewMetrics: document.getElementById("cropPreviewMetrics"),
    cropPreviewText: document.getElementById("cropPreviewText"),
    cropPreviewTitle: document.getElementById("cropPreviewTitle"),
    cropType: document.getElementById("cropType"),
    decisionBadge: document.getElementById("decisionBadge"),
    decisionText: document.getElementById("decisionText"),
    decisionTitle: document.getElementById("decisionTitle"),
    deployMode: document.getElementById("deployMode"),
    form: document.getElementById("analysisForm"),
    growthStage: document.getElementById("growthStage"),
    imageFile: document.getElementById("imageFile"),
    installBtn: document.getElementById("installBtn"),
    latitude: document.getElementById("latitude"),
    loadingBox: document.getElementById("loadingBox"),
    locationBtn: document.getElementById("locationBtn"),
    longitude: document.getElementById("longitude"),
    maxUpload: document.getElementById("maxUpload"),
    messageBox: document.getElementById("messageBox"),
    productMetrics: document.getElementById("productMetrics"),
    resultsSection: document.getElementById("resultsSection"),
    summaryBadges: document.getElementById("summaryBadges"),
    summaryCard: document.getElementById("summaryCard"),
    summaryText: document.getElementById("summaryText"),
    summaryTitle: document.getElementById("summaryTitle"),
    targetProblem: document.getElementById("targetProblem"),
    technicalNotes: document.getElementById("technicalNotes"),
    uploadBox: document.getElementById("uploadBox"),
    uploadHint: document.getElementById("uploadHint"),
    uploadName: document.getElementById("uploadName"),
    uploadPreviewImage: document.getElementById("uploadPreviewImage"),
    weatherMetrics: document.getElementById("weatherMetrics"),
    agricultureMetrics: document.getElementById("agricultureMetrics"),
    analysisMetrics: document.getElementById("analysisMetrics"),
    actionList: document.getElementById("actionList"),
};

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function formatNumber(value, digits = 2, suffix = "") {
    const numericValue = Number(value);
    if (Number.isNaN(numericValue)) {
        return "N/A";
    }

    return `${new Intl.NumberFormat("pt-BR", {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
    }).format(numericValue)}${suffix}`;
}

function formatInteger(value, suffix = "") {
    const numericValue = Number(value);
    if (Number.isNaN(numericValue)) {
        return "N/A";
    }

    return `${new Intl.NumberFormat("pt-BR", {
        maximumFractionDigits: 0,
    }).format(numericValue)}${suffix}`;
}

function normalizeRating(value) {
    const raw = String(value ?? "").trim().toLowerCase();

    if (["ideal", "excellent", "otima", "otimo", "favorable", "favoravel"].includes(raw)) {
        return "good";
    }

    if (["good", "boa", "adequada", "adequado"].includes(raw)) {
        return "good";
    }

    if (["caution", "moderate", "atencao", "alerta", "regular"].includes(raw)) {
        return "warn";
    }

    if (["poor", "bad", "inadequada", "inadequado", "critica", "critico"].includes(raw)) {
        return "bad";
    }

    return "neutral";
}

function buildBadge(label, tone = "neutral") {
    return `<span class="badge ${tone}">${escapeHtml(label)}</span>`;
}

function metricRow(label, value) {
    return `
        <div class="metric-row">
            <span class="k">${escapeHtml(label)}</span>
            <span class="v">${value}</span>
        </div>
    `;
}

function listItems(items, fallbackMessage) {
    const normalizedItems = (items || []).filter(Boolean);
    const finalItems = normalizedItems.length ? normalizedItems : [fallbackMessage];

    return finalItems.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
}

function mergeRecommendations(...groups) {
    const merged = groups.flat().filter(Boolean);
    return [...new Set(merged)];
}

function setMessage(text = "", type = "") {
    elements.messageBox.textContent = text;
    elements.messageBox.className = "message";

    if (text) {
        elements.messageBox.classList.add(type || "success");
    }
}

function setLoading(isLoading) {
    elements.loadingBox.hidden = !isLoading;
    elements.analyzeBtn.disabled = isLoading;
    elements.locationBtn.disabled = isLoading;
}

function updateUploadView(file) {
    if (!file) {
        elements.uploadBox.classList.remove("is-active");
        elements.uploadName.textContent = "Nenhum arquivo selecionado";
        elements.uploadHint.textContent = "Aceita JPG, PNG ou BMP.";
        elements.uploadPreviewImage.hidden = true;
        elements.uploadPreviewImage.removeAttribute("src");
        return;
    }

    elements.uploadBox.classList.add("is-active");
    elements.uploadName.textContent = file.name;
    elements.uploadHint.textContent = `${formatNumber(file.size / 1024 / 1024, 2, " MB")} pronto para analise`;

    if (state.previewUrl) {
        URL.revokeObjectURL(state.previewUrl);
    }

    state.previewUrl = URL.createObjectURL(file);
    elements.uploadPreviewImage.src = state.previewUrl;
    elements.uploadPreviewImage.hidden = false;
}

function populateCrops(crops) {
    const supportedCrops = crops?.length ? crops : fallbackCrops;
    elements.cropType.innerHTML = '<option value="">Selecione</option>';

    supportedCrops.forEach((crop) => {
        const option = document.createElement("option");
        option.value = crop.key;
        option.textContent = crop.name;
        option.dataset.stages = JSON.stringify(crop.growth_stages || []);
        elements.cropType.appendChild(option);
    });

    updateStages();
}

function updateStages() {
    const rawStages = elements.cropType.selectedOptions[0]?.dataset.stages;
    const stages = rawStages ? JSON.parse(rawStages) : [];

    elements.growthStage.innerHTML = '<option value="">Selecione</option>';

    stages.forEach((stage) => {
        const option = document.createElement("option");
        option.value = stage;
        option.textContent = stage.replaceAll("_", " ");
        elements.growthStage.appendChild(option);
    });
}

function updateSummaryCard(title, text, badges) {
    elements.summaryTitle.textContent = title;
    elements.summaryText.textContent = text;
    elements.summaryBadges.innerHTML = badges?.length ? badges.join("") : buildBadge("Sem resultado", "neutral");
}

function buildDecisionState(data) {
    const analysis = data.analysis || {};
    const weather = data.weather || {};
    const recommendation = data.recommendations || {};
    const application = recommendation.application || {};

    const coverage = Number(analysis.coverage_percentage || 0);
    const qualityScore = Number(analysis.quality_score || 0);
    const weatherTone = normalizeRating(application.weather_suitability || weather.spray_conditions?.overall_rating);

    if (weatherTone === "bad" || qualityScore < 50 || coverage < 30) {
        return {
            tone: "bad",
            badge: "Segure a aplicacao",
            title: "Aplicacao com alto risco agora",
            text: "A leitura combinada indica cobertura ou clima inadequados para seguir sem ajuste.",
        };
    }

    if (weatherTone === "warn" || qualityScore < 75 || coverage < 60) {
        return {
            tone: "warn",
            badge: "Aplicar com ajuste",
            title: "Cenario intermediario",
            text: "Existe espaco para aplicar, mas a recomendacao exige ajuste de tecnica, horario ou produto.",
        };
    }

    return {
        tone: "good",
        badge: "Cenario favoravel",
        title: "Aplicacao tecnicamente favoravel",
        text: "Cobertura, leitura da amostra e janela climatica formam um quadro mais seguro para a operacao.",
    };
}

function renderCropPreview(data) {
    const spray = data.spray_recommendations || {};
    const warnings = data.climate_considerations || [];
    elements.cropPreviewTitle.textContent = data.name || "Guia da cultura";
    elements.cropPreviewText.textContent = data.scientific_name || "Sem nome cientifico disponivel.";
    elements.cropPreviewMetrics.innerHTML = [
        metricRow("Bico indicado", escapeHtml(spray.nozzle_type || "N/A")),
        metricRow("Volume alvo", escapeHtml(spray.volume_ha ? `${spray.volume_ha} L/ha` : "N/A")),
        metricRow("Faixa de pressao", escapeHtml(spray.pressure || "N/A")),
        metricRow("Pontos de atencao", escapeHtml(warnings.slice(0, 2).join(" | ") || "Sem alertas extras")),
    ].join("");
    elements.cropPreviewCard.hidden = false;
}

async function loadCropPreview() {
    const cropType = elements.cropType.value;

    if (!cropType) {
        elements.cropPreviewCard.hidden = true;
        return;
    }

    const params = new URLSearchParams();
    if (elements.growthStage.value) {
        params.set("growth_stage", elements.growthStage.value);
    }

    try {
        const queryString = params.toString();
        const requestUrl = queryString
            ? `api/v1/agriculture/${encodeURIComponent(cropType)}?${queryString}`
            : `api/v1/agriculture/${encodeURIComponent(cropType)}`;
        const response = await fetch(requestUrl);
        if (!response.ok) {
            throw new Error("Falha ao carregar cultura");
        }

        const data = await response.json();
        renderCropPreview(data);
    } catch {
        elements.cropPreviewCard.hidden = true;
    }
}

async function loadConfig() {
    try {
        const response = await fetch("api/v1/client/config");
        if (!response.ok) {
            throw new Error("Falha ao carregar configuracao");
        }

        const config = await response.json();
        state.config = config;

        elements.deployMode.textContent = config.public_base_url ? "Servidor publico" : "Local ou rede";
        elements.maxUpload.textContent = `${config.max_upload_size_mb} MB`;
        elements.appVersion.textContent = config.app_version || "-";

        populateCrops(config.supported_crops || fallbackCrops);
    } catch {
        elements.deployMode.textContent = "Configuracao local";
        elements.maxUpload.textContent = "10 MB";
        elements.appVersion.textContent = "local";
        populateCrops(fallbackCrops);
        updateSummaryCard(
            "Configuracao local",
            "A interface entrou em modo resiliente e vai continuar operando com a configuracao padrao.",
            [buildBadge("Modo fallback", "warn")]
        );
    }
}

function requestLocation() {
    if (!navigator.geolocation) {
        setMessage("Geolocalizacao nao suportada por este navegador.", "error");
        return;
    }

    navigator.geolocation.getCurrentPosition(
        (position) => {
            elements.latitude.value = position.coords.latitude.toFixed(6);
            elements.longitude.value = position.coords.longitude.toFixed(6);
            setMessage("Localizacao preenchida com sucesso.", "success");
        },
        (error) => {
            setMessage(`Nao foi possivel obter a localizacao: ${error.message}`, "error");
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
}

function renderResults(data) {
    const analysis = data.analysis || {};
    const weather = data.weather || {};
    const agriculture = data.agriculture || {};
    const recommendations = data.recommendations || {};
    const pesticide = recommendations.pesticide || {};
    const dosage = recommendations.dosage || {};
    const application = recommendations.application || {};
    const productWeather = application.pesticide_weather_suitability || {};
    const decision = buildDecisionState(data);
    const practicalItems = mergeRecommendations(
        analysis.recommendations,
        recommendations.recommendations,
        productWeather.issues
    );

    elements.decisionTitle.textContent = decision.title;
    elements.decisionText.textContent = decision.text;
    elements.decisionBadge.className = `decision-badge ${decision.tone}`;
    elements.decisionBadge.textContent = decision.badge;

    elements.analysisMetrics.innerHTML = [
        metricRow("Total de gotas", escapeHtml(formatInteger(analysis.total_droplets || 0))),
        metricRow("Cobertura", escapeHtml(formatNumber(analysis.coverage_percentage || 0, 2, "%"))),
        metricRow("Densidade", escapeHtml(formatNumber(analysis.density_per_cm2 || 0, 2, " got/cm2"))),
        metricRow("CV", escapeHtml(formatNumber(analysis.cv_coefficient || 0, 2, "%"))),
        metricRow("DV50", escapeHtml(formatNumber(analysis.dv50_diameter || 0, 2, " um"))),
        metricRow("Classe da gota", escapeHtml(analysis.droplet_class || "N/A")),
    ].join("");

    elements.weatherMetrics.innerHTML = [
        metricRow("Temperatura", escapeHtml(formatNumber(weather.temperature ?? 0, 1, " C"))),
        metricRow("Umidade", escapeHtml(formatNumber(weather.humidity ?? 0, 1, "%"))),
        metricRow("Vento", escapeHtml(formatNumber(weather.wind_speed ?? 0, 1, " km/h"))),
        metricRow("Pressao", escapeHtml(formatNumber(weather.pressure ?? 0, 1, " hPa"))),
        metricRow("Leitura do clima", buildBadge(application.weather_suitability || weather.spray_conditions?.overall_rating || "indefinido", normalizeRating(application.weather_suitability || weather.spray_conditions?.overall_rating))),
    ].join("");

    elements.agricultureMetrics.innerHTML = [
        metricRow("Cultura", escapeHtml(agriculture.name || "N/A")),
        metricRow("Nome cientifico", escapeHtml(agriculture.scientific_name || "N/A")),
        metricRow("Bico sugerido", escapeHtml(agriculture.spray_recommendations?.nozzle_type || "N/A")),
        metricRow("Volume", escapeHtml(agriculture.spray_recommendations?.volume_ha ? `${agriculture.spray_recommendations.volume_ha} L/ha` : "N/A")),
        metricRow("Pressao", escapeHtml(agriculture.spray_recommendations?.pressure || "N/A")),
    ].join("");

    elements.productMetrics.innerHTML = [
        metricRow("Produto", escapeHtml(pesticide.name || "N/A")),
        metricRow("Ingrediente ativo", escapeHtml(pesticide.active_ingredient || "N/A")),
        metricRow("Dose", escapeHtml(dosage.recommended ? `${formatNumber(dosage.recommended, 2)} ${dosage.unit || "L/ha"}` : "N/A")),
        metricRow("Horario", escapeHtml(application.timing || "N/A")),
        metricRow("Confianca", escapeHtml(recommendations.confidence ? `${recommendations.confidence}%` : "N/A")),
        metricRow("Leitura do produto", buildBadge(productWeather.rating || "indefinido", normalizeRating(productWeather.rating))),
    ].join("");

    elements.actionList.innerHTML = listItems(
        practicalItems,
        "Sem observacoes adicionais para esta rodada."
    );

    elements.technicalNotes.innerHTML = [
        {
            title: "Resumo da resposta",
            content: `<p>${escapeHtml(data.message || "Analise concluida.")}</p>`,
        },
        {
            title: "Avaliacao da imagem",
            content: `<ul>${listItems(
                [
                    `Qualidade: ${analysis.quality_assessment || "N/A"}`,
                    `Pontuacao: ${analysis.quality_score ?? "N/A"}`,
                    `Tempo de processamento: ${analysis.processing_time ?? "N/A"} s`,
                ],
                "Sem leitura adicional."
            )}</ul>`,
        },
        {
            title: "Clima e produto",
            content: `<ul>${listItems(
                [
                    weather.spray_conditions?.summary,
                    productWeather.summary,
                    recommendations.reasoning,
                ].filter(Boolean),
                "Sem notas complementares."
            )}</ul>`,
        },
    ]
        .map((section) => `
            <article class="note-card">
                <h4>${escapeHtml(section.title)}</h4>
                ${section.content}
            </article>
        `)
        .join("");

    updateSummaryCard(decision.title, decision.text, [
        buildBadge(decision.badge, decision.tone),
        buildBadge(`Cobertura ${formatNumber(analysis.coverage_percentage || 0, 1, "%")}`, "neutral"),
        buildBadge(`Clima ${application.weather_suitability || weather.spray_conditions?.overall_rating || "indefinido"}`, normalizeRating(application.weather_suitability || weather.spray_conditions?.overall_rating)),
    ]);

    elements.resultsSection.hidden = false;
    elements.resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function submitAnalysis(event) {
    event.preventDefault();
    setMessage();

    const file = elements.imageFile.files?.[0];
    if (!file) {
        setMessage("Selecione uma imagem antes de continuar.", "error");
        return;
    }

    if (!elements.latitude.value || !elements.longitude.value || !elements.cropType.value) {
        setMessage("Preencha latitude, longitude e cultura antes de analisar.", "error");
        return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("latitude", elements.latitude.value);
    formData.append("longitude", elements.longitude.value);
    formData.append("crop_type", elements.cropType.value);
    formData.append("growth_stage", elements.growthStage.value);
    formData.append("target_problem", elements.targetProblem.value);

    setLoading(true);
    elements.resultsSection.hidden = true;

    try {
        const response = await fetch("api/v1/analyze-image", {
            method: "POST",
            body: formData,
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "Falha ao analisar imagem");
        }

        renderResults(data);
        setMessage("Analise concluida com sucesso.", "success");
    } catch (error) {
        setMessage(`Erro na analise: ${error.message}`, "error");
    } finally {
        setLoading(false);
    }
}

function setupInstallPrompt() {
    window.addEventListener("beforeinstallprompt", (event) => {
        event.preventDefault();
        state.deferredPrompt = event;
        elements.installBtn.hidden = false;
    });

    elements.installBtn.addEventListener("click", async () => {
        if (!state.deferredPrompt) {
            return;
        }

        state.deferredPrompt.prompt();
        await state.deferredPrompt.userChoice;
        state.deferredPrompt = null;
        elements.installBtn.hidden = true;
    });
}

function setupServiceWorker() {
    if ("serviceWorker" in navigator) {
        navigator.serviceWorker.register("service-worker.js").catch(() => undefined);
    }
}

function bindUploadInteractions() {
    elements.uploadBox.addEventListener("dragenter", (event) => {
        event.preventDefault();
        elements.uploadBox.classList.add("is-active");
    });

    elements.uploadBox.addEventListener("dragover", (event) => {
        event.preventDefault();
        elements.uploadBox.classList.add("is-active");
    });

    elements.uploadBox.addEventListener("dragleave", (event) => {
        event.preventDefault();
        if (!elements.imageFile.files?.length) {
            elements.uploadBox.classList.remove("is-active");
        }
    });

    elements.uploadBox.addEventListener("drop", (event) => {
        event.preventDefault();
        const files = event.dataTransfer?.files;
        if (!files?.length) {
            return;
        }

        elements.imageFile.files = files;
        updateUploadView(files[0]);
    });

    elements.imageFile.addEventListener("change", () => {
        updateUploadView(elements.imageFile.files?.[0]);
    });
}

function bindEvents() {
    elements.cropType.addEventListener("change", async () => {
        updateStages();
        await loadCropPreview();
    });

    elements.growthStage.addEventListener("change", loadCropPreview);
    elements.locationBtn.addEventListener("click", requestLocation);
    elements.form.addEventListener("submit", submitAnalysis);
}

async function init() {
    updateSummaryCard(
        "Aguardando analise",
        "O bloco de resumo vai condensar a leitura mais importante depois do envio da imagem.",
        [buildBadge("Pronto para receber imagem", "neutral")]
    );

    bindUploadInteractions();
    bindEvents();
    setupInstallPrompt();
    setupServiceWorker();
    await loadConfig();
}

init();
