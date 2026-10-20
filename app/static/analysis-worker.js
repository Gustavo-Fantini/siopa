"use strict";
importScripts("analysis-engine.js");
self.onmessage = async event => {
  const { id, imageData, options } = event.data || {};
  try {
    if (!imageData?.data || !imageData.width || !imageData.height) throw new Error("Imagem ausente no worker.");
    const result = await self.SiopaAnalysis.analyzeImageData(imageData, options || {});
    self.postMessage({ id, result, engineVersion: self.SiopaAnalysis.ENGINE_VERSION });
  } catch (error) { self.postMessage({ id, error: { message: error.message || String(error), name: error.name || "Error" } }); }
};
