# Spanish Config Plan

Plan for populating `config/spanish/` with the phonemic inventory, orthographic spelling rules, and verb conjugation paradigms of standard (Peninsular) Spanish. All symbols use **orthography**, not IPA.

---

## 1. Inventory (`inventory/`)

### `segments.yaml`

Spanish orthographic segments. Each letter/digraph that appears in verb stems or endings is an atomic symbol. All digraphs — ch, ll, rr, qu, gu, gü — are multi-character atomic symbols. The tokenizer's longest-match strategy handles ambiguity (e.g., `gu` in *pague* matches the digraph before matching `g` + `u` separately).

```yaml
kind: Inventory
data:
  consonants:
    _ref: "<C>"
    stops:
      _ref: "<Stop>"
      voiceless:
        _ref: "<P>"
        _phones: [p, t, c, k, qu]  # c=[k] before a/o/u, qu=[k] before e/i; k in loanwords
      voiced:
        _ref: "<B>"
        _phones: [b, d, g, gu]     # gu=[g] before e/i
    fricatives:
      _ref: "<Fric>"
      _phones: [f, s, z, j, h, x, v]  # j/g=[x], z=[θ/s], h=silent, v=[b]
    affricates:
      _ref: "<Affr>"
      _phones: [ch]
    nasals:
      _ref: "<N>"
      _phones: [m, n, ñ]
    liquids:
      _ref: "<Liq>"
      _phones: [l, ll, r, rr]
    glides:
      _ref: "<Glide>"
      _phones: [y, w]              # w in loanwords only
    labiovelar:
      _ref: "<Labvel>"
      _phones: [gü]               # gü=[gw] before e/i
  vowels:
    _ref: "<V>"
    plain:
      _ref: "<V_Plain>"
      _phones: [a, e, i, o, u]
    accented:
      _ref: "<V_Acc>"
      _phones: [á, é, í, ó, ú]
    diaeresis:
      _ref: "<V_Diaer>"
      _phones: [ü]
```

**Notes:**
- All digraphs (`ch`, `ll`, `rr`, `qu`, `gu`, `gü`) are atomic multi-char symbols. The tokenizer's longest-match logic ensures `gu` matches before `g`+`u`.
- `c` and `qu` are both voiceless stops since they both represent /k/ in complementary environments. Spelling rules handle the alternation.
- `g` and `gu` are both voiced stops — same logic.
- `v` is under fricatives since it patterns as a consonant orthographically, even though it's phonemically identical to `b`.
- `gü` gets its own `<Labvel>` subclass since it represents a labiovelar [gw] distinct from plain `gu` [g].

---

## 2. Patterns (`patterns/`)

### `vowel_classes.yaml`

Natural classes used in spelling rules and suffix conditioning.

```yaml
kind: Patterns
patterns:
  - Front vowel:
      pattern: "(e|i|é|í)"
      _ref: "<V_Front>"
  - Back vowel:
      pattern: "(a|o|u|á|ó|ú)"
      _ref: "<V_Back>"
  - Theme vowel:
      pattern: "(a|e|i)"
      _ref: "<ThemeV>"
  - Any vowel or accented vowel:
      pattern: "(<V_Plain>|<V_Acc>|ü)"
      _ref: "<V_Any>"
```

### `stem_final.yaml` (optional)

Patterns for stem-final consonant contexts relevant to spelling changes.

```yaml
kind: Patterns
patterns:
  - Stem-final velar spelling:
      pattern: "(c|g)"          # triggers qu/gu before front V
      _ref: "<StemVelar>"
```

---

## 3. Rules (`rules/`)

### `spelling_changes.yaml`

Orthographic adjustments at morpheme boundaries. These are the regular Spanish spelling change rules that apply when a stem-final consonant meets a suffix-initial vowel.

| Stem ends in | Before back V (a/o/u) | Before front V (e/i) | Example |
|---|---|---|---|
| **c** (=[k]) | c | qu | sacar → saqué |
| **g** (=[g]) | g | gu | pagar → pagué |
| **gu** (=[gw]) | gu | gü | averiguar → averigüé |
| **z** (=[θ/s]) | z | c | cazar → cacé |
| **g** (=[x]) | j | g | coger → cojo |
| **gu** (=[g]) | g | gu | seguir → sigo |
| **c** (=[θ/s]) | z | c | vencer → venzo |

