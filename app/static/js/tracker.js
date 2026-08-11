/*
 * Trove behavioral tracker
 * ------------------------
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
      document.cookie = "trove_sid=" + sid + "; path=/; max-age=86400; SameSite=Lax";
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
    if (queue.length === 0) return Promise.resolve();

    const payload = JSON.stringify({ events: queue.splice(0, queue.length) });

    // Prefer sendBeacon on unload so the request isn't cancelled.
    if (useBeacon && navigator.sendBeacon) {
      // Blob with type text/plain avoids preflight for beacon.
      try {
        navigator.sendBeacon(ENDPOINT, new Blob([payload], { type: "text/plain" }));
        return Promise.resolve();
      } catch (_e) { /* fall through to fetch */ }
    }

    // Return the fetch promise so callers can await the ingest round-trip.
    try {
      return fetch(ENDPOINT, {
        method: "POST",
        body: payload,
        keepalive: true,
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
      }).catch(function () { /* silent */ });
    } catch (_e) { return Promise.resolve(); }
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
        const payload = { label: el.getAttribute("data-track-click") };
        if (el.hasAttribute("data-category")) {
          payload.category = el.getAttribute("data-category");
        }
        if (el.hasAttribute("data-level")) {
          payload.level = el.getAttribute("data-level");
        }
        enqueue({
          event_type: "click",
          product_id: parseInt(el.getAttribute("data-product-id"), 10) || null,
          payload: payload,
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
  // Live Signal UI Updates & Polling
  // -----------------------------------------------------------------------
  async function fetchLiveSignal() {
    try {
      const resp = await fetch("/events/live-signal");
      if (!resp.ok) return;
      const data = await resp.json();

      // 1. Update top bar status text
      const statusTextEl = document.getElementById("agentLiveStatusText");
      if (statusTextEl && data.ai_signal_summary) {
        statusTextEl.textContent = data.ai_signal_summary;
      }

      // 2. Update "Your Signal" panel if present on product detail screen
      const summaryTextEl = document.getElementById("signalSummaryText");
      if (summaryTextEl && data.ai_signal_summary) {
        summaryTextEl.textContent = data.ai_signal_summary;
      }

      const badgeEl = document.getElementById("signalEngagementBadge");
      if (badgeEl && data.engagement_level) {
        badgeEl.textContent = data.engagement_level;
      }

      // Render category affinity progress bars
      const affinityBarsEl = document.getElementById("signalAffinityBars");
      if (affinityBarsEl && data.top_categories && data.top_categories.length > 0) {
        affinityBarsEl.innerHTML = data.top_categories.map(tc => `
          <div class="affinity-item">
            <div class="affinity-meta">
              <span>${escapeHtml(tc.category)}</span>
              <span class="affinity-pct">${tc.percentage}%</span>
            </div>
            <div class="affinity-bar">
              <div class="affinity-fill" style="width: ${tc.percentage}%;"></div>
            </div>
          </div>
        `).join("");
      }

      // Render search query chips
      const chipsEl = document.getElementById("signalSearchChips");
      if (chipsEl) {
        if (data.recent_searches && data.recent_searches.length > 0) {
          chipsEl.innerHTML = data.recent_searches.map(q => `
            <span class="signal-chip">"${escapeHtml(q)}"</span>
          `).join("");
        } else {
          chipsEl.innerHTML = '<span class="signal-chip muted-chip">No recent search terms</span>';
        }
      }

      // Render latest observation feed log
      const feedListEl = document.getElementById("signalFeedList");
      if (feedListEl && data.latest_events && data.latest_events.length > 0) {
        feedListEl.innerHTML = data.latest_events.map(ev => `
          <div class="signal-feed-item">
            <span class="feed-dot"></span>
            <span class="feed-text">${escapeHtml(ev.label)}</span>
            <span class="feed-time">${escapeHtml(ev.time)}</span>
          </div>
        `).join("");
      }

      // Render live recommended products
      const recoContainerEl = document.getElementById("signalRecoContainer");
      if (recoContainerEl) {
        if (data.recommended_products && data.recommended_products.length > 0) {
          recoContainerEl.innerHTML = data.recommended_products.map(p => `
            <a href="/products/${p.id}" class="signal-reco-card" target="_blank" rel="noopener noreferrer">
              ${p.image_url ? `<img src="${p.image_url}" alt="${escapeHtml(p.title)}" class="signal-reco-thumb" onerror="this.onerror=null;this.src='https://images.unsplash.com/photo-1518186285589-2f7649de83e0?w=600&auto=format&fit=crop';">` : ''}
              <div class="signal-reco-info">
                <div class="signal-reco-title">${escapeHtml(p.title)}</div>
                <div class="signal-reco-meta">
                  <span class="signal-reco-price">$${p.price.toFixed(2)}</span>
                  <span>${escapeHtml(p.category || '')}</span>
                </div>
              </div>
            </a>
          `).join("");
        } else {
          recoContainerEl.innerHTML = '<div class="signal-reco-loading muted small">No recommendations yet. Browse to generate picks!</div>';
        }
      }

      // Render recent recommendations history timeline
      const recoHistoryEl = document.getElementById("signalRecoHistory");
      if (recoHistoryEl) {
        if (data.recent_recommendations && data.recent_recommendations.length > 0) {
          recoHistoryEl.innerHTML = data.recent_recommendations.map(r => `
            <a href="/recommendations" class="signal-history-item">
              <div class="signal-history-top">
                <span class="signal-history-source-badge ${r.source === 'scheduled' ? 'scheduled' : 'web'}">${escapeHtml(r.source)}</span>
                <span class="signal-history-time">${escapeHtml(r.created_at)}</span>
              </div>
              <div class="signal-history-narrative">${escapeHtml(r.narrative_snippet)}</div>
              <div class="signal-history-meta">${r.product_count} product${r.product_count !== 1 ? 's' : ''} recommended</div>
            </a>
          `).join("");
        } else {
          recoHistoryEl.innerHTML = '<div class="signal-reco-loading muted small">No recommendation history yet.</div>';
        }
      }
    } catch (_err) {
      // Ignore background signal errors
    }
  }


  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // -----------------------------------------------------------------------
  // Public tiny API in case a template wants to fire a custom event
  // -----------------------------------------------------------------------
  window.Trove = window.Trove || {};
  window.Trove.track = enqueue;
  window.Trove.flush = function () { flush(false); };
  window.Trove.fetchLiveSignal = fetchLiveSignal;

  // -----------------------------------------------------------------------
  // Boot
  // -----------------------------------------------------------------------
  async function start() {
    trackPageView();
    trackSearchIfPresent();
    trackClicks();
    trackDwell();
    wireUnloadFlush();

    // Flush queued events (page view, search) and wait for the server to
    // ingest them BEFORE the first signal fetch.  This guarantees the
    // live-signal response includes the current page's product category
    // so recommendations are contextually correct on first paint.
    try { await flush(false); } catch (_e) { /* proceed anyway */ }

    fetchLiveSignal();
    setInterval(fetchLiveSignal, 6000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();

