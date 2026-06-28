# Mission Hub — Frontend Plan

A single-tab browser UI showing grammar load status and per-kind config stats.
Lays the groundwork for a multi-tab app; the tab bar scaffold is included from the start.

---

## 1. New API endpoints (`src/api.py`)

### `GET /grammar-stats`

Returns counts for every config kind. Requires the grammar to be loaded — if not,
returns a 503. Pulls data from the already-constructed `Grammar` object via `get_grammar()`.

Response shape:

```json
{
  "inventory":            { "files": 2, "phones": 34, "tags": 8, "classes": 12 },
  "patterns":             { "files": 1, "total": 18 },
  "rules":                { "files": 2, "total": 11 },
  "feature_markers":      { "files": 3, "total": 6 },
  "contingent_markers":   { "files": 1, "total": 4 },
  "paradigms":            { "files": 2, "total": 5 },
  "part_of_speech":       { "files": 1, "total": 3 },
  "morpheme_sets":        { "files": 1, "total": 7 },
  "morpheme_sequences":   { "files": 1, "total": 4 }
}
```

**Sources inside `Grammar`:**

| Kind | files source | item count source |
|------|-------------|-------------------|
| inventory | `fst_orchestrator.inventory_registry.config_objects` | `len(phones)` + `len(flags)` + `len(classes)` separately |
| patterns | `fst_orchestrator.pattern_registry.config_objects` | `fst_orchestrator.pattern_registry.data` |
| rules | `fst_orchestrator.rule_registry.config_objects` | `fst_orchestrator.rule_registry.data` |
| feature_markers | `marker_orchestrator.feature_markers_registry.config_objects` | `marker_orchestrator.feature_markers_registry.data` |
| contingent_markers | `marker_orchestrator.contingent_markers_registry.config_objects` | `marker_orchestrator.contingent_markers_registry.data` |
| paradigms | `paradigm_registry.config_objects` | `paradigm_registry.data` |
| part_of_speech | `lexicon_registry.config_objects` | `lexicon_registry.data` |
| morpheme_sets | `morpheme_set_registry.config_objects` | `morpheme_set_registry.data` |
| morpheme_sequences | `morpheme_sequence_registry.config_objects` | `morpheme_sequence_registry.data` |

Inventory is the only kind where three separate counts (phones, tags, classes) are returned;
all others return a single `total`.

**Error behaviour:** if `get_grammar()` raises (grammar failed to load), catch and return
`{"detail": "Grammar not loaded"}` with status 503.

---

## 2. Frontend files

```
frontend/
├── index.html       # shell: tab bar + tab panels
├── style.css        # layout, status colours, stat cards
├── api.js           # all fetch calls (only file that calls fetch)
└── hub.js           # Mission Hub tab — polls health + stats, renders cards
```

No build step. Vanilla ES modules via `<script type="module">`.

---

## 3. `index.html`

- A `<nav>` with one `<button data-tab="hub">Mission Hub</button>` (more tabs added later).
- A `<main>` with one `<section id="tab-hub">` panel.
- Imports `hub.js` as a module; `hub.js` imports `api.js`.
- Tab switching is a 5-line inline script (add `hidden` attr to non-active panels).
- No external dependencies.

---

## 4. `api.js`

Exports two functions only:

```js
export async function fetchGrammarHealth() { /* GET /grammar-health */ }
export async function fetchGrammarStats()  { /* GET /grammar-stats  */ }
```

Both return the parsed JSON on success and throw on non-2xx.

---

## 5. `hub.js` — Mission Hub tab

### Layout (rendered into `#tab-hub`)

```
┌─────────────────────────────────────────────────┐
│  Grammar Status                                 │
│  ● Loaded   /   ○ Not loaded   /   ◌ Checking   │
└─────────────────────────────────────────────────┘

Config Stats  (shown only when grammar is loaded)

┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Inventory   │ │   Patterns   │ │    Rules     │
│  2 files     │ │   1 file     │ │   2 files    │
│  34 phones   │ │  18 patterns │ │  11 rules    │
│   8 tags     │ │              │ │              │
│  12 classes  │ │              │ │              │
└──────────────┘ └──────────────┘ └──────────────┘

┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Feat.Markers│ │ Cont.Markers │ │   Paradigms  │
│  3 files     │ │   1 file     │ │   2 files    │
│   6 markers  │ │   4 markers  │ │   5 paradigms│
└──────────────┘ └──────────────┘ └──────────────┘

┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Part of Sp.  │ │ Morph. Sets  │ │ Morph. Seqs  │
│  1 file      │ │   1 file     │ │   1 file     │
│   3 lexemes  │ │   7 sets     │ │   4 sequences│
└──────────────┘ └──────────────┘ └──────────────┘
```

### Polling

- On tab mount, immediately call both endpoints.
- Re-poll every 5 seconds (using `setInterval`).
- If health flips from loaded → unloaded, grey out the stat cards without clearing their last known values (stale indicator).
- If health flips from unloaded → loaded, fetch stats immediately rather than waiting for the next interval tick.

### Status indicator colours

| State | Colour | Label |
|-------|--------|-------|
| loaded | green | Loaded |
| not loaded | red | Not loaded |
| fetch in flight / first load | grey | Checking… |
| grammar load error (503 from /grammar-stats) | amber | Load error |

---

## 6. `style.css`

- CSS custom properties for status colours (`--clr-loaded`, `--clr-error`, `--clr-stale`).
- Stat cards: `display: grid; grid-template-columns: repeat(3, 1fr)` with a max-width.
- No framework. ~80 lines total expected.

---

## 7. Serving the frontend

Uncomment the existing `StaticFiles` mount in `src/api.py` (line 113):

```python
app.mount("/", StaticFiles(directory="frontend", html=True), name="static")
```

This serves `frontend/index.html` at `/` with no extra config.

---

## 8. Implementation order

1. Add `GET /grammar-stats` to `src/api.py`.
2. Verify endpoint manually with `curl` / browser against a running server.
3. Write `frontend/api.js`.
4. Write `frontend/hub.js` (stub cards first, then wire polling).
5. Write `frontend/index.html` and `frontend/style.css`.
6. Uncomment the `StaticFiles` mount.
7. Smoke-test: load the page, confirm status flips when server restarts.