These are modeled as cdrewrite rules. Since `c` and `g` are ambiguous (each represents two phonemes), conflicting rules are split into separate files dispatched by the `spelling_class` lexical flag via paradigm `filter`.

### `spelling_velar.yaml` — verbs with stem-final velar stop

Applied to verbs with `spelling_class: c_velar` (e.g., *sacar*) or `g_velar` (e.g., *pagar*).

```yaml
kind: Rules
rules:
  # c=[k] → qu before front vowels (sacar → saqué)
  c_to_qu:
    description: "stem-final c (velar) becomes qu before front vowel"
    input_pattern: "c-?"
    output_pattern: "qu"
    right_context: "<V_Front>"

  # g=[g] → gu before front vowels (pagar → pagué)
  g_to_gu:
    description: "stem-final g (velar) becomes gu before front vowel"
    input_pattern: "g-?"
    output_pattern: "gu"
    right_context: "<V_Front>"
```

### `spelling_sibilant.yaml` — verbs with stem-final sibilant/interdental

Applied to verbs with `spelling_class: z_sibilant` (e.g., *cazar*) or `c_sibilant` (e.g., *vencer*).

```yaml
kind: Rules
rules:
  # z=[θ/s] → c before front vowels (cazar → cacé)
  z_to_c:
    description: "stem-final z becomes c before front vowel"
    input_pattern: "z-?"
    output_pattern: "c"
    right_context: "<V_Front>"

  # c=[θ/s] → z before back vowels (vencer → venzo)
  c_to_z:
    description: "stem-final c (sibilant) becomes z before back vowel"
    input_pattern: "c-?"
    output_pattern: "z"
    right_context: "<V_Back>"
```

### `spelling_fricative_g.yaml` — verbs with stem-final fricative g

Applied to verbs with `spelling_class: g_fricative` (e.g., *coger*).

```yaml
kind: Rules
rules:
  # g=[x] → j before back vowels (coger → cojo)
  g_to_j:
    description: "stem-final g (fricative) becomes j before back vowel"
    input_pattern: "g-?"
    output_pattern: "j"
    right_context: "<V_Back>"
```

### `spelling_labiovelar.yaml` — verbs with stem-final labiovelar gu

Applied to verbs with `spelling_class: gu_labiovelar` (e.g., *averiguar*).

```yaml
kind: Rules
rules:
  # gu=[gw] → gü before front vowels (averiguar → averigüé)
  gu_to_gue:
    description: "stem-final gu (labiovelar) becomes gü before front vowel"
    input_pattern: "gu-?"
    output_pattern: "gü"
    right_context: "<V_Front>"
```

### Dispatch via paradigm `filter`

Each spelling rule file is referenced by a paradigm variant that filters on the `spelling_class` lexical flag. Regular verbs get no spelling rule. For example, a present indicative paradigm for c-velar verbs:

```yaml
# paradigms/present_ind_c_velar.yaml
kind: Paradigm
part_of_speech: verb
order: [suffixation, spelling_change]
filter:
  lexical_flag: c_velar
# ... same features/contingents as present_ind.yaml ...
global_markers:
  - rule: "$c_to_qu"
    order: spelling_change
```

### `accent_rules.yaml` (optional, phase 2)

Accent mark placement. Spanish accent marks follow predictable rules (stress on penultimate syllable for words ending in vowel/n/s, else final; accent mark when stress deviates). For verb forms, accent marks are baked into the suffixes (e.g., `-é`, `-ó`, `-áis`), so explicit accent rules may not be needed for regular verbs. If needed later for compounds or enclitics (e.g., *dígame*), they can be added here.

### `unstressed_i_rules.yaml` (optional, phase 2)

Rules for unstressed `i` between vowels becoming `y`:
- leer → leyó, leyeron (not *leió)
- oír → oyó, oyeron

---

## 4. Features (`features/`)

### `verb_features.yaml`

