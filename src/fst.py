"""
src/fst.py - Config-driven FST compilation for Tira morphological parser.

Functions for loading YAML configs, building inventory registries,
compiling pattern strings, phonological rules, and morphological markers
into pynini FSTs/FSAs.

This module is the foundational layer of the config-driven refactor.
All higher-level config-driven code will depend on it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

import pynini
import yaml
import unicodedata

from src.constants import (
    BOUNDARY_STR,
    CLASS_PLACEHOLDER,
    EOS_STR,
    SYMBOL2DIAC,
    TONE_PLACEHOLDER_STR,
    TONE_SLOT_STR,
    TIRA_SYMBOL_TO_CHAR,
    WORD_BOUNDARY_STR,
)
from src.fst_helpers import (
    delete_fst,
    encode_fst_string,
    fst,
    insert_fst,
    set_symbols,
)
from src.lexicon.phonology import SIGMASTAR

# ---------------------------------------------------------------------------
# Config directory map: kind → subdirectory
# ---------------------------------------------------------------------------

CONFIG_DIR = Path("config")

_KIND_TO_SUBDIR: Dict[str, str] = {
    "Inventory": "inventory",
    "Patterns": "patterns",
    "Rules": "rules",
    "FeatureMarkers": "markers",
    "ContingentFeatureMarkers": "markers",
    "Paradigm": "paradigms",
    "PartsOfSpeech": "parts_of_speech",
    "FeatureDefinition": "features",
    "FeatureCombinations": "features",
}

# ---------------------------------------------------------------------------
# Section 1: Config Loading
# ---------------------------------------------------------------------------


def _find_config_file(name: str) -> Path:
    """Search all config subdirectories for <name>.yaml."""
    for subdir in _KIND_TO_SUBDIR.values():
        candidate = CONFIG_DIR / subdir / f"{name}.yaml"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Config file '{name}.yaml' not found in any config subdirectory."
    )


def resolve_ref(name: str) -> dict:
    """
    Resolve a $name cross-file reference.

    Strips the leading '$', searches all config subdirectories for
    <name>.yaml, and returns the raw (un-resolved) YAML dict.
    """
    if name.startswith("$"):
        name = name[1:]
    path = _find_config_file(name)
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _resolve_values(obj):
    """
    Recursively walk a deserialized YAML structure.
    Any string value starting with '$' is replaced by the fully-resolved
    content of the referenced config file.
    """
    if isinstance(obj, str):
        if obj.startswith("$"):
            ref_dict = resolve_ref(obj)
            return _resolve_values(ref_dict)
        return obj
    elif isinstance(obj, list):
        return [_resolve_values(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: _resolve_values(value) for key, value in obj.items()}
    else:
        return obj


def load_config(path: Union[Path, str]) -> dict:
    """
    Load a YAML config file and recursively resolve all $name references.

    Arguments:
        path: Path to the YAML config file.
    Returns:
        Fully-resolved config dict.
    """
    path = Path(path)
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return _resolve_values(raw)


# ---------------------------------------------------------------------------
# Section 2: Inventory Registry
# ---------------------------------------------------------------------------

# Special symbol strings used in pattern/rule contexts
_BOS_STR = "[BOS]"
_EOS_STR = "[EOS]"
_SIGMA_STR = "<Sigma>"
_EMPTY_STR = "<Empty>"


def _build_registry_from_node(node: dict, registry: Dict[str, pynini.Fst]) -> pynini.Fst:
    """
    Recursively walk an inventory data node.

    Returns an FSA that is the union of all phones/flags in this subtree,
    and registers any intermediate/top-level reprs encountered.
    """
    phones = node.get("phones", [])
    flags = node.get("flags", [])
    repr_str = node.get("repr", None)

    # Build the FSA for all phones/flags at this node
    parts: List[pynini.Fst] = []
    for phone in phones:
        parts.append(fst(phone))
    for flag in flags:
        # flags may have bracket notation like "[TBU]" — encode them
        # TODO Validate flag string meets expected format
        parts.append(fst(flag))

    # Recurse into child nodes (skip  keys)
    skip_keys = {"repr", "phones", "flags"}
    for key, value in node.items():
        if key in skip_keys:
            continue
        if isinstance(value, dict):
            child_fsa = _build_registry_from_node(value, registry)
            parts.append(child_fsa)

    if not parts:
        node_fsa = fst("")
    elif len(parts) == 1:
        node_fsa = parts[0]
    else:
        node_fsa = pynini.union(*parts).optimize()

    if repr_str is not None:
        registry[repr_str] = node_fsa

    return node_fsa


def build_inventory_registry(config: dict) -> Dict[str, pynini.Fst]:
    """
    Build a registry mapping repr strings (e.g. '<V>', '<C>') to FSAs.

    Walks the nested data tree of an Inventory config, unions all
    phones/flags beneath each node with a 'repr' key.

    Also adds:
      - '[BOS]'    → pynini BOS acceptor
      - '[EOS]'    → pynini EOS acceptor
      - '<Sigma>'  → SIGMASTAR
      - '<Empty>'  → fst('')
      - '-'        → boundary symbol FSA
      - '<TBU>'    → tone-bearing unit FSA
      - '<FLOAT>'  → floating tone FSA
      - '<CL>'     → class placeholder FSA

    Arguments:
        config: Fully-resolved Inventory config dict.
    Returns:
        registry: dict mapping repr strings to FSAs.
    """
    registry: Dict[str, pynini.Fst] = {}

    data = config.get("data", {})
    for key, value in data.items():
        if isinstance(value, dict):
            _build_registry_from_node(value, registry)

    # Special symbols
    # [BOS] and [EOS] are pynini's byte-level anchoring tokens; use pynini.accep directly
    registry[_BOS_STR] = pynini.accep("[BOS]")
    registry[_EOS_STR] = pynini.accep("[EOS]")
    registry[_SIGMA_STR] = SIGMASTAR
    registry[_EMPTY_STR] = fst("")
    registry[BOUNDARY_STR] = fst(BOUNDARY_STR)
    registry[TONE_SLOT_STR] = fst(TONE_SLOT_STR)
    registry[TONE_PLACEHOLDER_STR] = fst(TONE_PLACEHOLDER_STR)
    registry[CLASS_PLACEHOLDER] = fst(CLASS_PLACEHOLDER)

    return registry


# ---------------------------------------------------------------------------
# Section 3: Pattern String Compiler
# ---------------------------------------------------------------------------

# Regex for tokenizing pattern strings.
# Order matters: longest matches first.
_TOKEN_RE = re.compile(
    r"""
    (?P<special>  \[BOS\] | \[EOS\]   )  |   # BOS/EOS special tokens
    (?P<ref>      <[^>]+>              )  |   # <X> registry references
    (?P<op>       [*+?|]              )  |   # operators
    (?P<paren>    [()]                )  |   # grouping
    (?P<literal>  .                   )       # any other character (Unicode)
    """,
    re.VERBOSE | re.DOTALL,
)

def _tokenize_pattern(pattern_str: str) -> List[Tuple[str, str]]:
    """
    Tokenize a pattern string into typed tokens.

    Returns a list of (token_type, token_value) pairs where token_type is
    one of: 'ref', 'special', 'op', 'paren', 'literal'.

    Multi-character IPA tokens (dental stops) are kept together because
    they are handled as single symbols by the fst() factory.
    """
    tokens = []
    i = 0
    text = pattern_str
    # Encode to find multichar tokens (handles dental bridges etc.)
    # We work on the raw string but use fst() for actual FSA construction.
    while i < len(text):
        # Try special multi-char symbols first
        matched = False
        for tok_type, tok_re in [
            ("special", re.compile(r"\[BOS\]|\[EOS\]")),
            ("ref", re.compile(r"<[^>]+>")),
        ]:  
            m = tok_re.match(text, i)
            if m:
                tokens.append((tok_type, m.group()))
                i = m.end()
                matched = True
                break

        if matched:
            continue

        ch = text[i]
        if ch in "*+?|":
            tokens.append(("op", ch))
            i += 1
        elif ch in "()":
            tokens.append(("paren", ch))
            i += 1
        else:
            # Possibly a multi-byte Unicode character or dental bridge combo
            # Collect combining characters that follow
            j = i + 1
            while j < len(text) and unicodedata.combining(text[j]):
                j += 1
            literal = text[i:j]
            tokens.append(("literal", literal))
            i = j

    return tokens


class _PatternParser:
    """
    Recursive descent parser for pattern strings.

    Grammar:
        expr   ::= term ('|' term)*
        factor ::= atom ('*' | '+' | '?')?
        term   ::= factor+
        atom   ::= ref | special | literal | '(' expr ')'
    """

    def __init__(self, tokens: List[Tuple[str, str]], registry: Dict[str, pynini.Fst]):
        self._tokens = tokens
        self._pos = 0
        self._registry = registry

    def _peek(self) -> Optional[Tuple[str, str]]:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _consume(self) -> Tuple[str, str]:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def parse_expr(self) -> pynini.Fst:
        """expr ::= term ('|' term)*"""
        left = self._parse_term()
        while self._peek() == ("op", "|"):
            self._consume()
            right = self._parse_term()
            left = pynini.union(left, right).optimize()
        return left

    def _parse_term(self) -> pynini.Fst:
        """term ::= factor+"""
        # A term must have at least one factor
        result = self._parse_factor()
        while True:
            tok = self._peek()
            if tok is None:
                break
            if tok == ("paren", ")"):
                break
            if tok == ("op", "|"):
                break
            next_factor = self._parse_factor()
            result = pynini.concat(result, next_factor)
        return result

    def _parse_factor(self) -> pynini.Fst:
        """factor ::= atom ('*' | '+' | '?')?"""
        atom = self._parse_atom()
        tok = self._peek()
        if tok is not None and tok[0] == "op" and tok[1] in "*+?":
            self._consume()
            if tok[1] == "*":
                atom = pynini.closure(atom).optimize()
            elif tok[1] == "+":
                atom = pynini.closure(atom, 1).optimize()
            elif tok[1] == "?":
                atom = pynini.union(fst(""), atom).optimize()
        return atom

    def _parse_atom(self) -> pynini.Fst:
        """atom ::= ref | special | literal | '(' expr ')'"""
        tok = self._peek()
        if tok is None:
            raise ValueError("Unexpected end of pattern string")

        tok_type, tok_val = tok

        if tok_type == "paren" and tok_val == "(":
            self._consume()  # consume '('
            inner = self.parse_expr()
            closing = self._peek()
            if closing != ("paren", ")"):
                raise ValueError(f"Expected ')' but got {closing}")
            self._consume()  # consume ')'
            return inner

        elif tok_type == "ref":
            self._consume()
            if tok_val not in self._registry:
                raise KeyError(f"Pattern ref '{tok_val}' not found in registry")
            return self._registry[tok_val]

        elif tok_type == "special":
            self._consume()
            if tok_val == "[BOS]":
                # pynini byte-level BOS anchor
                return pynini.accep("[BOS]")
            elif tok_val == "[EOS]":
                # pynini byte-level EOS anchor
                return pynini.accep("[EOS]")
            else:
                raise ValueError(f"Unknown special token: {tok_val}")

        elif tok_type == "literal":
            self._consume()
            return fst(tok_val)

        else:
            raise ValueError(f"Unexpected token type: {tok}")


def compile_pattern_str(pattern_str: str, registry: Dict[str, pynini.Fst]) -> pynini.Fst:
    """
    Compile a pattern string (e.g. "(<V>|<R>|<N>)" or "<V>-?") to a pynini FSA.

    Arguments:
        pattern_str: Pattern string using registry refs and standard regex ops.
        registry:    Dict mapping repr strings to FSAs.
    Returns:
        FSA accepting the language described by pattern_str.
    """
    if pattern_str == "":
        return fst("")
    tokens = _tokenize_pattern(pattern_str)
    parser = _PatternParser(tokens, registry)
    result = parser.parse_expr()
    if parser._pos != len(tokens):
        remaining = tokens[parser._pos:]
        raise ValueError(f"Unexpected tokens at end of pattern: {remaining}")
    return result.optimize()


def compile_patterns(config: dict, registry: Dict[str, pynini.Fst]) -> Dict[str, pynini.Fst]:
    """
    Compile all patterns from a Patterns config into the registry.

    Iterates over the 'patterns' list, compiles each 'pattern' string
    using the current registry, and registers the result under its 'repr'.

    Arguments:
        config:   Fully-resolved Patterns config dict.
        registry: Existing registry (will be extended in-place and returned).
    Returns:
        Extended registry.
    """
    patterns_list = config.get("patterns", [])
    for entry in patterns_list:
        # Each entry is either {name: {pattern: ..., repr: ...}} or flat
        if isinstance(entry, dict):
            for _name, spec in entry.items():
                if not isinstance(spec, dict):
                    continue
                pattern_str = spec.get("pattern", "")
                repr_str = spec.get("repr", None)
                if repr_str is None:
                    continue
                fsa = compile_pattern_str(pattern_str, registry)
                registry[repr_str] = fsa
    return registry


# ---------------------------------------------------------------------------
# Section 4: Rule Compiler
# ---------------------------------------------------------------------------


def _compile_simple_rule(
    rule_dict: dict,
    registry: Dict[str, pynini.Fst],
) -> pynini.Fst:
    """Compile a simple_rule (cdrewrite-based) to an FST."""
    input_pattern = rule_dict.get("input_pattern", "")
    output_pattern = rule_dict.get("output_pattern", "")
    left_context = rule_dict.get("left_context", "")
    right_context = rule_dict.get("right_context", "")
    direction = rule_dict.get("direction", "ltr")
    sigma_str = rule_dict.get("sigma_star", None)

    input_fsa = compile_pattern_str(input_pattern, registry)
    output_fsa = compile_pattern_str(output_pattern, registry)

    # Build transducer tau
    if input_pattern == "" and output_pattern != "":
        tau = insert_fst(output_fsa)
    elif input_pattern != "" and output_pattern == "":
        tau = delete_fst(input_fsa)
    else:
        tau = pynini.cross(input_fsa, output_fsa)

    l_fsa = compile_pattern_str(left_context, registry) if left_context else fst("")
    r_fsa = compile_pattern_str(right_context, registry) if right_context else fst("")

    if sigma_str:
        sigma = compile_pattern_str(sigma_str, registry)
        sigma = pynini.closure(sigma).optimize()
    else:
        sigma = SIGMASTAR

    result = pynini.cdrewrite(tau, l_fsa, r_fsa, sigma, direction=direction)
    return result.optimize()


def _compile_map_rule(
    rule_dict: dict,
    registry: Dict[str, pynini.Fst],
) -> pynini.Fst:
    """Compile a map_rule (union of string mappings, wrapped in cdrewrite)."""
    string_map = rule_dict.get("string_map", [])
    left_context = rule_dict.get("left_context", "")
    right_context = rule_dict.get("right_context", "")
    direction = rule_dict.get("direction", "ltr")

    if not string_map:
        raise ValueError("map_rule must have a non-empty string_map")

    tau_parts = []
    for pair in string_map:
        src, tgt = pair
        src_fsa = compile_pattern_str(str(src), registry)
        tgt_fsa = compile_pattern_str(str(tgt), registry)
        tau_parts.append(pynini.cross(src_fsa, tgt_fsa))

    tau = pynini.union(*tau_parts).optimize()

    l_fsa = compile_pattern_str(left_context, registry) if left_context else fst("")
    r_fsa = compile_pattern_str(right_context, registry) if right_context else fst("")

    result = pynini.cdrewrite(tau, l_fsa, r_fsa, SIGMASTAR, direction=direction)
    return result.optimize()


def compile_rule(
    name: str,
    rule_dict: dict,
    all_rules: dict,
    registry: Dict[str, pynini.Fst],
    compiled_cache: Optional[Dict[str, pynini.Fst]] = None,
) -> pynini.Fst:
    """
    Compile a single rule to an FST.

    Dispatches on rule type detected from keys present in rule_dict:
      - 'rule_sequence' → chain_of_rules (composition)
      - 'string_map'    → map_rule
      - otherwise       → simple_rule (cdrewrite)

    Arguments:
        name:           Rule name (for cycle detection and caching).
        rule_dict:      Raw rule specification dict.
        all_rules:      Dict of all rules in the config (for chain lookups).
        registry:       FSA registry for pattern compilation.
        compiled_cache: Optional mutable cache to avoid recompilation.
    Returns:
        Compiled FST for this rule.
    """
    if compiled_cache is None:
        compiled_cache = {}

    if name in compiled_cache:
        return compiled_cache[name]

    if "rule_sequence" in rule_dict:
        # chain_of_rules: compose rules in sequence
        sequence = rule_dict["rule_sequence"]
        composed: Optional[pynini.Fst] = None
        for rule_name in sequence:
            if rule_name not in all_rules:
                raise KeyError(f"Rule '{rule_name}' not found in rules config")
            sub_rule = compile_rule(
                rule_name, all_rules[rule_name], all_rules, registry, compiled_cache
            )
            if composed is None:
                composed = sub_rule
            else:
                composed = pynini.compose(composed, sub_rule).optimize()
        result = composed if composed is not None else SIGMASTAR.copy()

    elif "string_map" in rule_dict:
        result = _compile_map_rule(rule_dict, registry)

    else:
        result = _compile_simple_rule(rule_dict, registry)

    compiled_cache[name] = result
    return result


def compile_rules(
    config: dict,
    registry: Dict[str, pynini.Fst],
) -> Dict[str, pynini.Fst]:
    """
    Compile all rules from a Rules config.

    Arguments:
        config:   Fully-resolved Rules config dict.
        registry: FSA registry for pattern compilation.
    Returns:
        Dict mapping rule name to compiled FST.
    """
    rules_spec = config.get("rules", {})
    compiled: Dict[str, pynini.Fst] = {}

    for name in rules_spec:
        compile_rule(name, rules_spec[name], rules_spec, registry, compiled)

    return compiled


# ---------------------------------------------------------------------------
# Section 5: Marker Compiler
# ---------------------------------------------------------------------------

from src.forms.form_helpers import prefix as _prefix_fst, suffix as _suffix_fst


def compile_marker_dict(
    marker_dict: Optional[dict],
    registry: Dict[str, pynini.Fst],
    rules: Dict[str, pynini.Fst],
) -> pynini.Fst:
    """
    Compile a single marker dict (or None for zero-marking) to an FST.

    Supported keys:
      - null / None  → identity transducer (SIGMASTAR)
      - prefix       → prepend prefix string to stem
      - suffix       → append suffix string to stem
      - replace      → [src, tgt] cross-rewrite via cdrewrite
      - rule         → named rule from rules dict (or '$name' ref)
      - suppletion   → maps any stem to the suppletive form

    If multiple ops are present (except suppletion), they are composed.

    Arguments:
        marker_dict: Marker specification dict, or None for zero-marking.
        registry:    FSA registry (not currently used, for future extension).
        rules:       Compiled rules dict.
    Returns:
        FST implementing the marker operation.
    """
    if marker_dict is None:
        # Zero marking: identity transducer
        return SIGMASTAR.copy()

    parts: List[pynini.Fst] = []

    # Handle suppletion first (incompatible with other ops)
    if "suppletion" in marker_dict:
        suppletive_form = marker_dict["suppletion"]
        # Maps any input to the suppletive form
        suppletive_fsa = fst(suppletive_form)
        result = pynini.compose(
            pynini.cross(SIGMASTAR, SIGMASTAR),
            fst("", suppletive_form)
        )
        # Simpler: accept anything, output suppletive form
        # This is: epsilon → suppletive_form composed with SIGMASTAR on input
        result = insert_fst(suppletive_fsa) @ SIGMASTAR
        return result.optimize()

    if "prefix" in marker_dict:
        prefix_str = marker_dict["prefix"]
        parts.append(_prefix_fst(prefix_str))

    if "suffix" in marker_dict:
        suffix_str = marker_dict["suffix"]
        parts.append(_suffix_fst(suffix_str))

    if "replace" in marker_dict:
        src, tgt = marker_dict["replace"]
        src_fsa = fst(str(src))
        tgt_fsa = fst(str(tgt))
        tau = pynini.cross(src_fsa, tgt_fsa)
        replace_rule = pynini.cdrewrite(tau, fst(""), fst(""), SIGMASTAR).optimize()
        parts.append(replace_rule)

    if "rule" in marker_dict:
        rule_ref = marker_dict["rule"]
        if rule_ref.startswith("$"):
            rule_ref = rule_ref[1:]
        if rule_ref not in rules:
            raise KeyError(f"Rule '{rule_ref}' not found in compiled rules dict")
        parts.append(rules[rule_ref])

    if not parts:
        # No operation specified, treat as identity
        return SIGMASTAR.copy()

    if len(parts) == 1:
        return parts[0].optimize()

    # Compose all parts in sequence
    result = parts[0]
    for part in parts[1:]:
        result = pynini.compose(result, part).optimize()
    return result


def compile_feature_markers(
    config: dict,
    registry: Dict[str, pynini.Fst],
    rules: Dict[str, pynini.Fst],
) -> Dict[str, List[pynini.Fst]]:
    """
    Compile a FeatureMarkers config into a dict of feature value → [FST, ...].

    Arguments:
        config:   Fully-resolved FeatureMarkers config dict.
        registry: FSA registry.
        rules:    Compiled rules dict.
    Returns:
        Dict mapping feature value string to list of compiled FSTs.
    """
    global_attributes = config.get("global_attributes", {})
    markers_spec = config.get("markers", {})

    result: Dict[str, List[pynini.Fst]] = {}

    for feature_value, marker_val in markers_spec.items():
        fsts: List[pynini.Fst] = []

        if marker_val is None:
            # Zero-marking
            fsts.append(compile_marker_dict(None, registry, rules))

        elif isinstance(marker_val, dict):
            # Merge global_attributes (individual marker wins on conflict)
            merged = {**global_attributes, **marker_val}
            fsts.append(compile_marker_dict(merged, registry, rules))

        elif isinstance(marker_val, list):
            # List of marker dicts applied in sequence
            for item in marker_val:
                if item is None:
                    fsts.append(compile_marker_dict(None, registry, rules))
                elif isinstance(item, dict):
                    merged = {**global_attributes, **item}
                    fsts.append(compile_marker_dict(merged, registry, rules))
                else:
                    raise ValueError(f"Unexpected marker item type: {type(item)}")
        else:
            raise ValueError(
                f"Unexpected marker value type for '{feature_value}': {type(marker_val)}"
            )

        result[str(feature_value)] = fsts

    return result


def compile_contingent_markers(
    config: dict,
    registry: Dict[str, pynini.Fst],
    rules: Dict[str, pynini.Fst],
) -> dict:
    """
    Compile a ContingentFeatureMarkers config into a nested dict.

    The nesting structure mirrors the 'markers' structure in the config:
    the outermost key is a feature name, the next level is feature values,
    and the leaves are dicts mapping the secondary feature values to FST lists.

    Arguments:
        config:   Fully-resolved ContingentFeatureMarkers config dict.
        registry: FSA registry.
        rules:    Compiled rules dict.
    Returns:
        Nested dict: {outer_feature: {outer_value: {inner_value: [FST, ...]}}}
    """
    markers_spec = config.get("markers", {})
    result = {}

    def _compile_nested(node: dict) -> dict:
        """Recursively compile nested marker specs."""
        out = {}
        for key, value in node.items():
            if isinstance(value, dict):
                # Check if this is a leaf marker dict (has marker keys)
                marker_keys = {"prefix", "suffix", "replace", "rule", "suppletion"}
                if marker_keys.intersection(value.keys()) or not value:
                    # Leaf: compile as marker dict
                    out[str(key)] = [compile_marker_dict(value or None, registry, rules)]
                else:
                    # Intermediate: recurse
                    out[str(key)] = _compile_nested(value)
            elif value is None:
                out[str(key)] = [compile_marker_dict(None, registry, rules)]
            elif isinstance(value, list):
                fsts = []
                for item in value:
                    fsts.append(compile_marker_dict(item if item else None, registry, rules))
                out[str(key)] = fsts
            else:
                out[str(key)] = value
        return out

    for feature_name, feature_spec in markers_spec.items():
        result[feature_name] = _compile_nested(feature_spec)

    return result


# ---------------------------------------------------------------------------
# Section 6: Decoding
# ---------------------------------------------------------------------------

# Symbols to strip from decoded strings
_STRIP_SYMBOLS = {TONE_SLOT_STR, TONE_PLACEHOLDER_STR, CLASS_PLACEHOLDER, EOS_STR}


def decode_fst_string(encoded_str: str) -> str:
    """
    Decode an FST output string to human-readable IPA.

    Reverses the encoding applied by encode_fst_string():
    - Collapses space-separated char encoding back to a string
    - Replaces tone symbols (<H>, <L>, <HL>, <LH>) with Unicode diacritics
    - Removes flag symbols (<TBU>, <FLOAT>, <CL>, <ENDOFSENTENCE>)
    - Replaces '|' word boundary with a space

    Arguments:
        encoded_str: Space-separated encoded FST output string.
    Returns:
        Human-readable IPA string.
    """
    # The encoded string uses spaces between characters and multichar tokens
    # in angle-brackets or special forms. We need to collapse it back.
    # Strategy: split on spaces, then join, then replace multichar symbols.

    # First handle if input is already decoded (no spaces)
    parts = encoded_str.split(" ")
    # Re-join parts: each part is either a single char or a multichar symbol
    raw = "".join(parts)

    # Replace tone symbols with diacritics
    for symbol, diac in SYMBOL2DIAC.items():
        raw = raw.replace(symbol, diac)

    # Replace word boundary with space
    raw = raw.replace(WORD_BOUNDARY_STR, " ")

    # Strip flag/placeholder symbols
    for sym in _STRIP_SYMBOLS:
        raw = raw.replace(sym, "")

    return raw
