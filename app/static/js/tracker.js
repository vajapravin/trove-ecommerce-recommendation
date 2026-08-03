/*
 * Trove behavioral tracker
 * ----------------------------
 * Buffers events on the client and flushes them in batches so tracking never
 * blocks the UI. Key properties:
 *
 *   - All work runs in event listeners; no synchronous XHR.
 *   - Batches flush on: MAX_QUEUE (10 events) OR FLUSH_INTERVAL_MS (5s) OR
 *     page visibility change / pagehide.
 *   - On unload we use navigator.sendBeacon so events survive tab close.
 *   - High-frequency signals (dwell ticks, scroll) are throttled to at most
 *     one entry per second per type.
 *   - Session IDs are stored in sessionStorage — cleared when the tab closes.
 */

(function () {
  "use strict";

  const ENDPOINT = "/events/ingest";
  const MAX_QUEUE = 10;
  const FLUSH_INTERVAL_MS = 5000;
  const THROTTLED_TYPES = new Set(["dwell", "scroll"]);
  const THROTTLE_MS = 1000;

  const queue = [];
  const lastEmitted = Object.create(null); // event_type -> ms timestamp
  let flushTimer = null;

  // -----------------------------------------------------------------------
  // Session id
  // -----------------------------------------------------------------------
  function getSessionId() {
    try {
      let sid = sessionStorage.getItem("trove_sid");
      if (!sid) {
        sid = "s_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
        sessionStorage.setItem("trove_sid", sid);
      }
      return sid;
    } catch (_e) {
      return null;
    }
  }
  const SESSION_ID = getSessionId();

  // -----------------------------------------------------------------------
  // Core enqueue / flush
  // -----------------------------------------------------------------------
  function enqueue(evt) {
    if (THROTTLED_TYPES.has(evt.event_type)) {
      const now = Date.now();
      if (lastEmitted[evt.event_type] && now - lastEmitted[evt.event_type] < THROTTLE_MS) {
        return;
      }
      lastEmitted[evt.event_type] = now;
    }
    queue.push({
      event_type: evt.event_type,
      product_id: evt.product_id || null,
      path: evt.path || location.pathname,
      session_id: SESSION_ID,
      ts: new Date().toISOString(),
      payload: evt.payload || null,
    });
    if (queue.length >= MAX_QUEUE) {
      flush();
    } else if (!flushTimer) {
      flushTimer = setTimeout(flush, FLUSH_INTERVAL_MS);
    }
  }

  function flush(useBeacon) {
    if (flushTimer) {
      clearTimeout(flushTimer);
      flushTimer = null;
    }
    if (queue.length === 0) return;

    const payload = JSON.stringify({ events: queue.splice(0, queue.length) });

    // Prefer sendBeacon on unload so the request isn't cancelled.
    if (useBeacon && navigator.sendBeacon) {
      // Blob with type text/plain avoids preflight for beacon.
      try {
        navigator.sendBeacon(ENDPOINT, new Blob([payload], { type: "text/plain" }));
        return;
      } catch (_e) { /* fall through to fetch */ }
    }

    // Fire-and-forget fetch — keepalive lets small requests survive unload too.
    try {
      fetch(ENDPOINT, {
        method: "POST",
        body: payload,
        keepalive: true,
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
      }).catch(function () { /* silent */ });
    } catch (_e) { /* silent */ }
  }

  // -----------------------------------------------------------------------
  // Automatic instrumentation
  // -----------------------------------------------------------------------
  function trackPageView() {
    const productPage = document.querySelector("[data-product-page]");
    if (productPage) {
      enqueue({
        event_type: "view_product",
        product_id: parseInt(productPage.getAttribute("data-product-id"), 10) || null,
      });
    } else {
      enqueue({ event_type: "view_page" });
    }
  }

  function trackSearchIfPresent() {
    const params = new URLSearchParams(location.search);
    const q = params.get("q");
    if (q && q.trim() && location.pathname === "/catalog") {
      enqueue({
        event_type: "search",
        payload: { q: q.trim(), category: params.get("category") || null },
      });
    }
  }

  function trackClicks() {
    document.addEventListener("click", function (e) {
      const el = e.target && e.target.closest ? e.target.closest("[data-track-click]") : null;
      if (el) {
        enqueue({
          event_type: "click",
          product_id: parseInt(el.getAttribute("data-product-id"), 10) || null,
          payload: { label: el.getAttribute("data-track-click") },
        });
        return;
      }
      // Product card clicks (implicit)
      const card = e.target && e.target.closest ? e.target.closest(".product-card[data-product-id]") : null;
      if (card) {
        enqueue({
          event_type: "click",
          product_id: parseInt(card.getAttribute("data-product-id"), 10) || null,
          payload: { label: "product-card" },
        });
      }
    }, { passive: true });
  }

  function trackDwell() {
    // Emit a "dwell" tick every 10 seconds the tab is visible.
    let dwellSeconds = 0;
    setInterval(function () {
      if (document.visibilityState === "visible") {
        dwellSeconds += 10;
        enqueue({ event_type: "dwell", payload: { seconds: 10, total: dwellSeconds } });
      }
    }, 10000);
  }

  function wireUnloadFlush() {
    // Modern: flush on visibilitychange -> hidden (fires reliably on mobile too)
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "hidden") flush(true);
    });
    // Belt and braces: pagehide fires on bfcache navigation
    window.addEventListener("pagehide", function () { flush(true); });
  }

  // -----------------------------------------------------------------------
  // Public tiny API in case a template wants to fire a custom event
  // -----------------------------------------------------------------------
  window.Trove = window.Trove || {};
  window.Trove.track = enqueue;
  window.Trove.flush = function () { flush(false); };

  // -----------------------------------------------------------------------
  // Boot
  // -----------------------------------------------------------------------
  function start() {
    trackPageView();
    trackSearchIfPresent();
    trackClicks();
    trackDwell();
    wireUnloadFlush();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