```yaml
kind: FeatureDefinitions
features:
  tense_mood:
    - present_ind
    - preterite
    - imperfect_ind
    - future
    - conditional
    - present_subj
    - imperfect_subj_ra
    - imperfect_subj_se
    - imperative
    - infinitive
    - gerund
    - past_participle
  person_number:
    - 1sg
    - 2sg
    - 3sg
    - 1pl
    - 2pl
    - 3pl
  conjugation_class: [ar, er, ir]
```

### `verb_feature_combinations.yaml`

Constrains which feature combinations are grammatical.

```yaml
kind: FeatureCombinations
features: [tense_mood, person_number, conjugation_class]
combinations:
  # Non-finite forms: no person/number
  - tense_mood: infinitive
    conjugation_class: "*"
  - tense_mood: gerund
    conjugation_class: "*"
  - tense_mood: past_participle
    conjugation_class: "*"

  # Imperative: limited person forms
  # (tú, usted, nosotros, vosotros, ustedes — no 1sg)
  - tense_mood: imperative
    person_number: [2sg, 3sg, 1pl, 2pl, 3pl]
    conjugation_class: "*"

  # All other tenses: full person paradigm
  - tense_mood: [present_ind, preterite, imperfect_ind, future, conditional, present_subj, imperfect_subj_ra, imperfect_subj_se]
    person_number: "*"
    conjugation_class: "*"
```

---

## 5. Parts of Speech (`parts_of_speech/`)

### `verb.yaml`

```yaml
kind: PartOfSpeech
name: verb
features: [tense_mood, person_number, conjugation_class]
invariant_features: []
lexical_flags: [spelling_class]
principal_parts: []
```

`spelling_class` flag values: `regular`, `c_velar`, `c_sibilant`, `g_velar`, `g_fricative`, `gu_labiovelar`, `z_sibilant`, etc. This drives which spelling-change rules apply.

---

## 6. Markers (`markers/`)

Each tense gets its own set of suffix markers, contingent on conjugation class and person/number. There are two structural patterns:

### Pattern A: Tenses where conjugation class matters (most tenses)

Use **ContingentFeatureMarkers** keyed by `conjugation_class × person_number`.

### Pattern B: Tenses where conjugation class is irrelevant (future, conditional)

Use plain **FeatureMarkers** keyed by `person_number` only, since future/conditional suffixes attach to the full infinitive and are identical across all three classes.

### File list

Where -er and -ir share identical endings, a single marker file covers both classes (referenced by both the -er and -ir paradigms). The filename makes the shared scope clear.

| File | Kind | Feature(s) | Notes |
|---|---|---|---|
| `present_ind_ar_suffixes.yaml` | FeatureMarkers | person_number | -o/-as/-a/-amos/-áis/-an |
| `present_ind_er_suffixes.yaml` | FeatureMarkers | person_number | -o/-es/-e/-emos/-éis/-en |
| `present_ind_ir_suffixes.yaml` | FeatureMarkers | person_number | -o/-es/-e/-imos/-ís/-en |
| `preterite_ar_suffixes.yaml` | FeatureMarkers | person_number | -é/-aste/-ó/-amos/-asteis/-aron |
| `preterite_er_ir_suffixes.yaml` | FeatureMarkers | person_number | -í/-iste/-ió/-imos/-isteis/-ieron |
| `imperfect_ind_ar_suffixes.yaml` | FeatureMarkers | person_number | -aba/-abas/-aba/-ábamos/-abais/-aban |
| `imperfect_ind_er_ir_suffixes.yaml` | FeatureMarkers | person_number | -ía/-ías/-ía/-íamos/-íais/-ían |
| `future_suffixes.yaml` | FeatureMarkers | person_number | -é/-ás/-á/-emos/-éis/-án (all classes) |
| `conditional_suffixes.yaml` | FeatureMarkers | person_number | -ía/-ías/-ía/-íamos/-íais/-ían (all classes) |
| `present_subj_ar_suffixes.yaml` | FeatureMarkers | person_number | -e/-es/-e/-emos/-éis/-en |
| `present_subj_er_ir_suffixes.yaml` | FeatureMarkers | person_number | -a/-as/-a/-amos/-áis/-an |
| `imperfect_subj_ra_ar_suffixes.yaml` | FeatureMarkers | person_number | -ara/-aras/-ara/-áramos/-arais/-aran |
| `imperfect_subj_ra_er_ir_suffixes.yaml` | FeatureMarkers | person_number | -iera/-ieras/-iera/-iéramos/-ierais/-ieran |
| `imperfect_subj_se_ar_suffixes.yaml` | FeatureMarkers | person_number | -ase/-ases/-ase/-ásemos/-aseis/-asen |
| `imperfect_subj_se_er_ir_suffixes.yaml` | FeatureMarkers | person_number | -iese/-ieses/-iese/-iésemos/-ieseis/-iesen |
| `imperative_ar_suffixes.yaml` | FeatureMarkers | person_number | -a/-e/-emos/-ad/-en |
| `imperative_er_suffixes.yaml` | FeatureMarkers | person_number | -e/-a/-amos/-ed/-an |
| `imperative_ir_suffixes.yaml` | FeatureMarkers | person_number | -e/-a/-amos/-id/-an |
| `nonfinite_suffixes.yaml` | ContingentFeatureMarkers | conjugation_class × tense_mood | -ar/-er/-ir, -ando/-iendo, -ado/-ido |
| `infinitive_stem.yaml` | FeatureMarkers | conjugation_class | -ar/-er/-ir (global marker for future/conditional) |

