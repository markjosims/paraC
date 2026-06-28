# VSCode Editor PoC

Implement a proof-of-concept VS Code + FastAPI developer tooling setup for editing morphological FST config files in YAML. Follow these instructions exactly.

## Repo structure to create

```
project/
├── .vscode/
│   ├── settings.json
│   ├── keybindings.json
│   └── templates/
│       ├── MorphemeSequence.yaml
│       ├── Paradigm.yaml
│       ├── FeatureMarkers.yaml
│       └── Inventory.yaml
├── backend/
│   ├── main.py
│   └── schemas.py
├── schemas/
│   ├── MorphemeSequence.json
│   ├── Paradigm.json
│   ├── FeatureMarkers.json
│   └── Inventory.json
└── configs/
    ├── rules/
    ├── paradigms/
    ├── markers/
    ├── sequences/
    ├── inventory/
    └── combinations/

```

---

## Schemas

Stored in `schemas/`.

---

## Backend

Implement `backend/main.py` and `backend/schemas.py` as a FastAPI app with the following requirements.

**Endpoints:**

`GET /schemas/{kind}` — reads `schemas/{kind}.json`, calls `patch_schema(schema, kind)`, returns the result as JSON.

`GET /configs?type={kind}` — returns a list of `$`-prefixed relative paths to all `.yaml` files in the subdirectory for that kind. Use this directory mapping:
```python
KIND_TO_DIR = {
    "Rule":                "rules",
    "Paradigm":            "paradigms",
    "FeatureMarkers":      "markers",
    "MorphemeSequence":    "sequences",
    "Inventory":           "inventory",
    "FeatureCombinations": "combinations",
    "ContingentMarkers":   "markers",  # same dir, filtered by kind if needed
}
```

Paths should be relative to `configs/` and prefixed with `$`, e.g. `$paradigms/verbal.yaml`.

`GET /file?path={path}` — reads and returns the file at the given path as JSON-parsed YAML.

`PUT /file?path={path}` — writes the JSON request body to the given path as YAML.

`GET /health` — returns `{"ok": true}`.

**`patch_schema(schema, kind)`** — deepcopies the schema and injects live enums as follows:

- `MorphemeSequence`: replace `properties.data.items` with a `oneOf` array, one branch per type in `["Rule", "Paradigm", "Lexicon", "MorphemeSet", "Pattern"]`. Each branch has `properties.type.const` set to the type and `properties.value.enum` set to the result of `get_refs(type)`.

- `Paradigm`:
  - Replace `properties.feature_markers.additionalProperties` with a `oneOf` of `[{type: string, enum: get_refs("FeatureMarkers")}, {type: null}]`.
  - Replace `properties.feature_combinations` with `{type: string, enum: get_refs("FeatureCombinations"), description: "..."}`.
  - Replace `properties.contingent_markers.items` with `{type: string, enum: get_refs("ContingentMarkers")}`.

- All other kinds: return schema unmodified.

**`get_refs(kind)`** — globs `configs/{KIND_TO_DIR[kind]}/*.yaml` and returns `$`-prefixed paths relative to `configs/`.

Add CORS middleware allowing all origins (this is a local dev tool).

---

## .vscode/settings.json

```json
{
  "yaml.schemas": {
    "http://localhost:8000/schemas/MorphemeSequence": "configs/sequences/*.yaml",
    "http://localhost:8000/schemas/Paradigm":         "configs/paradigms/*.yaml",
    "http://localhost:8000/schemas/FeatureMarkers":   "configs/markers/*.yaml",
    "http://localhost:8000/schemas/Inventory":        "configs/inventory/*.yaml"
  },
  "yaml.validate": true,
  "yaml.completion": true,
  "yaml.hover": true
}
```

## .vscode/keybindings.json

```json
[
  {
    "key": "ctrl+shift+r",
    "command": "yaml.clearCache",
    "when": "editorLangId == yaml"
  }
]
```

---

## File templates

Create `.vscode/templates/` files for use with the `rioj7.vscode-file-template` VS Code extension. Each template should be a valid minimal YAML file for that kind. Include inline comments explaining every field: what it does, what values are valid, and an example. For optional fields, comment them out but leave them present so the user can uncomment them. Use the schema `description` fields as the source of truth for comment text.

For `FeatureMarkers.yaml`: include commented examples of suffix, suppletion (2-element array value), and multi-marker entries.
For `Paradigm.yaml`: include commented examples of `filter`, `global_markers`, and `feature_markers` with `null`.
For `Inventory.yaml`: include commented examples of a phones node, flags node, and nested node with `_children`.
For `MorphemeSequence.yaml`: include a commented example of one data item of each type.

Use `${feature}` variable substitution in `FeatureMarkers.yaml` for the `feature` field, and `${part_of_speech}` in `Paradigm.yaml`, so the extension prompts for these values on file creation.

---

## Sample configs

Create the following minimal valid sample configs so the backend has something to return from `/configs` on first run:

- `configs/rules/example_rule.yaml` — `kind: Rule` with a placeholder `data` field
- `configs/paradigms/example_paradigm.yaml` — minimal valid Paradigm
- `configs/markers/example_markers.yaml` — minimal valid FeatureMarkers with one marker
- `configs/inventory/example_inventory.yaml` — minimal valid Inventory with one phones node

---

## README.md

Write a brief README with:

1. Prerequisites: Python 3.11+, VS Code, extensions to install (`redhat.vscode-yaml`, `rioj7.vscode-file-template`)
2. Setup: `pip install fastapi uvicorn pyyaml`, then `uvicorn backend.main:app --reload`
3. One-line explanation of the schema cache hotkey
4. How to create a new config file using the template extension

---

## Constraints

- Use `pyyaml` for YAML parsing/serialization, not `ruamel`.
- No frontend code, no HTML, no JS.
- No database. All state is the filesystem.
- The backend is a local dev tool; no auth, no security hardening needed.
- Do not add any dependencies beyond `fastapi`, `uvicorn`, and `pyyaml`.
