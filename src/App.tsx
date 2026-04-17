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

type ApiMarket = {
  ticker: string;
  title?: string;
  subtitle?: string;
  status?: string;
  yes_sub_title?: string;
  yes_bid_dollars?: string;
  yes_ask_dollars?: string;
  volume_fp?: string;
  rules_primary?: string;
};

type ApiEvent = {
  event_ticker: string;
  series_ticker: string;
  title: string;
  sub_title?: string;
  category?: string;
  strike_date?: string;
  markets?: ApiMarket[];
};

type EventRecord = {
  id: string;
  category: string;
  subcategory: string;
  title: string;
  startTime: string;
  isLive: boolean;
  markets: MarketRecord[];
};

type MarketRecord = {
  id: string;
  label: string;
  bid: number;
  ask: number;
  volume: number;
  rulesPrimary: string;
};

type FlatRow = {
  id: string;
  eventId: string;
  category: string;
  subcategory: string;
  eventTitle: string;
  displayName: string;
  marketLabel: string;
  startTime: string;
  isLive: boolean;
  bid: number;
  ask: number;
  volume: number;
  spread: number;
  rulesPrimary: string;
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
};

const API_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2";

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

function parsePriceToCents(value?: string): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? Math.round(parsed * 100) : 0;
}

function parseVolume(value?: string): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? Math.round(parsed) : 0;
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

function getMarketLabel(market: ApiMarket): string {
  return market.subtitle || market.yes_sub_title || market.title || market.ticker;
}

function normalizeApiEvent(event: ApiEvent): EventRecord | null {
  const rawMarkets = event.markets ?? [];
  const openMarkets = rawMarkets.filter((market) => market.status === "open");

  if (openMarkets.length === 0) {
    return null;
  }

  const markets: MarketRecord[] = openMarkets.map((market) => ({
    id: market.ticker,
    label: getMarketLabel(market),
    bid: parsePriceToCents(market.yes_bid_dollars),
    ask: parsePriceToCents(market.yes_ask_dollars),
    volume: parseVolume(market.volume_fp),
    rulesPrimary: market.rules_primary ?? "",
  }));

  return {
    id: event.event_ticker,
    category: event.category || "Other",
    subcategory: event.sub_title || event.series_ticker || "General",
    title: event.title,
    startTime: event.strike_date || new Date().toISOString(),
    isLive: markets.some((market) => market.volume > 0),
    markets,
  };
}

async function fetchEventCollection(
  path: string,
  includeStatus: boolean,
  signal: AbortSignal,
): Promise<EventRecord[]> {
  const events: EventRecord[] = [];
  let cursor = "";

  while (true) {
    const params = new URLSearchParams({
      with_nested_markets: "true",
      limit: "200",
    });

    if (includeStatus) {
      params.set("status", "open");
    }

    if (cursor) {
      params.set("cursor", cursor);
    }

    const response = await fetch(`${API_BASE_URL}${path}?${params.toString()}`, {
      signal,
    });

    if (!response.ok) {
      throw new Error(`Kalshi request failed with ${response.status}`);
    }

    const payload = (await response.json()) as { events?: ApiEvent[]; cursor?: string };

    for (const event of payload.events ?? []) {
      const normalized = normalizeApiEvent(event);
      if (normalized) {
        events.push(normalized);
      }
    }

    cursor = payload.cursor ?? "";
    if (!cursor) {
      break;
    }
  }

  return events;
}

async function fetchAllOpenEvents(signal: AbortSignal): Promise<EventRecord[]> {
  const [standardEvents, multivariateEvents] = await Promise.all([
    fetchEventCollection("/events", true, signal),
    fetchEventCollection("/events/multivariate", false, signal),
  ]);

  const deduped = new Map<string, EventRecord>();
  for (const event of [...standardEvents, ...multivariateEvents]) {
    deduped.set(event.id, event);
  }
  return Array.from(deduped.values());
}