### Example: `present_ind_ar_suffixes.yaml`

Since er/ir merger eliminates the need for ContingentFeatureMarkers in most tenses, each marker file is a plain FeatureMarkers config keyed by person_number. The paradigm references the right file per conjugation class.

```yaml
kind: FeatureMarkers
feature: person_number
global_order: suffixation
markers:
  1sg:
    suffix: "-o"
  2sg:
    suffix: "-as"
  3sg:
    suffix: "-a"
  1pl:
    suffix: "-amos"
  2pl:
    suffix: "-áis"
  3pl:
    suffix: "-an"
```

### Example: `preterite_er_ir_suffixes.yaml`

Shared by both -er and -ir paradigms (identical endings):

```yaml
kind: FeatureMarkers
feature: person_number
global_order: suffixation
markers:
  1sg:
    suffix: "-í"
  2sg:
    suffix: "-iste"
  3sg:
    suffix: "-ió"
  1pl:
    suffix: "-imos"
  2pl:
    suffix: "-isteis"
  3pl:
    suffix: "-ieron"
```

### Example: `infinitive_stem.yaml`

Global marker used by future and conditional paradigms. Maps conjugation_class to a suffix that reconstructs the infinitive from the bare stem, applied at the `infinitive_stem` stage before person/number suffixation.

```yaml
kind: FeatureMarkers
feature: conjugation_class
global_order: infinitive_stem
markers:
  ar:
    suffix: "-ar"
  er:
    suffix: "-er"
  ir:
    suffix: "-ir"
```

### Example: `future_suffixes.yaml`

These attach after the infinitive stem (hablar+é, comer+é, vivir+é), so no class contingency.

```yaml
kind: FeatureMarkers
feature: person_number
global_order: suffixation
markers:
  1sg:
    suffix: "-é"
  2sg:
    suffix: "-ás"
  3sg:
    suffix: "-á"
  1pl:
    suffix: "-emos"
  2pl:
    suffix: "-éis"
  3pl:
    suffix: "-án"
```

---

## 7. Paradigms (`paradigms/`)

One paradigm config per tense/mood **per conjugation class**. Each paradigm fixes both `tense_mood` and `conjugation_class` and references the appropriate marker file. This means duplicate paradigm files for -er and -ir when they share a marker file, but each paradigm is self-contained and the duplication is trivial (only the `conjugation_class` value and marker `$ref` differ).

### File list

