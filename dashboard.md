# Dashboard Spec

This document is our working spec for a custom Kalshi market dashboard.

Goal: design a calmer, more configurable interface for viewing open markets than the default Kalshi experience.

Status: draft

## Product Intent

We are defining what this dashboard should do, who it is for, and how it should feel before writing code or choosing libraries.

## Working Principles

- Optimize for fast scanning and decision-making.
- Prefer clarity over visual flair.
- Make important information configurable.
- Keep this document implementation-agnostic for now.

## Initial Notes

This section will hold the raw idea dump before we refine it.

- Primary layout: a main pane plus a right-side vertical configuration pane.
- Main pane: a list of markets that are currently open.
- The market list is controlled by filters configured in the right-side pane.
- Each market row should show:
  - Market name
  - Current bid / ask
  - Event start time
  - Volume
- Right-side pane: dedicated area for configuring what appears in the main pane.

## Current Draft

### Core Layout

The dashboard is centered around a two-pane layout:

- Top controls bar above the main pane
- Main pane: a dense, easy-to-scan list of currently open markets
- Right-side pane: controls for filtering and shaping the main list

The top controls bar is for lightweight display options that affect how the scanner is presented, without belonging in the heavier filter configuration area.

### Top Bar

The top bar should contain quick view controls rather than detailed filtering.

Initial v1 top-bar controls:

- `Group by event`
- `Sort by`
- `Ascending / Descending`
- `Auto-refresh`

Planned top-bar controls for later:

- `Density` (`Compact / Comfortable`)
- `Columns` chooser
- `Saved view` selector

### Tabs And Navigation

The dashboard should use a tabbed interface.

Each tab represents one currently open working view.

Tab behavior:

- Open a new tab
- Close the current tab
- Duplicate a tab
- Access tab actions from a right-click context menu on the tab
- Show an asterisk on tabs with unsaved changes

History behavior within the current tab:

- Back button: undo recent changes to the current view state
- Forward button: redo changes that were undone

Current interpretation:

- Back/forward should operate on view-state changes within the active tab
- The history should cover changes to filters and top-bar settings for that tab
- Row expansion / collapse state should not be part of the history model
- Tabs should behave like independent workspaces, each with its own current state and history

### Primary Workspace Tabs

In addition to saved-view tabs, the scanner should expose primary workspace tabs for the main data modes:

- `Markets`
- `Positions`
- `Watching`

Current interpretation:

- `Markets` is the main open-market scanner
- `Positions` shows currently open positions
- `Watching` shows markets that have been starred/pinned for monitoring
- The same core filter model should apply across these tabs where practical

### Main Pane

The main pane is a market scanner rather than a highly visual browsing experience.

Each visible market entry should include:

- Category
- Market name
- Current bid / ask
- Event start time
- Volume

Initial assumption:

- The default experience should emphasize compact scanning over large cards or promotional content.

### Filter Pane

The right-side vertical pane is where the user defines what appears in the market list.

Initial assumption:

- Filtering should feel like configuring a personal market scanner, not navigating a storefront.

Initial filter set:

- Category
- Live events only
- Volume range
- Bid / ask spread range
- Bid range
- Ask range
- Keyword match against market text

Possible future additions:

- Market status constraints beyond open-only
- Event timing windows
- Saved filter presets
- More advanced text / rule-based filtering

Current implementation note:

- `Sub-category` is intentionally removed from the near-term UI because the available values are too numerous and noisy to be useful in the current right-side pane
- Volume filtering for the `Markets` tab is a deferred TODO until we have a lightweight way to obtain trustworthy event-level volume without loading every market up front

### Control Placement Principles

We should keep control placement consistent:

- Top bar: quick display/view controls that change presentation
- Right-side pane: filtering criteria that determine which rows appear

Examples:

- Top bar: group by event, sort, sort direction, auto-refresh
- Right pane: category, sub-category, live-events-only, numeric ranges, keyword matching

## Saved Views

Saved views are reusable starting points for the dashboard.

Definition:

- A saved view contains the filter configuration plus the top-bar settings
- A saved view also contains a user-defined view title
- Saved views are stored as files in a structured format
- The exact file format is intentionally undecided for now

Load behavior:

- Loading a saved view snaps the current tab into that saved configuration
- After loading, the user is free to change filters or controls without modifying the saved view itself
- A saved view is therefore a launch state, not a live binding