function flattenEvents(events: EventRecord[]): FlatRow[] {
  return events.flatMap((event) =>
    event.markets.map((market) => ({
      id: market.id,
      eventId: event.id,
      category: event.category,
      subcategory: event.subcategory,
      eventTitle: event.title,
      displayName:
        event.markets.length > 1 ? `${event.title} - ${market.label}` : event.title,
      marketLabel: market.label,
      startTime: event.startTime,
      isLive: event.isLive,
      bid: market.bid,
      ask: market.ask,
      volume: market.volume,
      spread: market.ask - market.bid,
      rulesPrimary: market.rulesPrimary,
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
      !`${row.eventTitle} ${row.marketLabel} ${row.category} ${row.subcategory}`
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
  const grouped = new Map<string, EventGroup>();

  for (const row of rows) {
    const existing = grouped.get(row.eventId);

    if (existing) {
      existing.childRows.push(row);
      existing.aggregateVolume += row.volume;
      existing.sortBid = Math.max(existing.sortBid, row.bid);
      existing.sortAsk = Math.max(existing.sortAsk, row.ask);
      continue;
    }

    grouped.set(row.eventId, {
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
    });
  }

  const groups = Array.from(grouped.values()).map((group) => {
    const sortedChildren = sortRows(group.childRows, topBar);
    return {
      ...group,
      childRows: sortedChildren,
      summaryBid: sortedChildren.length === 1 ? sortedChildren[0].bid : null,
      summaryAsk: sortedChildren.length === 1 ? sortedChildren[0].ask : null,
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

function getNextSortState(
  field: SortField,
  current: TopBarState,
): Pick<TopBarState, "sortField" | "sortDirection"> {
  if (current.sortField === field) {
    return {
      sortField: field,
      sortDirection: current.sortDirection === "asc" ? "desc" : "asc",
    };
  }

  const defaultDirection =
    field === "bid" || field === "ask" || field === "volume" ? "desc" : "asc";

  return {
    sortField: field,
    sortDirection: defaultDirection,
  };
}

function App() {
  const [history, setHistory] = useState<HistoryState>({
    past: [],
    present: initialViewState,
    future: [],
  });
  const [viewTitle, setViewTitle] = useState("");
  const [expandedEventIds, setExpandedEventIds] = useState<string[]>([]);
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const flatRows = sortRows(
    filterRows(flattenEvents(events), history.present.filters),
    history.present.topBar,
  );
  const groupedRows = buildGroups(flatRows, history.present.topBar);
  const allRows = flattenEvents(events);
  const allCategories = Array.from(new Set(allRows.map((row) => row.category))).sort();
  const allSubcategories = Array.from(
    new Set(allRows.map((row) => row.subcategory)),
  ).sort();
  const isDirty = !isDefaultView(history.present, viewTitle);
  const isBlankDefault =
    history.present.filters.categories.length === 0 &&
    history.present.filters.subcategories.length === 0 &&
    history.present.filters.keyword.trim() === "" &&
    !history.present.filters.liveOnly;

  async function loadKalshiData(signal: AbortSignal) {
    setIsLoading(true);
    setLoadError("");

    try {
      const nextEvents = await fetchAllOpenEvents(signal);
      if (signal.aborted) {
        return;
      }
      setEvents(nextEvents);
      setLastRefresh(new Date());
    } catch (error) {
      if (signal.aborted) {
        return;
      }
      setLoadError(
        error instanceof Error ? error.message : "Unable to load Kalshi markets.",
      );
    } finally {
      if (!signal.aborted) {
        setIsLoading(false);
      }
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    void loadKalshiData(controller.signal);
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (history.present.topBar.autoRefresh === "off") {
      return;
    }

    const intervalMs =
      history.present.topBar.autoRefresh === "15s"
        ? 15000
        : history.present.topBar.autoRefresh === "30s"
          ? 30000
          : 60000;

    const timer = window.setInterval(() => {
      const controller = new AbortController();
      void loadKalshiData(controller.signal);
    }, intervalMs);

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

  function handleSortClick(field: SortField) {
    const nextSort = getNextSortState(field, history.present.topBar);
    setHistory((current) =>
      updateHistory(current, (present) => ({
        ...present,
        topBar: {
          ...present.topBar,
          ...nextSort,
        },
      })),
    );
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
              <div className="status-pill">{events.length} open events loaded</div>
              <div className="status-pill">{allRows.length} open markets loaded</div>
              <div className="status-pill">
                Showing{" "}
                {history.present.topBar.groupByEvent
                  ? `${groupedRows.length} events`
                  : `${flatRows.length} markets`}
              </div>
              <div className="status-pill">
                Last refresh{" "}
                {lastRefresh
                  ? lastRefresh.toLocaleTimeString([], {
                      hour: "numeric",
                      minute: "2-digit",
                      second: "2-digit",
                    })
                  : "pending"}
              </div>
            </div>

            <section className="main-pane">
              <div className="table-header">
                <SortHeader
                  activeField={history.present.topBar.sortField}
                  direction={history.present.topBar.sortDirection}
                  field="category"
                  label="Category"
                  onClick={handleSortClick}
                />
                <SortHeader
                  activeField={history.present.topBar.sortField}
                  direction={history.present.topBar.sortDirection}
                  field="market"
                  label="Market"
                  onClick={handleSortClick}
                />
                <SortHeader
                  activeField={history.present.topBar.sortField}
                  direction={history.present.topBar.sortDirection}
                  field="bid"
                  label="Bid"
                  onClick={handleSortClick}
                />
                <SortHeader
                  activeField={history.present.topBar.sortField}
                  direction={history.present.topBar.sortDirection}
                  field="ask"
                  label="Ask"
                  onClick={handleSortClick}
                />
                <SortHeader
                  activeField={history.present.topBar.sortField}
                  direction={history.present.topBar.sortDirection}
                  field="startTime"
                  label="Event start"
                  onClick={handleSortClick}
                />
                <SortHeader
                  activeField={history.present.topBar.sortField}
                  direction={history.present.topBar.sortDirection}
                  field="volume"
                  label="Volume"
                  onClick={handleSortClick}
                />
              </div>

              <div className="table-body">
                {loadError ? (
                  <div className="message-card error-card">
                    <h1>Kalshi data failed to load.</h1>
                    <p>{loadError}</p>
                  </div>
                ) : isLoading && events.length === 0 ? (
                  <div className="message-card">
                    <h1>Loading open markets from Kalshi…</h1>
                    <p>
                      This viewer now pulls live event and market data instead of
                      rendering the original mock prototype.
                    </p>
                  </div>
                ) : isBlankDefault ? (
                  <div className="message-card">
                    <p className="blank-eyebrow">Blank default view</p>
                    <h1>Pick a category or sub-category to begin scanning markets.</h1>
                    <p>
                      The app is already loaded with live open Kalshi data, but the
                      default view intentionally starts with an empty main pane.
                    </p>
                  </div>
                ) : history.present.topBar.groupByEvent ? (
                  groupedRows.length === 0 ? (
                    <div className="message-card">
                      <h1>No events match the current filters.</h1>
                      <p>Try loosening category, keyword, or range constraints.</p>
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
                              hasChildren ? toggleEventExpansion(group.id) : undefined
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
                              <span className="event-toggle-label">
                                {hasChildren ? (
                                  <span className="toggle-glyph">
                                    {expanded ? "▾" : "▸"}
                                  </span>
                                ) : null}
                                {group.title}
                              </span>
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
                                      {row.marketLabel}
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
                  )
                ) : flatRows.length === 0 ? (
                  <div className="message-card">
                    <h1>No markets match the current filters.</h1>
                    <p>Try loosening category, keyword, or range constraints.</p>
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
            </section>
          </section>

          <aside className="filter-pane">
            <div className="filter-pane-header">
              <p className="pane-eyebrow">Filter Configuration</p>
              <h2>Shape the scanner</h2>
              <p>
                The right pane controls which rows appear. Each pane scrolls
                independently so the app shell stays fixed.
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
                {allCategories.map((category) => (
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
                {allSubcategories.map((subcategory) => (
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

type SortHeaderProps = {
  field: SortField;
  label: string;
  activeField: SortField;
  direction: SortDirection;
  onClick: (field: SortField) => void;
};

function SortHeader({
  field,
  label,
  activeField,
  direction,
  onClick,
}: SortHeaderProps) {
  const isActive = activeField === field;
  const arrow = isActive ? (direction === "asc" ? "↑" : "↓") : "";

  return (
    <button
      className={isActive ? "header-button active-header" : "header-button"}
      onClick={() => onClick(field)}
      type="button"
    >
      <span>{label}</span>
      <span className="header-arrow">{arrow}</span>
    </button>
  );
}

export default App;
