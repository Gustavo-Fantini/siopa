'use strict';
const fs = require('node:fs');
const engine = require('../app/static/analysis-engine.js');
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', async () => {
  try {
    const fixture = JSON.parse(input);
    const result = await engine.analyzeImageData({ width: fixture.width, height: fixture.height, data: new Uint8ClampedArray(fixture.data) }, fixture.options);
    process.stdout.write(JSON.stringify(result));
  } catch (error) { process.stderr.write(error.stack); process.exitCode = 1; }
});