Current implication:

- Unsaved edits after loading a view should be treated as local state in the current tab
- If the user wants to preserve those edits, they would later need an explicit save/update action

### Default Startup State

When the viewer first opens, it should drop into a default unsaved view.

Current design direction:

- The default view has no name
- The main pane starts effectively blank
- No categories or events are selected in the filters
- The default state acts as an empty starting workspace rather than a preconfigured opinionated layout

### View Naming

View titles should be part of the saved view data and should not be derived from the filename.

Implications:

- The tab title should come from the view title field
- The filename is just the storage container and does not define the user-facing name
- Unsaved tabs should still have a visible tab label

Current design direction:

- Include an editable view title field in the UI
- The title field should be easy to find but not overemphasized
- A blank unsaved view can use a temporary fallback title until the user names it

Candidate pattern:

- Place a small editable title field in the top bar, aligned near the left side
- If no explicit title exists yet, show a placeholder such as `Untitled View`
- When the tab has unsaved changes, show an asterisk in the tab label

### File Menu Behavior

The application should support a macOS-style `File` menu.

Initial `File` menu actions:

- `New`
- `Open`
- `Save`
- `Save As`
- `Close`

Action meanings:

- `New`: open a new tab with a default unsaved view
- `Open`: open a saved view file
- `Save`: write changes back to the currently associated saved-view file
- `Save As`: save the current tab state as a new saved-view file
- `Close`: close the current tab

Current saved-view model:

- Opening a view means loading it from a file
- A tab may either be associated with an existing saved-view file or be unsaved
- `Save` updates the current file-backed view
- `Save As` creates a new file-backed view from the current state

### Unsaved Changes On Close

If the user tries to close a tab with unsaved changes, the app should prompt:

- `Close view without saving?`

Prompt actions:

- `Yes`
- `No`

Interpretation:

- `Yes` closes the tab and discards unsaved changes
- `No` cancels the close action
- If the user wants to save, they should use the normal save flow rather than saving from this prompt
- The purpose of the prompt is to prevent accidental loss of unsaved work while keeping the close interaction simple

### Keyboard Shortcuts

The app should support standard keyboard shortcuts for core file actions.

Initial shortcuts:

- `Cmd+S`: save the current view
- `Cmd+N`: open a new blank view
- `Cmd+O`: open a saved view file
- `Shift+Cmd+S`: save the current view as a new file
- `Cmd+W`: close the current tab

### First Product Shape

The first version of this dashboard may simply be:

- A configurable list of open markets
- A persistent filter panel on the right

### Positions Tab

The product should include a dedicated `Positions` tab.

Behavior:

- Pull down all open-position data at once for the current account
- Apply filtering locally after the data is loaded
- Reuse the same core filter controls as the market scanner
- Surface position-specific values in the table, such as current position and exposure

### Watching Tab

The product should include a dedicated `Watching` tab.

Behavior:

- The user can star or pin an individual market from elsewhere in the app
- Starred markets are collected into the `Watching` tab
- The watchlist is intended as a lightweight personal monitor, separate from actual positions
- Watched-market filtering should happen locally after their data is loaded
- A clean, low-noise layout optimized for scanning

### Sorting

The main list should support ordinary ascending / descending sorting by visible columns.

Initial sortable columns:

- Category
- Market name
- Bid
- Ask
- Event start time
- Volume

### Row Interactions

Different click targets in a row should do different things:

- Contract/rules icon: open a compact view showing the contract language
- Bid click: open an order book view focused on the bid side
- Ask click: open an order book view focused on the ask side
- External-link icon: open the corresponding Kalshi market page in the browser

### Hierarchical Market Display

We should support the case where a higher-level tradable subject contains multiple underlying outcomes.

Current design direction:

- Add a `Group by event` checkbox in the top controls bar above the main pane
- When `Group by event` is unchecked, show all markets as flat rows
- When `Group by event` is checked, collect markets under parent event rows
- Grouped parent rows can be expanded to reveal child market rows
- Parent rows with multiple child markets should display `--` for bid / ask
- Child rows should display their own bid / ask, volume, and other tradable data

Important terminology note:

- In Kalshi's official model, the parent grouping is usually closer to an `event`, and the individual tradable outcomes underneath it are `markets`
- So what we first called a "top level market" may actually need to be represented as an event row with nested market rows when grouping is enabled

