/* SIOPA portable analysis. No network, DOM, model, package or CDN dependency.
 * ImageData must be decoded with EXIF orientation before this entry point.
 * Physical units require explicit calibration. See docs/IMAGE_METHOD.md.
 */
(function (global) {
  'use strict';
  const ENGINE_VERSION = '3.0.0-offline';
  const SCREENING_PROFILE = Object.freeze({ id: 'experimental-screening', mode: 'screening', culture: 'generic', coverageMin: 5, coverageTarget: 15, coverageMax: 35, densityMin: 10, densityTarget: 50, densityMax: 250, uniformityCvMax: 50, confirmed: false });
  const clamp = (x, low, high) => Math.max(low, Math.min(high, x));
  const numeric = x => x !== null && x !== undefined && typeof x !== 'boolean' && Number.isFinite(Number(x)) ? Number(x) : null;
  const positive = (x, fallback = null) => numeric(x) > 0 ? Number(x) : fallback;
  const option = (o, camel, snake, fallback) => o[camel] !== undefined ? o[camel] : o[snake] !== undefined ? o[snake] : fallback;
  const round = (x, precision = 3) => x === null ? null : Math.round(x * (10 ** precision)) / (10 ** precision);
  const ramp = (x, low, high) => clamp((x - low) / Math.max(high - low, 1e-9), 0, 1);
  const memberships = (x, low, target, high) => ({ low: 1 - ramp(x, low, target), adequate: Math.min(ramp(x, low, target), 1 - ramp(x, target, high)), high: ramp(x, target, high) });

  function evaluateQuality(metrics, profile) {
    const fields = ['coverageMin', 'coverageTarget', 'coverageMax', 'densityMin', 'densityTarget', 'densityMax', 'uniformityCvMax'];
    const invalidProfile = profile !== undefined && profile !== null && (typeof profile !== 'object' || Array.isArray(profile));
    const requested = !invalidProfile && profile ? profile : {};
    const fallback = requested.status === 'requires_local_calibration' && fields.every(key => requested[key] === null || requested[key] === undefined) && requested.confirmed !== true;
    const chosen = Object.assign({}, SCREENING_PROFILE, fallback ? Object.fromEntries(['culture', 'stage'].filter(key => key in requested).map(key => [key, requested[key]])) : requested);
    const evidence = { coverage_percentage: numeric(metrics.coverage_percentage), density_per_cm2: numeric(metrics.density_per_cm2), spatial_cv: numeric((metrics.spatial_uniformity || {}).cv), coalesced_fraction: numeric(metrics.coalesced_fraction) || 0, isolated_count: Number(metrics.valid_droplets || metrics.total_droplets || 0) };
    const result = { score: null, status: 'insufficient', label: 'Dados insuficientes', method: 'Sugeno experimental; graus de pertinencia, nao probabilidade', profile: chosen, evidence, memberships: {}, rules: [], limitations: ['Indice de deposito no papel; nao mede eficacia, dose, deriva ou residuos.', 'Uma amostra nao representa a lavoura; repetir em posicoes e alturas do dossel.', 'Metas do perfil sao parametros configuraveis, nao norma universal por cultura.'] };
    result.profile_source = fallback ? 'experimental_fallback' : Object.keys(requested).length ? 'user' : 'experimental_default';
    if (fallback) { result.requested_profile = requested; result.limitations.push('Catalogo sem metas numericas: aplicado explicitamente o preset experimental de triagem, sem validacao por cultura.'); }
    if (invalidProfile) { result.reason = 'Perfil invalido: esperado um objeto com parametros.'; return result; }
    if (!(metrics.calibration || {}).valid) { result.reason = 'Confirme dimensoes do papel detectado ou uma escala manual antes de avaliar.'; return result; }
    const p = Object.fromEntries(fields.map(key => [key, numeric(chosen[key])]));
    if (fields.some(key => p[key] === null) || !(0 <= p.coverageMin && p.coverageMin < p.coverageTarget && p.coverageTarget < p.coverageMax && p.coverageMax <= 100 && 0 <= p.densityMin && p.densityMin < p.densityTarget && p.densityTarget < p.densityMax && p.uniformityCvMax > 0)) { result.reason = 'Perfil invalido: informe limites minimo < alvo < maximo e CV positivo.'; return result; }
    if (evidence.coverage_percentage === null || evidence.density_per_cm2 === null) { result.reason = 'Cobertura e densidade calibrada sao necessarias.'; return result; }
    if (evidence.isolated_count > 0 && evidence.spatial_cv === null) { result.reason = 'Uniformidade espacial indisponivel para esta amostra.'; return result; }
    const coverage = memberships(evidence.coverage_percentage, p.coverageMin, p.coverageTarget, p.coverageMax);
    const density = memberships(evidence.density_per_cm2, p.densityMin, p.densityTarget, p.densityMax);
    const cv = evidence.spatial_cv === null ? p.uniformityCvMax * 2 : evidence.spatial_cv;
    const uniform = 1 - ramp(cv, p.uniformityCvMax * .5, p.uniformityCvMax * 2);
    const merged = ramp(evidence.coalesced_fraction, .05, .35);
    const good = Math.min(coverage.adequate, density.adequate, uniform, 1 - merged);
    const poor = Math.max(coverage.low, coverage.high, density.low, density.high, 1 - uniform, merged);
    const intermediate = Math.max(0, 1 - Math.max(good, poor));
    const absent = evidence.isolated_count === 0 ? 1 : 0;
    const rules = [{ id: 'adequate_deposit', activation: good, consequent: 90 }, { id: 'limiting_factor', activation: poor, consequent: 20 }, { id: 'intermediate_deposit', activation: intermediate, consequent: 55 }, { id: 'no_isolated_stains', activation: absent, consequent: 0 }];
    const divisor = rules.reduce((sum, rule) => sum + rule.activation, 0);
    const score = absent ? 0 : rules.reduce((sum, rule) => sum + rule.activation * rule.consequent, 0) / Math.max(divisor, 1e-9);
    Object.assign(result, { score: round(score, 2), status: chosen.confirmed === true ? 'indicative' : 'provisional', label: score >= 75 ? 'Favoravel ao perfil' : score >= 45 ? 'Requer ajuste' : 'Limitado para o perfil', memberships: { coverage, density, spatial_uniformity: uniform, coalescence: merged }, rules });
    if (!chosen.confirmed) result.limitations.push('Perfil experimental nao confirmado; valores nao validados para cultura/alvo/estagio.');
    if (evidence.isolated_count < 20) result.limitations.push('Poucas manchas isoladas: densidade e uniformidade sao instaveis.');
    return result;
  }

  function polygonArea(points) {
    let sum = 0;
    for (let i = 0; i < points.length; i++) { const a = points[i], b = points[(i + 1) % points.length]; sum += a[0] * b[1] - a[1] * b[0]; }
    return Math.abs(sum) / 2;
  }
  const distance = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  function convexHull(points) {
    if (points.length <= 2) return points.slice();
    const sorted = points.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    const lower = [], upper = [];
    for (const point of sorted) { while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], point) <= 0) lower.pop(); lower.push(point); }
    for (let i = sorted.length - 1; i >= 0; i--) { const point = sorted[i]; while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], point) <= 0) upper.pop(); upper.push(point); }
    lower.pop(); upper.pop(); return lower.concat(upper);
  }
  function canonicalCorners(input) {
    if (!Array.isArray(input) || input.length !== 4) throw new Error('Informe quatro cantos finitos do papel.');
    let points = input.map(p => Array.isArray(p) ? [numeric(p[0]), numeric(p[1])] : [numeric(p.x), numeric(p.y)]);
    if (points.some(p => p.some(x => x === null))) throw new Error('Informe quatro cantos finitos do papel.');
    const cx = points.reduce((s, p) => s + p[0], 0) / 4, cy = points.reduce((s, p) => s + p[1], 0) / 4;
    points.sort((a, b) => Math.atan2(a[1] - cy, a[0] - cx) - Math.atan2(b[1] - cy, b[0] - cx));
    const start = points.reduce((best, p, i) => p[0] + p[1] < points[best][0] + points[best][1] ? i : best, 0);
    points = points.slice(start).concat(points.slice(0, start));
    if (distance(points[1], points[0]) + distance(points[3], points[2]) < distance(points[2], points[1]) + distance(points[0], points[3])) points.push(points.shift());
    if (polygonArea(points) < 16 || convexHull(points).length !== 4) throw new Error('Os cantos nao definem um papel valido.');
    return points;
  }
  function sampleRGBA(input, x, y, output, offset) {
    x = clamp(x, 0, input.width - 1); y = clamp(y, 0, input.height - 1);
    const x0 = Math.floor(x), y0 = Math.floor(y), x1 = Math.min(input.width - 1, x0 + 1), y1 = Math.min(input.height - 1, y0 + 1), fx = x - x0, fy = y - y0;
    for (let channel = 0; channel < 3; channel++) {
      const a = input.data[(y0 * input.width + x0) * 4 + channel], b = input.data[(y0 * input.width + x1) * 4 + channel], c = input.data[(y1 * input.width + x0) * 4 + channel], d = input.data[(y1 * input.width + x1) * 4 + channel];
      output[offset + channel] = a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy;
    }
    output[offset + 3] = 255;
  }
  function resize(input, target) {
    const scale = Math.min(1, target / Math.max(input.width, input.height));
    if (scale === 1) return { image: { width: input.width, height: input.height, data: new Uint8ClampedArray(input.data) }, scale };
    const width = Math.max(1, Math.round(input.width * scale)), height = Math.max(1, Math.round(input.height * scale)), data = new Uint8ClampedArray(width * height * 4);
    for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) sampleRGBA(input, (x + .5) / scale - .5, (y + .5) / scale - .5, data, (y * width + x) * 4);
    return { image: { width, height, data }, scale };
  }
  function warp(input, corners, width, height) {
    const [p0, p1, p2, p3] = corners;
    const sx = p0[0] - p1[0] + p2[0] - p3[0], sy = p0[1] - p1[1] + p2[1] - p3[1];
    const dx1 = p1[0] - p2[0], dx2 = p3[0] - p2[0], dy1 = p1[1] - p2[1], dy2 = p3[1] - p2[1];
    const determinant = dx1 * dy2 - dx2 * dy1;
    if (Math.abs(determinant) < 1e-9) throw new Error('Perspectiva degenerada; selecione novamente os cantos.');
    const g = (sx * dy2 - dx2 * sy) / determinant, h = (dx1 * sy - sx * dy1) / determinant;
    const a = p1[0] - p0[0] + g * p1[0], b = p3[0] - p0[0] + h * p3[0], c = p0[0], d = p1[1] - p0[1] + g * p1[1], e = p3[1] - p0[1] + h * p3[1], f = p0[1];
    const data = new Uint8ClampedArray(width * height * 4);
    for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) { const u = x / Math.max(width - 1, 1), v = y / Math.max(height - 1, 1), denominator = g * u + h * v + 1; sampleRGBA(input, (a * u + b * v + c) / denominator, (d * u + e * v + f) / denominator, data, (y * width + x) * 4); }
    return { width, height, data };
  }
  function boxMorph(mask, width, height, radius, dilate) {
    const stride = width + 1, prefix = new Int32Array((width + 1) * (height + 1)), result = new Uint8Array(mask.length);
    for (let y = 0; y < height; y++) { let row = 0; for (let x = 0; x < width; x++) { row += mask[y * width + x]; prefix[(y + 1) * stride + x + 1] = prefix[y * stride + x + 1] + row; } }
    for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) { const x0 = Math.max(0, x - radius), y0 = Math.max(0, y - radius), x1 = Math.min(width, x + radius + 1), y1 = Math.min(height, y + radius + 1); const sum = prefix[y1 * stride + x1] - prefix[y0 * stride + x1] - prefix[y1 * stride + x0] + prefix[y0 * stride + x0]; result[y * width + x] = dilate ? Number(sum > 0) : Number(sum === (x1 - x0) * (y1 - y0)); }
    return result;
  }
  function connected(mask, width, height) {
    const labels = new Int32Array(mask.length), queue = new Int32Array(mask.length), components = [];
    let next = 0;
    for (let start = 0; start < mask.length; start++) {
      if (!mask[start] || labels[start]) continue;
      next++; let head = 0, tail = 1, left = start % width, right = left, top = Math.floor(start / width), bottom = top;
      queue[0] = start; labels[start] = next;
      while (head < tail) {
        const index = queue[head++], x = index % width, y = Math.floor(index / width);
        left = Math.min(left, x); right = Math.max(right, x); top = Math.min(top, y); bottom = Math.max(bottom, y);
        for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) { if (!dx && !dy) continue; const nx = x + dx, ny = y + dy, ni = ny * width + nx; if (nx >= 0 && nx < width && ny >= 0 && ny < height && mask[ni] && !labels[ni]) { labels[ni] = next; queue[tail++] = ni; } }
      }
      components.push({ id: next, area: tail, left, top, width: right - left + 1, height: bottom - top + 1, pixels: queue.slice(0, tail) });
    }
    return { labels, components };
  }
  function boundaryPoints(component, labels, width, height) {
    const points = [];
    for (const index of component.pixels) { const x = index % width, y = Math.floor(index / width); if (x === 0 || x === width - 1 || y === 0 || y === height - 1 || labels[index - 1] !== component.id || labels[index + 1] !== component.id || labels[index - width] !== component.id || labels[index + width] !== component.id) points.push([x, y]); }
    return points;
  }
  function detectPaper(input, expectedAspect) {
    const resized = resize(input, 640), image = resized.image, warm = new Uint8Array(image.width * image.height);
    for (let i = 0; i < warm.length; i++) { const r = image.data[i * 4], g = image.data[i * 4 + 1], b = image.data[i * 4 + 2]; warm[i] = Number(r > 75 && g > 55 && r > b * 1.25 && g > b * 1.10 && r >= g * .85); }
    const closed = boxMorph(boxMorph(warm, image.width, image.height, 3, true), image.width, image.height, 3, false);
    const parts = connected(closed, image.width, image.height);
    let best = null, confidence = 0, bestScore = 0;
    for (const part of parts.components) {
      if (part.area < warm.length * .04) continue;
      let hull = convexHull(boundaryPoints(part, parts.labels, image.width, image.height));
      while (hull.length > 4) { let loss = Infinity, selected = 0; for (let i = 0; i < hull.length; i++) { const local = Math.abs(cross(hull[(i + hull.length - 1) % hull.length], hull[i], hull[(i + 1) % hull.length])); if (local < loss) { selected = i; loss = local; } } hull.splice(selected, 1); }
      if (hull.length !== 4) continue;
      let corners; try { corners = canonicalCorners(hull); } catch (_) { continue; }
      const area = polygonArea(corners), fill = Math.min(1, part.area / Math.max(area, 1)), sides = corners.map((p, i) => distance(p, corners[(i + 1) % 4])), aspect = (sides[0] + sides[2]) / Math.max(sides[1] + sides[3], 1);
      if (Math.min(...sides) < 18 || aspect < 1.3 || aspect > 5.5 || fill < .50) continue;
      const edge = corners.some(p => p[0] <= 1 || p[1] <= 1 || p[0] >= image.width - 2 || p[1] >= image.height - 2), aspectScore = Math.max(0, 1 - Math.abs(Math.log(aspect / expectedAspect)) / 1.4), quality = fill * .55 + aspectScore * .45 - (edge ? .18 : 0), score = quality * Math.min(1, part.area / (warm.length * .25));
      if (quality >= .62 && score > bestScore) { best = corners.map(p => p.map(v => v / resized.scale)); confidence = quality; bestScore = score; }
    }
    return { points: best, confidence: Math.min(1, confidence) };
  }
  function geometry(part, labels, width, height) {
    let sx = 0, sy = 0, edges = 0;
    const localWidth = part.width + 2, localHeight = part.height + 2, localMask = new Uint8Array(localWidth * localHeight);
    for (const index of part.pixels) { const x = index % width, y = Math.floor(index / width); sx += x; sy += y; localMask[(y - part.top + 1) * localWidth + x - part.left + 1] = 1; if (x === 0 || labels[index - 1] !== part.id) edges++; if (x === width - 1 || labels[index + 1] !== part.id) edges++; if (y === 0 || labels[index - width] !== part.id) edges++; if (y === height - 1 || labels[index + width] !== part.id) edges++; }
    const cx = sx / part.area, cy = sy / part.area;
    let xx = 0, yy = 0, xy = 0;
    for (const index of part.pixels) { const x = index % width - cx, y = Math.floor(index / width) - cy; xx += x * x; yy += y * y; xy += x * y; }
    xx /= part.area; yy /= part.area; xy /= part.area;
    const discriminant = Math.sqrt((xx - yy) ** 2 + 4 * xy * xy), major = (xx + yy + discriminant) / 2, minor = (xx + yy - discriminant) / 2, aspect = Math.sqrt((major + .25) / (minor + .25));
    const perimeter = edges * Math.PI / 4, hull = convexHull(boundaryPoints(part, labels, width, height)), solidity = Math.min(1, part.area / Math.max(polygonArea(hull) + perimeter / 2 + 1, 1)), circularity = Math.min(1, 4 * Math.PI * part.area / Math.max(perimeter * perimeter, 1));
    const dist = new Float32Array(localMask.length);
    for (let i = 0; i < dist.length; i++) dist[i] = localMask[i] ? 100000 : 0;
    const straight = .955, diagonal = 1.3693;
    for (let y = 1; y < localHeight - 1; y++) for (let x = 1; x < localWidth - 1; x++) { const i = y * localWidth + x; if (localMask[i]) dist[i] = Math.min(dist[i], dist[i - 1] + straight, dist[i - localWidth] + straight, dist[i - localWidth - 1] + diagonal, dist[i - localWidth + 1] + diagonal); }
    let maxDistance = 0;
    for (let y = localHeight - 2; y >= 1; y--) for (let x = localWidth - 2; x >= 1; x--) { const i = y * localWidth + x; if (localMask[i]) { dist[i] = Math.min(dist[i], dist[i + 1] + straight, dist[i + localWidth] + straight, dist[i + localWidth + 1] + diagonal, dist[i + localWidth - 1] + diagonal); maxDistance = Math.max(maxDistance, dist[i]); } }
    const threshold = Math.max(maxDistance * .72, 1.5), peakMask = new Uint8Array(localMask.length);
    for (let i = 0; i < peakMask.length; i++) peakMask[i] = Number(localMask[i] && dist[i] >= threshold);
    const peaks = Math.max(1, connected(peakMask, localWidth, localHeight).components.filter(p => p.area >= 2).length);
    return { center: [cx, cy], aspect, solidity, circularity, peaks };
  }
  function mean(values) { return values.length ? values.reduce((s, v) => s + v, 0) / values.length : null; }
  function coefficient(values) { const average = mean(values); return average > 0 ? Math.sqrt(values.reduce((s, v) => s + (v - average) ** 2, 0) / values.length) / average * 100 : null; }
  function median(values) { const sorted = values.slice().sort((a, b) => a - b), n = sorted.length; return n ? n % 2 ? sorted[Math.floor(n / 2)] : (sorted[n / 2 - 1] + sorted[n / 2]) / 2 : null; }
  function volumeMedian(values) { const sorted = values.slice().sort((a, b) => a - b), threshold = sorted.reduce((s, v) => s + v ** 3, 0) / 2; let sum = 0; for (const value of sorted) { sum += value ** 3; if (sum >= threshold) return value; } return null; }
  function drawBox(image, bbox, color) {
    const [left, top, width, height] = bbox, put = (x, y) => { const i = (y * image.width + x) * 4; for (let c = 0; c < 3; c++) image.data[i + c] = color[c]; image.data[i + 3] = 255; };
    for (let x = left; x < left + width; x++) { put(x, top); put(x, top + height - 1); }
    for (let y = top; y < top + height; y++) { put(left, y); put(left + width - 1, y); }
  }

  async function analyzeImageData(input, options = {}) {
    const started = Date.now();
    if (!input || !Number.isInteger(input.width) || !Number.isInteger(input.height) || input.width < 8 || input.height < 8 || !input.data || input.data.length !== input.width * input.height * 4 || input.width * input.height > 80000000) throw new Error('ImageData invalido ou imagem excede 80 megapixels.');
    const target = clamp(Math.trunc(positive(option(options, 'analysisLongEdgePx', 'analysis_long_edge_px', 2400), 2400)), 128, 2400), widthInput = positive(option(options, 'paperWidthMm', 'paper_width_mm', 76)), heightInput = positive(option(options, 'paperHeightMm', 'paper_height_mm', 26)), widthMm = Math.max(widthInput, heightInput), heightMm = Math.min(widthInput, heightInput), confirmed = option(options, 'paperSizeConfirmed', 'paper_size_confirmed', false) === true, manualScale = positive(option(options, 'mmPerPixel', 'mm_per_pixel', null));
    if (widthInput === null || heightInput === null) throw new Error('Dimensoes do papel devem ser finitas e positivas.');
    if (option(options, 'mmPerPixel', 'mm_per_pixel', null) !== null && manualScale === null) throw new Error('Escala manual deve ser finita e positiva.');
    const manual = option(options, 'paperCorners', 'paper_corners', null);
    let detected = manual ? { points: canonicalCorners(manual), confidence: 1 } : detectPaper(input, widthMm / heightMm);
    if (detected.points && detected.points.some(p => p[0] < 0 || p[1] < 0 || p[0] >= input.width || p[1] >= input.height)) throw new Error('Os cantos devem ficar dentro da imagem.');
    let image, scale = null, source, warnings = [];
    if (detected.points && (!manualScale || confirmed)) {
      const sides = detected.points.map((p, i) => distance(p, detected.points[(i + 1) % 4])), naturalWidth = (sides[0] + sides[2]) / 2, naturalHeight = (sides[1] + sides[3]) / 2, aspect = confirmed ? widthMm / heightMm : naturalWidth / Math.max(naturalHeight, 1), width = Math.max(2, Math.min(target, Math.round(naturalWidth))), height = Math.max(2, Math.round(width / aspect));
      image = warp(input, detected.points, width, height); scale = confirmed ? widthMm / width : null; source = confirmed ? 'confirmed_paper_dimensions' : 'unconfirmed_paper';
    } else {
      const resized = resize(input, target); image = resized.image; scale = manualScale ? manualScale / resized.scale : null; source = manualScale ? 'manual_scale' : 'uncalibrated';
      if (!detected.points) warnings.push('Papel nao identificado: selecione os quatro cantos e confirme suas dimensoes.');
    }
    if (!scale) warnings.push('Sem calibracao confirmada: apenas pixels, cobertura e contagem visual; sem mm, densidade ou qualidade conclusiva.');
    const margin = Math.min(Math.max(1, Math.round(Math.min(image.width, image.height) * clamp(Number(option(options, 'borderMarginRatio', 'border_margin_ratio', .02)), 0, .12))), Math.floor(Math.min(image.width, image.height) / 4)), width = image.width, height = image.height, mask = new Uint8Array(width * height);
    for (let i = 0; i < mask.length; i++) { const r = image.data[i * 4], g = image.data[i * 4 + 1], b = image.data[i * 4 + 2], maximum = Math.max(r, g, b), minimum = Math.min(r, g, b); mask[i] = Number((maximum - minimum) / Math.max(maximum, 1) >= .12 && Math.max(b - r, (r + b) / 2 - g) >= 15 && b > g * 1.05 && maximum > 25); }
    const parts = connected(mask, width, height), minDiameter = positive(option(options, 'minStainDiameterMm', 'min_stain_diameter_mm', .10), .10), minPixels = Math.max(4, Math.trunc(option(options, 'minComponentPixels', 'min_component_pixels', 9))), maxDiameter = positive(option(options, 'maxStainDiameterMm', 'max_stain_diameter_mm', 2.5), 2.5), rows = clamp(Math.trunc(option(options, 'gridRows', 'grid_rows', 3)), 1, 12), cols = clamp(Math.trunc(option(options, 'gridCols', 'grid_cols', 6)), 1, 12), grid = Array.from({ length: rows }, () => Array(cols).fill(0)), counts = { valid: 0, coalesced: 0, edge: 0, tiny: 0, noise: 0 }, components = [], diameters = [], palette = { valid: [50, 210, 70], coalesced: [255, 150, 30], edge: [40, 190, 255], tiny: [180, 180, 180], noise: [200, 65, 130] };
    const resolutionDiameterPx = 2 * Math.sqrt(minPixels / Math.PI), effectiveMinimumMm = scale ? Math.max(minDiameter, resolutionDiameterPx * scale) : null;
    let coveragePixels = 0;
    for (const part of parts.components) {
      if (part.area < minPixels) { counts.tiny++; continue; }
      for (const index of part.pixels) { const x = index % width, y = Math.floor(index / width); if (x >= margin && x < width - margin && y >= margin && y < height - margin) coveragePixels++; }
      const shape = geometry(part, parts.labels, width, height), diameterPx = 2 * Math.sqrt(part.area / Math.PI), diameterMm = scale ? diameterPx * scale : null, edge = part.left <= margin || part.top <= margin || part.left + part.width >= width - margin || part.top + part.height >= height - margin;
      let label;
      if (diameterMm !== null && diameterMm < minDiameter) label = 'tiny';
      else if (edge) label = 'edge';
      else if (shape.aspect > 4 || shape.solidity < .40) label = 'noise';
      else if (shape.peaks >= 2 || shape.aspect > 1.8 || (shape.solidity < .72 && shape.circularity < .60) || (diameterMm !== null && diameterMm > maxDiameter)) label = 'coalesced';
      else label = 'valid';
      counts[label]++;
      const record = { label, bbox: [part.left, part.top, part.width, part.height], centroid: shape.center.map(v => round(v)), area_px: part.area, diameter_px: round(diameterPx), stain_diameter_um: diameterMm ? round(diameterMm * 1000) : null, aspect_ratio: round(shape.aspect), solidity: round(shape.solidity), circularity: round(shape.circularity), peak_count: shape.peaks };
      if (components.length < 5000) components.push(record);
      if (label === 'valid') { diameters.push(scale ? diameterMm * 1000 : diameterPx); const row = clamp(Math.floor((shape.center[1] - margin) * rows / Math.max(height - 2 * margin, 1)), 0, rows - 1), col = clamp(Math.floor((shape.center[0] - margin) * cols / Math.max(width - 2 * margin, 1)), 0, cols - 1); grid[row][col]++; }
      if (option(options, 'includeOverlayPixels', 'include_overlay_pixels', false)) drawBox(image, record.bbox, palette[label]);
    }
    const area = (width - margin * 2) * (height - margin * 2), density = scale ? counts.valid / (area * scale * scale / 100) : null, spatialCv = counts.valid ? coefficient(grid.flat()) : null, diameterCv = diameters.length ? coefficient(diameters) : null, proxy = scale && diameters.length ? volumeMedian(diameters) : null, nonTiny = counts.valid + counts.coalesced + counts.edge + counts.noise;
    if (counts.coalesced) warnings.push('Manchas coalescidas excluidas da contagem; gotas sobrepostas nao podem ser recuperadas com confianca.');
    if (scale && minDiameter / scale < 3) warnings.push('Resolucao insuficiente para o limiar fisico escolhido: fotografe mais perto, sem zoom digital.');
    if (scale && minDiameter < resolutionDiameterPx * scale) warnings.push('O piso de pixels e maior que o limiar solicitado; o limiar efetivo exibido limita as menores manchas contaveis.');
    if (components.length >= 5000) warnings.push('Overlay limitado a 5000 componentes; contagens incluem todos.');
    warnings.push('Diametros sao de manchas; DV50 proxy pondera diametro da mancha ao cubo e nao mede gotas originais sem fator de espalhamento validado.');
    const dimensions = confirmed && detected.points ? { width: widthMm, height: heightMm } : null;
    const result = { engine_version: ENGINE_VERSION, measurement_status: scale ? 'calibrated' : 'uncalibrated', total_droplets: counts.valid, valid_droplets: counts.valid, candidate_droplets: parts.components.length, double_droplets: counts.coalesced, duplicated_droplets: counts.coalesced, coalesced_components: counts.coalesced, edge_droplets: counts.edge, rejected_noise: counts.noise, rejected_by_size: counts.tiny, estimated_total_impacts: null, coverage_percentage: round(coveragePixels / Math.max(area, 1) * 100), coverage_method: 'stained_pixels_in_inner_roi', density_per_cm2: round(density), cv_coefficient: round(spatialCv), diameter_cv_coefficient: round(diameterCv), dv50_diameter: null, dv50_proxy_um: round(proxy), droplet_class: 'Nao determinada (manchas, sem fator de espalhamento)', mean_diameter: scale && diameters.length ? round(mean(diameters)) : null, min_diameter: scale && diameters.length ? round(diameters.reduce((a, b) => Math.min(a, b), Infinity)) : null, max_diameter: scale && diameters.length ? round(diameters.reduce((a, b) => Math.max(a, b), -Infinity)) : null, stain_diameter: { unit: scale ? 'um' : 'px', count: diameters.length, mean: round(mean(diameters)), median: round(median(diameters)), volume_weighted_proxy_dv50_um: round(proxy), spread_factor_applied: false }, spatial_uniformity: { cv: round(spatialCv), rows, cols, counts: grid, method: 'population_CV_of_isolated_counts_in_equal_area_cells', sample_scope: 'one_collector' }, coalesced_fraction: counts.coalesced / Math.max(nonTiny, 1), paper_detected: !!detected.points, paper_confidence: round(detected.confidence), paper_dimensions_mm: dimensions, analysis_scale_mm_per_px: scale, scale_source: source, calibration: { valid: !!scale, confirmed: !!scale, source, mm_per_px: scale, paper_size_confirmed: confirmed, paper_dimensions_mm: dimensions }, analysis_area_px: area, min_stain_diameter_mm: minDiameter, min_component_pixels: minPixels, effective_min_stain_diameter_mm: round(effectiveMinimumMm, 6), resolution_min_stain_diameter_px: round(resolutionDiameterPx, 6), overlay: { width, height, paper_polygon: detected.points, components, legend: { valid: 'Mancha isolada contada', coalesced: 'Coalescida: excluida', edge: 'Borda: excluida', tiny: 'Abaixo do limiar: excluida', noise: 'Artefato: excluido' } }, warnings, orientation_applied: 'ImageData supplied by decoder; EXIF must be applied before analysis' };
    if (option(options, 'includeOverlayPixels', 'include_overlay_pixels', false)) result.overlay.rgba_data = image.data;
    result.quality = evaluateQuality(result, option(options, 'profile', 'quality_profile', options.application_profile)); result.quality_score = result.quality.score; result.quality_assessment = result.quality.label;
    result.recommendations = warnings.concat(['Indice fuzzy experimental: ' + result.quality.label + '. Nao representa probabilidade de eficacia.']);
    result.processing_time = round((Date.now() - started) / 1000);
    return result;
  }
  const api = Object.freeze({ ENGINE_VERSION, SCREENING_PROFILE, analyzeImageData, evaluateQuality });
  global.SiopaAnalysis = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : self);
