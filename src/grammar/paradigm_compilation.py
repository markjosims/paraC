"""
Paradigm inflect / parse / fuzzy-search graph compilation.

Caches:
  inflect + parse + search FSTs → YAML_DIR/.cache/paradigms.far
  Invalidated when any of Paradigm, FeatureMarkers, ContingentFeatureMarkers,
  Inventory, FeatureDefinitions, or Rules dirs change.
"""

from __future__ import annotations

import itertools
import os

import pynini
import pywrapfst
from loguru import logger
from pynini.lib import pynutil

from src.fst_utils import ReservedSymbolMixin as R
from src.launcher import YAML_DIR
from src.lexicon import get_roots
from src.yaml_utils.schema_validation import CONFIG_KIND_TO_PARDIR
from src.yaml_utils.yaml_server import (
    get_feature_map,
    get_yaml_kind,
    get_yaml_data_safe,
    is_cache_valid,
)
from src.grammar.acceptor_compilation import (
    fsa,
    word_fsa,
    get_sigma_star,
    get_symbol_table,
    get_token_map,
)
from src.grammar.marker_resolution import get_markers_for_paradigm
from src.grammar.transducer_compilation import get_marker_fst

EDIT_BOUND = 5
EDIT_COST = 1.0

"""
## Cache paths
"""

CACHE_DIR = os.path.join(YAML_DIR, ".cache")
PARADIGMS_FAR_PATH = os.path.join(CACHE_DIR, "paradigms.far")


def _kind_dir(kind: str) -> str:
    return os.path.join(YAML_DIR, CONFIG_KIND_TO_PARDIR[kind], kind)


_SOURCE_DIRS = (
    _kind_dir("Paradigm"),
    _kind_dir("FeatureMarkers"),
    _kind_dir("ContingentFeatureMarkers"),
    _kind_dir("Inventory"),
    _kind_dir("FeatureDefinitions"),
    _kind_dir("Rules"),
)

"""
## Module-level cache state
"""

_paradigm_fsts: dict[str, pynini.Fst] | None = None


def invalidate_paradigm_fsts() -> None:
    global _paradigm_fsts
    _paradigm_fsts = None

"""
## FAR I/O
"""


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
        logger.warning(f"Failed to load paradigms FAR from {path}; will recompile.")
        return None

"""
## Helpers
"""


def _feature_combinations(
    paradigm_data: dict,
    feature_map: dict,
) -> tuple[list[set[tuple[str, str]]], list[str], list[str]]:
    """
    Return (combos, marker_files, contingent_files) for a paradigm.
    Each combo is a set of (feature, value) pairs covering all free features
    plus any fixed feature values.
    """
    fixed: dict[str, str] = {}
    marker_files: list[str] = []
    free_feature_names: list[str] = []

    for feature_name, ref in paradigm_data.get("feature_markers", {}).items():
        if ref is None:
            continue
        if isinstance(ref, str) and ref.startswith("$"):
            free_feature_names.append(feature_name)
            marker_files.append(ref)
        else:
            fixed[feature_name] = ref

    contingent_files = list(paradigm_data.get("contingent_markers", []))

    free_value_lists = []
    for fname in free_feature_names:
        if fname not in feature_map:
            logger.warning(f"Feature '{fname}' not in feature map — skipping.")
            continue
        free_value_lists.append([(fname, v) for v in feature_map[fname].values])

    if not free_value_lists:
        combos = [set(fixed.items())]
    else:
        combos = [
            set(fixed.items()) | set(combo_tuples)
            for combo_tuples in itertools.product(*free_value_lists)
        ]
    return combos, marker_files, contingent_files


def _stringify_features(feature_values: set[tuple[str, str]]) -> str:
    return "".join(f"[{f}={v}]" for f, v in sorted(feature_values))


def _apply_markers(stem_fst: pynini.Fst, markers: list) -> pynini.Fst:
    current = stem_fst
    for marker in markers:
        current = pynini.compose(current, get_marker_fst(marker))
    return current

"""
## Graph builders
"""