### Event Start Time

Your requested "start time of the event" should likely come from the Kalshi event object, not the market object.

Open implementation/data question for later:

- Which event timestamp should be surfaced in the UI for all categories as the most intuitive "start time"?

## Open Questions

- Who is the primary user workflow we want to optimize for?
- What information needs to be visible at a glance?
- What should be configurable per user or per view?
- What parts of the Kalshi experience feel noisy, distracting, or slow today?
- What should the first version do, and what can wait?
- Should the main list support sorting, and if so by what fields?
- Should the filter pane always be visible, or collapsible?
- What exactly should "event start time" mean for all market types?
- Should rows be click-through to a detail panel, or remain scanner-only at first?
- Do you want the dashboard to focus only on discovery, or also help with position awareness?
- For "sub-category," do we want to model Kalshi `tags`, a derived grouping from title/ticker, or a custom user-defined grouping?
- Should the scanner's primary rows be `events` with expandable child `markets`, or should every child market always be shown flat by default?
- When the contract-language icon is clicked, should it show full rules text inline, in a modal, or in a side panel?
- When bid/ask is clicked, should the order book appear inline beneath the row or in a separate detail area?
- Do we want separate columns for bid and ask, or one combined "bid / ask" column with independent click targets inside it?
- Do back/forward buttons track only filter/control changes, or also selection state?
- How should saved views be renamed or deleted beyond normal file operations?
- What exact state should be represented by the initial blank default view?
- What should the fallback tab title be for unnamed unsaved views?

## Candidate Sections

- Market list / scanner
- Market detail view
- Filters and saved views
- Watchlists
- Positions and exposure
- Alerts / changes worth noticing
- Layout and density preferences

## Technical Direction

This section captures the recommended implementation direction for the desktop app.

### Chosen Stack

Chosen stack:

- Desktop shell: `Tauri`
- UI language: `TypeScript`
- UI framework: `React`
- Frontend build tool: `Vite`

Summary:

- Build the app as a desktop application using Tauri
- Build the interface itself as a React app in TypeScript
- Use Vite for a fast local development loop

### Why This Is The Best Fit

This stack best matches the current product goals:

- Runs well on macOS
- Supports rapid iteration during UI-heavy development
- Gives us a rich, flexible UI model for tabs, panes, context menus, sortable tables, saved views, and polished interactions
- Avoids the visual limitations and dated feel that often come with basic Python desktop GUI toolkits

Why `Tauri`:

- Tauri is explicitly designed for desktop applications
- Tauri supports using essentially any web frontend framework, which gives us freedom on the UI side
- Tauri uses the OS web renderer instead of bundling a full Chromium runtime, which is attractive for a relatively lean desktop tool

Why `React`:

- React is a strong fit for stateful interfaces with lots of composable UI pieces
- This dashboard will have a lot of interactive state: tabs, filters, grouped rows, history, saved views, and detail popups
- React has a very mature ecosystem for building these kinds of interfaces cleanly

Why `TypeScript`:

- The app will have a lot of structured state and interaction rules
- TypeScript will help keep that complexity from getting sloppy as the UI grows

Why `Vite`:

- Vite is built for a fast development loop
- Fast startup and hot updates matter a lot for UI iteration, especially when we will be repeatedly tweaking layout and interaction details

### Why Not Pure Python For The UI

Python can still be useful in this project, but I do not think it is the right primary language for the desktop UI.

Reasoning:

- You already dislike the feel of Tkinter, which is a meaningful signal
- Python desktop options can work, but they are generally less attractive for building a highly polished custom desktop interface quickly
- Since you will not be writing the UI code yourself, we should optimize for the best product and iteration speed rather than for your current language comfort alone

Practical compromise:

- Use TypeScript/React/Tauri for the desktop UI
- Keep the option to use Python later for separate trading scripts, data processing, analytics, or strategy logic if that becomes useful

### Alternatives Considered

#### SwiftUI

Strengths:

- Excellent native fit for macOS
- Very good-looking Apple-platform UI framework
- Strong system integration

Why I am not recommending it first:

- It is a very good option if we were optimizing purely for Apple-native development
- But it is a less convenient choice for fast iteration by me compared with a modern web UI stack
- The breadth of battle-tested UI patterns and libraries for complex scanner-style interfaces is generally better in the web ecosystem

#### Electron

Strengths:

- Very mature desktop-web app ecosystem
- Easy to build rich UIs with web technology

Why I prefer Tauri:

- Electron bundles Chromium and Node.js, which is heavier than we need for this kind of tool
- Tauri gives us a similar frontend-development experience with a lighter desktop shell

#### PySide6 / Qt

Strengths:

- Best serious Python desktop option
- Much more capable than Tkinter
- Can produce real desktop apps

Why I still would not choose it first:

- It is a reasonable fallback if we decide Python-first matters more than expected
- But for this specific product, I think Tauri + React will give us a smoother path to a polished, modern UI

### Implementation Philosophy

Even though the recommended stack uses web UI technology, this should still behave like a desktop app.

That means:

- Native-feeling menus and keyboard shortcuts
- File-based saved views
- Fast launch and iteration
- Clean handling of multiple tabs and document-like state

### Python's Role

Python is not the chosen language for the UI layer, but it remains a strong option for adjacent tooling in this project.

Likely future uses for Python:

- Trading logic
- Data processing
- Analytics
- Strategy experiments
- Supporting scripts or services behind the desktop app

## Application Architecture

This section defines the high-level technical architecture for the app.

### Architecture Summary

The app should use a layered architecture with a clear separation between:

- Desktop host responsibilities
- UI rendering and interaction state
- Kalshi data access
- View-file persistence
- Future analytics/trading extensions

Recommended shape:

- `Tauri` handles the desktop shell, native menus, file dialogs, and window integration
- `React + TypeScript` handles the entire visible application UI and user interaction model
- A frontend data layer handles fetching, normalizing, caching, and refreshing Kalshi market data
- A persistence layer handles reading and writing saved-view files
- Future Python components remain outside the core UI and communicate through clear boundaries when needed

### Layer Breakdown

#### 1. Desktop Shell Layer

Responsibilities:

- App window lifecycle
- Native macOS-style menu wiring
- File open/save dialogs
- Keyboard shortcuts
- Launching into the default blank view

Primary technology:

- `Tauri`

Why this layer exists:

- It keeps OS integration concerns out of the React UI code
- It lets the app feel like a real desktop application instead of a browser tab

#### 2. UI Layer

Responsibilities:

- Rendering tabs, panes, rows, controls, and popups
- Managing interaction state for the current session
- Responding to filter changes, sorting, tab actions, and history navigation
- Showing live market data in scanner form

Primary technology:

- `React + TypeScript`

Why this layer exists:

- This product is mostly an interaction-heavy stateful UI
- React is a strong fit for composing many small interface concerns into a coherent whole

#### 3. Data Access Layer

Responsibilities:

- Call Kalshi endpoints
- Map Kalshi API responses into app-friendly models
- Merge event-level and market-level data into scanner rows
- Refresh data on demand or on an interval
- Handle loading states and network failures cleanly

Current design direction:

- Keep this logic inside the TypeScript app initially
- Use a dedicated client module rather than scattering fetch logic through UI components

Why this layer exists:

- It prevents the UI from becoming tightly coupled to raw API response shapes
- It gives us a clean place to adapt terminology and compose event/market relationships

#### 4. Persistence Layer

Responsibilities:

- Read saved-view files from disk
- Write saved-view files to disk
- Track whether the current tab has unsaved changes relative to its last saved state
- Load saved views into new tabs

Current design direction:

- Treat saved views as document-like files
- Persist only durable view configuration, not transient inspection state

Why this layer exists:

- It keeps the document model explicit
- It makes save/open behavior predictable and testable

#### 5. Future Automation / Analytics Layer

Responsibilities:

- Optional future trading logic
- Analytics workflows
- Data enrichment
- Strategy tooling

Current design direction:

- Keep this separate from the UI architecture at first
- If needed later, expose it through a clean API boundary rather than embedding ad hoc logic into the React app

Likely future technology:

- `Python`

### State Model

The app should distinguish between several kinds of state.

#### Persisted View State

This state belongs in the saved-view file:

- View title
- Filter values
- Top-bar settings
- Possibly column-visibility preferences if we include them

This is the state that defines the reusable identity of a view.

#### Tab Session State

This state belongs to an open tab during the current session:

- Current working filter values
- Current top-bar settings
- Back/forward history stack
- Associated saved-view file path, if any
- Dirty/unsaved flag

This state may start from a saved view, but it evolves independently after load.

