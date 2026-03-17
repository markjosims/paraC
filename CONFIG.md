# CONFIG.md

Reference for the YAML config system under `config/`. Each config file has a `kind` field that determines its type and schema (validated against `config/schemas/<Kind>.json`). Cross-file references use `$name` syntax, resolved by searching all config subdirectories for `<name>.yaml`.

## Directory map

| Directory | Config kinds | Purpose |
|---|---|---|
| `config/inventory/` | `Inventory` | Phoneme/flag definitions |
| `config/patterns/` | `Patterns` | Reusable FSA patterns |
| `config/rules/` | `Rules` | Phonological rules (FSTs) |
| `config/features/` | `FeatureDefinitions`, `FeatureCombinations` | Feature values and licit combos |
| `config/markers/` | `FeatureMarkers`, `ContingentFeatureMarkers` | Morphological formatives |
| `config/paradigms/` | `Paradigm` | Inflectional paradigm assembly |
| `config/parts_of_speech/` | `PartOfSpeech` | POS metadata |

## Config kinds

---

### Inventory

**Directory:** `config/inventory/`
**Python:** `InventoryRegistry` / `InventoryItem` in `src/fst_registry.py`

Defines the phoneme inventory: the atomic symbols the FST system operates over. Every phone, flag, and class referenced anywhere in patterns, rules, or markers must be declared here.

**Structure:**
```yaml
kind: Inventory
data:
  <category_name>:          # e.g. "consonants", "vowels", "tones"
    _ref: "<CLASS_REF>"     # angle-bracket ref for the entire class (e.g. "<C>", "<V>")
    <subcategory>:
      _ref: "<SUBCLASS_REF>"
      _phones: [a, b, c]    # leaf phones — atomic segments
    <another_subcategory>:
      _ref: "<SUBCLASS_REF>"
      _flags: ["[TBU]"]     # leaf flags — internal-only markers cleaned on decode
```

**Key rules:**
- `_ref` must use `<angle brackets>` for classes, `[square brackets]` for flags. Phones are bare strings.
- Classes are hierarchical and nest arbitrarily. A class's FSA accepts any phone/flag in its subtree.
- `_phones` and `_flags` are leaf arrays; they cannot coexist in the same node, and leaf nodes cannot have children.
- All items must be globally unique across all Inventory configs.

**Reserved symbols** (cannot be used as inventory values):
- `<Phone>`, `<Flag>`, `<Sigma>`, `<Empty>` — universal FSA references
- `-` (morpheme boundary), `=` (clitic boundary)
- `[BOS]`, `[EOS]` — string boundaries
- `*`, `+`, `?` — Kleene star, plus, optional
- `|`, `(`, `)`, `{`, `}` — union and grouping

