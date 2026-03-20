/**
 * notion-sync.js — Sync to Notion button handler.
 *
 * Connects to the local serve.py server at /api/notion-sync,
 * reads the NDJSON progress stream, and updates the UI.
 *
 * This file is copied to site/assets/ by the site generator.
 */

(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Panel template (injected into #notion-sync-panel on first click)
  // ---------------------------------------------------------------------------
  const PANEL_INNER = `
    <div class="sync-progress-header">
      <span class="sync-spinner" aria-hidden="true"></span>
      <span class="sync-status-text">Syncing…</span>
    </div>
    <ul class="sync-section-list" aria-live="polite"></ul>
    <p class="sync-summary"></p>
  `;

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  let syncing = false;

  // ---------------------------------------------------------------------------
  // Init on DOM ready
  // ---------------------------------------------------------------------------
  document.addEventListener('DOMContentLoaded', function () {
    const btn = document.getElementById('notion-sync-btn');
    if (!btn) return;
    btn.addEventListener('click', startSync);
  });

  // ---------------------------------------------------------------------------
  // Main sync flow
  // ---------------------------------------------------------------------------
  async function startSync() {
    if (syncing) return;
    syncing = true;

    const btn = document.getElementById('notion-sync-btn');
    const panel = document.getElementById('notion-sync-panel');

    // Set up panel
    btn.disabled = true;
    panel.innerHTML = PANEL_INNER;
    panel.removeAttribute('hidden');

    const statusText = panel.querySelector('.sync-status-text');
    const sectionList = panel.querySelector('.sync-section-list');
    const summary = panel.querySelector('.sync-summary');
    const spinner = panel.querySelector('.sync-spinner');

    // Map slug → <li> element for fast updates
    const sectionItems = {};
    let topicTotal = 0;
    let errorCount = 0;

    function setStatus(text) {
      if (statusText) statusText.textContent = text;
    }

    function addSectionItem(slug, label) {
      const li = document.createElement('li');
      li.className = 'active';
      li.dataset.slug = slug;
      li.textContent = label;
      sectionList.appendChild(li);
      sectionItems[slug] = li;
      return li;
    }

    function handleEvent(evt) {
      switch (evt.type) {
        case 'start':
          setStatus(`Syncing ${evt.total_sections} sections…`);
          break;

        case 'section_start':
          addSectionItem(evt.slug, evt.label);
          setStatus(`Syncing: ${evt.label}`);
          break;

        case 'topic_done':
          topicTotal++;
          setStatus(`Syncing topics… (${topicTotal} done)`);
          break;

        case 'section_done': {
          const li = sectionItems[evt.slug];
          if (li) {
            li.className = 'done';
            li.textContent = `${evt.label} (${evt.topic_count} topics)`;
          }
          break;
        }

        case 'error': {
          errorCount++;
          const context = evt.topic ? `${evt.slug}/${evt.topic}` : evt.slug;
          if (context && sectionItems[evt.slug]) {
            const errLi = document.createElement('li');
            errLi.className = 'error';
            errLi.textContent = `Error in ${context}: ${evt.message}`;
            sectionList.appendChild(errLi);
          } else {
            // Fatal / config error — show prominently
            setStatus(`Error: ${evt.message}`);
            if (spinner) spinner.style.display = 'none';
          }
          break;
        }

        case 'done':
          if (spinner) spinner.style.display = 'none';
          setStatus('Sync complete ✓');
          summary.textContent = `${evt.total_topics} topics synced across ${Object.keys(sectionItems).length} sections` +
            (evt.total_errors > 0 ? ` (${evt.total_errors} errors)` : '') + '.';
          btn.disabled = false;
          syncing = false;
          break;

        default:
          break;
      }
    }

    // ---------------------------------------------------------------------------
    // Fetch + stream
    // ---------------------------------------------------------------------------
    try {
      const response = await fetch('/api/notion-sync', { method: 'POST' });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      if (!response.body) {
        throw new Error('Streaming not supported by this browser.');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // Split on newlines; keep incomplete last line in buffer
        const lines = buffer.split('\n');
        buffer = lines.pop(); // last element may be incomplete

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          try {
            const evt = JSON.parse(trimmed);
            handleEvent(evt);
          } catch {
            // Ignore malformed lines
          }
        }
      }

      // Process any remaining buffered content
      if (buffer.trim()) {
        try {
          handleEvent(JSON.parse(buffer.trim()));
        } catch {
          // Ignore
        }
      }

    } catch (err) {
      if (spinner) spinner.style.display = 'none';
      const isNetworkError = err instanceof TypeError && err.message.toLowerCase().includes('fetch');
      if (isNetworkError) {
        setStatus('Cannot connect to local server.');
        summary.textContent = 'Make sure the server is running: python3 scripts/serve.py';
      } else {
        setStatus(`Error: ${err.message}`);
      }
      btn.disabled = false;
      syncing = false;
    }
  }
})();
