import { useEffect, useState } from "react";
import "./App.css";

type SortField = "category" | "market" | "bid" | "ask" | "startTime" | "volume";
type SortDirection = "asc" | "desc";
type RefreshInterval = "off" | "15s" | "30s" | "60s";

type FilterRanges = {
  volumeMin: string;
  volumeMax: string;
  spreadMin: string;
  spreadMax: string;
  bidMin: string;
  bidMax: string;
  askMin: string;
  askMax: string;
};

type FilterState = FilterRanges & {
  categories: string[];
  subcategories: string[];
  liveOnly: boolean;
  keyword: string;
};

type TopBarState = {
  groupByEvent: boolean;
  sortField: SortField;
  sortDirection: SortDirection;
  autoRefresh: RefreshInterval;
};

type ViewState = {
  filters: FilterState;
  topBar: TopBarState;
};

type HistoryState = {
  past: ViewState[];
  present: ViewState;
  future: ViewState[];
};

type Market = {
  id: string;
  label: string;
  bid: number;
  ask: number;
  volume: number;
};

type EventRecord = {
  id: string;
  category: string;
  subcategory: string;
  title: string;
  startTime: string;
  isLive: boolean;
  markets: Market[];
};

type FlatRow = {
  kind: "market";
  id: string;
  eventId: string;
  category: string;
  subcategory: string;
  marketName: string;
  eventTitle: string;
  displayName: string;
  startTime: string;
  isLive: boolean;
  bid: number;
  ask: number;
  volume: number;
  spread: number;
};

type EventGroup = {
  id: string;
  category: string;
  subcategory: string;
  title: string;
  startTime: string;
  isLive: boolean;
  childRows: FlatRow[];
  aggregateVolume: number;
  summaryBid: number | null;
  summaryAsk: number | null;
  sortBid: number;
  sortAsk: number;
  spread: number;
};

const MOCK_EVENTS: EventRecord[] = [
  {
    id: "evt-trump-words",
    category: "Politics",
    subcategory: "Elections",
    title: "What will Trump say today?",
    startTime: "2026-04-17T09:00:00-07:00",
    isLive: true,
    markets: [
      { id: "iran", label: "Iran", bid: 43, ask: 47, volume: 184000 },
      { id: "oil", label: "Oil", bid: 38, ask: 42, volume: 129000 },
      { id: "tariffs", label: "Tariffs", bid: 56, ask: 60, volume: 205000 },
    ],
  },
  {
    id: "evt-senate-control",
    category: "Politics",
    subcategory: "Senate",
    title: "Which party will control the Senate after the election?",
    startTime: "2026-11-03T17:00:00-08:00",
    isLive: false,
    markets: [
      { id: "democrats", label: "Democrats", bid: 49, ask: 52, volume: 912000 },
      { id: "republicans", label: "Republicans", bid: 48, ask: 51, volume: 887000 },
    ],
  },
  {
    id: "evt-fomc-cuts",
    category: "Economics",
    subcategory: "Fed",
    title: "Will the Fed cut rates at the next meeting?",
    startTime: "2026-06-17T11:00:00-07:00",
    isLive: false,
    markets: [{ id: "yes", label: "Yes", bid: 31, ask: 34, volume: 275000 }],
  },
  {
    id: "evt-lakers-playoffs",
    category: "Sports",
    subcategory: "NBA",
    title: "Will the Lakers make the playoffs?",
    startTime: "2026-04-24T19:30:00-07:00",
    isLive: true,
    markets: [{ id: "yes", label: "Yes", bid: 67, ask: 70, volume: 321000 }],
  },
  {
    id: "evt-ai-headlines",
    category: "Tech & Science",
    subcategory: "AI",
    title: "Which AI company will dominate headlines this week?",
    startTime: "2026-04-18T06:00:00-07:00",
    isLive: true,
    markets: [
      { id: "openai", label: "OpenAI", bid: 64, ask: 68, volume: 403000 },
      { id: "google", label: "Google", bid: 27, ask: 31, volume: 212000 },
      { id: "anthropic", label: "Anthropic", bid: 18, ask: 22, volume: 118000 },
    ],
  },
  {
    id: "evt-weather-nyc",
    category: "Climate",
    subcategory: "Weather",
    title: "Will NYC hit 80F tomorrow?",
    startTime: "2026-04-18T08:00:00-04:00",
    isLive: false,
    markets: [{ id: "yes", label: "Yes", bid: 22, ask: 26, volume: 82000 }],
  },
];