| File | Fixes | Stages |
|---|---|---|
| `present_ind_ar.yaml` | present_ind + ar | suffixation |
| `present_ind_er.yaml` | present_ind + er | suffixation |
| `present_ind_ir.yaml` | present_ind + ir | suffixation |
| `preterite_ar.yaml` | preterite + ar | suffixation |
| `preterite_er.yaml` | preterite + er | suffixation |
| `preterite_ir.yaml` | preterite + ir | suffixation |
| `imperfect_ind_ar.yaml` | imperfect_ind + ar | suffixation |
| `imperfect_ind_er.yaml` | imperfect_ind + er | suffixation |
| `imperfect_ind_ir.yaml` | imperfect_ind + ir | suffixation |
| `future_ar.yaml` | future + ar | infinitive_stem → suffixation |
| `future_er.yaml` | future + er | infinitive_stem → suffixation |
| `future_ir.yaml` | future + ir | infinitive_stem → suffixation |
| `conditional_ar.yaml` | conditional + ar | infinitive_stem → suffixation |
| `conditional_er.yaml` | conditional + er | infinitive_stem → suffixation |
| `conditional_ir.yaml` | conditional + ir | infinitive_stem → suffixation |
| `present_subj_ar.yaml` | present_subj + ar | suffixation |
| `present_subj_er.yaml` | present_subj + er | suffixation |
| `present_subj_ir.yaml` | present_subj + ir | suffixation |
| `imperfect_subj_ra_ar.yaml` | imperfect_subj_ra + ar | suffixation |
| `imperfect_subj_ra_er.yaml` | imperfect_subj_ra + er | suffixation |
| `imperfect_subj_ra_ir.yaml` | imperfect_subj_ra + ir | suffixation |
| `imperfect_subj_se_ar.yaml` | imperfect_subj_se + ar | suffixation |
| `imperfect_subj_se_er.yaml` | imperfect_subj_se + er | suffixation |
| `imperfect_subj_se_ir.yaml` | imperfect_subj_se + ir | suffixation |
| `imperative_ar.yaml` | imperative + ar | suffixation |
| `imperative_er.yaml` | imperative + er | suffixation |
| `imperative_ir.yaml` | imperative + ir | suffixation |
| `nonfinite.yaml` | infinitive/gerund/past_participle | suffixation |

Spelling-change variants duplicate the relevant paradigm with an added `filter` and `spelling_change` stage (see rules section).

### Example: `present_ind_ar.yaml`

```yaml
kind: Paradigm
part_of_speech: verb
order: [suffixation]
features:
  tense_mood: present_ind
  conjugation_class: ar
  person_number: "$present_ind_ar_suffixes"
feature_combinations: ["$verb_feature_combinations"]
```

### Example: `preterite_er.yaml` and `preterite_ir.yaml`

Both reference the same shared marker file. The only difference is the fixed `conjugation_class` value:

```yaml
# preterite_er.yaml
kind: Paradigm
part_of_speech: verb
order: [suffixation]
features:
  tense_mood: preterite
  conjugation_class: er
  person_number: "$preterite_er_ir_suffixes"
feature_combinations: ["$verb_feature_combinations"]
```

```yaml
# preterite_ir.yaml
kind: Paradigm
part_of_speech: verb
order: [suffixation]
features:
  tense_mood: preterite
  conjugation_class: ir
  person_number: "$preterite_er_ir_suffixes"
feature_combinations: ["$verb_feature_combinations"]
```

### Example: `future_ar.yaml`

Uses the `infinitive_stem` global marker to reconstruct the infinitive before suffixation:

```yaml
kind: Paradigm
part_of_speech: verb
order: [infinitive_stem, suffixation]
features:
  tense_mood: future
  conjugation_class: "$infinitive_stem"   # maps ar→suffix "-ar", applied at infinitive_stem stage
  person_number: "$future_suffixes"
feature_combinations: ["$verb_feature_combinations"]
```

The `$infinitive_stem` FeatureMarkers config maps `conjugation_class` values to suffixes (`-ar`, `-er`, `-ir`) at the `infinitive_stem` stage, reconstructing the infinitive from the bare stem before the person/number suffix is applied.

---

## 8. Lexicon (`data/lexicon/`)

### `verb.csv`

```csv
root,gloss,conjugation_class,spelling_class
habl,speak,ar,regular
com,eat,er,regular
viv,live,ir,regular
sac,take_out,ar,c_velar
caz,hunt,ar,z_sibilant
pag,pay,ar,g_velar
cog,catch,er,g_fricative
venc,conquer,er,c_sibilant
```

