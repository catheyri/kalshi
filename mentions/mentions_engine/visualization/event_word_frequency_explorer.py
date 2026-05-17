from __future__ import annotations

import json


def render_event_word_frequency_explorer(payload: dict) -> str:
    data_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).replace("</", "<\\/")
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mention Event Word Explorer</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f4;
      --ink: #162126;
      --muted: #5d6870;
      --line: #ccd6d1;
      --panel: #ffffff;
      --panel-alt: #edf3ef;
      --accent: #0f766e;
      --accent-dark: #0a5d57;
      --focus: #1f4e8c;
      --yes: #147d3f;
      --no: #b03232;
      --open: #8a640c;
    }
    * {
      box-sizing: border-box;
    }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
    }
    .shell {
      display: grid;
      grid-template-columns: minmax(300px, 390px) minmax(0, 1fr);
      min-height: 100vh;
    }
    aside {
      min-width: 0;
      display: flex;
      flex-direction: column;
      background: var(--panel);
      border-right: 1px solid var(--line);
    }
    header {
      padding: 18px 18px 12px;
      border-bottom: 1px solid var(--line);
    }
    h1 {
      margin: 0 0 6px;
      font-size: 18px;
      line-height: 1.2;
      font-weight: 760;
      letter-spacing: 0;
    }
    .meta {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }
    .controls {
      display: grid;
      gap: 10px;
      padding: 14px 18px;
      border-bottom: 1px solid var(--line);
    }
    label {
      display: grid;
      gap: 5px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }
    input[type="search"],
    input[type="number"],
    select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      padding: 8px 9px;
      font: inherit;
      font-size: 14px;
    }
    .inline {
      display: flex;
      gap: 14px;
      align-items: center;
      flex-wrap: wrap;
    }
    .inline label {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--ink);
      font-size: 13px;
      font-weight: 650;
    }
    .event-list {
      min-height: 0;
      overflow: auto;
      padding: 8px;
    }
    .event-row {
      width: 100%;
      border: 0;
      border-radius: 6px;
      background: transparent;
      color: var(--ink);
      padding: 10px;
      text-align: left;
      cursor: pointer;
      font: inherit;
      display: grid;
      gap: 5px;
    }
    .event-row:hover,
    .event-row.active {
      background: var(--panel-alt);
    }
    .event-title-line {
      display: flex;
      gap: 8px;
      justify-content: space-between;
      align-items: baseline;
      min-width: 0;
    }
    .event-date {
      color: var(--accent-dark);
      font-weight: 760;
      font-size: 13px;
      white-space: nowrap;
    }
    .event-counts {
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }
    .event-name {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 13px;
      color: var(--ink);
    }
    main {
      min-width: 0;
      padding: 22px 24px 28px;
      display: grid;
      gap: 16px;
      align-content: start;
    }
    .summary {
      display: grid;
      grid-template-columns: repeat(4, minmax(120px, 1fr));
      gap: 10px;
    }
    .stat,
    .panel {
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 6px;
      min-width: 0;
    }
    .stat {
      padding: 12px;
    }
    .stat-value {
      font-size: 22px;
      font-weight: 760;
      line-height: 1.1;
    }
    .stat-label {
      color: var(--muted);
      font-size: 12px;
      margin-top: 4px;
    }
    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
    }
    h2 {
      margin: 0;
      font-size: 18px;
      line-height: 1.25;
      letter-spacing: 0;
    }
    .badges {
      display: flex;
      gap: 6px;
      align-items: center;
      justify-content: flex-end;
      flex-wrap: wrap;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 999px;
      padding: 3px 8px;
      background: var(--panel-alt);
      color: var(--muted);
      font-size: 12px;
      font-weight: 760;
      white-space: nowrap;
    }
    .badge.yes {
      color: var(--yes);
      background: #e7f4ec;
    }
    .badge.no {
      color: var(--no);
      background: #f8eaea;
    }
    .badge.open,
    .badge.unknown,
    .badge.mixed {
      color: var(--open);
      background: #f7f0dc;
    }
    .chart-wrap {
      padding: 12px 16px 16px;
    }
    canvas {
      display: block;
      width: 100%;
      height: 330px;
    }
    .word-toolbar {
      display: grid;
      grid-template-columns: minmax(180px, 1fr) auto auto;
      gap: 10px;
      align-items: end;
      padding: 12px 16px;
      border-bottom: 1px solid var(--line);
    }
    .word-toolbar .inline {
      padding-bottom: 8px;
    }
    .word-list {
      max-height: 430px;
      overflow: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th,
    td {
      border-top: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }
    th {
      position: sticky;
      top: 0;
      z-index: 1;
      color: var(--muted);
      background: #fbfcfa;
      text-transform: uppercase;
      font-size: 11px;
    }
    tr.word-row {
      cursor: pointer;
    }
    tr.word-row:hover,
    tr.word-row.active {
      background: var(--panel-alt);
    }
    .word-name {
      font-weight: 720;
    }
    .truncate {
      max-width: 520px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .muted {
      color: var(--muted);
    }
    @media (max-width: 920px) {
      .shell {
        grid-template-columns: 1fr;
      }
      aside {
        border-right: 0;
        border-bottom: 1px solid var(--line);
        max-height: 48vh;
      }
      main {
        padding: 16px;
      }
      .summary {
        grid-template-columns: repeat(2, minmax(120px, 1fr));
      }
      .word-toolbar {
        grid-template-columns: 1fr;
      }
      canvas {
        height: 280px;
      }
    }
  </style>
</head>
<body>
  <script id="word-frequency-data" type="application/json">__DATA_JSON__</script>
  <div class="shell">
    <aside>
      <header>
        <h1>Mention Event Word Explorer</h1>
        <div class="meta" id="datasetMeta"></div>
      </header>
      <div class="controls">
        <label>
          Search Events
          <input id="eventSearch" type="search" autocomplete="off">
        </label>
        <div class="inline">
          <label><input id="eventsWithKalshiOnly" type="checkbox" checked> With Kalshi words</label>
        </div>
        <label>
          Sort Events
          <select id="eventSort">
            <option value="date_desc">Newest first</option>
            <option value="date_asc">Oldest first</option>
            <option value="kalshi">Kalshi word count</option>
            <option value="terms">Total term count</option>
          </select>
        </label>
        <label>
          Limit
          <input id="eventLimit" type="number" min="20" max="500" step="10" value="120">
        </label>
      </div>
      <div class="event-list" id="eventList"></div>
    </aside>
    <main>
      <section class="summary">
        <div class="stat">
          <div class="stat-value" id="statEvents">0</div>
          <div class="stat-label">Events</div>
        </div>
        <div class="stat">
          <div class="stat-value" id="statTerms">0</div>
          <div class="stat-label">Terms</div>
        </div>
        <div class="stat">
          <div class="stat-value" id="statRows">0</div>
          <div class="stat-label">Rows</div>
        </div>
        <div class="stat">
          <div class="stat-value" id="statScope">0</div>
          <div class="stat-label">Speaker Scope</div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h2 id="chartTitle">Word Over Time</h2>
            <div class="meta" id="chartSubtitle"></div>
          </div>
          <div class="badges" id="chartBadges"></div>
        </div>
        <div class="chart-wrap">
          <canvas id="chart" width="1200" height="360"></canvas>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h2 id="eventTitle">Event Words</h2>
            <div class="meta" id="eventSubtitle"></div>
          </div>
          <div class="badges" id="eventBadges"></div>
        </div>
        <div class="word-toolbar">
          <label>
            Search Words
            <input id="wordSearch" type="search" autocomplete="off">
          </label>
          <div class="inline">
            <label><input id="kalshiWordsOnly" type="checkbox" checked> Kalshi words only</label>
          </div>
          <label>
            Sort Words
            <select id="wordSort">
              <option value="kalshi">Kalshi first</option>
              <option value="count">Count</option>
              <option value="share">Share</option>
              <option value="alpha">A-Z</option>
            </select>
          </label>
        </div>
        <div class="word-list">
          <table>
            <thead>
              <tr>
                <th>Word</th>
                <th>Count</th>
                <th>Share</th>
                <th>Kalshi</th>
                <th>Market</th>
                <th>Variants</th>
              </tr>
            </thead>
            <tbody id="wordRows"></tbody>
          </table>
        </div>
      </section>
    </main>
  </div>
  <script>
    const data = JSON.parse(document.getElementById("word-frequency-data").textContent);
    const eventKey = event => `${event.event_id}::${event.transcript_id}`;
    const rowKey = row => `${row.event_id}::${row.transcript_id}`;

    const rowsByEvent = new Map();
    const rowsByEventTerm = new Map();
    for (const row of data.rows) {
      const key = rowKey(row);
      if (!rowsByEvent.has(key)) rowsByEvent.set(key, []);
      rowsByEvent.get(key).push(row);
      rowsByEventTerm.set(`${key}::${row.term}`, row);
    }

    const marketRecords = data.markets || [];
    const marketsByDate = new Map();
    for (const market of marketRecords) {
      if (!marketsByDate.has(market.event_date)) marketsByDate.set(market.event_date, []);
      marketsByDate.get(market.event_date).push(market);
    }

    const enrichedEvents = data.events.map(event => {
      const rows = rowsByEvent.get(eventKey(event)) || [];
      const eventMarkets = marketsByDate.get(event.event_date) || [];
      const uniqueEventMarkets = uniqueMarketRecords(eventMarkets);
      const marketTerms = new Set(eventMarkets.map(market => marketTermGroupKey(market)));
      return {
        ...event,
        key: eventKey(event),
        row_count: rows.length,
        market_count: uniqueEventMarkets.length,
        kalshi_word_count: marketTerms.size,
        kalshi_yes_count: uniqueEventMarkets.filter(market => market.result === "yes").length,
        kalshi_no_count: uniqueEventMarkets.filter(market => market.result === "no").length,
      };
    });

    let selectedEventKey = enrichedEvents.find(event => event.market_count > 0)?.key || enrichedEvents[0]?.key || null;
    let selectedWordKey = null;

    const el = {
      datasetMeta: document.getElementById("datasetMeta"),
      eventSearch: document.getElementById("eventSearch"),
      eventsWithKalshiOnly: document.getElementById("eventsWithKalshiOnly"),
      eventSort: document.getElementById("eventSort"),
      eventLimit: document.getElementById("eventLimit"),
      eventList: document.getElementById("eventList"),
      statEvents: document.getElementById("statEvents"),
      statTerms: document.getElementById("statTerms"),
      statRows: document.getElementById("statRows"),
      statScope: document.getElementById("statScope"),
      chartTitle: document.getElementById("chartTitle"),
      chartSubtitle: document.getElementById("chartSubtitle"),
      chartBadges: document.getElementById("chartBadges"),
      chart: document.getElementById("chart"),
      eventTitle: document.getElementById("eventTitle"),
      eventSubtitle: document.getElementById("eventSubtitle"),
      eventBadges: document.getElementById("eventBadges"),
      wordSearch: document.getElementById("wordSearch"),
      kalshiWordsOnly: document.getElementById("kalshiWordsOnly"),
      wordSort: document.getElementById("wordSort"),
      wordRows: document.getElementById("wordRows"),
    };

    const profileLabel = [data.speaker_name, data.event_type].filter(Boolean).join(" | ");
    el.datasetMeta.textContent = `${profileLabel ? profileLabel + " | " : ""}${data.generated_at} | min count ${data.min_count}`;
    el.statEvents.textContent = formatNumber(data.event_count);
    el.statTerms.textContent = formatNumber(data.term_count);
    el.statRows.textContent = formatNumber(data.row_count);
    el.statScope.textContent = data.speaker_scope;

    for (const control of [el.eventSearch, el.eventsWithKalshiOnly, el.eventSort, el.eventLimit]) {
      control.addEventListener("input", () => {
        renderEventList();
        ensureSelectedEventVisible();
        renderSelectedEvent();
      });
    }
    for (const control of [el.wordSearch, el.kalshiWordsOnly, el.wordSort]) {
      control.addEventListener("input", renderSelectedEvent);
    }

    function render() {
      renderEventList();
      renderSelectedEvent();
    }

    function filteredEvents() {
      const query = el.eventSearch.value.trim().toLowerCase();
      let events = enrichedEvents.slice();
      if (query) {
        events = events.filter(event => {
          return (event.event_date || "").includes(query)
            || event.event_title.toLowerCase().includes(query)
            || event.event_id.toLowerCase().includes(query);
        });
      }
      if (el.eventsWithKalshiOnly.checked) {
        events = events.filter(event => event.market_count > 0);
      }
      const sortMode = el.eventSort.value;
      events.sort((a, b) => {
        if (sortMode === "date_asc") return compareDate(a, b) || a.event_id.localeCompare(b.event_id);
        if (sortMode === "kalshi") return b.kalshi_word_count - a.kalshi_word_count || compareDateDesc(a, b);
        if (sortMode === "terms") return b.event_total_terms - a.event_total_terms || compareDateDesc(a, b);
        return compareDateDesc(a, b) || a.event_id.localeCompare(b.event_id);
      });
      return events.slice(0, Number(el.eventLimit.value || 120));
    }

    function ensureSelectedEventVisible() {
      const events = filteredEvents();
      if (!events.find(event => event.key === selectedEventKey)) {
        selectedEventKey = events[0]?.key || enrichedEvents[0]?.key || null;
        selectedWordKey = null;
      }
    }

    function renderEventList() {
      const events = filteredEvents();
      el.eventList.innerHTML = "";
      for (const event of events) {
        const button = document.createElement("button");
        button.className = "event-row" + (event.key === selectedEventKey ? " active" : "");
        button.type = "button";
        button.innerHTML = `
          <span class="event-title-line">
            <span class="event-date">${escapeHtml(event.event_date || "undated")}</span>
            <span class="event-counts">${formatNumber(event.market_count)} markets | ${formatNumber(event.row_count)} words</span>
          </span>
          <span class="event-name">${escapeHtml(event.event_title)}</span>
        `;
        button.addEventListener("click", () => {
          selectedEventKey = event.key;
          selectedWordKey = null;
          renderEventList();
          renderSelectedEvent();
        });
        el.eventList.appendChild(button);
      }
    }

    function selectedEvent() {
      return enrichedEvents.find(event => event.key === selectedEventKey) || enrichedEvents[0] || null;
    }

    function eventRows() {
      const event = selectedEvent();
      return event ? (rowsByEvent.get(event.key) || []) : [];
    }

    function eventMarkets() {
      const event = selectedEvent();
      return event ? (marketsByDate.get(event.event_date) || []) : [];
    }

    function mergedEventWordItems() {
      const event = selectedEvent();
      if (!event) return [];
      const rowMap = new Map(eventRows().map(row => [row.term, row]));
      const marketGroups = new Map();
      for (const market of eventMarkets()) {
        const key = marketTermGroupKey(market);
        if (!marketGroups.has(key)) marketGroups.set(key, []);
        marketGroups.get(key).push(market);
      }
      const usedMarketTerms = new Set();
      const items = [];
      for (const [groupKey, marketRecords] of marketGroups.entries()) {
        const item = buildMarketWordItem(event, groupKey, marketRecords, rowMap);
        for (const term of item.terms) usedMarketTerms.add(term);
        items.push(item);
      }
      for (const row of eventRows()) {
        if (usedMarketTerms.has(row.term)) continue;
        items.push({
          ...row,
          key: `term:${row.term}`,
          terms: [row.term],
          market_term_key: null,
          market_records: [],
        });
      }
      return items;
    }

    function visibleWordRows() {
      const query = el.wordSearch.value.trim().toLowerCase();
      let rows = mergedEventWordItems();
      if (query) {
        rows = rows.filter(row => {
          return row.terms.join(" ").includes(query)
            || row.display_term.toLowerCase().includes(query)
            || row.kalshi_target_phrases.join(" ").toLowerCase().includes(query);
        });
      }
      if (el.kalshiWordsOnly.checked) {
        rows = rows.filter(row => row.is_kalshi_market);
      }
      const sortMode = el.wordSort.value;
      rows.sort((a, b) => {
        if (sortMode === "alpha") return a.display_term.localeCompare(b.display_term);
        if (sortMode === "share") return termShare(b) - termShare(a) || b.count - a.count;
        if (sortMode === "count") return b.count - a.count || a.display_term.localeCompare(b.display_term);
        return Number(b.is_kalshi_market) - Number(a.is_kalshi_market)
          || b.count - a.count
          || a.display_term.localeCompare(b.display_term);
      });
      return rows;
    }

    function renderSelectedEvent() {
      const event = selectedEvent();
      if (!event) return;
      const rows = visibleWordRows();
      if (!selectedWordKey || !rows.find(row => row.key === selectedWordKey)) {
        selectedWordKey = rows[0]?.key || null;
      }
      el.eventTitle.textContent = event.event_date || "Selected Event";
      el.eventSubtitle.textContent = event.event_title;
      el.eventBadges.innerHTML = [
        `<span class="badge">${formatNumber(event.event_total_terms)} terms</span>`,
        `<span class="badge yes">${formatNumber(event.kalshi_yes_count)} yes</span>`,
        `<span class="badge no">${formatNumber(event.kalshi_no_count)} no</span>`,
        `<span class="badge">${formatNumber(event.row_count)} word rows</span>`,
      ].join(" ");
      renderWordRows(rows);
      renderChart();
    }

    function renderWordRows(rows) {
      el.wordRows.innerHTML = "";
      for (const row of rows) {
        const tr = document.createElement("tr");
        tr.className = "word-row" + (row.key === selectedWordKey ? " active" : "");
        tr.innerHTML = `
          <td class="word-name">${escapeHtml(row.display_term)}</td>
          <td>${formatNumber(row.count)}</td>
          <td>${formatPercent(termShare(row))}</td>
          <td>${row.is_kalshi_market ? `<span class="badge ${row.kalshi_result || "unknown"}">${escapeHtml(row.kalshi_result || "market")}</span>` : ""}</td>
          <td class="truncate">${escapeHtml(row.kalshi_target_phrases.join(", "))}</td>
          <td class="truncate">${escapeHtml(formatVariants(row.variants))}</td>
        `;
        tr.addEventListener("click", () => {
          selectedWordKey = row.key;
          renderSelectedEvent();
        });
        el.wordRows.appendChild(tr);
      }
    }

    function renderChart() {
      const event = selectedEvent();
      const selectedItem = mergedEventWordItems().find(row => row.key === selectedWordKey);
      if (!event || !selectedItem) {
        el.chartTitle.textContent = "Word Over Time";
        el.chartSubtitle.textContent = "";
        el.chartBadges.innerHTML = "";
        drawChart([], null);
        return;
      }
      const selectedTerms = selectedItem.terms || [selectedItem.term].filter(Boolean);
      const selectedTermMarkets = marketsMatchingTerms(selectedTerms);
      const timeline = data.events
        .filter(item => item.event_date)
        .map(item => ({
          event: item,
          row: combinedRowForEvent(item, selectedTerms),
          market_records: marketsMatchingTermsOnDate(item.event_date, selectedTerms),
        }))
        .sort((a, b) => (a.event.event_date || "").localeCompare(b.event.event_date || "") || a.event.event_id.localeCompare(b.event.event_id));

      const selectedRow = combinedRowForEvent(event, selectedTerms);
      const totalCount = timeline.reduce((sum, item) => sum + (item.row?.count || 0), 0);
      const saidEvents = timeline.filter(item => (item.row?.count || 0) > 0).length;
      el.chartTitle.textContent = `${selectedItem.display_term} Over Time`;
      el.chartSubtitle.textContent = event ? `Selected event: ${event.event_date || "undated"} | ${event.event_title}` : "";
      el.chartBadges.innerHTML = [
        `<span class="badge">${formatNumber(totalCount)} total</span>`,
        `<span class="badge">${formatNumber(saidEvents)} said events</span>`,
        `<span class="badge yes">${formatNumber(selectedTermMarkets.filter(market => market.result === "yes").length)} yes markets</span>`,
        `<span class="badge no">${formatNumber(selectedTermMarkets.filter(market => market.result === "no").length)} no markets</span>`,
        selectedRow || selectedTermMarkets.length ? `<span class="badge">selected date highlighted</span>` : "",
      ].filter(Boolean).join(" ");
      drawChart(timeline, event?.key || null);
    }

    function drawChart(timeline, selectedKey) {
      const canvas = el.chart;
      const ctx = canvas.getContext("2d");
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = Math.max(1, Math.floor(rect.width * dpr));
      canvas.height = Math.max(1, Math.floor(rect.height * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const width = rect.width;
      const height = rect.height;
      ctx.clearRect(0, 0, width, height);

      const pad = { left: 46, right: 18, top: 16, bottom: 48 };
      const plotW = width - pad.left - pad.right;
      const plotH = height - pad.top - pad.bottom;
      const maxCount = Math.max(1, ...timeline.map(item => item.row?.count || 0));

      ctx.strokeStyle = "#ccd6d1";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(pad.left, pad.top);
      ctx.lineTo(pad.left, pad.top + plotH);
      ctx.lineTo(pad.left + plotW, pad.top + plotH);
      ctx.stroke();

      ctx.fillStyle = "#5d6870";
      ctx.font = "12px system-ui, sans-serif";
      ctx.textAlign = "right";
      ctx.fillText(String(maxCount), pad.left - 8, pad.top + 4);
      ctx.fillText("0", pad.left - 8, pad.top + plotH);

      if (!timeline.length) return;
      const step = plotW / Math.max(timeline.length, 1);
      timeline.forEach((item, index) => {
        const key = eventKey(item.event);
        const count = item.row?.count || 0;
        const x = pad.left + index * step + Math.max(1, step * 0.12);
        const barW = Math.max(2, step * 0.72);
        const centerX = x + barW / 2;
        const barH = (count / maxCount) * plotH;
        const y = pad.top + plotH - barH;
        const selected = key === selectedKey;
        const marketResult = summarizeResults(unique(item.market_records.map(market => market.result).filter(Boolean)));
        ctx.fillStyle = selected ? "#1f4e8c" : (marketResult === "yes" ? "#147d3f" : "#8ba39a");
        if (count > 0) {
          ctx.fillRect(x, y, barW, Math.max(1, barH));
        }
        if (selected) {
          ctx.strokeStyle = "#162126";
          ctx.lineWidth = 2;
          if (count > 0) {
            ctx.strokeRect(x - 1, Math.max(pad.top, y - 1), barW + 2, Math.min(plotH, barH + 2));
          } else {
            ctx.strokeStyle = "#1f4e8c";
            ctx.beginPath();
            ctx.moveTo(centerX, pad.top);
            ctx.lineTo(centerX, pad.top + plotH);
            ctx.stroke();
          }
        }
        if (item.market_records.length) {
          const markerY = count > 0 ? Math.max(pad.top + 8, y - 7) : pad.top + plotH - 6;
          drawMarketMarker(ctx, centerX, markerY, marketResult, selected);
        }
      });

      const tickEvery = Math.max(1, Math.ceil(timeline.length / 9));
      ctx.fillStyle = "#5d6870";
      ctx.textAlign = "center";
      timeline.forEach((item, index) => {
        if (index % tickEvery !== 0 && index !== timeline.length - 1) return;
        const x = pad.left + index * step + step * 0.5;
        ctx.save();
        ctx.translate(x, pad.top + plotH + 31);
        ctx.rotate(-Math.PI / 6);
        ctx.fillText(shortDate(item.event.event_date), 0, 0);
        ctx.restore();
      });
    }

    function drawMarketMarker(ctx, x, y, result, selected) {
      const radius = selected ? 6 : 5;
      ctx.save();
      ctx.fillStyle = result === "no" ? "#b03232" : result === "yes" ? "#147d3f" : "#8a640c";
      ctx.strokeStyle = selected ? "#1f4e8c" : "#ffffff";
      ctx.lineWidth = selected ? 3 : 2;
      ctx.beginPath();
      if (result === "no") {
        ctx.moveTo(x, y - radius);
        ctx.lineTo(x + radius, y);
        ctx.lineTo(x, y + radius);
        ctx.lineTo(x - radius, y);
        ctx.closePath();
      } else if (result === "yes") {
        ctx.arc(x, y, radius, 0, Math.PI * 2);
      } else {
        ctx.rect(x - radius, y - radius, radius * 2, radius * 2);
      }
      ctx.fill();
      ctx.stroke();
      ctx.restore();
    }

    function buildMarketWordItem(event, groupKey, marketRecords, rowMap) {
      const uniqueRecords = uniqueMarketRecords(marketRecords);
      const terms = unique(marketRecords.flatMap(market => marketTerms(market))).sort();
      const rows = terms.map(term => rowMap.get(term)).filter(Boolean);
      const targetPhrases = unique(uniqueRecords.map(market => market.target_phrase).filter(Boolean));
      const kalshiResults = unique(uniqueRecords.map(market => market.result).filter(Boolean));
      const displayTerm = targetPhrases.length === 1
        ? targetPhrases[0]
        : (uniqueRecords[0]?.display_term || terms.join(" / ") || "Market");
      const marketIds = unique(uniqueRecords.map(market => market.market_id).filter(Boolean));
      return {
        event_id: event.event_id,
        event_date: event.event_date,
        event_title: event.event_title,
        transcript_id: event.transcript_id,
        transcript_type: event.transcript_type,
        key: `market:${groupKey}`,
        term: terms[0] || groupKey,
        terms,
        market_term_key: groupKey,
        display_term: displayTerm,
        count: rows.reduce((sum, row) => sum + row.count, 0),
        event_total_terms: event.event_total_terms,
        variants: mergeRowVariants(rows),
        is_kalshi_market: true,
        kalshi_result: summarizeResults(kalshiResults),
        kalshi_market_id: marketIds.length === 1 ? marketIds[0] : null,
        kalshi_market_ids: marketIds,
        kalshi_target_phrases: targetPhrases,
        kalshi_results: kalshiResults,
        market_records: uniqueRecords,
      };
    }

    function combinedRowForEvent(event, terms) {
      const rows = unique(terms)
        .map(term => rowsByEventTerm.get(`${eventKey(event)}::${term}`))
        .filter(Boolean);
      if (!rows.length) return null;
      return {
        count: rows.reduce((sum, row) => sum + row.count, 0),
        event_total_terms: event.event_total_terms,
        variants: mergeRowVariants(rows),
      };
    }

    function marketsMatchingTerms(terms) {
      const termSet = new Set(terms);
      return uniqueMarketRecords(
        marketRecords.filter(market => marketTerms(market).some(term => termSet.has(term)))
      );
    }

    function marketsMatchingTermsOnDate(eventDate, terms) {
      const termSet = new Set(terms);
      return uniqueMarketRecords(
        (marketsByDate.get(eventDate) || []).filter(market => (
          marketTerms(market).some(term => termSet.has(term))
        ))
      );
    }

    function marketTerms(market) {
      if (Array.isArray(market.market_terms) && market.market_terms.length) {
        return unique(market.market_terms.filter(Boolean));
      }
      return market.term ? [market.term] : [];
    }

    function marketTermGroupKey(market) {
      return market.market_term_key || market.market_id || marketTerms(market).slice().sort().join("|") || market.term || "market";
    }

    function uniqueMarketRecords(markets) {
      const byId = new Map();
      for (const market of markets) {
        const key = market.market_id || `${market.event_date}::${marketTermGroupKey(market)}::${market.target_phrase || ""}`;
        if (!byId.has(key)) byId.set(key, market);
      }
      return Array.from(byId.values());
    }

    function mergeRowVariants(rows) {
      const variants = {};
      for (const row of rows) {
        for (const [variant, count] of Object.entries(row.variants || {})) {
          variants[variant] = (variants[variant] || 0) + count;
        }
      }
      return variants;
    }

    function compareDate(a, b) {
      return (a.event_date || "").localeCompare(b.event_date || "");
    }

    function compareDateDesc(a, b) {
      return (b.event_date || "").localeCompare(a.event_date || "");
    }

    function summarizeResults(results) {
      const values = unique(results.filter(Boolean));
      if (!values.length) return null;
      if (values.length === 1) return values[0];
      const settled = values.filter(value => value === "yes" || value === "no");
      if (settled.length === 1 && values.every(value => value === settled[0] || value === "open" || value === "unknown")) {
        return settled[0];
      }
      return "mixed";
    }

    function unique(values) {
      return Array.from(new Set(values));
    }

    function termShare(row) {
      return row.event_total_terms ? row.count / row.event_total_terms : 0;
    }

    function formatPercent(value) {
      return `${(value * 100).toFixed(2)}%`;
    }

    function formatVariants(variants) {
      return Object.entries(variants || {})
        .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
        .slice(0, 5)
        .map(([variant, count]) => `${variant} (${count})`)
        .join(", ");
    }

    function shortDate(value) {
      return value ? value.slice(5) : "";
    }

    function formatNumber(value) {
      return new Intl.NumberFormat().format(value || 0);
    }

    function escapeHtml(value) {
      return String(value || "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[char]));
    }

    window.addEventListener("resize", renderChart);
    render();
  </script>
</body>
</html>
"""
    return html.replace("__DATA_JSON__", data_json)