#### Transient UI State

This state should not be persisted:

- Expanded/collapsed event rows
- Open contract-language popup
- Open order-book popup
- Hover/focus state
- Temporary loading indicators

This is short-lived interaction state, not document state.

#### Live Remote Data

This state comes from Kalshi and should not be saved into view files:

- Current bid/ask values
- Current volume
- Current spread
- Event/market metadata fetched from the API

Saved views define how to look at markets, not snapshots of market data.

### Data Model

The app should not directly treat raw Kalshi responses as UI state everywhere.

Instead, use app-level models:

- `SeriesSummary`
- `EventSummary`
- `MarketSummary`
- `ScannerRow`
- `SavedView`
- `TabState`

Current design direction:

- `EventSummary` represents the higher-level grouping
- `MarketSummary` represents each tradable binary contract
- `ScannerRow` is the display-oriented model used by the main pane
- In grouped mode, rows are organized by event
- In ungrouped mode, each row maps directly to a market-oriented display record

Why this matters:

- It allows us to keep API details from leaking all over the app
- It gives us room to evolve the UI without being handcuffed to Kalshi response shapes

### Saved-View File Schema

We do not need to choose the actual file format yet, but we should define what conceptually belongs in it.

A saved view should contain:

- View title
- Filter settings
- Top-bar settings
- Maybe version metadata for future compatibility

A saved view should not contain:

- Live market data
- Open popovers
- Expanded/collapsed rows
- Current history stack
- Temporary selection/hover state

Current recommendation:

- Include a schema version field from the beginning
- Keep the saved-view format narrow and human-inspectable

### History Model

History should be tab-local.

Each history entry should capture:

- Filter state
- Top-bar state

History should not capture:

- Expanded rows
- Popup visibility
- Other purely transient UI state

Why this matters:

- It keeps back/forward useful and predictable
- It avoids cluttering history with low-value interface noise

### Fetching Strategy

Initial approach:

- Fetch open markets and related event data from Kalshi
- Normalize the data into app models
- Derive scanner rows from normalized data
- Refresh on demand and via the top-bar auto-refresh setting

Current recommendation:

- Start with straightforward polling rather than jumping immediately to WebSockets
- Add WebSocket-based updates later only if polling feels too stale or too inefficient

Why:

- Polling is simpler to reason about during early UI development
- We are still figuring out interaction design, so lower implementation complexity is valuable

### Future Real-Time Upgrade Path

The architecture should intentionally leave room for a later WebSocket-based live-data upgrade.

Future direction:

- Keep polling as the v1 data-refresh model
- Design the data layer so that polling and WebSocket updates can both feed the same normalized app state
- When we later want more real-time behavior, add Kalshi WebSocket integration without redesigning the rest of the UI architecture

Why this matters:

- The product is likely to benefit from more live market updates over time
- We want to avoid painting ourselves into a corner with a polling-only design
- A clean data layer now will make the future move to streaming updates much easier

Current architectural intent:

- UI components should consume normalized app state, not care whether that state came from polling or WebSockets
- The transport mechanism should be swappable behind the data-access layer
- WebSockets are a planned improvement, not an afterthought

### Error Handling

The app should treat data and file errors as first-class product concerns.

Important error categories:

- Kalshi API auth/config errors
- Kalshi network failures
- Invalid or outdated saved-view files
- Save/open failures from the local filesystem

Current design direction:

- Show human-readable, localizable error messages in the UI
- Keep the app usable even if one tab fails to load data
- Avoid crashes caused by malformed view files or partial API failures

### Future Python Integration

If we later add Python-based logic, do not let the UI depend on Python for basic rendering or view management.

Preferred pattern:

- The desktop app remains fully functional on its own for market browsing
- Python components are optional supporting modules or services
- The interface between the UI and Python should be explicit and narrow

Examples of future Python responsibilities:

- Custom analytics calculations
- Signal generation
- Historical data processing
- Trade recommendation engines
- Execution tooling outside the core viewer

### Project Structure Direction

At a high level, the project should likely separate into areas such as:

- Desktop app shell
- UI components
- State management
- Kalshi API client
- Persistence / saved views
- Shared data models
- Future Python tools

Exact folder names can be decided during implementation, but the architectural boundary is more important than the final directory naming.

## Decisions

We will record settled decisions here as we make them.