**Stem convention:** Bare stem without theme vowel (habl-, com-, viv-). The conjugation class tells the system which suffix set to use, and suffixes include the theme vowel.

For future/conditional, a `principal_parts` column could supply the infinitive stem (hablar, comer, vivir), or a global marker could derive it from root + class.

---

## Implementation Order

### Phase 1: Core infrastructure
1. `inventory/segments.yaml` — orthographic inventory
2. `patterns/vowel_classes.yaml` — front/back vowel classes
3. `features/verb_features.yaml` — feature definitions
4. `features/verb_feature_combinations.yaml` — valid combinations
5. `parts_of_speech/verb.yaml` — POS metadata

### Phase 2: Regular present indicative (proof of concept)
6. `markers/present_ind_ar_suffixes.yaml` — -ar present indicative suffixes
7. `markers/present_ind_er_suffixes.yaml` — -er present indicative suffixes
8. `markers/present_ind_ir_suffixes.yaml` — -ir present indicative suffixes
9. `paradigms/present_ind_ar.yaml`, `present_ind_er.yaml`, `present_ind_ir.yaml`
10. Test: habl+present_ind+1sg → hablo, com+present_ind+1sg → como, viv+present_ind+1pl → vivimos

### Phase 3: Remaining tenses
11. `markers/preterite_ar_suffixes.yaml`, `preterite_er_ir_suffixes.yaml`
12. `markers/imperfect_ind_ar_suffixes.yaml`, `imperfect_ind_er_ir_suffixes.yaml`
13. `markers/infinitive_stem.yaml`, `future_suffixes.yaml`, `conditional_suffixes.yaml`
14. `markers/present_subj_ar_suffixes.yaml`, `present_subj_er_ir_suffixes.yaml`
15. `markers/imperfect_subj_ra_ar_suffixes.yaml`, `imperfect_subj_ra_er_ir_suffixes.yaml`
16. `markers/imperfect_subj_se_ar_suffixes.yaml`, `imperfect_subj_se_er_ir_suffixes.yaml`
17. `markers/imperative_ar_suffixes.yaml`, `imperative_er_suffixes.yaml`, `imperative_ir_suffixes.yaml`
18. `markers/nonfinite_suffixes.yaml`
19. Corresponding paradigm configs for each tense × class

### Phase 4: Spelling changes
20. `rules/spelling_velar.yaml`, `spelling_sibilant.yaml`, `spelling_fricative_g.yaml`, `spelling_labiovelar.yaml`
21. Spelling-change paradigm variants (e.g., `present_ind_ar_c_velar.yaml`) with `filter` + `spelling_change` stage
22. Test with spelling-change verbs (sacar→saqué, pagar→pagué, cazar→cacé, coger→cojo, etc.)

### Phase 5: Extensions (optional)
22. Accent placement rules for enclitics
23. Unstressed i→y rules
24. Stem-changing verbs (e→ie, o→ue, e→i) via lexical flags + rules
25. Irregular verb handling

---

## Design Decisions (resolved)

1. **Multi-char symbols:** All digraphs (`ch`, `ll`, `rr`, `qu`, `gu`, `gü`) are **atomic multi-char symbols**. The tokenizer's longest-match strategy handles ambiguity.

2. **Infinitive-stem tenses:** Future/conditional use a **global marker** (`$infinitive_stem`) that maps conjugation_class → suffix `-ar`/`-er`/`-ir` at the `infinitive_stem` stage.

3. **Spelling class granularity:** **Single `spelling_class` lexical flag** with enumerated values (`regular`, `c_velar`, `c_sibilant`, `g_velar`, `g_fricative`, `gu_labiovelar`, `z_sibilant`). Paradigm `filter` dispatches the right spelling rules.

4. **er/ir merger:** Marker files are **shared where endings are identical** (e.g., `preterite_er_ir_suffixes.yaml`). Paradigm files remain **separate per class** (duplicate but self-contained).

5. **Voseo:** Deferred to phase 5 as a dialect extension.