const ALL_CATEGORIES = Array.from(
  new Set(MOCK_EVENTS.map((event) => event.category)),
).sort();

const ALL_SUBCATEGORIES = Array.from(
  new Set(MOCK_EVENTS.map((event) => event.subcategory)),
).sort();

const defaultFilters: FilterState = {
  categories: [],
  subcategories: [],
  liveOnly: false,
  keyword: "",
  volumeMin: "",
  volumeMax: "",
  spreadMin: "",
  spreadMax: "",
  bidMin: "",
  bidMax: "",
  askMin: "",
  askMax: "",
};

const defaultTopBar: TopBarState = {
  groupByEvent: false,
  sortField: "volume",
  sortDirection: "desc",
  autoRefresh: "off",
};

const initialViewState: ViewState = {
  filters: defaultFilters,
  topBar: defaultTopBar,
};

function updateHistory(
  history: HistoryState,
  updater: (present: ViewState) => ViewState,
): HistoryState {
  const nextPresent = updater(history.present);

  if (JSON.stringify(nextPresent) === JSON.stringify(history.present)) {
    return history;
  }

  return {
    past: [...history.past, history.present],
    present: nextPresent,
    future: [],
  };
}

function parseNumber(value: string): number | null {
  if (!value.trim()) {
    return null;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatCurrencyPoints(value: number | null): string {
  return value === null ? "--" : `${value.toFixed(0)}c`;
}

function formatVolume(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function rangePasses(value: number, min: string, max: string): boolean {
  const parsedMin = parseNumber(min);
  const parsedMax = parseNumber(max);

  if (parsedMin !== null && value < parsedMin) {
    return false;
  }

  if (parsedMax !== null && value > parsedMax) {
    return false;
  }

  return true;
}

function flattenEvents(events: EventRecord[]): FlatRow[] {
  return events.flatMap((event) =>
    event.markets.map((market) => ({
      kind: "market" as const,
      id: `${event.id}-${market.id}`,
      eventId: event.id,
      category: event.category,
      subcategory: event.subcategory,
      marketName: market.label,
      eventTitle: event.title,
      displayName:
        event.markets.length > 1 ? `${event.title} - ${market.label}` : event.title,
      startTime: event.startTime,
      isLive: event.isLive,
      bid: market.bid,
      ask: market.ask,
      volume: market.volume,
      spread: market.ask - market.bid,
    })),
  );
}

function filterRows(rows: FlatRow[], filters: FilterState): FlatRow[] {
  const keyword = filters.keyword.trim().toLowerCase();

  return rows.filter((row) => {
    if (filters.categories.length > 0 && !filters.categories.includes(row.category)) {
      return false;
    }

    if (
      filters.subcategories.length > 0 &&
      !filters.subcategories.includes(row.subcategory)
    ) {
      return false;
    }

    if (filters.liveOnly && !row.isLive) {
      return false;
    }

    if (
      keyword &&
      !`${row.eventTitle} ${row.marketName} ${row.category} ${row.subcategory}`
        .toLowerCase()
        .includes(keyword)
    ) {
      return false;
    }

    if (!rangePasses(row.volume, filters.volumeMin, filters.volumeMax)) {
      return false;
    }

    if (!rangePasses(row.spread, filters.spreadMin, filters.spreadMax)) {
      return false;
    }

    if (!rangePasses(row.bid, filters.bidMin, filters.bidMax)) {
      return false;
    }

    if (!rangePasses(row.ask, filters.askMin, filters.askMax)) {
      return false;
    }

    return true;
  });
}

function sortRows(rows: FlatRow[], topBar: TopBarState): FlatRow[] {
  const multiplier = topBar.sortDirection === "asc" ? 1 : -1;
  const sorted = [...rows];

  sorted.sort((left, right) => {
    let leftValue: number | string = "";
    let rightValue: number | string = "";

    switch (topBar.sortField) {
      case "category":
        leftValue = `${left.category}-${left.subcategory}-${left.displayName}`;
        rightValue = `${right.category}-${right.subcategory}-${right.displayName}`;
        break;
      case "market":
        leftValue = left.displayName;
        rightValue = right.displayName;
        break;
      case "bid":
        leftValue = left.bid;
        rightValue = right.bid;
        break;
      case "ask":
        leftValue = left.ask;
        rightValue = right.ask;
        break;
      case "startTime":
        leftValue = new Date(left.startTime).getTime();
        rightValue = new Date(right.startTime).getTime();
        break;
      case "volume":
        leftValue = left.volume;
        rightValue = right.volume;
        break;
    }

    if (leftValue < rightValue) {
      return -1 * multiplier;
    }

    if (leftValue > rightValue) {
      return 1 * multiplier;
    }

    return left.displayName.localeCompare(right.displayName) * multiplier;
  });

  return sorted;
}

function buildGroups(rows: FlatRow[], topBar: TopBarState): EventGroup[] {
  const byEvent = new Map<string, EventGroup>();

  for (const row of rows) {
    const existing = byEvent.get(row.eventId);

    if (existing) {
      existing.childRows.push(row);
      existing.aggregateVolume += row.volume;
      existing.sortBid = Math.max(existing.sortBid, row.bid);
      existing.sortAsk = Math.max(existing.sortAsk, row.ask);
      existing.spread = Math.max(existing.spread, row.spread);
      continue;
    }

    byEvent.set(row.eventId, {
      id: row.eventId,
      category: row.category,
      subcategory: row.subcategory,
      title: row.eventTitle,
      startTime: row.startTime,
      isLive: row.isLive,
      childRows: [row],
      aggregateVolume: row.volume,
      summaryBid: row.bid,
      summaryAsk: row.ask,
      sortBid: row.bid,
      sortAsk: row.ask,
      spread: row.spread,
    });
  }

  const groups = Array.from(byEvent.values()).map((group) => {
    const sortedChildren = sortRows(group.childRows, topBar);
    const hasMultipleMarkets = sortedChildren.length > 1;

    return {
      ...group,
      childRows: sortedChildren,
      summaryBid: hasMultipleMarkets ? null : sortedChildren[0].bid,
      summaryAsk: hasMultipleMarkets ? null : sortedChildren[0].ask,
    };
  });

  const multiplier = topBar.sortDirection === "asc" ? 1 : -1;

  groups.sort((left, right) => {
    let leftValue: number | string = "";
    let rightValue: number | string = "";

    switch (topBar.sortField) {
      case "category":
        leftValue = `${left.category}-${left.subcategory}-${left.title}`;
        rightValue = `${right.category}-${right.subcategory}-${right.title}`;
        break;
      case "market":
        leftValue = left.title;
        rightValue = right.title;
        break;
      case "bid":
        leftValue = left.sortBid;
        rightValue = right.sortBid;
        break;
      case "ask":
        leftValue = left.sortAsk;
        rightValue = right.sortAsk;
        break;
      case "startTime":
        leftValue = new Date(left.startTime).getTime();
        rightValue = new Date(right.startTime).getTime();
        break;
      case "volume":
        leftValue = left.aggregateVolume;
        rightValue = right.aggregateVolume;
        break;
    }

    if (leftValue < rightValue) {
      return -1 * multiplier;
    }

    if (leftValue > rightValue) {
      return 1 * multiplier;
    }

    return left.title.localeCompare(right.title) * multiplier;
  });

  return groups;
}

function toggleValue(values: string[], target: string): string[] {
  return values.includes(target)
    ? values.filter((value) => value !== target)
    : [...values, target];
}

function isDefaultView(view: ViewState, title: string): boolean {
  return JSON.stringify(view) === JSON.stringify(initialViewState) && !title.trim();
}

function App() {
  const [history, setHistory] = useState<HistoryState>({
    past: [],
    present: initialViewState,
    future: [],
  });
  const [viewTitle, setViewTitle] = useState("");
  const [expandedEventIds, setExpandedEventIds] = useState<string[]>([]);
  const [lastMockRefresh, setLastMockRefresh] = useState(new Date());

  const isDirty = !isDefaultView(history.present, viewTitle);
  const flatRows = sortRows(
    filterRows(flattenEvents(MOCK_EVENTS), history.present.filters),
    history.present.topBar,
  );
  const groupedRows = buildGroups(flatRows, history.present.topBar);
  const visibleMarketCount = flatRows.length;
  const visibleEventCount = groupedRows.length;
  const isBlankDefault =
    history.present.filters.categories.length === 0 &&
    history.present.filters.subcategories.length === 0 &&
    history.present.filters.keyword.trim() === "" &&
    !history.present.filters.liveOnly;

  useEffect(() => {
    if (history.present.topBar.autoRefresh === "off") {
      return;
    }

    const milliseconds =
      history.present.topBar.autoRefresh === "15s"
        ? 15000
        : history.present.topBar.autoRefresh === "30s"
          ? 30000
          : 60000;

    const timer = window.setInterval(() => {
      setLastMockRefresh(new Date());
    }, milliseconds);

    return () => window.clearInterval(timer);
  }, [history.present.topBar.autoRefresh]);

  function setTopBar<K extends keyof TopBarState>(key: K, value: TopBarState[K]) {
    setHistory((current) =>
      updateHistory(current, (present) => ({
        ...present,
        topBar: {
          ...present.topBar,
          [key]: value,
        },
      })),
    );
  }

  function setFilter<K extends keyof FilterState>(key: K, value: FilterState[K]) {
    setHistory((current) =>
      updateHistory(current, (present) => ({
        ...present,
        filters: {
          ...present.filters,
          [key]: value,
        },
      })),
    );
  }

  function goBack() {
    setHistory((current) => {
      if (current.past.length === 0) {
        return current;
      }

      const previous = current.past[current.past.length - 1];
      return {
        past: current.past.slice(0, -1),
        present: previous,
        future: [current.present, ...current.future],
      };
    });
  }

  function goForward() {
    setHistory((current) => {
      if (current.future.length === 0) {
        return current;
      }

      const [next, ...remaining] = current.future;
      return {
        past: [...current.past, current.present],
        present: next,
        future: remaining,
      };
    });
  }

  function toggleEventExpansion(eventId: string) {
    setExpandedEventIds((current) =>
      current.includes(eventId)
        ? current.filter((id) => id !== eventId)
        : [...current, eventId],
    );
  }

  const tabLabel = viewTitle.trim() || "Untitled View";

  return (
    <div className="dashboard-shell">
      <aside className="window-chrome">
        <div className="window-dots">
          <span className="dot dot-red" />
          <span className="dot dot-gold" />
          <span className="dot dot-green" />
        </div>
        <p className="window-caption">Single-view prototype</p>
      </aside>

      <div className="dashboard-app">
        <header className="tab-strip">
          <button className="tab active-tab" type="button">
            <span className="tab-title">{tabLabel}</span>
            {isDirty ? <span className="tab-dirty">*</span> : null}
          </button>
        </header>

        <div className="workspace">
          <section className="main-column">
            <div className="toolbar">
              <div className="toolbar-leading">
                <button
                  className="nav-button"
                  disabled={history.past.length === 0}
                  onClick={goBack}
                  type="button"
                >
                  Back
                </button>
                <button
                  className="nav-button"
                  disabled={history.future.length === 0}
                  onClick={goForward}
                  type="button"
                >
                  Forward
                </button>
              </div>

              <div className="view-title-block">
                <label className="field-label" htmlFor="view-title">
                  View Title
                </label>
                <input
                  id="view-title"
                  className="title-input"
                  onChange={(event) => setViewTitle(event.currentTarget.value)}
                  placeholder="Untitled View"
                  value={viewTitle}
                />
              </div>

              <div className="toolbar-controls">
                <label className="checkbox-control">
                  <input
                    checked={history.present.topBar.groupByEvent}
                    onChange={(event) =>
                      setTopBar("groupByEvent", event.currentTarget.checked)
                    }
                    type="checkbox"
                  />
                  <span>Group by event</span>
                </label>

                <label className="select-control">
                  <span>Sort by</span>
                  <select
                    onChange={(event) =>
                      setTopBar("sortField", event.currentTarget.value as SortField)
                    }
                    value={history.present.topBar.sortField}
                  >
                    <option value="category">Category</option>
                    <option value="market">Market</option>
                    <option value="bid">Bid</option>
                    <option value="ask">Ask</option>
                    <option value="startTime">Start time</option>
                    <option value="volume">Volume</option>
                  </select>
                </label>

                <label className="select-control">
                  <span>Direction</span>
                  <select
                    onChange={(event) =>
                      setTopBar(
                        "sortDirection",
                        event.currentTarget.value as SortDirection,
                      )
                    }
                    value={history.present.topBar.sortDirection}
                  >
                    <option value="asc">Ascending</option>
                    <option value="desc">Descending</option>
                  </select>
                </label>

                <label className="select-control">
                  <span>Auto-refresh</span>
                  <select
                    onChange={(event) =>
                      setTopBar(
                        "autoRefresh",
                        event.currentTarget.value as RefreshInterval,
                      )
                    }
                    value={history.present.topBar.autoRefresh}
                  >
                    <option value="off">Off</option>
                    <option value="15s">15s</option>
                    <option value="30s">30s</option>
                    <option value="60s">60s</option>
                  </select>
                </label>
              </div>
            </div>

            <div className="status-bar">
              <div className="status-pill">
                {history.present.topBar.groupByEvent
                  ? `${visibleEventCount} events`
                  : `${visibleMarketCount} markets`}
              </div>
              <div className="status-pill">
                Refresh:{" "}
                {history.present.topBar.autoRefresh === "off"
                  ? "manual prototype"
                  : history.present.topBar.autoRefresh}
              </div>
              <div className="status-pill">
                Last refresh {lastMockRefresh.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" })}
              </div>
            </div>

            <section className="main-pane">
              <div className="table-header">
                <span>Category</span>
                <span>Market</span>
                <span>Bid</span>
                <span>Ask</span>
                <span>Event start</span>
                <span>Volume</span>
              </div>

              {isBlankDefault ? (
                <div className="blank-state">
                  <p className="blank-eyebrow">Blank default view</p>
                  <h1>Pick a category or sub-category to begin scanning markets.</h1>
                  <p>
                    This prototype starts empty on purpose so the main pane behaves
                    like the document-style blank view we defined in the spec.
                  </p>
                </div>
              ) : history.present.topBar.groupByEvent ? (
                <div className="table-body">
                  {groupedRows.length === 0 ? (
                    <div className="no-results">
                      <p>No events match the current filters.</p>
                    </div>
                  ) : (
                    groupedRows.map((group) => {
                      const expanded = expandedEventIds.includes(group.id);
                      const hasChildren = group.childRows.length > 1;

                      return (
                        <div className="event-group" key={group.id}>
                          <button
                            className="event-row"
                            onClick={() =>
                              hasChildren ? toggleEventExpansion(group.id) : null
                            }
                            type="button"
                          >
                            <span className="cell category-cell">
                              <span className="category-pill">{group.category}</span>
                              <span className="subcategory-text">
                                {group.subcategory}
                              </span>
                            </span>
                            <span className="cell market-cell">
                              {hasChildren ? (
                                <span className="event-toggle-label">
                                  <span className="toggle-glyph">
                                    {expanded ? "▾" : "▸"}
                                  </span>
                                  {group.title}
                                </span>
                              ) : (
                                group.title
                              )}
                            </span>
                            <span className="cell numeric-cell">
                              {formatCurrencyPoints(group.summaryBid)}
                            </span>
                            <span className="cell numeric-cell">
                              {formatCurrencyPoints(group.summaryAsk)}
                            </span>
                            <span className="cell">{formatDate(group.startTime)}</span>
                            <span className="cell numeric-cell">
                              {formatVolume(group.aggregateVolume)}
                            </span>
                          </button>

                          {expanded && hasChildren ? (
                            <div className="child-rows">
                              {group.childRows.map((row) => (
                                <div className="child-row" key={row.id}>
                                  <span className="cell category-cell child-category">
                                    <span className="child-market-label">
                                      {row.marketName}
                                    </span>
                                  </span>
                                  <span className="cell market-cell child-market-cell">
                                    {row.eventTitle}
                                  </span>
                                  <span className="cell numeric-cell">
                                    {formatCurrencyPoints(row.bid)}
                                  </span>
                                  <span className="cell numeric-cell">
                                    {formatCurrencyPoints(row.ask)}
                                  </span>
                                  <span className="cell">{formatDate(row.startTime)}</span>
                                  <span className="cell numeric-cell">
                                    {formatVolume(row.volume)}
                                  </span>
                                </div>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      );
                    })
                  )}
                </div>
              ) : (
                <div className="table-body">
                  {flatRows.length === 0 ? (
                    <div className="no-results">
                      <p>No markets match the current filters.</p>
                    </div>
                  ) : (
                    flatRows.map((row) => (
                      <div className="market-row" key={row.id}>
                        <span className="cell category-cell">
                          <span className="category-pill">{row.category}</span>
                          <span className="subcategory-text">{row.subcategory}</span>
                        </span>
                        <span className="cell market-cell">{row.displayName}</span>
                        <span className="cell numeric-cell">
                          {formatCurrencyPoints(row.bid)}
                        </span>
                        <span className="cell numeric-cell">
                          {formatCurrencyPoints(row.ask)}
                        </span>
                        <span className="cell">{formatDate(row.startTime)}</span>
                        <span className="cell numeric-cell">
                          {formatVolume(row.volume)}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              )}
            </section>
          </section>

          <aside className="filter-pane">
            <div className="filter-pane-header">
              <p className="pane-eyebrow">Filter Configuration</p>
              <h2>Shape the scanner</h2>
              <p>
                This right rail owns row inclusion logic. It is intentionally
                separate from the lighter view controls in the top bar.
              </p>
            </div>

            <section className="filter-section">
              <div className="section-header">
                <h3>Scope</h3>
                <label className="checkbox-control">
                  <input
                    checked={history.present.filters.liveOnly}
                    onChange={(event) =>
                      setFilter("liveOnly", event.currentTarget.checked)
                    }
                    type="checkbox"
                  />
                  <span>Live events only</span>
                </label>
              </div>

              <div className="tag-grid">
                {ALL_CATEGORIES.map((category) => (
                  <button
                    className={
                      history.present.filters.categories.includes(category)
                        ? "tag-button active-tag"
                        : "tag-button"
                    }
                    key={category}
                    onClick={() =>
                      setFilter(
                        "categories",
                        toggleValue(history.present.filters.categories, category),
                      )
                    }
                    type="button"
                  >
                    {category}
                  </button>
                ))}
              </div>

              <div className="tag-grid muted-grid">
                {ALL_SUBCATEGORIES.map((subcategory) => (
                  <button
                    className={
                      history.present.filters.subcategories.includes(subcategory)
                        ? "tag-button active-tag"
                        : "tag-button"
                    }
                    key={subcategory}
                    onClick={() =>
                      setFilter(
                        "subcategories",
                        toggleValue(
                          history.present.filters.subcategories,
                          subcategory,
                        ),
                      )
                    }
                    type="button"
                  >
                    {subcategory}
                  </button>
                ))}
              </div>
            </section>

            <section className="filter-section">
              <div className="section-header">
                <h3>Keyword</h3>
              </div>
              <input
                className="text-filter"
                onChange={(event) => setFilter("keyword", event.currentTarget.value)}
                placeholder="Search market text"
                value={history.present.filters.keyword}
              />
            </section>

            <section className="filter-section">
              <div className="section-header">
                <h3>Ranges</h3>
              </div>

              <div className="range-grid">
                <RangePair
                  label="Volume"
                  maxKey="volumeMax"
                  minKey="volumeMin"
                  onChange={setFilter}
                  state={history.present.filters}
                />
                <RangePair
                  label="Spread"
                  maxKey="spreadMax"
                  minKey="spreadMin"
                  onChange={setFilter}
                  state={history.present.filters}
                />
                <RangePair
                  label="Bid"
                  maxKey="bidMax"
                  minKey="bidMin"
                  onChange={setFilter}
                  state={history.present.filters}
                />
                <RangePair
                  label="Ask"
                  maxKey="askMax"
                  minKey="askMin"
                  onChange={setFilter}
                  state={history.present.filters}
                />
              </div>
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}

type RangePairProps = {
  label: string;
  minKey: keyof FilterRanges;
  maxKey: keyof FilterRanges;
  state: FilterState;
  onChange: <K extends keyof FilterState>(key: K, value: FilterState[K]) => void;
};

function RangePair({ label, minKey, maxKey, state, onChange }: RangePairProps) {
  return (
    <div className="range-card">
      <span className="range-label">{label}</span>
      <div className="range-inputs">
        <input
          inputMode="numeric"
          onChange={(event) => onChange(minKey, event.currentTarget.value)}
          placeholder="Min"
          value={state[minKey]}
        />
        <input
          inputMode="numeric"
          onChange={(event) => onChange(maxKey, event.currentTarget.value)}
          placeholder="Max"
          value={state[maxKey]}
        />
      </div>
    </div>
  );
}

export default App;
