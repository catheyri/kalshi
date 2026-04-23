# Dashboard Implementation Plan

This document breaks the dashboard spec into practical delivery phases.

It is separate from the product spec in [`dashboard.md`](dashboard.md) so we can refine implementation order without muddying the feature definition.

## Planning Principles

- Build the smallest useful version first
- De-risk architecture early
- Prefer visible progress over invisible plumbing
- Keep room for iteration after each phase
- Do not overbuild for future features before the core scanner feels right

## Delivery Strategy

The project should be built in layers:

1. Establish the desktop app foundation
2. Build the core scanner workflow
3. Add document/view management
4. Refine interaction details
5. Prepare for later real-time and analytics expansion

## Phase 0: Project Foundation

Goal:

- Create a working desktop-app skeleton with the chosen stack

Scope:

- Scaffold `Tauri + React + TypeScript + Vite`
- Set up basic project structure
- Configure development scripts and local build flow
- Create a minimal app shell that launches on macOS
- Add baseline styling approach and design tokens

Deliverable:

- A desktop app window opens locally and supports rapid iteration

Why first:

- This removes setup uncertainty before we spend time on product behavior

## Phase 1: App Shell And Layout

Goal:

- Build the static structural UI of the dashboard without real Kalshi data yet

Scope:

- Top bar
- Main pane
- Right-side filter pane
- Tab bar
- Empty-state / blank default view
- Basic menu wiring placeholders

Deliverable:

- A clickable static prototype of the dashboard shell with the correct regions and controls

Why this phase matters:

- It lets us validate the overall information architecture before data complexity enters the picture

## Phase 2: Core View State

Goal:

- Make the dashboard actually behave like a working single-tab scanner view

Scope:

- Filter state model
- Top-bar state model
- Sort behavior
- `Group by event` behavior
- View title field
- Dirty/unsaved tracking for the current tab
- Back/forward history for filter and top-bar state

Deliverable:

- One fully interactive local view with realistic state behavior, even if the data is still mocked

Why this phase matters:

- This is the heart of the product
- It validates the document/view model before we add persistence and live data

## Phase 3: Kalshi Data Integration V1

Goal:

- Replace mocked scanner content with real Kalshi data using polling

Scope:

- Build a TypeScript Kalshi client for the viewer
- Fetch open markets and related event data
- Normalize API responses into app models
- Derive scanner rows for grouped and ungrouped modes
- Support manual refresh and auto-refresh
- Add loading, empty, and error states

Deliverable:

- The dashboard displays real open Kalshi markets and responds to filters/sorts

Implementation note:

- Event-summary volume is a known follow-up item; volume filtering on the `Markets` tab should be revisited once we have a lightweight event-level aggregation path

Why this phase matters:

- This is the first genuinely useful version of the product

## Phase 4: Row Interactions

Goal:

- Add the market-inspection interactions that make the scanner practical

Scope:

- Contract-language trigger/icon
- Order-book interaction from bid/ask
- External-link action to open the Kalshi page
- Expand/collapse event groups in grouped mode
- Star / pin interaction on individual markets
- `Watching` tab backed by starred markets
- `Positions` tab that loads all open positions for local filtering

Deliverable:

- The scanner becomes a usable browsing and inspection tool rather than just a filtered list, with dedicated views for open positions and watched markets

Why this phase matters:

- This is where the dashboard starts feeling tailored instead of generic

## Phase 5: Tabs And Saved Views

Goal:

- Turn the viewer into a true multi-view desktop workflow

Scope:

- Multiple tabs
- New / Open / Close / Duplicate tab behavior
- Unsaved indicator in tabs
- File-backed saved views
- `Save`, `Save As`, and `Open`
- Default blank view behavior
- Close-with-unsaved-changes prompt
- Keyboard shortcuts and native-feeling file operations

Deliverable:

- The app behaves like a document-based desktop application for saved market views

Why this phase matters:

- This is the major leap from “tool screen” to “real desktop app”

## Phase 6: Polish And Usability Pass

Goal:

- Improve quality, clarity, and visual feel after the core behavior is real

Scope:

- Layout refinement
- Density tuning
- Better spacing and typography
- Better empty/loading/error states
- Performance tuning for larger result sets
- Better context-menu and keyboard-flow ergonomics
- Better affordances around deferred filters such as event-level volume

Deliverable:

- A stable, pleasant version worth using regularly

Why this phase matters:

- We already agreed the exact visual feel is easier to tune once the product is real

## Phase 7: Real-Time And Advanced Extensions

Goal:

- Prepare the app for more advanced workflows after the first solid release

Scope:

- Optional WebSocket upgrade path
- More advanced saved-view controls
- Additional filter types
- Column configuration
- Analytics hooks
- Python-backed tools or services if needed

Deliverable:

- A roadmap-ready foundation for more live and sophisticated usage

Why this phase matters:

- It keeps advanced ideas visible without forcing them into the first implementation

## Recommended Execution Order

Suggested first build sequence:

1. Phase 0
2. Phase 1
3. Phase 2
4. Phase 3
5. Phase 4
6. Phase 5
7. Phase 6

Phase 7 should remain intentionally deferred until the earlier phases feel stable.

## MVP Cut

If we want the first meaningful usable version as soon as possible, the MVP should be:

- Phase 0
- Phase 1
- Phase 2
- Phase 3
- A minimal slice of Phase 4

MVP outcome:

- Open the app
- See a blank default view
- Adjust filters and top-bar controls
- Load real open Kalshi markets
- Sort and group them
- Inspect basic market details

Tabs and saved views are important, but they can come just after the first real scanner is working.

## Risks And Mitigations

### Risk: Overbuilding the state model too early

Mitigation:

- Start with one-tab behavior before multi-tab persistence complexity

### Risk: API shape complexity around events vs markets

Mitigation:

- Normalize data into app-specific models instead of binding UI directly to raw responses

### Risk: UI complexity explodes before usefulness appears

Mitigation:

- Prioritize scanner usefulness before advanced desktop behaviors

### Risk: Real-time ambitions distract from v1

Mitigation:

- Use polling first and keep WebSockets as a planned later phase

## Definition Of “Good First Release”

A good first release should:

- Feel calm and readable
- Let you filter open markets effectively
- Support grouping and sorting cleanly
- Make contract language and order-book inspection easy
- Be stable enough that you would actually prefer it over browsing Kalshi’s default UI for discovery

## Immediate Next Step

When we move from planning to implementation, the first concrete step should be:

- Execute Phase 0 and scaffold the desktop app foundation with the chosen stack
