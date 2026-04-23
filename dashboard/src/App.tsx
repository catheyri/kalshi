import { invoke } from "@tauri-apps/api/core";
import {
  startTransition,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import "./App.css";

type AppTab = "markets" | "positions" | "watching";
type SortField =
  | "category"
  | "market"
  | "yes"
  | "no"
  | "startTime"
  | "volume"
  | "position"
  | "exposure"
  | "pnl";
type SortDirection = "asc" | "desc";
type RefreshInterval = "off" | "15s" | "30s" | "60s";
type PageSize = 25 | 50 | 100;

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
  liveOnly: boolean;
  keyword: string;
};

type TopBarState = {
  groupByEvent: boolean;
  sortField: SortField;
  sortDirection: SortDirection;
  autoRefresh: RefreshInterval;
  pageSize: PageSize;
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

type EventSummary = {
  id: string;
  category: string;
  subcategory: string;
  title: string;
  startTime: string;
  isLive: boolean;
};

type MarketRecord = {
  id: string;
  label: string;
  yesBid: number;
  yesAsk: number;
  noBid: number;
  noAsk: number;
  volume: number;
  rulesPrimary: string;
};

type EventDetails = {
  id: string;
  markets: MarketRecord[];
};

type EventPage = {
  category: string;
  events: EventSummary[];
  cursor: string | null;
};

type PositionRecord = {
  ticker: string;
  eventTicker: string;
  category: string;
  eventTitle: string;
  marketLabel: string;
  startTime: string;
  isLive: boolean;
  yesBid: number;
  yesAsk: number;
  noBid: number;
  noAsk: number;
  volume: number;
  position: number;
  exposureDollars: number;
  totalTradedDollars: number;
  realizedPnlDollars: number;
  feesPaidDollars: number;
  rulesPrimary: string;
};

type CategoryCacheEntry = {
  events: EventSummary[];
  isLoading: boolean;
  isComplete: boolean;
  lastUpdatedAt: number | null;
};

type EventDetailCacheEntry = {
  markets: MarketRecord[];
  isLoading: boolean;
  loaded: boolean;
};

type FlatMarketRow = {
  id: string;
  eventId: string;
  category: string;
  eventTitle: string;
  marketLabel: string;
  displayName: string;
  startTime: string;
  isLive: boolean;
  yesBid: number;
  yesAsk: number;
  noBid: number;
  noAsk: number;
  volume: number;
  spread: number;
};

type PortfolioRow = {
  id: string;
  eventId: string;
  category: string;
  eventTitle: string;
  marketLabel: string;
  displayName: string;
  startTime: string;
  isLive: boolean;
  yesBid: number;
  yesAsk: number;
  noBid: number;
  noAsk: number;
  volume: number;
  spread: number;
  position: number;
  exposureDollars: number;
  realizedPnlDollars: number;
  rulesPrimary: string;
};

type EventGroup<T> = {
  id: string;
  category: string;
  title: string;
  startTime: string;
  isLive: boolean;
  rows: T[];
};

const WATCH_STORAGE_KEY = "kalshi-dashboard-watchlist";

const defaultFilters: FilterState = {
  categories: [],
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
  groupByEvent: true,
  sortField: "startTime",
  sortDirection: "asc",
  autoRefresh: "off",
  pageSize: 25,
};

const initialViewState: ViewState = {
  filters: defaultFilters,
  topBar: defaultTopBar,
};

const PERF_FLAG = "kalshi-dashboard-perf";

function isPerfEnabled(): boolean {
  if (!import.meta.env.DEV) {
    return false;
  }

  if (typeof window === "undefined") {
    return false;
  }

  return window.localStorage.getItem(PERF_FLAG) === "1";
}

function logPerfMetric(name: string, durationMs: number, detail?: Record<string, unknown>) {
  if (!isPerfEnabled()) {
    return;
  }

  const payload = {
    kind: "ui",
    name,
    duration_ms: Number(durationMs.toFixed(2)),
    ...detail,
  };

  console.log("[perf]", JSON.stringify(payload));
}

function measurePerf<T>(name: string, run: () => T, detail?: Record<string, unknown>): T {
  if (!isPerfEnabled()) {
    return run();
  }

  const startedAt = performance.now();
  const result = run();
  logPerfMetric(name, performance.now() - startedAt, detail);
  return result;
}

async function measureAsyncPerf<T>(
  name: string,
  run: () => Promise<T>,
  detail?: Record<string, unknown>,
): Promise<T> {
  if (!isPerfEnabled()) {
    return run();
  }

  const startedAt = performance.now();
  try {
    return await run();
  } finally {
    logPerfMetric(name, performance.now() - startedAt, detail);
  }
}

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

function formatQuote(bid: number | null, ask: number | null): string {
  if (bid === null || ask === null) {
    return "--";
  }

  return `${formatCurrencyPoints(bid)}/${formatCurrencyPoints(ask)}`;
}

function formatVolume(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

function formatDollarAmount(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatPosition(value: number): string {
  if (!Number.isFinite(value) || value === 0) {
    return "--";
  }

  return value.toFixed(0);
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
    field === "yes" ||
    field === "no" ||
    field === "volume" ||
    field === "position" ||
    field === "exposure" ||
    field === "pnl"
      ? "desc"
      : "asc";

  return {
    sortField: field,
    sortDirection: defaultDirection,
  };
}

function mergeEventSummaries(current: EventSummary[], incoming: EventSummary[]) {
  const deduped = new Map(current.map((event) => [event.id, event]));
  for (const event of incoming) {
    deduped.set(event.id, event);
  }
  return Array.from(deduped.values());
}

function delayMs(durationMs: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, durationMs));
}

function getCategoryRefreshFreshnessMs(autoRefresh: RefreshInterval): number {
  if (autoRefresh === "15s") {
    return 10_000;
  }

  if (autoRefresh === "30s") {
    return 20_000;
  }

  if (autoRefresh === "60s") {
    return 40_000;
  }

  return 0;
}

function getCategoryRefreshStatus(
  entry: CategoryCacheEntry | undefined,
  freshnessMs: number,
): "loading" | "fresh" | "stale" | "pending" {
  if (!entry) {
    return "pending";
  }

  if (entry.isLoading) {
    return "loading";
  }

  if (entry.lastUpdatedAt === null) {
    return "pending";
  }

  if (freshnessMs > 0 && Date.now() - entry.lastUpdatedAt < freshnessMs) {
    return "fresh";
  }

  return "stale";
}

function formatElapsedMs(timestamp: number | null): string {
  if (timestamp === null) {
    return "Not loaded yet";
  }

  const elapsedSeconds = Math.max(0, Math.round((Date.now() - timestamp) / 1000));
  if (elapsedSeconds < 5) {
    return "Updated just now";
  }
  if (elapsedSeconds < 60) {
    return `Updated ${elapsedSeconds}s ago`;
  }

  const elapsedMinutes = Math.round(elapsedSeconds / 60);
  return `Updated ${elapsedMinutes}m ago`;
}

function compareValues(
  left: string | number,
  right: string | number,
  direction: SortDirection,
) {
  const multiplier = direction === "asc" ? 1 : -1;

  if (left < right) {
    return -1 * multiplier;
  }

  if (left > right) {
    return 1 * multiplier;
  }

  return 0;
}

function filterPortfolioRows(rows: PortfolioRow[], filters: FilterState) {
  const keyword = filters.keyword.trim().toLowerCase();

  return rows.filter((row) => {
    if (filters.categories.length > 0 && !filters.categories.includes(row.category)) {
      return false;
    }
    if (filters.liveOnly && !row.isLive) {
      return false;
    }
    if (
      keyword &&
      !`${row.eventTitle} ${row.marketLabel} ${row.category}`
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
    if (!rangePasses(row.yesBid, filters.bidMin, filters.bidMax)) {
      return false;
    }
    if (!rangePasses(row.yesAsk, filters.askMin, filters.askMax)) {
      return false;
    }
    return true;
  });
}

function sortPortfolioRows(rows: PortfolioRow[], topBar: TopBarState) {
  const sorted = [...rows];

  sorted.sort((left, right) => {
    let leftValue: string | number = "";
    let rightValue: string | number = "";

    switch (topBar.sortField) {
      case "category":
        leftValue = `${left.category}-${left.eventTitle}-${left.marketLabel}`;
        rightValue = `${right.category}-${right.eventTitle}-${right.marketLabel}`;
        break;
      case "market":
        leftValue = `${left.eventTitle}-${left.marketLabel}`;
        rightValue = `${right.eventTitle}-${right.marketLabel}`;
        break;
      case "startTime":
        leftValue = new Date(left.startTime).getTime();
        rightValue = new Date(right.startTime).getTime();
        break;
      case "yes":
        leftValue = left.yesBid;
        rightValue = right.yesBid;
        break;
      case "no":
        leftValue = left.noBid;
        rightValue = right.noBid;
        break;
      case "volume":
        leftValue = left.volume;
        rightValue = right.volume;
        break;
      case "position":
        leftValue = left.position;
        rightValue = right.position;
        break;
      case "exposure":
        leftValue = left.exposureDollars;
        rightValue = right.exposureDollars;
        break;
      case "pnl":
        leftValue = left.realizedPnlDollars;
        rightValue = right.realizedPnlDollars;
        break;
    }

    const comparison = compareValues(leftValue, rightValue, topBar.sortDirection);
    if (comparison !== 0) {
      return comparison;
    }

    return left.displayName.localeCompare(right.displayName);
  });

  return sorted;
}

function groupPortfolioRows(rows: PortfolioRow[]) {
  const grouped = new Map<string, EventGroup<PortfolioRow>>();

  for (const row of rows) {
    const current = grouped.get(row.eventId);
    if (current) {
      current.rows.push(row);
      continue;
    }

    grouped.set(row.eventId, {
      id: row.eventId,
      category: row.category,
      title: row.eventTitle,
      startTime: row.startTime,
      isLive: row.isLive,
      rows: [row],
    });
  }

  return Array.from(grouped.values());
}

function sortEventGroups<T extends { yesBid: number; noBid: number; volume: number }>(
  groups: EventGroup<T>[],
  topBar: TopBarState,
) {
  const sorted = [...groups];

  sorted.sort((left, right) => {
    let leftValue: string | number = "";
    let rightValue: string | number = "";

    switch (topBar.sortField) {
      case "category":
        leftValue = `${left.category}-${left.title}`;
        rightValue = `${right.category}-${right.title}`;
        break;
      case "market":
        leftValue = left.title;
        rightValue = right.title;
        break;
      case "startTime":
        leftValue = new Date(left.startTime).getTime();
        rightValue = new Date(right.startTime).getTime();
        break;
      case "yes":
        leftValue = Math.max(...left.rows.map((row) => row.yesBid), -1);
        rightValue = Math.max(...right.rows.map((row) => row.yesBid), -1);
        break;
      case "no":
        leftValue = Math.max(...left.rows.map((row) => row.noBid), -1);
        rightValue = Math.max(...right.rows.map((row) => row.noBid), -1);
        break;
      case "volume":
        leftValue = left.rows.reduce((sum, row) => sum + row.volume, 0);
        rightValue = right.rows.reduce((sum, row) => sum + row.volume, 0);
        break;
      default:
        leftValue = left.title;
        rightValue = right.title;
        break;
    }

    const comparison = compareValues(leftValue, rightValue, topBar.sortDirection);
    if (comparison !== 0) {
      return comparison;
    }

    return left.title.localeCompare(right.title);
  });

  return sorted;
}

function flattenLoadedMarkets(
  summaries: EventSummary[],
  detailsCache: Record<string, EventDetailCacheEntry>,
): FlatMarketRow[] {
  return summaries.flatMap((summary) => {
    const details = detailsCache[summary.id];
    if (!details?.loaded) {
      return [];
    }

    return details.markets.map((market) => ({
      id: market.id,
      eventId: summary.id,
      category: summary.category,
      eventTitle: summary.title,
      marketLabel: market.label,
      displayName:
        details.markets.length > 1 ? `${summary.title} - ${market.label}` : summary.title,
      startTime: summary.startTime,
      isLive: summary.isLive,
      yesBid: market.yesBid,
      yesAsk: market.yesAsk,
      noBid: market.noBid,
      noAsk: market.noAsk,
      volume: market.volume,
      spread: market.yesAsk - market.yesBid,
    }));
  });
}

function App() {
  const [history, setHistory] = useState<HistoryState>({
    past: [],
    present: initialViewState,
    future: [],
  });
  const [activeTab, setActiveTab] = useState<AppTab>("markets");
  const [viewTitle, setViewTitle] = useState("");
  const [expandedEventIds, setExpandedEventIds] = useState<string[]>([]);
  const [availableCategories, setAvailableCategories] = useState<string[]>([]);
  const [categoriesLoading, setCategoriesLoading] = useState(true);
  const [categoriesError, setCategoriesError] = useState("");
  const [categoryCache, setCategoryCache] = useState<Record<string, CategoryCacheEntry>>(
    {},
  );
  const [detailsCache, setDetailsCache] = useState<Record<string, EventDetailCacheEntry>>(
    {},
  );
  const [currentPage, setCurrentPage] = useState(1);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [positions, setPositions] = useState<PortfolioRow[]>([]);
  const [positionsLoading, setPositionsLoading] = useState(false);
  const [positionsLoaded, setPositionsLoaded] = useState(false);
  const [positionsError, setPositionsError] = useState("");
  const [watchingRows, setWatchingRows] = useState<PortfolioRow[]>([]);
  const [watchingLoading, setWatchingLoading] = useState(false);
  const [watchingLoaded, setWatchingLoaded] = useState(false);
  const [watchingError, setWatchingError] = useState("");
  const [watchedTickers, setWatchedTickers] = useState<string[]>([]);
  const inFlightCategories = useRef<Set<string>>(new Set());
  const inFlightDetails = useRef<Set<string>>(new Set());
  const marketsRefreshInFlightRef = useRef(false);
  const deferredViewState = useDeferredValue(history.present);
  const pendingInteractionRef = useRef<{
    name: string;
    startedAt: number;
    detail?: Record<string, unknown>;
  } | null>(null);

  const selectedCategories = history.present.filters.categories;

  const allSelectedEvents = useMemo(() => {
    return measurePerf("derive:allSelectedEvents", () => {
      const deduped = new Map<string, EventSummary>();
      for (const category of selectedCategories) {
        const entry = categoryCache[category];
        if (!entry) {
          continue;
        }
        for (const event of entry.events) {
          deduped.set(event.id, event);
        }
      }
      return Array.from(deduped.values());
    }, { selected_categories: selectedCategories.length });
  }, [categoryCache, selectedCategories]);

  const filteredEvents = useMemo(() => {
    return measurePerf("derive:filteredEvents", () => {
      const keyword = deferredViewState.filters.keyword.trim().toLowerCase();

      return allSelectedEvents.filter((event) => {
        if (deferredViewState.filters.liveOnly && !event.isLive) {
          return false;
        }

        if (
          keyword &&
          !`${event.title} ${event.category} ${event.subcategory}`
            .toLowerCase()
            .includes(keyword)
        ) {
          return false;
        }

        return true;
      });
    }, { input_rows: allSelectedEvents.length });
  }, [allSelectedEvents, deferredViewState.filters]);

  const sortedEvents = useMemo(() => {
    return measurePerf("derive:sortedEvents", () => {
      return sortEventGroups(
        filteredEvents.map((event) => ({
          id: event.id,
          category: event.category,
          title: event.title,
          startTime: event.startTime,
          isLive: event.isLive,
          rows:
            detailsCache[event.id]?.loaded
              ? detailsCache[event.id].markets.map((market) => ({
                  yesBid: market.yesBid,
                  noBid: market.noBid,
                  volume: market.volume,
                }))
              : [],
        })),
        deferredViewState.topBar,
      ).map((group) =>
        filteredEvents.find((event) => event.id === group.id) ?? {
          id: group.id,
          category: group.category,
          title: group.title,
          startTime: group.startTime,
          isLive: group.isLive,
          subcategory: "",
        },
      );
    }, {
      input_rows: filteredEvents.length,
      sort_field: deferredViewState.topBar.sortField,
      sort_direction: deferredViewState.topBar.sortDirection,
    });
  }, [deferredViewState.topBar, detailsCache, filteredEvents]);

  const pagedEvents = useMemo(() => {
    const start = (currentPage - 1) * deferredViewState.topBar.pageSize;
    const end = start + deferredViewState.topBar.pageSize;
    return sortedEvents.slice(start, end);
  }, [currentPage, deferredViewState.topBar.pageSize, sortedEvents]);

  const flatMarketRows = useMemo(() => {
    return measurePerf("derive:flatMarketRows", () => {
      const loadedRows = flattenLoadedMarkets(pagedEvents, detailsCache);
      return loadedRows.filter((row) => {
        if (
          !rangePasses(
            row.spread,
            deferredViewState.filters.spreadMin,
            deferredViewState.filters.spreadMax,
          )
        ) {
          return false;
        }
        if (
          !rangePasses(
            row.yesBid,
            deferredViewState.filters.bidMin,
            deferredViewState.filters.bidMax,
          )
        ) {
          return false;
        }
        if (
          !rangePasses(
            row.yesAsk,
            deferredViewState.filters.askMin,
            deferredViewState.filters.askMax,
          )
        ) {
          return false;
        }
        return true;
      });
    }, { paged_events: pagedEvents.length });
  }, [deferredViewState.filters, detailsCache, pagedEvents]);

  const filteredPositions = useMemo(
    () =>
      measurePerf("derive:filteredPositions", () => filterPortfolioRows(positions, deferredViewState.filters), {
        input_rows: positions.length,
      }),
    [deferredViewState.filters, positions],
  );
  const filteredWatching = useMemo(
    () =>
      measurePerf(
        "derive:filteredWatching",
        () => filterPortfolioRows(watchingRows, deferredViewState.filters),
        {
          input_rows: watchingRows.length,
        },
      ),
    [deferredViewState.filters, watchingRows],
  );

  const sortedPositions = useMemo(
    () =>
      measurePerf(
        "derive:sortedPositions",
        () => sortPortfolioRows(filteredPositions, deferredViewState.topBar),
        {
          input_rows: filteredPositions.length,
          sort_field: deferredViewState.topBar.sortField,
        },
      ),
    [deferredViewState.topBar, filteredPositions],
  );
  const sortedWatching = useMemo(
    () =>
      measurePerf(
        "derive:sortedWatching",
        () => sortPortfolioRows(filteredWatching, deferredViewState.topBar),
        {
          input_rows: filteredWatching.length,
          sort_field: deferredViewState.topBar.sortField,
        },
      ),
    [deferredViewState.topBar, filteredWatching],
  );

  const groupedPositions = useMemo(
    () =>
      measurePerf("derive:groupedPositions", () => {
        return sortEventGroups(groupPortfolioRows(filteredPositions), deferredViewState.topBar);
      }, { input_rows: filteredPositions.length }),
    [deferredViewState.topBar, filteredPositions],
  );
  const groupedWatching = useMemo(
    () =>
      measurePerf("derive:groupedWatching", () => {
        return sortEventGroups(groupPortfolioRows(filteredWatching), deferredViewState.topBar);
      }, { input_rows: filteredWatching.length }),
    [deferredViewState.topBar, filteredWatching],
  );

  const totalPages = useMemo(() => {
    const totalItems =
      activeTab === "markets"
        ? sortedEvents.length
        : activeTab === "positions"
          ? deferredViewState.topBar.groupByEvent
            ? groupedPositions.length
            : sortedPositions.length
          : deferredViewState.topBar.groupByEvent
            ? groupedWatching.length
            : sortedWatching.length;

    return Math.max(1, Math.ceil(totalItems / deferredViewState.topBar.pageSize));
  }, [
    activeTab,
    deferredViewState.topBar,
    groupedPositions.length,
    groupedWatching.length,
    sortedEvents.length,
    sortedPositions.length,
    sortedWatching.length,
  ]);

  const safeCurrentPage = Math.min(currentPage, totalPages);

  useEffect(() => {
    if (currentPage !== safeCurrentPage) {
      setCurrentPage(safeCurrentPage);
    }
  }, [currentPage, safeCurrentPage]);

  const pagedPositionGroups = useMemo(() => {
    const start = (safeCurrentPage - 1) * deferredViewState.topBar.pageSize;
    const end = start + deferredViewState.topBar.pageSize;
    return groupedPositions.slice(start, end);
  }, [deferredViewState.topBar.pageSize, groupedPositions, safeCurrentPage]);

  const pagedWatchingGroups = useMemo(() => {
    const start = (safeCurrentPage - 1) * deferredViewState.topBar.pageSize;
    const end = start + deferredViewState.topBar.pageSize;
    return groupedWatching.slice(start, end);
  }, [deferredViewState.topBar.pageSize, groupedWatching, safeCurrentPage]);

  const pagedPositionRows = useMemo(() => {
    const start = (safeCurrentPage - 1) * deferredViewState.topBar.pageSize;
    const end = start + deferredViewState.topBar.pageSize;
    return sortedPositions.slice(start, end);
  }, [deferredViewState.topBar.pageSize, safeCurrentPage, sortedPositions]);

  const pagedWatchingRows = useMemo(() => {
    const start = (safeCurrentPage - 1) * deferredViewState.topBar.pageSize;
    const end = start + deferredViewState.topBar.pageSize;
    return sortedWatching.slice(start, end);
  }, [deferredViewState.topBar.pageSize, safeCurrentPage, sortedWatching]);

  const visibleMarketCategories = useMemo(() => {
    const visible = new Set<string>();
    const ordered: string[] = [];

    for (const event of pagedEvents) {
      if (!selectedCategories.includes(event.category) || visible.has(event.category)) {
        continue;
      }

      visible.add(event.category);
      ordered.push(event.category);
    }

    return ordered;
  }, [pagedEvents, selectedCategories]);
  const categoryRefreshFreshnessMs = useMemo(
    () => getCategoryRefreshFreshnessMs(history.present.topBar.autoRefresh),
    [history.present.topBar.autoRefresh],
  );
  const selectedCategoryStatuses = useMemo(
    () =>
      selectedCategories.map((category) => {
        const entry = categoryCache[category];
        return {
          category,
          detail: formatElapsedMs(entry?.lastUpdatedAt ?? null),
          status: getCategoryRefreshStatus(entry, categoryRefreshFreshnessMs),
        };
      }),
    [categoryCache, categoryRefreshFreshnessMs, selectedCategories],
  );

  const isDirty = !isDefaultView(history.present, viewTitle);
  const isBlankDefault = activeTab === "markets" && selectedCategories.length === 0;
  const selectedCategoryLoadingCount = selectedCategories.filter(
    (category) => categoryCache[category]?.isLoading,
  ).length;
  const loadedCategoryCount = selectedCategories.filter(
    (category) => categoryCache[category]?.events.length,
  ).length;

  const tabLabel = viewTitle.trim() || "Untitled View";
  const positionsOpenCount = positions.filter((row) => row.position !== 0).length;

  async function fetchCategories() {
    setCategoriesLoading(true);
    setCategoriesError("");

    try {
      const categories = await measureAsyncPerf("invoke:fetchCategories", () =>
        invoke<string[]>("fetch_categories_command"),
      );
      setAvailableCategories(categories);
    } catch (error) {
      setCategoriesError(
        error instanceof Error ? error.message : "Unable to load categories.",
      );
    } finally {
      setCategoriesLoading(false);
    }
  }

  async function fetchEventPage(
    source: "standard" | "multivariate",
    category: string,
    cursor: string | null,
  ) {
    return measureAsyncPerf(
      "invoke:fetchEventPage",
      () =>
        invoke<EventPage>("fetch_event_page_command", {
          source,
          category,
          cursor,
        }),
      { source, category, cursor: cursor ?? "initial" },
    );
  }

  async function fetchEventDetails(eventTicker: string) {
    return measureAsyncPerf(
      "invoke:fetchEventDetails",
      () =>
        invoke<EventDetails>("fetch_event_details_command", {
          eventTicker,
        }),
      { event_ticker: eventTicker },
    );
  }

  async function fetchPositions() {
    const payload = await measureAsyncPerf("invoke:fetchPositions", () =>
      invoke<PositionRecord[]>("fetch_positions_command"),
    );
    return payload.map<PortfolioRow>((row) => ({
      id: row.ticker,
      eventId: row.eventTicker,
      category: row.category,
      eventTitle: row.eventTitle,
      marketLabel: row.marketLabel,
      displayName: `${row.eventTitle} - ${row.marketLabel}`,
      startTime: row.startTime,
      isLive: row.isLive,
      yesBid: row.yesBid,
      yesAsk: row.yesAsk,
      noBid: row.noBid,
      noAsk: row.noAsk,
      volume: row.volume,
      spread: row.yesAsk - row.yesBid,
      position: row.position,
      exposureDollars: row.exposureDollars,
      realizedPnlDollars: row.realizedPnlDollars,
      rulesPrimary: row.rulesPrimary,
    }));
  }

  async function fetchWatching(tickers: string[]) {
    const payload = await measureAsyncPerf(
      "invoke:fetchWatching",
      () =>
        invoke<PositionRecord[]>("fetch_watch_markets_command", {
          tickers,
        }),
      { ticker_count: tickers.length },
    );
    return payload.map<PortfolioRow>((row) => ({
      id: row.ticker,
      eventId: row.eventTicker,
      category: row.category,
      eventTitle: row.eventTitle,
      marketLabel: row.marketLabel,
      displayName: `${row.eventTitle} - ${row.marketLabel}`,
      startTime: row.startTime,
      isLive: row.isLive,
      yesBid: row.yesBid,
      yesAsk: row.yesAsk,
      noBid: row.noBid,
      noAsk: row.noAsk,
      volume: row.volume,
      spread: row.yesAsk - row.yesBid,
      position: 0,
      exposureDollars: 0,
      realizedPnlDollars: 0,
      rulesPrimary: row.rulesPrimary,
    }));
  }

  async function loadCategory(category: string, force = false) {
    if (inFlightCategories.current.has(category)) {
      return;
    }

    const existing = categoryCache[category];
    if (!force && existing && (existing.isLoading || existing.isComplete)) {
      return;
    }

    inFlightCategories.current.add(category);
    setCategoryCache((current) => ({
      ...current,
      [category]: {
        ...(current[category] ?? {
          events: [],
          isLoading: false,
          isComplete: false,
          lastUpdatedAt: null,
        }),
        isLoading: true,
      },
    }));

    try {
      const [standardPage, multivariatePage] = await Promise.all([
        fetchEventPage("standard", category, null),
        fetchEventPage("multivariate", category, null),
      ]);

      let accumulated = mergeEventSummaries([], [
        ...standardPage.events,
        ...multivariatePage.events,
      ]);

      startTransition(() => {
        setCategoryCache((current) => ({
          ...current,
          [category]: {
            events: accumulated,
            isLoading: true,
            isComplete: false,
            lastUpdatedAt: current[category]?.lastUpdatedAt ?? null,
          },
        }));
      });

      let standardCursor = standardPage.cursor;
      let multivariateCursor = multivariatePage.cursor;

      while (standardCursor || multivariateCursor) {
        if (standardCursor) {
          const nextStandard = await fetchEventPage("standard", category, standardCursor);
          accumulated = mergeEventSummaries(accumulated, nextStandard.events);
          standardCursor = nextStandard.cursor;
        }

        if (multivariateCursor) {
          const nextMultivariate = await fetchEventPage(
            "multivariate",
            category,
            multivariateCursor,
          );
          accumulated = mergeEventSummaries(accumulated, nextMultivariate.events);
          multivariateCursor = nextMultivariate.cursor;
        }

        const snapshot = accumulated;
        startTransition(() => {
          setCategoryCache((current) => ({
            ...current,
          [category]: {
            events: snapshot,
            isLoading: true,
            isComplete: false,
            lastUpdatedAt: current[category]?.lastUpdatedAt ?? null,
          },
        }));
      });
      }

      startTransition(() => {
        setCategoryCache((current) => ({
          ...current,
          [category]: {
            events: accumulated,
            isLoading: false,
            isComplete: true,
            lastUpdatedAt: Date.now(),
          },
        }));
      });
      setLastRefresh(new Date());
    } finally {
      inFlightCategories.current.delete(category);
    }
  }

  async function refreshCategoryHead(category: string) {
    if (inFlightCategories.current.has(category)) {
      return;
    }

    const existing = categoryCache[category];
    if (!existing?.events.length) {
      await loadCategory(category, true);
      return;
    }

    inFlightCategories.current.add(category);
    setCategoryCache((current) => ({
      ...current,
      [category]: {
        ...(current[category] ?? {
          events: [],
          isLoading: false,
          isComplete: false,
          lastUpdatedAt: null,
        }),
        isLoading: true,
      },
    }));

    try {
      const [standardPage, multivariatePage] = await Promise.all([
        fetchEventPage("standard", category, null),
        fetchEventPage("multivariate", category, null),
      ]);

      const refreshedEvents = mergeEventSummaries(existing.events, [
        ...standardPage.events,
        ...multivariatePage.events,
      ]);

      startTransition(() => {
        setCategoryCache((current) => ({
          ...current,
          [category]: {
            events: refreshedEvents,
            isLoading: false,
            isComplete: existing.isComplete,
            lastUpdatedAt: Date.now(),
          },
        }));
      });
      setLastRefresh(new Date());
    } finally {
      inFlightCategories.current.delete(category);
    }
  }

  async function loadDetails(eventId: string) {
    if (inFlightDetails.current.has(eventId) || detailsCache[eventId]?.loaded) {
      return;
    }

    inFlightDetails.current.add(eventId);
    setDetailsCache((current) => ({
      ...current,
      [eventId]: {
        markets: current[eventId]?.markets ?? [],
        isLoading: true,
        loaded: false,
      },
    }));

    try {
      const details = await fetchEventDetails(eventId);
      startTransition(() => {
        setDetailsCache((current) => ({
          ...current,
          [eventId]: {
            markets: details.markets,
            isLoading: false,
            loaded: true,
          },
        }));
      });
    } finally {
      inFlightDetails.current.delete(eventId);
    }
  }

  async function loadPositions(force = false) {
    if (positionsLoading || (positionsLoaded && !force)) {
      return;
    }

    setPositionsLoading(true);
    setPositionsError("");

    try {
      const rows = await fetchPositions();
      startTransition(() => {
        setPositions(rows);
        setPositionsLoaded(true);
      });
      setLastRefresh(new Date());
    } catch (error) {
      setPositionsError(
        error instanceof Error ? error.message : "Unable to load positions.",
      );
    } finally {
      setPositionsLoading(false);
    }
  }

  async function loadWatching(force = false) {
    if (watchedTickers.length === 0) {
      setWatchingRows([]);
      setWatchingLoaded(true);
      setWatchingError("");
      return;
    }

    if (watchingLoading || (watchingLoaded && !force)) {
      return;
    }

    setWatchingLoading(true);
    setWatchingError("");

    try {
      const rows = await fetchWatching(watchedTickers);
      startTransition(() => {
        setWatchingRows(rows);
        setWatchingLoaded(true);
      });
      setLastRefresh(new Date());
    } catch (error) {
      setWatchingError(
        error instanceof Error ? error.message : "Unable to load watched markets.",
      );
    } finally {
      setWatchingLoading(false);
    }
  }

  async function refreshMarketsVisibleFirst() {
    if (selectedCategories.length === 0 || marketsRefreshInFlightRef.current) {
      return;
    }

    marketsRefreshInFlightRef.current = true;

    try {
      const prioritizedCategories =
        visibleMarketCategories.length > 0
          ? visibleMarketCategories
          : selectedCategories.slice(0, Math.min(2, selectedCategories.length));
      const prioritizedSet = new Set(prioritizedCategories);
      const backgroundCategories = selectedCategories.filter((category) => {
        if (prioritizedSet.has(category)) {
          return false;
        }

        const lastUpdatedAt = categoryCache[category]?.lastUpdatedAt;
        if (lastUpdatedAt === null || lastUpdatedAt === undefined) {
          return true;
        }

        return Date.now() - lastUpdatedAt >= categoryRefreshFreshnessMs;
      });

      const prioritizedRefreshes = prioritizedCategories.map((category) =>
        loadCategory(category, true),
      );

      if (backgroundCategories.length > 0) {
        await Promise.race([Promise.allSettled(prioritizedRefreshes), delayMs(500)]);
      }

      for (const category of backgroundCategories) {
        await refreshCategoryHead(category);
      }

      await Promise.allSettled(prioritizedRefreshes);
    } finally {
      marketsRefreshInFlightRef.current = false;
    }
  }

  function toggleWatchTicker(ticker: string) {
    setWatchedTickers((current) => {
      const next = toggleValue(current, ticker);
      window.localStorage.setItem(WATCH_STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }

  useEffect(() => {
    const raw = window.localStorage.getItem(WATCH_STORAGE_KEY);
    if (!raw) {
      return;
    }

    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        setWatchedTickers(parsed.filter((value): value is string => typeof value === "string"));
      }
    } catch {
      window.localStorage.removeItem(WATCH_STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    void fetchCategories();
  }, []);

  useEffect(() => {
    if (activeTab !== "markets") {
      return;
    }

    for (const category of selectedCategories) {
      if (!categoryCache[category]) {
        void loadCategory(category);
      }
    }
  }, [activeTab, categoryCache, selectedCategories]);

  useEffect(() => {
    setCurrentPage(1);
  }, [activeTab, deferredViewState.filters, deferredViewState.topBar.groupByEvent, deferredViewState.topBar.pageSize]);

  useEffect(() => {
    if (activeTab === "positions") {
      void loadPositions();
      return;
    }

    if (activeTab === "watching") {
      setWatchingLoaded(false);
      void loadWatching(true);
    }
  }, [activeTab, watchedTickers]);

  useEffect(() => {
    if (activeTab !== "markets") {
      return;
    }

    if (deferredViewState.topBar.groupByEvent) {
      for (const eventId of expandedEventIds) {
        const visible = pagedEvents.some((event) => event.id === eventId);
        if (visible) {
          void loadDetails(eventId);
        }
      }
      return;
    }

    for (const event of pagedEvents) {
      void loadDetails(event.id);
    }
  }, [activeTab, deferredViewState.topBar.groupByEvent, expandedEventIds, pagedEvents]);

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
      if (activeTab === "markets") {
        void refreshMarketsVisibleFirst();
        return;
      }

      if (activeTab === "positions") {
        void loadPositions(true);
        return;
      }

      void loadWatching(true);
    }, intervalMs);

    return () => window.clearInterval(timer);
  }, [
    activeTab,
    categoryCache,
    categoryRefreshFreshnessMs,
    history.present.topBar.autoRefresh,
    selectedCategories,
    visibleMarketCategories,
    watchedTickers,
  ]);

  useEffect(() => {
    if (!pendingInteractionRef.current) {
      return;
    }

    const interaction = pendingInteractionRef.current;
    const frameId = window.requestAnimationFrame(() => {
      logPerfMetric(
        `interaction:${interaction.name}`,
        performance.now() - interaction.startedAt,
        interaction.detail,
      );
      pendingInteractionRef.current = null;
    });

    return () => window.cancelAnimationFrame(frameId);
  }, [
    activeTab,
    deferredViewState,
    safeCurrentPage,
    pagedEvents,
    pagedPositionGroups,
    pagedPositionRows,
    pagedWatchingGroups,
    pagedWatchingRows,
  ]);

  function setTopBar<K extends keyof TopBarState>(key: K, value: TopBarState[K]) {
    pendingInteractionRef.current = {
      name: "topBarChange",
      startedAt: performance.now(),
      detail: { key, value: String(value) },
    };
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
    pendingInteractionRef.current = {
      name: "filterChange",
      startedAt: performance.now(),
      detail: { key },
    };
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
    pendingInteractionRef.current = {
      name: "historyBack",
      startedAt: performance.now(),
    };
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
    pendingInteractionRef.current = {
      name: "historyForward",
      startedAt: performance.now(),
    };
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
    pendingInteractionRef.current = {
      name: "toggleEventExpansion",
      startedAt: performance.now(),
      detail: { event_id: eventId },
    };
    setExpandedEventIds((current) =>
      current.includes(eventId)
        ? current.filter((id) => id !== eventId)
        : [...current, eventId],
    );
  }

  const marketsColumns: Array<{ field: SortField; label: string }> = [
    { field: "category", label: "Category" },
    { field: "market", label: "Market" },
    { field: "yes", label: "Yes" },
    { field: "no", label: "No" },
    { field: "startTime", label: "Event start" },
    { field: "volume", label: "Volume" },
  ];

  const positionsColumns: Array<{ field: SortField; label: string }> = [
    ...marketsColumns,
    { field: "position", label: "Position" },
    { field: "exposure", label: "Exposure" },
    { field: "pnl", label: "Realized PnL" },
  ];

  const activeColumns = activeTab === "positions" ? positionsColumns : marketsColumns;
  const tableClass = activeTab === "positions" ? "positions-layout" : "markets-layout";
  const currentTotalItems =
    activeTab === "markets"
      ? sortedEvents.length
      : activeTab === "positions"
        ? deferredViewState.topBar.groupByEvent
          ? groupedPositions.length
          : sortedPositions.length
        : deferredViewState.topBar.groupByEvent
          ? groupedWatching.length
          : sortedWatching.length;

  return (
    <div className="dashboard-shell">
      <div className="dashboard-app">
        <header className="tab-strip">
          <button
            className={activeTab === "markets" ? "tab active-tab" : "tab"}
            onClick={() => {
              pendingInteractionRef.current = {
                name: "tabSwitch",
                startedAt: performance.now(),
                detail: { tab: "markets" },
              };
              setActiveTab("markets");
            }}
            type="button"
          >
            <span className="tab-title">{tabLabel}</span>
            {isDirty ? <span className="tab-dirty">*</span> : null}
          </button>
          <button
            className={activeTab === "positions" ? "tab active-tab" : "tab"}
            onClick={() => {
              pendingInteractionRef.current = {
                name: "tabSwitch",
                startedAt: performance.now(),
                detail: { tab: "positions" },
              };
              setActiveTab("positions");
            }}
            type="button"
          >
            <span className="tab-title">Positions</span>
          </button>
          <button
            className={activeTab === "watching" ? "tab active-tab" : "tab"}
            onClick={() => {
              pendingInteractionRef.current = {
                name: "tabSwitch",
                startedAt: performance.now(),
                detail: { tab: "watching" },
              };
              setActiveTab("watching");
            }}
            type="button"
          >
            <span className="tab-title">Watching</span>
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
                  <span>
                    {activeTab === "markets"
                      ? "Events per page"
                      : history.present.topBar.groupByEvent
                        ? "Events per page"
                        : "Markets per page"}
                  </span>
                  <select
                    onChange={(event) =>
                      setTopBar("pageSize", Number(event.currentTarget.value) as PageSize)
                    }
                    value={history.present.topBar.pageSize}
                  >
                    <option value="25">25</option>
                    <option value="50">50</option>
                    <option value="100">100</option>
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
              {activeTab === "markets" ? (
                <>
                  <div className="status-pill">
                    {selectedCategories.length} categories selected
                  </div>
                  <div className="status-pill">
                    {loadedCategoryCount}/{selectedCategories.length} categories loaded
                  </div>
                  <div className="status-pill">
                    {allSelectedEvents.length} open events loaded
                  </div>
                  {selectedCategoryLoadingCount > 0 ? (
                    <div className="status-pill">
                      Loading {selectedCategoryLoadingCount} categories…
                    </div>
                  ) : null}
                </>
              ) : activeTab === "positions" ? (
                <>
                  <div className="status-pill">{positionsOpenCount} open positions</div>
                  <div className="status-pill">{positions.length} position rows loaded</div>
                </>
              ) : (
                <>
                  <div className="status-pill">{watchedTickers.length} watched markets</div>
                  <div className="status-pill">{watchingRows.length} watch rows loaded</div>
                </>
              )}

              <div className="status-pill">
                Page {safeCurrentPage} of {totalPages}
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
              <div className={`table-header ${tableClass}`}>
                <div className="watch-header">Watch</div>
                {activeColumns.map((column) => (
                  <SortHeader
                    key={column.field}
                    activeField={history.present.topBar.sortField}
                    direction={history.present.topBar.sortDirection}
                    field={column.field}
                    label={column.label}
                    onClick={handleSortClick}
                  />
                ))}
              </div>

              <div className="table-body">
                {categoriesError && activeTab === "markets" ? (
                  <div className="message-card error-card">
                    <h1>Kalshi data failed to load.</h1>
                    <p>{categoriesError}</p>
                  </div>
                ) : positionsError && activeTab === "positions" ? (
                  <div className="message-card error-card">
                    <h1>Positions failed to load.</h1>
                    <p>{positionsError}</p>
                  </div>
                ) : watchingError && activeTab === "watching" ? (
                  <div className="message-card error-card">
                    <h1>Watchlist failed to load.</h1>
                    <p>{watchingError}</p>
                  </div>
                ) : categoriesLoading && activeTab === "markets" ? (
                  <div className="message-card">
                    <h1>Loading categories…</h1>
                    <p>Fetching lightweight metadata first.</p>
                  </div>
                ) : positionsLoading && activeTab === "positions" && !positionsLoaded ? (
                  <div className="message-card">
                    <h1>Loading open positions…</h1>
                    <p>Pulling down the full open-position set for local filtering.</p>
                  </div>
                ) : watchingLoading && activeTab === "watching" && !watchingLoaded ? (
                  <div className="message-card">
                    <h1>Loading watched markets…</h1>
                    <p>Refreshing the markets you pinned to keep an eye on.</p>
                  </div>
                ) : activeTab === "watching" && watchedTickers.length === 0 ? (
                  <div className="message-card">
                    <p className="blank-eyebrow">Watching</p>
                    <h1>Star a market to add it here.</h1>
                    <p>
                      Any starred market from the Markets or Positions tabs will show up in
                      this watchlist tab.
                    </p>
                  </div>
                ) : isBlankDefault ? (
                  <div className="message-card">
                    <p className="blank-eyebrow">Blank default view</p>
                    <h1>Pick one or more categories to begin scanning events.</h1>
                    <p>
                      This version loads event summaries first, then requests market
                      details only when you expand an event.
                    </p>
                  </div>
                ) : activeTab === "markets" ? (
                  deferredViewState.topBar.groupByEvent ? (
                    pagedEvents.length === 0 ? (
                      <div className="message-card">
                        <h1>No events match the current filters.</h1>
                        <p>Try loosening keyword or live-only constraints.</p>
                      </div>
                    ) : (
                      pagedEvents.map((event) => {
                        const expanded = expandedEventIds.includes(event.id);
                        const details = detailsCache[event.id];
                        const singleMarket =
                          details?.loaded && details.markets.length === 1
                            ? details.markets[0]
                            : null;
                        const totalVolume = details?.loaded
                          ? details.markets.reduce((sum, market) => sum + market.volume, 0)
                          : 0;

                        return (
                          <div className="event-group" key={event.id}>
                            <div className={`event-row ${tableClass}`}>
                              <span className="cell watch-cell">--</span>
                              <span className="cell category-cell">
                                <span className="category-pill">{event.category}</span>
                              </span>
                              <span className="cell market-cell">
                                <button
                                  className="toggle-button"
                                  onClick={() => {
                                    toggleEventExpansion(event.id);
                                    if (!details?.loaded) {
                                      void loadDetails(event.id);
                                    }
                                  }}
                                  type="button"
                                >
                                  <span className="toggle-glyph">
                                    {expanded ? "▾" : "▸"}
                                  </span>
                                  <span>{event.title}</span>
                                </button>
                              </span>
                              <span className="cell numeric-cell">
                                {singleMarket
                                  ? formatQuote(singleMarket.yesBid, singleMarket.yesAsk)
                                  : "--"}
                              </span>
                              <span className="cell numeric-cell">
                                {singleMarket
                                  ? formatQuote(singleMarket.noBid, singleMarket.noAsk)
                                  : "--"}
                              </span>
                              <span className="cell">{formatDate(event.startTime)}</span>
                              <span className="cell numeric-cell">
                                {details?.loaded ? formatVolume(totalVolume) : "--"}
                              </span>
                            </div>

                            {expanded ? (
                              <div className="child-rows">
                                {details?.isLoading ? (
                                  <div className={`child-row loading-row ${tableClass}`}>
                                    <span className="cell market-cell">Loading markets…</span>
                                  </div>
                                ) : details?.loaded ? (
                                  details.markets.map((market) => (
                                    <div className={`child-row ${tableClass}`} key={market.id}>
                                      <span className="cell watch-cell">
                                        <WatchButton
                                          active={watchedTickers.includes(market.id)}
                                          onClick={() => toggleWatchTicker(market.id)}
                                        />
                                      </span>
                                      <span className="cell category-cell child-category">
                                        <span className="child-market-label">
                                          {event.category}
                                        </span>
                                      </span>
                                      <span className="cell market-cell child-market-cell">
                                        {event.title} - {market.label}
                                      </span>
                                      <span className="cell numeric-cell">
                                        {formatQuote(market.yesBid, market.yesAsk)}
                                      </span>
                                      <span className="cell numeric-cell">
                                        {formatQuote(market.noBid, market.noAsk)}
                                      </span>
                                      <span className="cell">
                                        {formatDate(event.startTime)}
                                      </span>
                                      <span className="cell numeric-cell">
                                        {formatVolume(market.volume)}
                                      </span>
                                    </div>
                                  ))
                                ) : (
                                  <div className={`child-row loading-row ${tableClass}`}>
                                    <span className="cell market-cell">
                                      No market details loaded yet.
                                    </span>
                                  </div>
                                )}
                              </div>
                            ) : null}
                          </div>
                        );
                      })
                    )
                  ) : flatMarketRows.length === 0 ? (
                    <div className="message-card">
                      <h1>No loaded markets match the current filters.</h1>
                      <p>
                        In ungrouped mode, only the visible page’s events are expanded into
                        market rows.
                      </p>
                    </div>
                  ) : (
                    flatMarketRows.map((row) => (
                      <div className={`market-row ${tableClass}`} key={row.id}>
                        <span className="cell watch-cell">
                          <WatchButton
                            active={watchedTickers.includes(row.id)}
                            onClick={() => toggleWatchTicker(row.id)}
                          />
                        </span>
                        <span className="cell category-cell">
                          <span className="category-pill">{row.category}</span>
                        </span>
                        <span className="cell market-cell">{row.displayName}</span>
                        <span className="cell numeric-cell">
                          {formatQuote(row.yesBid, row.yesAsk)}
                        </span>
                        <span className="cell numeric-cell">
                          {formatQuote(row.noBid, row.noAsk)}
                        </span>
                        <span className="cell">{formatDate(row.startTime)}</span>
                        <span className="cell numeric-cell">
                          {formatVolume(row.volume)}
                        </span>
                      </div>
                    ))
                  )
                ) : activeTab === "positions" ? (
                  deferredViewState.topBar.groupByEvent ? (
                    pagedPositionGroups.length === 0 ? (
                      <div className="message-card">
                        <h1>No positions match the current filters.</h1>
                        <p>Try adjusting the category, keyword, or range constraints.</p>
                      </div>
                    ) : (
                      pagedPositionGroups.map((group) => {
                        const expanded = expandedEventIds.includes(`positions-${group.id}`);
                        const singleMarket = group.rows.length === 1 ? group.rows[0] : null;
                        const totalVolume = group.rows.reduce(
                          (sum, row) => sum + row.volume,
                          0,
                        );
                        const totalExposure = group.rows.reduce(
                          (sum, row) => sum + row.exposureDollars,
                          0,
                        );
                        const totalPnl = group.rows.reduce(
                          (sum, row) => sum + row.realizedPnlDollars,
                          0,
                        );

                        return (
                          <div className="event-group" key={group.id}>
                            <div className={`event-row ${tableClass}`}>
                              <span className="cell watch-cell">--</span>
                              <span className="cell category-cell">
                                <span className="category-pill">{group.category}</span>
                              </span>
                              <span className="cell market-cell">
                                <button
                                  className="toggle-button"
                                  onClick={() => toggleEventExpansion(`positions-${group.id}`)}
                                  type="button"
                                >
                                  <span className="toggle-glyph">
                                    {expanded ? "▾" : "▸"}
                                  </span>
                                  <span>{group.title}</span>
                                </button>
                              </span>
                              <span className="cell numeric-cell">
                                {singleMarket
                                  ? formatQuote(singleMarket.yesBid, singleMarket.yesAsk)
                                  : "--"}
                              </span>
                              <span className="cell numeric-cell">
                                {singleMarket
                                  ? formatQuote(singleMarket.noBid, singleMarket.noAsk)
                                  : "--"}
                              </span>
                              <span className="cell">{formatDate(group.startTime)}</span>
                              <span className="cell numeric-cell">
                                {formatVolume(totalVolume)}
                              </span>
                              <span className="cell numeric-cell">
                                {formatPosition(
                                  group.rows.reduce((sum, row) => sum + row.position, 0),
                                )}
                              </span>
                              <span className="cell numeric-cell">
                                {formatDollarAmount(totalExposure)}
                              </span>
                              <span className="cell numeric-cell">
                                {formatDollarAmount(totalPnl)}
                              </span>
                            </div>

                            {expanded ? (
                              <div className="child-rows">
                                {group.rows.map((row) => (
                                  <div className={`child-row ${tableClass}`} key={row.id}>
                                    <span className="cell watch-cell">
                                      <WatchButton
                                        active={watchedTickers.includes(row.id)}
                                        onClick={() => toggleWatchTicker(row.id)}
                                      />
                                    </span>
                                    <span className="cell category-cell child-category">
                                      <span className="child-market-label">
                                        {row.category}
                                      </span>
                                    </span>
                                    <span className="cell market-cell child-market-cell">
                                      {row.eventTitle} - {row.marketLabel}
                                    </span>
                                    <span className="cell numeric-cell">
                                      {formatQuote(row.yesBid, row.yesAsk)}
                                    </span>
                                    <span className="cell numeric-cell">
                                      {formatQuote(row.noBid, row.noAsk)}
                                    </span>
                                    <span className="cell">
                                      {formatDate(row.startTime)}
                                    </span>
                                    <span className="cell numeric-cell">
                                      {formatVolume(row.volume)}
                                    </span>
                                    <span className="cell numeric-cell">
                                      {formatPosition(row.position)}
                                    </span>
                                    <span className="cell numeric-cell">
                                      {formatDollarAmount(row.exposureDollars)}
                                    </span>
                                    <span className="cell numeric-cell">
                                      {formatDollarAmount(row.realizedPnlDollars)}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            ) : null}
                          </div>
                        );
                      })
                    )
                  ) : pagedPositionRows.length === 0 ? (
                    <div className="message-card">
                      <h1>No positions match the current filters.</h1>
                      <p>Try adjusting the category, keyword, or range constraints.</p>
                    </div>
                  ) : (
                    pagedPositionRows.map((row) => (
                      <div className={`market-row ${tableClass}`} key={row.id}>
                        <span className="cell watch-cell">
                          <WatchButton
                            active={watchedTickers.includes(row.id)}
                            onClick={() => toggleWatchTicker(row.id)}
                          />
                        </span>
                        <span className="cell category-cell">
                          <span className="category-pill">{row.category}</span>
                        </span>
                        <span className="cell market-cell">{row.displayName}</span>
                        <span className="cell numeric-cell">
                          {formatQuote(row.yesBid, row.yesAsk)}
                        </span>
                        <span className="cell numeric-cell">
                          {formatQuote(row.noBid, row.noAsk)}
                        </span>
                        <span className="cell">{formatDate(row.startTime)}</span>
                        <span className="cell numeric-cell">
                          {formatVolume(row.volume)}
                        </span>
                        <span className="cell numeric-cell">
                          {formatPosition(row.position)}
                        </span>
                        <span className="cell numeric-cell">
                          {formatDollarAmount(row.exposureDollars)}
                        </span>
                        <span className="cell numeric-cell">
                          {formatDollarAmount(row.realizedPnlDollars)}
                        </span>
                      </div>
                    ))
                  )
                ) : deferredViewState.topBar.groupByEvent ? (
                  pagedWatchingGroups.length === 0 ? (
                    <div className="message-card">
                      <h1>No watched markets match the current filters.</h1>
                      <p>Try loosening the category, keyword, or range constraints.</p>
                    </div>
                  ) : (
                    pagedWatchingGroups.map((group) => {
                      const expanded = expandedEventIds.includes(`watching-${group.id}`);
                      const singleMarket = group.rows.length === 1 ? group.rows[0] : null;
                      const totalVolume = group.rows.reduce(
                        (sum, row) => sum + row.volume,
                        0,
                      );

                      return (
                        <div className="event-group" key={group.id}>
                          <div className={`event-row ${tableClass}`}>
                            <span className="cell watch-cell">--</span>
                            <span className="cell category-cell">
                              <span className="category-pill">{group.category}</span>
                            </span>
                            <span className="cell market-cell">
                              <button
                                className="toggle-button"
                                onClick={() => toggleEventExpansion(`watching-${group.id}`)}
                                type="button"
                              >
                                <span className="toggle-glyph">
                                  {expanded ? "▾" : "▸"}
                                </span>
                                <span>{group.title}</span>
                              </button>
                            </span>
                            <span className="cell numeric-cell">
                              {singleMarket
                                ? formatQuote(singleMarket.yesBid, singleMarket.yesAsk)
                                : "--"}
                            </span>
                            <span className="cell numeric-cell">
                              {singleMarket
                                ? formatQuote(singleMarket.noBid, singleMarket.noAsk)
                                : "--"}
                            </span>
                            <span className="cell">{formatDate(group.startTime)}</span>
                            <span className="cell numeric-cell">
                              {formatVolume(totalVolume)}
                            </span>
                          </div>

                          {expanded ? (
                            <div className="child-rows">
                              {group.rows.map((row) => (
                                <div className={`child-row ${tableClass}`} key={row.id}>
                                  <span className="cell watch-cell">
                                    <WatchButton
                                      active={watchedTickers.includes(row.id)}
                                      onClick={() => toggleWatchTicker(row.id)}
                                    />
                                  </span>
                                  <span className="cell category-cell child-category">
                                    <span className="child-market-label">{row.category}</span>
                                  </span>
                                  <span className="cell market-cell child-market-cell">
                                    {row.eventTitle} - {row.marketLabel}
                                  </span>
                                  <span className="cell numeric-cell">
                                    {formatQuote(row.yesBid, row.yesAsk)}
                                  </span>
                                  <span className="cell numeric-cell">
                                    {formatQuote(row.noBid, row.noAsk)}
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
                ) : pagedWatchingRows.length === 0 ? (
                  <div className="message-card">
                    <h1>No watched markets match the current filters.</h1>
                    <p>Try loosening the category, keyword, or range constraints.</p>
                  </div>
                ) : (
                  pagedWatchingRows.map((row) => (
                    <div className={`market-row ${tableClass}`} key={row.id}>
                      <span className="cell watch-cell">
                        <WatchButton
                          active={watchedTickers.includes(row.id)}
                          onClick={() => toggleWatchTicker(row.id)}
                        />
                      </span>
                      <span className="cell category-cell">
                        <span className="category-pill">{row.category}</span>
                      </span>
                      <span className="cell market-cell">{row.displayName}</span>
                      <span className="cell numeric-cell">
                        {formatQuote(row.yesBid, row.yesAsk)}
                      </span>
                      <span className="cell numeric-cell">
                        {formatQuote(row.noBid, row.noAsk)}
                      </span>
                      <span className="cell">{formatDate(row.startTime)}</span>
                      <span className="cell numeric-cell">
                        {formatVolume(row.volume)}
                      </span>
                    </div>
                  ))
                )}
              </div>

              <div className="pagination-bar">
                <button
                  className="nav-button"
                  disabled={safeCurrentPage <= 1}
                  onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
                  type="button"
                >
                  Prev
                </button>
                <div className="pagination-status">
                  {currentTotalItems === 0
                    ? "No items"
                    : `${(safeCurrentPage - 1) * deferredViewState.topBar.pageSize + 1}-${Math.min(
                        safeCurrentPage * deferredViewState.topBar.pageSize,
                        currentTotalItems,
                      )} of ${currentTotalItems}`}
                </div>
                <button
                  className="nav-button"
                  disabled={safeCurrentPage >= totalPages}
                  onClick={() =>
                    setCurrentPage((page) => Math.min(totalPages, page + 1))
                  }
                  type="button"
                >
                  Next
                </button>
              </div>
            </section>
          </section>

          <aside className="filter-pane">
            <div className="filter-pane-header">
              <p className="pane-eyebrow">Filter Configuration</p>
              <h2>Shape the scanner</h2>
              <p>
                Markets stay lightweight by fetching event summaries first. Positions and
                watched markets pull their full data up front so filtering stays local.
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
                {availableCategories.map((category) => (
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
              {selectedCategoryStatuses.length > 0 ? (
                <div className="category-status-list">
                  {selectedCategoryStatuses.map(({ category, detail, status }) => (
                    <div className="category-status-row" key={category}>
                      <div className="category-status-copy">
                        <span className="category-status-name">{category}</span>
                        <span className="category-status-detail">{detail}</span>
                      </div>
                      <span className={`category-status-pill ${status}`}>
                        {status}
                      </span>
                    </div>
                  ))}
                </div>
              ) : null}
            </section>

            <section className="filter-section">
              <div className="section-header">
                <h3>Keyword</h3>
              </div>
              <input
                className="text-filter"
                onChange={(event) => setFilter("keyword", event.currentTarget.value)}
                placeholder="Search event or market text"
                value={history.present.filters.keyword}
              />
            </section>

            <section className="filter-section">
              <div className="section-header">
                <h3>Ranges</h3>
                {activeTab === "markets" ? (
                  <p className="filter-note">
                    Volume filtering is intentionally deferred for the Markets tab until we
                    add a lightweight event-level volume path.
                  </p>
                ) : null}
              </div>
              <div className="range-grid">
                <RangePair
                  disabled={activeTab === "markets"}
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
                  label="Yes Bid"
                  maxKey="bidMax"
                  minKey="bidMin"
                  onChange={setFilter}
                  state={history.present.filters}
                />
                <RangePair
                  label="Yes Ask"
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
  disabled?: boolean;
  onChange: <K extends keyof FilterState>(key: K, value: FilterState[K]) => void;
};

function RangePair({
  label,
  minKey,
  maxKey,
  state,
  disabled = false,
  onChange,
}: RangePairProps) {
  return (
    <div className={disabled ? "range-card disabled-range" : "range-card"}>
      <span className="range-label">{label}</span>
      <div className="range-inputs">
        <input
          disabled={disabled}
          inputMode="numeric"
          onChange={(event) => onChange(minKey, event.currentTarget.value)}
          placeholder="Min"
          value={state[minKey]}
        />
        <input
          disabled={disabled}
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

function WatchButton({
  active,
  onClick,
}: {
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      aria-label={active ? "Remove from watchlist" : "Add to watchlist"}
      className={active ? "watch-button active-watch" : "watch-button"}
      onClick={onClick}
      type="button"
    >
      {active ? "★" : "☆"}
    </button>
  );
}

export default App;
