"""
Functional FST compilation for Rules and Markers.

Caches:
  rule FSTs   → YAML_DIR/.cache/rules.far   (rules + inv + feat dirs)
  marker FSTs → in-memory only              (cleared on source changes)
"""

from __future__ import annotations

import hashlib
import os

import pynini
import pywrapfst
from loguru import logger

from src.fst_utils import ReservedSymbolMixin as R
from src.launcher import YAML_DIR
from src.yaml_utils.models import (
    Marker,
    Rule,
    SimpleRule,
    StringMapRule,
    RuleSequence,
    SingleStringMarker,
    StringTupleMarker,
    UnorderedMarker,
    StringMapMarker,
)
from src.yaml_utils.schema_validation import CONFIG_KIND_TO_PARDIR
from src.yaml_utils.yaml_server import get_rules, is_cache_valid
from src.grammar.acceptor_compilation import fsa, word_fsa, get_sigma_star, get_symbol_table

"""
## Cache paths
"""

CACHE_DIR = os.path.join(YAML_DIR, ".cache")
RULES_FAR_PATH = os.path.join(CACHE_DIR, "rules.far")


def _kind_dir(kind: str) -> str:
    return os.path.join(YAML_DIR, CONFIG_KIND_TO_PARDIR[kind], kind)


INVENTORY_DIR = _kind_dir("Inventory")
FEATURES_DIR = _kind_dir("FeatureDefinitions")
RULES_DIR = _kind_dir("Rules")

"""
## Module-level cache state
"""

_rule_fsts: dict[str, pynini.Fst] | None = None
_marker_fsts: dict[str, pynini.Fst] | None = None

"""
## Cache invalidation
"""


def invalidate_rule_fsts() -> None:
    global _rule_fsts
    _rule_fsts = None


def invalidate_marker_fsts() -> None:
    global _marker_fsts
    _marker_fsts = None


def invalidate_all() -> None:
    invalidate_rule_fsts()
    invalidate_marker_fsts()

"""
## Helpers
"""


def _cache_key(obj) -> str:
    return hashlib.sha256(repr(obj).encode()).hexdigest()[:16]


def _save_far(fsts: dict[str, pynini.Fst], path: str) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    writer = pywrapfst.FarWriter.create(path)
    for key, fst in sorted(fsts.items()):
        writer[key] = fst
    del writer


def _load_far(path: str) -> dict[str, pynini.Fst] | None:
    if not os.path.exists(path):
        return None
    try:
        reader = pywrapfst.FarReader.open(path)
        result: dict[str, pynini.Fst] = {}
        while not reader.done():
            result[reader.get_key()] = reader.get_fst().copy()
            reader.next()
        return result
    except Exception:
        logger.warning(f"Failed to load FAR from {path}, will recompile.")
        return None

"""
## Rule compilation
"""


def _compile_simple_rule(rule: SimpleRule) -> pynini.Fst:
    sigma_star = get_sigma_star()
    tau = pynini.cross(fsa(rule.input_pattern), fsa(rule.output_pattern)).optimize()
    l = fsa(rule.left_context) if rule.left_context else ""
    r = fsa(rule.right_context) if rule.right_context else ""
    return pynini.cdrewrite(tau, l, r, sigma_star)


def _compile_string_map_rule(rule: StringMapRule) -> pynini.Fst:
    sigma_star = get_sigma_star()
    tau = pynini.union(
        *[pynini.cross(fsa(i), fsa(o)) for i, o in rule.string_map]
    ).optimize()
    l = fsa(rule.left_context) if rule.left_context else ""
    r = fsa(rule.right_context) if rule.right_context else ""
    return pynini.cdrewrite(tau, l, r, sigma_star)


def compile_rule(rule: Rule) -> pynini.Fst | list[pynini.Fst]:
    if isinstance(rule, SimpleRule):
        return _compile_simple_rule(rule)
    if isinstance(rule, StringMapRule):
        return _compile_string_map_rule(rule)
    if isinstance(rule, RuleSequence):
        rules = get_rules()
        result: list[pynini.Fst] = []
        for name in rule.rules:
            sub_fst = compile_rule(rules[name])
            if isinstance(sub_fst, list):
                result.extend(sub_fst)
            else:
                result.append(sub_fst)
        return result
    raise ValueError(f"Unknown rule type: {type(rule)!r}")

