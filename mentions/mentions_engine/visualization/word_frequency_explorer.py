from __future__ import annotations

import json


def render_word_frequency_explorer(payload: dict) -> str:
    data_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mention Word Frequencies</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8f3;
      --ink: #172026;
      --muted: #5d6870;
      --line: #cfd7d3;
      --panel: #ffffff;
      --panel-alt: #eef3ef;
      --accent: #0f766e;
      --accent-dark: #0b5f59;
      --yes: #147d3f;
      --no: #b03232;
      --open: #7a5b12;
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
    }}
    .shell {{
      display: grid;
      grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
      min-height: 100vh;
    }}
    aside {{
      border-right: 1px solid var(--line);
      background: var(--panel);
      min-width: 0;
      display: flex;
      flex-direction: column;
    }}
    header {{
      padding: 18px 18px 12px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{
      font-size: 18px;
      line-height: 1.2;
      margin: 0 0 6px;
      font-weight: 700;
      letter-spacing: 0;
    }}
    .meta {{
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }}
    .controls {{
      display: grid;
      gap: 10px;
      padding: 14px 18px;
      border-bottom: 1px solid var(--line);
    }}
    label {{
      display: grid;
      gap: 5px;
      font-size: 12px;
      color: var(--muted);
      font-weight: 600;
    }}
    input[type="search"],
    input[type="number"],
    select {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      padding: 8px 9px;
      font: inherit;
      font-size: 14px;
    }}
    .inline {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }}
    .inline label {{
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--ink);
      font-size: 13px;
      font-weight: 600;
    }}
    .term-list {{
      overflow: auto;
      min-height: 0;
      padding: 8px;
    }}
    .term-row {{
      width: 100%;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      align-items: center;
      border: 0;
      border-radius: 6px;
      background: transparent;
      color: var(--ink);
      padding: 9px 10px;
      text-align: left;
      cursor: pointer;
      font: inherit;
    }}
    .term-row:hover,
    .term-row.active {{
      background: var(--panel-alt);
    }}
    .term-name {{
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-weight: 650;
      font-size: 14px;
    }}
    .term-counts {{
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }}
    main {{
      min-width: 0;
      padding: 22px 24px 28px;
      display: grid;
      gap: 18px;
      align-content: start;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(120px, 1fr));
      gap: 10px;
    }}
    .stat {{
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 6px;
      padding: 12px;
      min-width: 0;
    }}
    .stat-value {{
      font-size: 22px;
      font-weight: 750;
      line-height: 1.1;
    }}
    .stat-label {{
      color: var(--muted);
      font-size: 12px;
      margin-top: 4px;
    }}
    .detail {{
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 6px;
      min-width: 0;
    }}
    .detail-header {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
    }}
    h2 {{
      margin: 0;
      font-size: 18px;
      line-height: 1.25;
      letter-spacing: 0;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 12px;
      font-weight: 700;
      background: var(--panel-alt);
      color: var(--muted);
      white-space: nowrap;
    }}
    .badge.yes {{
      color: var(--yes);
      background: #e7f4ec;
    }}
    .badge.no {{
      color: var(--no);
      background: #f8eaea;
    }}
    .badge.open,
    .badge.unknown,
    .badge.mixed {{
      color: var(--open);
      background: #f7f0dc;
    }}
    .chart-wrap {{
      padding: 12px 16px 16px;
    }}
    canvas {{
      width: 100%;
      height: 320px;
      display: block;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th,
    td {{
      border-top: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      background: #fbfcfa;
      position: sticky;
      top: 0;
      z-index: 1;
    }}
    .table-wrap {{
      max-height: 420px;
      overflow: auto;
    }}
    .muted {{
      color: var(--muted);
    }}
    .truncate {{
      max-width: 460px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    @media (max-width: 860px) {{
      .shell {{
        grid-template-columns: 1fr;
      }}
      aside {{
        border-right: 0;
        border-bottom: 1px solid var(--line);
        max-height: 48vh;
      }}
      .summary {{
        grid-template-columns: repeat(2, minmax(120px, 1fr));
      }}
      main {{
        padding: 16px;
      }}
      canvas {{
        height: 260px;
      }}
    }}
  </style>
</head>
<body>
  <script id="word-frequency-data" type="application/json">{data_json}</script>
  <div class="shell">
    <aside>
      <header>
        <h1>Mention Word Frequencies</h1>
        <div class="meta" id="datasetMeta"></div>
      </header>
      <div class="controls">
        <label>
          Search
          <input id="search" type="search" autocomplete="off">
        </label>
        <div class="inline">
          <label><input id="kalshiOnly" type="checkbox"> Kalshi only</label>
          <label><input id="nonzeroOnly" type="checkbox" checked> Nonzero events</label>
        </div>
        <label>
          Sort
          <select id="sortMode">
            <option value="total">Total count</option>
            <option value="events">Event count</option>
            <option value="kalshi">Kalshi events</option>
            <option value="alpha">A-Z</option>
          </select>
        </label>
        <label>
          Limit
          <input id="limit" type="number" min="20" max="1000" step="10" value="120">
        </label>
      </div>
      <div class="term-list" id="termList"></div>
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
      <section class="detail">
        <div class="detail-header">
          <h2 id="selectedTitle">Term</h2>
          <div id="selectedBadges"></div>
        </div>
        <div class="chart-wrap">
          <canvas id="chart" width="1200" height="360"></canvas>
        </div>
      </section>
      <section class="detail">
        <div class="detail-header">
          <h2>Event Rows</h2>
          <div class="muted" id="rowCount"></div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Count</th>
                <th>Share</th>
                <th>Kalshi</th>
                <th>Market</th>
                <th>Event</th>
              </tr>
            </thead>
            <tbody id="eventRows"></tbody>
          </table>
        </div>
      </section>
    </main>
  </div>
  <script>
    const data = JSON.parse(document.getElementById("word-frequency-data").textContent);
    const rowsByTerm = new Map();
    for (const row of data.rows) {{
      if (!rowsByTerm.has(row.term)) rowsByTerm.set(row.term, []);
      rowsByTerm.get(row.term).push(row);
    }}

    const termSummaries = new Map(data.terms.map(term => [term.term, term]));
    let selectedTerm = data.terms[0]?.term || null;

    const el = {{
      datasetMeta: document.getElementById("datasetMeta"),
      search: document.getElementById("search"),
      kalshiOnly: document.getElementById("kalshiOnly"),
      nonzeroOnly: document.getElementById("nonzeroOnly"),
      sortMode: document.getElementById("sortMode"),
      limit: document.getElementById("limit"),
      termList: document.getElementById("termList"),
      statEvents: document.getElementById("statEvents"),
      statTerms: document.getElementById("statTerms"),
      statRows: document.getElementById("statRows"),
      statScope: document.getElementById("statScope"),
      selectedTitle: document.getElementById("selectedTitle"),
      selectedBadges: document.getElementById("selectedBadges"),
      chart: document.getElementById("chart"),
      rowCount: document.getElementById("rowCount"),
      eventRows: document.getElementById("eventRows"),
    }};

    const profileLabel = [data.speaker_name, data.event_type].filter(Boolean).join(" · ");
    el.datasetMeta.textContent = `${{profileLabel ? profileLabel + " · " : ""}}${{data.generated_at}} · min count ${{data.min_count}}`;
    el.statEvents.textContent = formatNumber(data.event_count);
    el.statTerms.textContent = formatNumber(data.term_count);
    el.statRows.textContent = formatNumber(data.row_count);
    el.statScope.textContent = data.speaker_scope;

    for (const control of [el.search, el.kalshiOnly, el.nonzeroOnly, el.sortMode, el.limit]) {{
      control.addEventListener("input", render);
    }}

    function render() {{
      renderTermList();
      renderSelectedTerm();
    }}

    function filteredTerms() {{
      const query = el.search.value.trim().toLowerCase();
      let terms = data.terms.slice();
      if (query) {{
        terms = terms.filter(term => term.term.includes(query) || term.display_term.includes(query));
      }}
      if (el.kalshiOnly.checked) {{
        terms = terms.filter(term => term.kalshi_market_event_count > 0);
      }}
      if (el.nonzeroOnly.checked) {{
        terms = terms.filter(term => term.total_count > 0);
      }}
      const sortMode = el.sortMode.value;
      terms.sort((a, b) => {{
        if (sortMode === "alpha") return a.display_term.localeCompare(b.display_term);
        if (sortMode === "events") return b.event_count - a.event_count || b.total_count - a.total_count || a.term.localeCompare(b.term);
        if (sortMode === "kalshi") return b.kalshi_market_event_count - a.kalshi_market_event_count || b.total_count - a.total_count || a.term.localeCompare(b.term);
        return b.total_count - a.total_count || b.event_count - a.event_count || a.term.localeCompare(b.term);
      }});
      return terms.slice(0, Number(el.limit.value || 120));
    }}

    function renderTermList() {{
      const terms = filteredTerms();
      if (!terms.find(term => term.term === selectedTerm)) {{
        selectedTerm = terms[0]?.term || data.terms[0]?.term || null;
      }}
      el.termList.innerHTML = "";
      for (const term of terms) {{
        const button = document.createElement("button");
        button.className = "term-row" + (term.term === selectedTerm ? " active" : "");
        button.type = "button";
        button.innerHTML = `
          <span class="term-name">${{escapeHtml(term.display_term)}}</span>
          <span class="term-counts">${{formatNumber(term.total_count)}} · ${{formatNumber(term.event_count)}}</span>
        `;
        button.addEventListener("click", () => {{
          selectedTerm = term.term;
          render();
        }});
        el.termList.appendChild(button);
      }}
    }}

    function renderSelectedTerm() {{
      const summary = termSummaries.get(selectedTerm);
      const rows = (rowsByTerm.get(selectedTerm) || []).slice().sort((a, b) => {{
        return (a.event_date || "").localeCompare(b.event_date || "") || a.event_id.localeCompare(b.event_id);
      }});
      if (!summary) return;
      el.selectedTitle.textContent = summary.display_term;
      el.selectedBadges.innerHTML = [
        `<span class="badge">${{formatNumber(summary.total_count)}} total</span>`,
        `<span class="badge">${{formatNumber(summary.event_count)}} events</span>`,
        summary.kalshi_market_event_count ? `<span class="badge yes">${{formatNumber(summary.kalshi_market_event_count)}} Kalshi</span>` : "",
      ].filter(Boolean).join(" ");
      drawChart(rows);
      renderRows(rows);
    }}

    function drawChart(rows) {{
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

      const pad = {{ left: 44, right: 18, top: 14, bottom: 46 }};
      const plotW = width - pad.left - pad.right;
      const plotH = height - pad.top - pad.bottom;
      const maxCount = Math.max(1, ...rows.map(row => row.count));

      ctx.strokeStyle = "#cfd7d3";
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

      if (!rows.length) return;
      const step = plotW / Math.max(rows.length, 1);
      rows.forEach((row, index) => {{
        const x = pad.left + index * step + Math.max(2, step * 0.12);
        const barW = Math.max(2, step * 0.72);
        const barH = (row.count / maxCount) * plotH;
        ctx.fillStyle = row.is_kalshi_market ? colorForResult(row.kalshi_result) : "#0f766e";
        ctx.fillRect(x, pad.top + plotH - barH, barW, barH);
      }});

      const tickEvery = Math.max(1, Math.ceil(rows.length / 8));
      ctx.fillStyle = "#5d6870";
      ctx.textAlign = "center";
      rows.forEach((row, index) => {{
        if (index % tickEvery !== 0 && index !== rows.length - 1) return;
        const x = pad.left + index * step + step * 0.5;
        ctx.save();
        ctx.translate(x, pad.top + plotH + 30);
        ctx.rotate(-Math.PI / 6);
        ctx.fillText(shortDate(row.event_date), 0, 0);
        ctx.restore();
      }});
    }}

    function renderRows(rows) {{
      const visibleRows = rows.slice().reverse();
      el.rowCount.textContent = `${{formatNumber(visibleRows.length)}} rows`;
      el.eventRows.innerHTML = "";
      for (const row of visibleRows) {{
        const share = row.event_total_terms ? ((row.count / row.event_total_terms) * 100).toFixed(2) + "%" : "";
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${{escapeHtml(row.event_date || "")}}</td>
          <td>${{formatNumber(row.count)}}</td>
          <td>${{share}}</td>
          <td>${{row.is_kalshi_market ? `<span class="badge ${{row.kalshi_result || "unknown"}}">${{escapeHtml(row.kalshi_result || "market")}}</span>` : ""}}</td>
          <td class="truncate">${{escapeHtml(row.kalshi_target_phrases.join(", "))}}</td>
          <td class="truncate">${{escapeHtml(row.event_title)}}</td>
        `;
        el.eventRows.appendChild(tr);
      }}
    }}

    function colorForResult(result) {{
      if (result === "yes") return "#147d3f";
      if (result === "no") return "#b03232";
      if (result === "open" || result === "unknown" || result === "mixed") return "#b8871f";
      return "#0f766e";
    }}

    function shortDate(value) {{
      if (!value) return "";
      return value.slice(5);
    }}

    function formatNumber(value) {{
      return new Intl.NumberFormat().format(value || 0);
    }}

    function escapeHtml(value) {{
      return String(value || "").replace(/[&<>"']/g, char => ({{
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }}[char]));
    }}

    window.addEventListener("resize", () => renderSelectedTerm());
    render();
  </script>
</body>
</html>
"""