def build_inflect_graph(paradigm_name: str) -> pynini.Fst:
    """root[features...] → surface form."""
    paradigm_data = get_yaml_data_safe("Paradigm", paradigm_name)
    if paradigm_data is None:
        raise ValueError(f"Paradigm '{paradigm_name}' not found or invalid.")

    part_of_speech = paradigm_data["part_of_speech"]
    feature_map = get_feature_map()
    roots = get_roots(part_of_speech)
    combos, marker_files, contingent_files = _feature_combinations(paradigm_data, feature_map)

    inflect_fsts: list[pynini.Fst] = []
    for root in roots:
        root_fsa = word_fsa(root)
        for feature_values in combos:
            try:
                markers = get_markers_for_paradigm(
                    marker_files, contingent_files, feature_values, paradigm_name
                )
                inflected_output = pynini.project(
                    _apply_markers(root_fsa, markers), project_type="output"
                )
            except Exception as e:
                logger.warning(
                    f"Skipping {paradigm_name} root={root} fv={feature_values}: {e}"
                )
                continue

            feature_str = _stringify_features(feature_values)
            inflect_input = (
                pynini.concat(root_fsa, fsa(feature_str)) if feature_str else root_fsa
            )
            inflect_fsts.append(pynini.cross(inflect_input, inflected_output).optimize())

    if not inflect_fsts:
        return pynini.Fst()
    return pynini.union(*inflect_fsts).optimize()


def build_parse_graph(inflect_graph: pynini.Fst) -> pynini.Fst:
    return pynini.invert(inflect_graph).optimize()


def build_search_graph(inflect_graph: pynini.Fst) -> pynini.Fst:
    """Fuzzy-searchable form lattice via edit transducers."""
    sigma = get_token_map()["dot"][0].fsa
    sigma_star = get_sigma_star()
    syms = get_symbol_table()

    insert_fst = pynutil.insert(
        pynini.accep(R.insert, weight=EDIT_COST / 2, token_type=syms)
    )
    delete_fst = pynini.cross(
        sigma,
        pynini.accep(R.delete, weight=EDIT_COST / 2, token_type=syms),
    )
    substitute_fst = pynini.cross(
        sigma,
        pynini.accep(R.substitute, weight=EDIT_COST / 2, token_type=syms),
    )
    edit_fst = pynini.union(insert_fst, delete_fst, substitute_fst).optimize()

    left_factor = sigma_star.copy()
    for _ in range(EDIT_BOUND):
        left_factor = pynini.concat(
            left_factor, pynini.concat(edit_fst.ques, sigma_star)
        )
    left_factor.optimize()

    right_factor = pynini.invert(left_factor)
    insert_label = syms.find(R.insert)
    delete_label = syms.find(R.delete)
    right_factor = right_factor.relabel_pairs(
        ipairs=[(insert_label, delete_label), (delete_label, insert_label)]
    )

    form_lattice = pynini.project(inflect_graph, project_type="output")
    return pynini.compose(right_factor, form_lattice).optimize()

"""
## Cache warming and public entry points
"""


def _warm_cache() -> None:
    global _paradigm_fsts
    if is_cache_valid(PARADIGMS_FAR_PATH, *_SOURCE_DIRS):
        loaded = _load_far(PARADIGMS_FAR_PATH)
        if loaded is not None:
            _paradigm_fsts = loaded
            return
    fsts: dict[str, pynini.Fst] = {}
    for basename, _ in get_yaml_kind("Paradigm")["valid"]:
        name = basename.removesuffix(".yaml")
        try:
            inflect = build_inflect_graph(name)
            fsts[f"{name}:inflect"] = inflect
            fsts[f"{name}:parse"] = build_parse_graph(inflect)
            fsts[f"{name}:search"] = build_search_graph(inflect)
        except Exception as e:
            logger.warning(f"Failed to build graphs for paradigm '{name}': {e}")
    _save_far(fsts, PARADIGMS_FAR_PATH)
    _paradigm_fsts = fsts


def _ensure_cache() -> None:
    global _paradigm_fsts
    if _paradigm_fsts is None:
        _warm_cache()


def _get_or_build(paradigm_name: str, graph_type: str) -> pynini.Fst:
    _ensure_cache()
    key = f"{paradigm_name}:{graph_type}"
    if key not in _paradigm_fsts:
        inflect = build_inflect_graph(paradigm_name)
        _paradigm_fsts[f"{paradigm_name}:inflect"] = inflect
        _paradigm_fsts[f"{paradigm_name}:parse"] = build_parse_graph(inflect)
        _paradigm_fsts[f"{paradigm_name}:search"] = build_search_graph(inflect)
    return _paradigm_fsts[key]


def get_inflect_graph(paradigm_name: str) -> pynini.Fst:
    return _get_or_build(paradigm_name, "inflect")


def get_parse_graph(paradigm_name: str) -> pynini.Fst:
    return _get_or_build(paradigm_name, "parse")


def get_search_graph(paradigm_name: str) -> pynini.Fst:
    return _get_or_build(paradigm_name, "search")
