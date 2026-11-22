(() => {
  // Each document has its own toggle state. Only the rewrite cache survives a reload.
  if (globalThis.readableSession) {
    globalThis.readableSession.restore();
    return;
  }

  const root = document.querySelector("main") || document.querySelector("article") || document.body;
  const skip = "pre,code,kbd,samp,math,svg,canvas,script,style,noscript,textarea,input,select,button,nav,footer,[role=navigation],[contenteditable]:not([contenteditable=false]),[hidden],[aria-hidden=true],.katex,.MathJax,mjx-container,[data-rehype-pretty-code-fragment],.mermaid,[role=img]";
  const boundary = "p,h1,h2,h3,h4,h5,h6,li,blockquote,figcaption,caption,th,td,dt,dd,div,section,article,aside,summary";
  const groups = new Map();
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const parent = node.parentElement;
    const raw = node.data;
    if (!raw.trim() || !parent || parent.closest(skip) || !parent.getClientRects().length) continue;
    const block = parent.closest(boundary) || root;
    if (!groups.has(block)) groups.set(block, []);
    groups.get(block).push({node, raw, applied: null});
  }

  const box = document.createElement("div");
  box.setAttribute("role", "status");
  Object.assign(box.style, {position:"fixed", bottom:"18px", right:"18px", zIndex:"2147483647",
    background:"#182525", color:"white", padding:"10px 14px", borderRadius:"8px",
    font:"14px/1.4 system-ui", maxWidth:"380px", boxShadow:"0 2px 10px #0003"});
  document.documentElement.append(box);
  const show = message => { box.textContent = message; };
  const session = {restore};
  globalThis.readableSession = session;
  let port;
  let finished = false;

  function restore() {
    finished = true;
    port?.disconnect();
    for (const items of groups.values()) {
      for (const {node, raw, applied} of items) {
        // The page may have updated this node since we rewrote it.
        if (node.data === applied) node.data = raw;
      }
    }
    box.remove();
    delete globalThis.readableSession;
  }

  function apply(items, texts) {
    items.forEach((item, i) => {
      if (!item.node.isConnected || item.node.data !== item.raw) return;
      item.applied = item.raw.match(/^\s*/)[0] + texts[i].trim() + item.raw.match(/\s*$/)[0];
      item.node.data = item.applied;
    });
  }

  function finish(message, failed = false) {
    if (finished) return;
    finished = true;
    port?.disconnect();
    show(message);
    if (!failed) setTimeout(() => box.remove(), 4000);
  }

  async function start() {
    if (!groups.size) {
      finish("No readable prose found");
      return;
    }
    show("Checking saved rewrites…");
    const url = new URL(location.href);
    url.hash = "";
    const blocks = Array.from(groups, ([element, items]) => {
      const rect = element.getBoundingClientRect();
      const slots = items.map(item => item.raw.trim());
      // Capture all inline context for invalidation and send only a bounded excerpt.
      const context = items.length > 1 || element.querySelector("code,math,.katex")
        ? element.innerText : "";
      return {source: JSON.stringify([1, url.href, element.tagName, slots, context]), items, slots,
        context: context.slice(0, 900), visible: rect.bottom > 0 && rect.top < innerHeight,
        distance: rect.bottom < 0 ? -rect.bottom : Math.max(rect.top - innerHeight, 0)};
    });
    blocks.sort((a, b) => Number(b.visible) - Number(a.visible) || a.distance - b.distance);

    port = chrome.runtime.connect({name: "rewrite"});
    port.onDisconnect.addListener(() => {
      finish("Lost connection to the helper. Click Readable to restore, then retry.", true);
    });
    const batches = [];
    let next = 0;
    let pending = 0;
    let done = 0;
    let firstError;
    let cacheWriteFailed = false;

    function send() {
      while (!firstError && pending < 5 && next < batches.length) {
        const batch = batches[next];
        pending++;
        port.postMessage({batch: next++, blocks: batch.map(({key, slots, context}) => ({key, slots, context}))});
      }
      if (!pending) {
        if (firstError) finish(firstError + " Click Readable to restore, then retry.", true);
        else if (cacheWriteFailed) finish("Page rewritten, but Readable could not save it locally.");
        else finish("Page rewritten · click Readable to restore");
      } else {
        show("Rewriting · " + done + " of " + batches.length + " batches finished");
      }
    }

    port.onMessage.addListener(reply => {
      if (finished) return;
      if ("cached" in reply) {
        let batch = [];
        let size = 0;
        blocks.forEach((block, i) => {
          block.key = reply.keys[i];
          const hit = reply.cached[i];
          if (hit?.length === block.items.length) {
            apply(block.items, hit);
            return;
          }
          const cost = block.slots.reduce((total, slot) => total + slot.length + 4, block.context.length + 20);
          // Give the visible text a small first request and keep the other lanes busy.
          const limit = batches.length === 0 ? 1600 : 4200;
          if (batch.length && (size + cost > limit || batch.length >= 28)) {
            batches.push(batch);
            batch = [];
            size = 0;
          }
          batch.push(block);
          size += cost;
        });
        if (batch.length) batches.push(batch);
        if (!batches.length) finish("Saved rewrite applied · click Readable to restore");
        else send();
        return;
      }

      const batch = batches[reply.batch];
      if (!batch) {
        finish((reply.error || "Incomplete rewrite.") + " Click Readable to restore, then retry.", true);
        return;
      }
      if (Number.isInteger(reply.block)) {
        apply(batch[reply.block].items, reply.texts);
        return;
      }
      pending--;
      if (reply.error) firstError ||= reply.error;
      else if (reply.complete) {
        cacheWriteFailed ||= !reply.saved;
        done++;
      } else {
        firstError ||= "Incomplete rewrite.";
      }
      send();
    });
    port.postMessage({lookup: blocks.map(({source}) => source)});
  }

  start().catch(() => finish("Readable could not start. Click Readable to restore, then retry.", true));
})();
