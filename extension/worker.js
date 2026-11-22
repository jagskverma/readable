const cacheLimit = 5000;
let database;

function openCache() {
  database ||= new Promise((resolve, reject) => {
    const open = indexedDB.open("readable", 1);
    open.onupgradeneeded = () => {
      const store = open.result.createObjectStore("rewrites", {keyPath: "key"});
      store.createIndex("saved", "saved");
    };
    open.onsuccess = () => resolve(open.result);
    open.onerror = () => reject(open.error);
  }).catch(error => {
    database = undefined;
    throw error;
  });
  return database;
}

async function readCache(keys) {
  const db = await openCache();
  const store = db.transaction("rewrites").objectStore("rewrites");
  return Promise.all(keys.map(key => new Promise((resolve, reject) => {
    const request = store.get(key);
    request.onsuccess = () => resolve(request.result?.texts ?? null);
    request.onerror = () => reject(request.error);
  })));
}

async function saveCache(entries) {
  if (!entries.length) return;
  const db = await openCache();
  await new Promise((resolve, reject) => {
    const tx = db.transaction("rewrites", "readwrite");
    tx.oncomplete = resolve;
    tx.onabort = () => reject(tx.error);
    const store = tx.objectStore("rewrites");
    const saved = Date.now();
    for (const entry of entries) store.put({...entry, saved});
    const count = store.count();
    count.onsuccess = () => {
      let excess = count.result - cacheLimit;
      if (excess <= 0) return;
      const oldest = store.index("saved").openCursor();
      oldest.onsuccess = () => {
        const cursor = oldest.result;
        if (!cursor || excess-- <= 0) return;
        cursor.delete();
        cursor.continue();
      };
    };
  });
}

chrome.action.onClicked.addListener(async tab => {
  try {
    await chrome.scripting.executeScript({target: {tabId: tab.id}, files: ["page.js"]});
  } catch {
    await chrome.action.setBadgeText({tabId: tab.id, text: "!"});
    await chrome.action.setTitle({tabId: tab.id, title: "Open a web article to use Readable."});
  }
});

chrome.runtime.onConnect.addListener(port => {
  if (port.name !== "rewrite" || port.sender.id !== chrome.runtime.id || !port.sender.tab) return;
  const pending = new Map();
  let native;
  let closed = false;

  function post(message) {
    if (!closed) port.postMessage(message);
  }

  port.onMessage.addListener(async message => {
    if (message.lookup) {
      const keys = await Promise.all(message.lookup.map(async source => {
        const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(source));
        return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
      }));
      const cached = await readCache(keys).catch(() => keys.map(() => null));
      post({keys, cached});
      return;
    }
    if (!native) {
      native = chrome.runtime.connectNative("local.readable.rewriter");
      native.onMessage.addListener(async reply => {
        const batch = pending.get(reply.batch);
        if (!batch) return;
        if (Number.isInteger(reply.block)) {
          batch.entries.push({key: batch.blocks[reply.block].key, texts: reply.texts});
          post(reply);
          return;
        }
        pending.delete(reply.batch);
        const saved = await saveCache(batch.entries).then(() => true, () => false);
        post({...reply, saved});
      });
      native.onDisconnect.addListener(() => {
        const error = chrome.runtime.lastError?.message || "The Mac helper stopped.";
        post({error});
      });
    }
    const {batch, blocks} = message;
    pending.set(batch, {blocks, entries: []});
    native.postMessage({batch, blocks: blocks.map(({slots, context}) => context ? {slots, context} : {slots})});
  });
  port.onDisconnect.addListener(() => {
    closed = true;
    native?.disconnect();
    // Retain complete paragraphs if the reader toggles off during a batch.
    for (const {entries} of pending.values()) void saveCache(entries).catch(() => {});
    pending.clear();
  });
});