- Initial layout direction: two-pane dashboard with a main market list and a right-side filter/configuration pane.
- Initial main-list fields: category, market name, current bid/ask, event start time, and volume.
- Initial scope focus: open markets only.
- Main list should support standard ascending / descending sorting by column.
- Initial filter set includes category, sub-category, live-events-only, volume range, spread range, bid range, ask range, and keyword match.
- Row interactions should be target-based: contract icon for contract language, bid/ask click for order book, external-link icon for Kalshi page.
- The dashboard should support both flat and grouped display modes.
- A `Group by event` checkbox should live above the main pane and control whether markets are grouped under expandable parent event rows.
- Initial top-bar controls: `Group by event`, `Sort by`, `Ascending / Descending`, and `Auto-refresh`.
- Control-placement rule: top bar for view/presentation controls, right pane for row-filtering criteria.
- Saved views should be a feature of the product.
- A saved view should store filter settings plus top-bar settings.
- Loading a saved view should apply that configuration to the current tab as a starting point, without live-linking future edits back to the saved view.
- The dashboard should use tabs, with each tab representing an open working view.
- Tab context menu should support opening a new tab, closing a tab, and duplicating a tab.
- The dashboard should provide back/forward controls to undo and redo view-state changes within the active tab.
- Tabs with unsaved changes should display an asterisk indicator.
- History should include filter changes and top-bar setting changes, but not row expansion/collapse state.
- Duplicating a tab should carry over the full history stack, not just the current visible state.
- The app should open into a default unnamed unsaved view.
- The default startup view should begin blank rather than pre-populated.
- Saved views should be file-based, with the exact structured file format to be decided later.
- Saved views should contain a user-defined title field separate from the filename.
- The app should expose a macOS-style `File` menu with `New`, `Open`, `Save`, `Save As`, and `Close`.
- `Save` should update the current associated saved-view file, while `Save As` should create a new saved-view file from the current state.
- `Open` should always load the selected saved view into a new tab.
- Closing a tab with unsaved changes should prompt `Close view without saving?` with `Yes` and `No` options.
- Keyboard shortcuts should follow standard macOS conventions: `Cmd+N` for new, `Cmd+O` for open, `Cmd+S` for save, `Shift+Cmd+S` for save as, and `Cmd+W` for close.
- The UI should provide a way to edit the current view title directly, rather than deriving it from the file name.
- Chosen implementation stack: `Tauri + React + TypeScript + Vite`.
- Python is not the chosen primary language for the desktop UI, though it remains a good option for future trading/data/analytics tooling outside the UI layer.
- Architecture should be layered: desktop shell, UI, data access, persistence, and future optional Python tooling.
- Saved views should persist durable view configuration only, not live market data or transient UI state.
- The initial Kalshi data strategy should use polling, with WebSockets considered later if needed.
- The initial data-access logic should live in the TypeScript application rather than requiring a separate backend service.
- The data layer should be designed so a future WebSocket-based real-time feed can replace or augment polling without forcing a UI redesign.

## Glossary

This section aligns our product language with Kalshi's official terminology.

### Official Kalshi Terms

- Series: a collection of related events that follow the same template over different time periods. Example from Kalshi docs: recurring things like daily weather or monthly jobs reports.
- Event: a real-world occurrence that users conceptually interact with. An event contains one or more markets.
- Market: a specific tradable binary outcome within an event. This is the actual yes/no contract with its own bid, ask, volume, and rules.
- Category: an official field exposed by Kalshi on series and events. Examples in the docs and product include broad groups like sports, politics, economics, and technology-related areas.
- Ticker: Kalshi's identifier for a series, event, or market.
- Orderbook: the live bids and asks for a market.

### Practical Translation For Our Spec

- What we casually called a "market page" in the consumer UI may correspond to an event that contains several underlying markets.
- What you described as sub-markets are usually Kalshi markets under a shared event.
- If we use expandable parent rows, the parent row likely represents an event and the child rows represent markets.

### Terms We Need To Use Carefully

- Category: official Kalshi term.
- Sub-category: not clearly documented by Kalshi as a first-class field in the API docs I checked.
- Tags: Kalshi does expose `tags` on series, and those may end up being useful for a sub-category-like filter.

Current recommendation:

- Use `category` as an official field name in the spec.
- Treat `sub-category` as a product concept for now, pending a later decision on whether it maps to tags, series groupings, or our own derived label.