**Tira files:**
- `segments.yaml` — consonants (stops, nasals, fricatives, resonants) and vowels (high, mid, low)
- `tones.yaml` — tone diacritics (H `´`, L `` ` ``, F `ˆ`, R `ˇ`) and tone flags (`[TBU]`, `[FLOAT]`)

---

### Patterns

**Directory:** `config/patterns/`
**Python:** `PatternRegistry` / `Pattern` in `src/fst_registry.py`

Named FSA fragments that can be reused inside rules and other patterns. Think of them as regex macros that compile to pynini acceptors.

**Structure:**
```yaml
kind: Patterns
patterns:
  - <human_name>:
      pattern: "<V_Mid>|<V_Low>"   # regex-like string referencing inventory classes or other patterns
      _ref: "<PATTERN_REF>"         # angle-bracket ref for use elsewhere
```

**Key rules:**
- `pattern` is a string (or list of strings unioned together) using inventory `_ref`s, other pattern `_ref`s, literal phones, operators (`*`, `+`, `?`, `|`), and grouping `()`.
- `_ref` must be unique across all Patterns configs and must not collide with Inventory `_ref`s.
- Patterns form a dependency graph. A pattern can reference another pattern defined earlier in the same file or in a different file, but circular references are forbidden. The `PatternRegistry` topologically sorts patterns before compilation.
- The human-readable name key (e.g. `Non-High vowel`) is discarded internally; only `_ref` is used as the identifier.

**Tira files:**
- `phonological_classes.yaml` — `<V_NonHigh>`, `<CorObs>`, `<VelStop>` (base patterns from inventory classes)
- `clusters.yaml` — `<Ng>`, `<CorSeq>`, `<VelCor>` (composite patterns referencing other patterns)

---

### Rules

**Directory:** `config/rules/`
**Python:** `RuleRegistry` / `Rule` in `src/fst_registry.py`

Phonological rules that compile to FSTs via `pynini.cdrewrite`. Three rule kinds, inferred from which keys are present:

#### Simple rule (`input_pattern` + `output_pattern`)
```yaml
rules:
  rule_name:
    description: "human-readable description"
    input_pattern: "<pattern_string>"     # what to match (FSA)
    output_pattern: "<pattern_string>"    # what to replace with (FSA); null = deletion
    left_context: "<pattern_string>"      # optional
    right_context: "<pattern_string>"     # optional
    direction: "ltr"                      # optional: ltr (default), rtl, sim
```
Compiles to `pynini.cdrewrite(cross(input, output), left, right, sigma_star)`.

#### Map rule (`string_map`)
```yaml
rules:
  rule_name:
    string_map:
      - ["input1", "output1"]
      - ["input2", "output2"]
    left_context: "..."    # optional
    right_context: "..."   # optional
```
Each pair becomes a `pynini.cross`, all unioned into a single tau.

#### Rule sequence (`rule_sequence`)
```yaml
rules:
  rule_name:
    rule_sequence: [subrule_a, subrule_b]
```
Composes sub-rules via `sigma_star @ Rule1 @ Rule2 ...`. Sub-rules must be defined in the same or another Rules config. The `RuleRegistry` topologically sorts to ensure dependencies compile first.

**Pattern strings** in rules use the same syntax as Pattern configs — inventory refs, pattern refs, literal phones, and regex operators. `null` as `output_pattern` means deletion. An empty string `""` as `input_pattern` means insertion (epenthesis).

**Tira files:**
- `vowel_coalescence.yaml` — hiatus resolution: V[-high]i > ɛ, V deletion before V, and a composed sequence
- `tone_association.yaml` — TBU insertion after vowels/sonorants, removal from onset/coda consonants

---

### FeatureDefinitions

**Directory:** `config/features/`
**Python:** `FeatureRegistry` (stub in `src/feature_registry.py`)

Enumerates morphological features and their possible values.

**Structure:**
```yaml
kind: FeatureDefinitions
features:
  <feature_name>:
    - value1
    - value2
  <feature_name>: [value1, value2, value3]
```

**Key rules:**
- Feature names must be globally unique across all FeatureDefinitions configs.
- Each part of speech declares which subset of features it uses (in its PartOfSpeech config).
- The values listed here are the universe of possible values; FeatureCombinations configs further constrain which combinations are grammatical.

**Tira file:** `verb_and_adjective.yaml` — defines `class` (11 noun classes), `deixis`, `object`, `subject` (person/number), `tam` (5 TAM values).

---

### FeatureCombinations

**Directory:** `config/features/`
**Python:** `FeatureValueCombinations` in `src/marker_registry.py`

Constrains which feature-value combinations are grammatical. Used by Paradigm configs to determine what slots to build.

**Structure:**
```yaml
kind: FeatureCombinations
features: [feature1, feature2, ...]    # all features this config covers
combinations:
  - feature1: value_or_list_or_star
    feature2: value_or_list_or_star
  - feature1: value
    # feature2 omitted = unmarked
```

**Key rules:**
- Each combination entry is a dict of feature names to values. Values can be:
  - A single string value
  - A list of values `[a, b, c]`
  - `"*"` — wildcard, expands to all values defined in FeatureDefinitions
- Omitted features are assumed unmarked (not applicable for that combination).
- The `FeatureValueCombinations` class expands all wildcards and lists into a flat DataFrame of every licit combination, then deduplicates.

**Tira file:** `verb_feature_combinations.yaml` — infinitives require ð-class; imperatives only take itive/ventive deixis.

---

### FeatureMarkers

**Directory:** `config/markers/`
**Python:** `FeatureMarkers` / `Marker` in `src/marker_registry.py`

Maps each value of a **single** feature to a morphological formative (affix, rule, replacement, or suppletion).

**Structure:**
```yaml
kind: FeatureMarkers
feature: <feature_name>
global_attributes:              # optional — applied to all markers
  order: <stage_name>
markers:
  <value1>:
    suffix: "-string"           # append
    prefix: "string-"           # prepend
    replace: ["in", "out"]      # substring replacement
    rule: "$rule_name"          # phonological rule reference
    order: <stage_name>         # ordering stage (overrides global)
  <value2>: null                # zero-marking (no overt formative)
  <value3>:
    suppletion: "full_form"     # replaces entire stem — incompatible with other keys
```

**Marker operations** (the `Marker` dataclass):
- `suffix` — appends string (must end with boundary `-` or `=` in the string)
- `prefix` — prepends string (must start with boundary `-` or `=` in the string)
- `replace` — `[input_string, output_string]` pair, applied across all contexts
- `rule` — name of a Rules config rule (prefixed with `$`)
- `suppletion` — wholesale stem replacement (cannot combine with anything else)
- `null` — zero morpheme, no change
- Multiple operations can be combined in a single marker (e.g. `prefix` + `suffix`), except `suppletion`.

**Ordered markers:** When a feature value needs multiple sequential operations, use a list:
```yaml
value:
  - suffix: "-te"
    order: suffixation
  - replace: [dt, tt]
    order: assimilation
```
The `order` stage names are resolved against the Paradigm's `order` list.

**Global marker:** A special key `global_marker` applies a formative to all values in the config.

**Inheritance:** `inherits: $other_config` loads another FeatureMarkers config as a base, then individual markers override specific values.

**Tira files:**
- `ipfv_subj_markers.yaml` — imperfective subject prefixes (e.g. `íŋ-<CL>-` for 1sg). Uses `<CL>` placeholder for class prefix slot.
- `ipfv_obj_markers.yaml` — imperfective object suffixes (e.g. `-ŋɛ̂` for 1sg)
- `class_prefixes.yaml` — replaces `[CL]` placeholder with actual class consonant (l, g, r, ð, n, ŋ, ɲ, j, s, t̪)

---

### ContingentFeatureMarkers

**Directory:** `config/markers/`
**Python:** `ContingentMarkers` in `src/marker_registry.py`

Like FeatureMarkers but maps **combinations** of multiple features to a formative. Used when the realization of one feature depends on the value of another.

**Structure:**
```yaml
kind: ContingentFeatureMarkers
features: [feature_a, feature_b]
global_attributes:
  order: <stage_name>
markers:
  <outer_feature>:
    <outer_value>:
      <inner_feature>:
        <inner_value>:
          prefix: "..."
          suffix: "..."
```

The nesting can go in either direction. The `ContingentMarkers` dataclass internally flattens these into a dict keyed by sorted `"feature=value feature=value"` strings for O(1) lookup.

**Inheritance in contingent markers:** Sub-paradigms can be imported with `inherits: $config_name` at any nesting level.

**Tira file:** `ipfv_3person_obj_markers.yaml` — when the object is 3sg, subject person determines both a prefix `[CL]-` and a unique suffix (e.g. 1sg+3sg.obj → suff  415 +| `\|` | Union |                                                                                               
ix `-ɛ́`).

---

### Paradigm

**Directory:** `config/paradigms/`
**Python:** `ParadigmMarkers` in `src/paradigm_registry.py`

The top-level assembly config that combines markers, rules, features, and combinations into a complete inflectional (sub-)paradigm.

**Structure:**
```yaml
kind: Paradigm
part_of_speech: <pos_name>           # must match a PartOfSpeech config
order: [stage1, stage2, stage3, ...] # application order for marker stages

features:
  <feature>: "$marker_config"        # import FeatureMarkers
  <feature>: <literal_value>         # fix to a single value (zero-marked)
  <feature>:                         # inline markers
    value1: null
    value2:
      suffix: "-x"

contingent_features:
  "<feat_a>&<feat_b>": "$contingent_config"  # ampersand-joined feature names as key

feature_combinations: ["$combo_config"]      # list of FeatureCombinations refs

filter:                              # optional: restrict to certain lexemes
  lexical_flag: "<flag_name>"

global_markers:                      # optional: rules/affixes applied to ALL forms
  - rule: "$rule_name"
    order: <stage_name>
```

**Key rules:**
- `order` defines the sequence of stages. Every marker with an `order` attribute must reference a stage listed here. Markers without `order` apply last.
- `features` maps feature names to either:
  - A `$ref` to a FeatureMarkers config
  - A literal string (fixes the paradigm to that value, zero-marked)
  - An inline markers dict
- `contingent_features` maps ampersand-joined feature names (e.g. `"subject&object"`) to a ContingentFeatureMarkers config. Contingent markers take priority over standard markers during lookup.
- `feature_combinations` imports FeatureCombinations configs to constrain which slots are built.
- `global_markers` are marker dicts applied to every form in the paradigm (e.g. tone rules, vowel harmony).
- `filter` restricts which lexical roots the paradigm applies to (using lexical flags from the CSV).
- The `ParadigmMarkers` class iterates all licit feature combinations, looks up markers (contingent first, then standard), sorts by `order`, and stores the result in a hashmap keyed by feature-value strings.

**Tira file:** `ipfv_it.yaml` — imperfective itive sub-paradigm with stages: root_tone → final_vowel → argument_marker → class_prefix → resolve_hiatus → vowel_harmony → tone_processes. Fixes `tam=imperfective`, `deixis=itive`. Imports subject markers as contingent on class, object markers as contingent on subject.

---

### PartOfSpeech

**Directory:** `config/parts_of_speech/`
**Python:** not yet implemented as a registry

Metadata for a part of speech, linking it to a lexicon CSV and declaring which features apply.

**Structure:**
```yaml
kind: PartOfSpeech
name: <pos_name>
features: [feat1, feat2, ...]       # morphological features this POS inflects for
invariant_features: [feat, ...]     # optional: inherent features (e.g. gender on nouns)
lexical_flags: [flag, ...]          # optional: column names in CSV for inflection class info
principal_parts: [stem1, stem2, ...]# optional: alternate stems listed as CSV columns
```

**Key rules:**
- `name` must correspond to a CSV file in `data/lexicon/` (e.g. `verb.yaml` → `verb.csv`).
- `invariant_features` appear in glosses but have no morphological marking.
- `lexical_flags` are CSV columns used by Paradigm `filter` to select lexeme subsets.
- `principal_parts` are CSV columns containing alternate stems that Paradigms can reference.

**Tira file:** `verb.yaml` — features: [tam, deixis, class, subject, object, wh], lexical flag: fv_class.

---

## Cross-reference resolution

Any string value starting with `$` is a cross-file reference. The `Registry._resolve_values()` method:
1. Strips the leading `$`
2. Searches all config subdirectories for `<name>.yaml`
3. Loads and recursively resolves that file's contents
4. Replaces the `$ref` string with the resolved dict

This means a Paradigm config that says `class: "$class_prefixes"` will inline the entire contents of `config/markers/class_prefixes.yaml` at that position.

## Compilation pipeline

```
Inventory configs
    → InventoryRegistry (phones, flags, classes with acceptors)
        → Symbol table (pynini.SymbolTable)

Pattern configs
    → PatternRegistry (topologically sorted)
        → Pattern acceptors (FSAs)

Rule configs
    → RuleRegistry (topologically sorted)
        → Rule transducers (FSTs via cdrewrite)

All three registries
    → FstRegistry (orchestrates compilation)
        → Token map for pattern string parsing
        → Sigma/Phone/Flag universal acceptors

Feature configs
    → FeatureDefinitions + FeatureCombinations

Marker configs
    → FeatureMarkers / ContingentMarkers

Paradigm configs + all of the above
    → ParadigmMarkers (feature combo → ordered marker list)
```

## Pattern string syntax

Used in Pattern `pattern` fields, Rule `input_pattern`/`output_pattern`/`left_context`/`right_context` fields, and anywhere a phonological string is specified.

| Token | Meaning |
|---|---|
| `a`, `b`, `ɛ` | Literal phone (must be in Inventory) |
| `<V>`, `<C>` | Inventory class ref (union of member phones) |
| `<V_NonHigh>` | Pattern ref (defined in Patterns config) |
| `[TBU]`, `[FLOAT]` | Flag ref (internal marker, cleaned on decode) |
| `[BOS]`, `[EOS]` | String boundary markers |
| `<Phone>` | Any phone in inventory |
| `<Flag>` | Any flag in inventory |
| `<Sigma>` | Any symbol (phone, flag, or boundary) |
| `<Empty>` | Epsilon (empty string — for insertion/deletion) |
| `-` | Morpheme boundary |
| `=` | Clitic boundary |
| `*` | Kleene star (0+) |
| `+` | Kleene plus (1+) |
| `?` | Optional (0 or 1) |
| `\|` | Union |
| `(`, `)` | Grouping |

The `FstRegistry.parse_pattern()` method tokenizes these strings and builds pynini acceptors via recursive descent.
