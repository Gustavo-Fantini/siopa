/* Device-only history. Photos never enter a network synchronization queue. */
(function (root) {
  "use strict";
  let databasePromise;
  function open() {
    if (!root.indexedDB) return Promise.reject(new Error("Este navegador não disponibiliza IndexedDB."));
    if (!databasePromise) databasePromise = new Promise((resolve, reject) => {
      const request = root.indexedDB.open("siopa-offline", 1);
      request.onupgradeneeded = () => { const db = request.result; const records = db.createObjectStore("samples", { keyPath: "id" }); records.createIndex("createdAt", "createdAt"); db.createObjectStore("metadata", { keyPath: "key" }); };
      request.onsuccess = () => { const db = request.result; db.onversionchange = () => { db.close(); databasePromise = undefined; }; resolve(db); };
      request.onerror = () => { databasePromise = undefined; reject(request.error); };
      request.onblocked = () => { databasePromise = undefined; reject(new Error("Feche outras abas do SIOPA para abrir o banco local.")); };
    });
    return databasePromise;
  }
  async function transaction(store, mode, action) {
    const db = await open();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(store, mode); let result;
      try { const request = action(tx.objectStore(store)); request.onsuccess = () => { result = request.result; }; }
      catch (error) { reject(error); return; }
      tx.oncomplete = () => resolve(result);
      tx.onerror = () => reject(tx.error || new Error("Falha no banco local."));
      tx.onabort = () => reject(tx.error || new Error("Armazenamento local cancelado."));
    });
  }
  root.SiopaStore = Object.freeze({ open,
    saveSample: sample => transaction("samples", "readwrite", store => store.put(sample)),
    getSample: id => transaction("samples", "readonly", store => store.get(id)),
    deleteSample: id => transaction("samples", "readwrite", store => store.delete(id)),
    listSamples: async () => (await transaction("samples", "readonly", store => store.getAll())).sort((a, b) => b.createdAt.localeCompare(a.createdAt)),
    setMetadata: (key, value) => transaction("metadata", "readwrite", store => store.put({ key, value })),
    getMetadata: async key => (await transaction("metadata", "readonly", store => store.get(key)))?.value,
  });
})(typeof window !== "undefined" ? window : globalThis);