"""
## Marker compilation
"""


def _compile_prefix(value: str) -> pynini.Fst:
    sigma_star = get_sigma_star()
    syms = get_symbol_table()
    bow = pynini.accep(R.bow, token_type=syms)
    tau = pynini.cross(bow, pynini.concat(bow, fsa(value)))
    return pynini.cdrewrite(tau, "", "", sigma_star)


def _compile_suffix(value: str) -> pynini.Fst:
    sigma_star = get_sigma_star()
    syms = get_symbol_table()
    eow = pynini.accep(R.eow, token_type=syms)
    tau = pynini.cross(eow, pynini.concat(fsa(value), eow))
    return pynini.cdrewrite(tau, "", "", sigma_star)


def _compile_string_map(string_map: tuple[tuple[str, str], ...]) -> pynini.Fst:
    # word-level substitution: cross(word_fsa(root), word_fsa(pp)) per entry
    return pynini.union(
        *[pynini.cross(word_fsa(i), word_fsa(o)) for i, o in string_map]
    ).optimize()


def compile_marker(marker: Marker) -> pynini.Fst:
    if isinstance(marker, SingleStringMarker):
        if marker.operation == "prefix":
            return _compile_prefix(marker.value)
        if marker.operation == "suffix":
            return _compile_suffix(marker.value)
        if marker.operation == "suppletion":
            sigma_star = get_sigma_star()
            tau = pynini.cross(sigma_star, fsa(marker.value))
            return pynini.cdrewrite(tau, "", "", sigma_star)
        if marker.operation == "rule":
            rules = get_rules()
            if marker.value not in rules:
                raise KeyError(f"Rule '{marker.value}' not found")
            result = compile_rule(rules[marker.value])
            if isinstance(result, list):
                composed = result[0]
                for f in result[1:]:
                    composed = pynini.compose(composed, f)
                return composed
            return result
    if isinstance(marker, StringTupleMarker) and marker.operation == "replace":
        sigma_star = get_sigma_star()
        tau = pynini.cross(fsa(marker.value[0]), fsa(marker.value[1]))
        return pynini.cdrewrite(tau, "", "", sigma_star)
    if isinstance(marker, StringMapMarker) and marker.operation == "string_map":
        return _compile_string_map(marker.value)
    if isinstance(marker, UnorderedMarker) and marker.operation == "principal_part":
        raise ValueError(
            "UnorderedMarker(principal_part) must be resolved to StringMapMarker "
            "via get_markers_for_paradigm before compilation"
        )
    raise ValueError(f"Unknown marker: {marker!r}")

"""
## Caching entry points
"""


def _warm_rule_cache() -> None:
    global _rule_fsts
    if is_cache_valid(RULES_FAR_PATH, RULES_DIR, INVENTORY_DIR, FEATURES_DIR):
        loaded = _load_far(RULES_FAR_PATH)
        if loaded is not None:
            _rule_fsts = loaded
            return
    rules = get_rules()
    compiled: dict[str, pynini.Fst] = {}
    for name, rule in rules.items():
        if isinstance(rule, RuleSequence):
            continue  # assembled at runtime
        key = _cache_key(rule)
        try:
            compiled[key] = compile_rule(rule)
        except Exception as e:
            logger.warning(f"Failed to compile rule '{name}': {e}")
    _save_far(compiled, RULES_FAR_PATH)
    _rule_fsts = compiled


def get_rule_fst(rule_name: str) -> pynini.Fst | list[pynini.Fst]:
    global _rule_fsts
    rules = get_rules()
    if rule_name not in rules:
        raise KeyError(f"Rule '{rule_name}' not found")
    rule = rules[rule_name]

    if isinstance(rule, RuleSequence):
        return [get_rule_fst(name) for name in rule.rules]

    if _rule_fsts is None:
        _warm_rule_cache()

    key = _cache_key(rule)
    if key not in _rule_fsts:
        _rule_fsts[key] = compile_rule(rule)
    return _rule_fsts[key]


def get_marker_fst(marker: Marker) -> pynini.Fst:
    global _marker_fsts
    if _marker_fsts is None:
        _marker_fsts = {}
    key = _cache_key(marker)
    if key not in _marker_fsts:
        _marker_fsts[key] = compile_marker(marker)
    return _marker_fsts[key]
