/* Real Chromium integration: worker, IndexedDB, cache, reload, no photo HTTP requests. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { spawn } = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const staticRoot = path.join(root, 'app/static');
const profile = path.join(root, '.tools', `browser-test-${Date.now()}`);
const browserPath = process.env.SIOPA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const requests = [];
const catalog = JSON.parse(fs.readFileSync(path.join(staticRoot, 'crops.json'), 'utf8').replace(/^\uFEFF/, ''));
const server = http.createServer((req, res) => {
  requests.push({ method: req.method, path: req.url });
  if (req.url.startsWith('/api/v1/offline/bootstrap')) {
    res.setHeader('Content-Type', 'application/json');
    const environment = { fetched_at: '2000-01-01T00:00:00Z', expires_at: '2000-01-02T00:00:00Z', stale: true, availability: 'partial', coordinates: { latitude: 0, longitude: 0 }, weather: { current: { temperature: 20, humidity: 60, wind_speed: 5, source: 'test_fixture' } }, soil: { availability: 'partial', ph: 6.1, source: 'test_fixture', fetched_at: '2000-01-01T00:00:00Z', properties: {} }, terrain: { availability: 'available', elevation_m: 100, source: 'test_fixture', fetched_at: '2000-01-01T00:00:00Z' } };
    res.end(JSON.stringify({ schema_version: 1, generated_at: new Date().toISOString(), crops: catalog.crops, quality_profiles: catalog.quality_profiles, environment, capabilities: { dataset_api: false } })); return;
  }
  const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
  const relative = pathname === '/' ? 'index.html' : pathname.startsWith('/static/') ? pathname.slice(8) : pathname.slice(1);
  const file = path.resolve(staticRoot, relative);
  if (!file.startsWith(staticRoot + path.sep) || !fs.existsSync(file)) { res.writeHead(404); res.end(); return; }
  const ext = path.extname(file), types = { '.js': 'application/javascript', '.css': 'text/css', '.html': 'text/html', '.json': 'application/json', '.svg': 'image/svg+xml', '.webmanifest': 'application/manifest+json' };
  res.setHeader('Content-Type', types[ext] || 'application/octet-stream'); fs.createReadStream(file).pipe(res);
});
let browser, socket;
async function waitFor(check, label, limit = 30000) { const end = Date.now() + limit; while (Date.now() < end) { try { const value = await check(); if (value) return value; } catch {} await new Promise(r => setTimeout(r, 100)); } throw new Error(`Timeout: ${label}`); }
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  browser = spawn(browserPath, ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank'], { windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'] });
  let stderr = ''; browser.stderr.on('data', data => { stderr += data; });
  const wsUrl = await waitFor(() => stderr.match(/DevTools listening on (ws:\/\/[^\s]+)/)?.[1], 'DevTools');
  socket = new WebSocket(wsUrl); await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  let next = 0; const pending = new Map();
  socket.onmessage = event => { const msg = JSON.parse(event.data); const request = pending.get(msg.id); if (request) { pending.delete(msg.id); msg.error ? request.reject(new Error(JSON.stringify(msg.error))) : request.resolve(msg.result); } };
  function send(method, params = {}, sessionId) { return new Promise((resolve, reject) => { const id = ++next; const timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)); }, 15000); pending.set(id, { resolve: value => { clearTimeout(timer); resolve(value); }, reject: error => { clearTimeout(timer); reject(error); } }); socket.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) })); }); }
  const { targetId } = await send('Target.createTarget', { url: origin });
  const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
  await send('Network.enable', {}, sessionId);
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true }, sessionId);
  const evaluate = async expression => { const out = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true }, sessionId); if (out.exceptionDetails) throw new Error(out.exceptionDetails.exception?.description || JSON.stringify(out.exceptionDetails)); return out.result.value; };
  await waitFor(() => evaluate(`typeof SiopaStore !== 'undefined' && document.getElementById('cropType').options.length > 50 && document.getElementById('offlineStatus').textContent.includes('prontos')`), 'catalog and service worker', 45000);
  await waitFor(() => evaluate(`state.snapshot?.environment?.stale === true`), 'bootstrap context');
  assert.match(await evaluate(`document.getElementById('snapshotStatus').textContent`), /Validade vencida/);
  assert.match(await evaluate(`document.getElementById('terrainMetrics').textContent`), /Altitude estimada100 m/);
  assert.match(await evaluate(`document.getElementById('soilMetrics').textContent`), /pH estimado/);
  const homeScreenshot = await send('Page.captureScreenshot', { format: 'png' }, sessionId);
  fs.writeFileSync(path.join(root, '.tools/mobile-home.png'), Buffer.from(homeScreenshot.data, 'base64'));
  await send('Network.emulateNetworkConditions', { offline: true, latency: 0, downloadThroughput: 0, uploadThroughput: 0 }, sessionId);
  await evaluate(`(async()=>{const c=document.createElement('canvas');c.width=600;c.height=300;const x=c.getContext('2d');x.fillStyle='#46503c';x.fillRect(0,0,600,300);x.fillStyle='#f0da41';x.fillRect(50,70,500,170);x.fillStyle='#2d378c';for(let row=0;row<3;row++)for(let col=0;col<8;col++){x.beginPath();x.arc(85+col*58,100+row*55,4,0,Math.PI*2);x.fill()}const b=await new Promise(r=>c.toBlob(r,'image/png'));await loadImage(new File([b],'offline-paper.png',{type:'image/png'}));document.getElementById('paperSizeConfirmed').checked=false;document.getElementById('analysisForm').dispatchEvent(new Event('submit',{cancelable:true}));})()`);
  await waitFor(() => evaluate(`!state.analyzing && state.record !== null`), 'uncalibrated offline analysis');
  const uncalibrated = await evaluate(`({valid:state.record.result.calibration.valid,density:state.record.result.density_per_cm2,score:state.record.result.quality.score,display:document.getElementById('analysisMetrics').textContent})`);
  assert.equal(uncalibrated.valid, false); assert.equal(uncalibrated.density, null); assert.equal(uncalibrated.score, null);
  assert.match(uncalibrated.display, /Diâmetro mediano da manchaIndisponível/);
  await evaluate(`state.corners=[{x:50,y:70},{x:550,y:70},{x:550,y:240},{x:50,y:240}];document.getElementById('manualCorners').checked=true;document.getElementById('paperSizeConfirmed').checked=true;document.getElementById('analysisForm').dispatchEvent(new Event('submit',{cancelable:true}));`);
  await waitFor(() => evaluate(`!state.analyzing && state.record?.result.calibration.valid`), 'calibrated offline analysis');
  const measured = await evaluate(`(async()=>({count:state.record.result.total_droplets,quality:state.record.result.quality.status,score:state.record.result.quality.score,execution:state.record.execution_mode,saved:document.getElementById('saveStatus').textContent,records:await SiopaStore.listSamples().then(r=>r.length)}))()`);
  assert.ok(measured.count > 0); assert.equal(measured.quality, 'provisional'); assert.ok(Number.isFinite(measured.score)); assert.equal(measured.execution, 'worker'); assert.equal(measured.records, 2); assert.match(measured.saved, /salvos/);
  await send('Page.reload', {}, sessionId);
  await waitFor(() => evaluate(`typeof SiopaStore !== 'undefined' && document.querySelectorAll('.history-item').length === 2`), 'offline reload and history');
  await evaluate(`document.querySelector('.history-item button').click()`);
  await waitFor(() => evaluate(`state.record !== null && !document.getElementById('resultsSection').hidden`), 'open stored image and result');
  const restored = await evaluate(`({count:state.record.result.total_droplets,bytes:state.record.imageBlob.size,overlay:state.record.overlayBlob.size,crops:document.getElementById('cropType').options.length})`);
  assert.equal(restored.count, measured.count); assert.ok(restored.bytes > 0 && restored.overlay > 0); assert.ok(restored.crops >= 100);
  const resultScreenshot = await send('Page.captureScreenshot', { format: 'png' }, sessionId);
  fs.writeFileSync(path.join(root, '.tools/mobile-result.png'), Buffer.from(resultScreenshot.data, 'base64'));
  await evaluate(`(async()=>{const saved=state.record;window.Worker=function(){throw new Error('test fallback')};await loadImage(new File([saved.imageBlob],'compatibility.png',{type:'image/png'}));document.getElementById('analysisForm').dispatchEvent(new Event('submit',{cancelable:true}));})()`);
  await waitFor(() => evaluate(`!state.analyzing && state.record?.execution_mode === 'main_thread'`), 'main thread compatibility fallback');
  assert.equal(await evaluate(`state.record.result.calibration.valid`), false);
  assert.equal(requests.filter(r => r.method !== 'GET').length, 0, 'photos must never be uploaded');
  const report = { passed: true, checks: ['worker offline', 'uncalibrated quantities null', 'confirmed manual geometry', 'fuzzy provisional', 'IndexedDB photos and results', 'service worker offline reload', 'history reopen', 'main-thread compatibility fallback', 'stale context/source labels', 'soil/terrain estimates', 'no HTTP photo upload'], measured, restored };
  fs.writeFileSync(path.join(root, '.tools/mobile-browser-test-result.json'), JSON.stringify(report, null, 2)); console.log(JSON.stringify(report));
  await send('Browser.close');
})().catch(error => { fs.writeFileSync(path.join(root, '.tools/mobile-browser-test-result.json'), JSON.stringify({ passed: false, error: error.stack })); console.error(error.stack); process.exitCode = 1; }).finally(async () => {
  socket?.close(); browser?.kill(); server.close();
  await new Promise(r => setTimeout(r, 700));
  const allowed = path.resolve(root, '.tools') + path.sep;
  if (path.resolve(profile).startsWith(allowed)) { try { fs.rmSync(profile, { recursive: true, force: true }); } catch {} }
});
