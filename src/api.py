"""
FastAPI backend for parC grammar.
Provides following endpoints:
- `GET /schema/<kind>`: Retrieve the schema for a specific configuration kind.
- `GET /configs/<kind>`: List all configuration files for a specific kind.
- `GET /file/<kind>/<path>`: Read a specific configuration file.
- `PUT /file/<kind>/<path>`: Update a specific configuration file.
"""

import os
import yaml
import dotenv
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from jsonschema import validate, ValidationError
from camel_converter import to_snake

from src.config_utils.schema_validation import load_schema, CONFIG_KINDS
from src.config_utils.config_walker import ConfigWalker
from src.config_utils.watcher import _config_changed, start_watcher
from src.grammar.orchestrator.grammar_orchestrator import Grammar

from src.grammar.registry.lexicon_registry import Lexicon
from src.grammar.registry.paradigm_registry import Paradigm

dotenv.load_dotenv()
_raw = os.environ.get("CONFIG_DIR")
if not _raw:
    raise RuntimeError("CONFIG_DIR env var is not set")
_path = Path(_raw).expanduser()
if not _path.is_absolute():
    from src.constants import PROJECT_ROOT
    _path = Path(PROJECT_ROOT) / _path
CONFIG_DIR = _path.resolve()
if not CONFIG_DIR.is_dir():
    raise RuntimeError(f"CONFIG_DIR is not a valid directory: {CONFIG_DIR}")

start_watcher(str(CONFIG_DIR))

app = FastAPI()

_grammar: Grammar | None = None


def get_grammar() -> Grammar:
    global _grammar
    if _grammar is None or _config_changed.is_set():
        _config_changed.clear()
        _grammar = Grammar(**ConfigWalker(CONFIG_DIR).config_data)
    return _grammar

@app.get("/grammar-health")
def grammar_loaded():
    if get_grammar() is None:
        return {"status": "unloaded"}
    return {"status": "loaded"}


@app.post("/grammar-recompile")
def grammar_recompile():
    _config_changed.set()
    try:
        get_grammar()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to recompile: {e}")
    return {"status": "success"}



@app.get("/grammar-stats")
def grammar_stats():
    try:
        g = get_grammar()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Grammar not loaded: {e}")
    if g is None:
        raise HTTPException(status_code=503, detail="Grammar not loaded")

    fst = g.fst_orchestrator
    inv = fst.inventory_registry
    pat = fst.pattern_registry
    rul = fst.rule_registry
    fm  = g.marker_orchestrator.feature_markers_registry
    cm  = g.marker_orchestrator.contingent_markers_registry
    fd  = g.feature_orchestrator.feature_values_registry
    # TODO: FeatureCombinations, MorphemeSequence and MorphemeSet are buggy
    # so they are commented out for now
    # fc  = g.feature_orchestrator.feature_combinations_registry

    return {
        "inventory": {
            "files":   len(inv.config_objects),
            "phones":  len(inv.phones),
            "tags":    len(inv.flags),
            "classes": len(inv.classes),
        },
        "feature_definitions": {
            "files": len(fd.config_objects),
            "total": len(fd.data),
        },
        # "feature_combinations": {
        #     "files": len(fc.config_objects),
        #     "total": sum(len(c.combinations) for c in fc.data.values()),
        # },
        "patterns": {
            "files": len(pat.config_objects),
            "total": len(pat.data),
        },
        "rules": {
            "files": len(rul.config_objects),
            "total": len(rul.data),
        },
        "feature_markers": {
            "files": len(fm.config_objects),
            "total": len(fm.data),
        },
        "contingent_markers": {
            "files": len(cm.config_objects),
            "total": len(cm.data),
        },
        "paradigms": {
            "files": len(g.paradigm_registry.config_objects),
            "total": len(g.paradigm_registry.data),
        },
        "part_of_speech": {
            "files": len(g.lexicon_registry.config_objects),
            "total": sum(len(lexicon.entries) for lexicon in g.lexicon_registry.data.values()),
        },
        # "morpheme_sets": {
        #     "files": len(g.morpheme_set_registry.config_objects),
        #     "total": len(g.morpheme_set_registry.data),
        # },
        # "morpheme_sequences": {
        #     "files": len(g.morpheme_sequence_registry.config_objects),
        #     "total": len(g.morpheme_sequence_registry.data),
        # },
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}

def _resolve_path(kind: str, ref: str) -> Path:
    if kind not in CONFIG_KINDS:
        raise HTTPException(status_code=400, detail=f"Unknown kind: {kind!r}")
    stem = ref.removeprefix("$")
    resolved = (CONFIG_DIR / to_snake(kind) / stem).with_suffix(".yaml").resolve()
    if not resolved.is_relative_to(CONFIG_DIR):
        raise HTTPException(status_code=400, detail="Path traversal not allowed")
    return resolved


@app.get("/schemas/{kind}")
def get_schema(kind: str):
    if kind not in CONFIG_KINDS:
        raise HTTPException(status_code=404, detail=f"Unknown kind: {kind!r}")
    schema = load_schema(kind)
    if schema is None:
        raise HTTPException(status_code=500, detail=f"Schema file missing for kind: {kind!r}")
    return schema


@app.get("/configs")
def list_configs(kind: str):
    if kind not in CONFIG_KINDS:
        raise HTTPException(status_code=400, detail=f"Unknown kind: {kind!r}")
    kind_dir = CONFIG_DIR / to_snake(kind)
    if not kind_dir.is_dir():
        return []
    return sorted(f"${p.stem}" for p in kind_dir.glob("*.yaml"))


@app.get("/file")
def read_file(kind: str, path: str):
    resolved = _resolve_path(kind, path)
    if not resolved.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path!r}")
    with resolved.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


@app.put("/file")
def write_file(kind: str, path: str, body: dict[str, Any]):
    resolved = _resolve_path(kind, path)
    schema = load_schema(kind)
    if schema is None:
        raise HTTPException(status_code=500, detail=f"Schema missing for kind: {kind!r}")
    try:
        validate(instance=body, schema=schema)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)
    with resolved.open("w", encoding="utf-8") as f:
        yaml.safe_dump(body, f, allow_unicode=True)

class InflectRequest(BaseModel):
    kind: str
    name: str
    stems: list[str]
    features: dict[str, str]

class ParseRequest(BaseModel):
    kind: str
    name: str
    form: str


@app.get("/inflection-meta")
def inflection_meta():
    try:
        g = get_grammar()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Grammar not loaded: {e}")
    if g is None:
        raise HTTPException(status_code=503, detail="Grammar not loaded")

    features_meta = {}
    for feat_name, feat_obj in g.feature_orchestrator.features.items():
        features_meta[feat_name] = feat_obj.to_dict()

    paradigms = []
    for name, p in g.paradigm_registry.data.items():
        paradigms.append({
            "name": name,
            "features": [f.name for f in p.features],
            "lexical_features": [lf.name for lf in p.part_of_speech.lexical_features],
        })

    # sequences = []
    # for name, seq in g.morpheme_sequence_registry.data.items():
    #     stems_list = [item for item in seq.morphemes if type(item) in [Lexicon, Paradigm]]
    #     stem_kinds = [type(stem).__name__ for stem in stems_list]
    #     stem_names = [stem.name for stem in stems_list]
    #     num_stems = len(stems_list)
    #     sequences.append({
    #         "name": name,
    #         "features": [f.name for f in seq.features],
    #         "num_stems": num_stems,
    #         "stem_kinds": stem_kinds,
    #         "stem_names": stem_names,
    #     })

    return {
        "features": features_meta,
        "paradigms": paradigms,
        # "sequences": sequences
    }

@app.get("/roots")
def get_roots(kind: str, name: str):
    """
    Get the roots of a paradigm or lexicon.
    """
    grammar = get_grammar()
    if kind == "paradigm":
        if name not in grammar.paradigm_registry.data:
            raise HTTPException(status_code=404, detail=f"Paradigm '{name}' not found")
        paradigm = grammar.paradigm_registry.data[name]
        return paradigm.lexicon.get_roots() if paradigm.lexicon else []
    elif kind == "lexicon":
        if name not in grammar.lexicon_registry.data:
            raise HTTPException(status_code=404, detail=f"Lexicon '{name}' not found")
        lexicon = grammar.lexicon_registry.data[name]
        return lexicon.get_roots()
    else:
        raise HTTPException(status_code=400, detail="Invalid kind")

@app.get("/lexical-features")
def get_lexical_features(kind: str, name: str, root: str):
    """
    Get the lexical features of a single root in a paradigm or lexicon.
    """
    grammar = get_grammar()
    if kind == "paradigm":
        if name not in grammar.paradigm_registry.data:
            raise HTTPException(status_code=404, detail=f"Paradigm '{name}' not found")
        paradigm = grammar.paradigm_registry.data[name]
        lexicon = paradigm.lexicon
    elif kind == "lexicon":
        if name not in grammar.lexicon_registry.data:
            raise HTTPException(status_code=404, detail=f"Lexicon '{name}' not found")
        lexicon = grammar.lexicon_registry.data[name]
    else:
        raise HTTPException(status_code=400, detail="Invalid kind")
    
    if not lexicon:
        raise HTTPException(status_code=404, detail=f"Lexicon for '{name}' not found")

    return lexicon.get_features_for_root(root)

@app.get("/patterns")
def get_patterns():
    try:
        g = get_grammar()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Grammar not loaded: {e}")
    fst = g.fst_orchestrator
    return [
        {
            "ref": p.ref,
            "value": p.value,
            "test_includes": p.test_includes,
            "test_excludes": p.test_excludes,
        }
        for p in fst.patterns.values()
    ]


@app.get("/rules")
def get_rules():
    try:
        g = get_grammar()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Grammar not loaded: {e}")
    fst = g.fst_orchestrator
    return [
        {
            "name": r.name,
            "kind": r.kind,
            "test_mappings": [list(pair) for pair in r.test_mappings],
        }
        for r in fst.rules.values()
    ]


class TestPatternRequest(BaseModel):
    pattern: str
    test_includes: list[str] = []
    test_excludes: list[str] = []


@app.post("/test-pattern")
def api_test_pattern(req: TestPatternRequest):
    try:
        g = get_grammar()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Grammar not loaded: {e}")
    try:
        result = g.fst_orchestrator.test_pattern(
            req.pattern, req.test_includes, req.test_excludes
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


class TestRuleRequest(BaseModel):
    rule: str
    test_mappings: list[list[str]]


@app.post("/test-rule")
def api_test_rule(req: TestRuleRequest):
    try:
        g = get_grammar()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Grammar not loaded: {e}")
    try:
        result = g.fst_orchestrator.test_rule(
            req.rule, [tuple(pair) for pair in req.test_mappings]
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


class RunYamlTestsRequest(BaseModel):
    kind: str = "all"


@app.post("/run-yaml-tests")
def api_run_yaml_tests(req: RunYamlTestsRequest):
    try:
        g = get_grammar()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Grammar not loaded: {e}")
    if req.kind not in ("patterns", "rules", "all"):
        raise HTTPException(status_code=400, detail="kind must be 'patterns', 'rules', or 'all'")

    fst = g.fst_orchestrator
    pattern_results = []
    rule_results = []

    if req.kind in ("patterns", "all"):
        for p in fst.patterns.values():
            if not p.test_includes and not p.test_excludes:
                continue
            try:
                result = fst.test_pattern(p.value, p.test_includes, p.test_excludes)
                result["ref"] = p.ref
            except Exception as e:
                result = {"ref": p.ref, "results": [], "all_pass": False, "error": str(e)}
            pattern_results.append(result)

    if req.kind in ("rules", "all"):
        for r in fst.rules.values():
            if not r.test_mappings:
                continue
            try:
                result = fst.test_rule(r, list(r.test_mappings))
            except Exception as e:
                result = {"ref": r.name, "results": [], "all_pass": False, "error": str(e)}
            rule_results.append(result)

    all_pass = all(r["all_pass"] for r in pattern_results + rule_results)
    return {"patterns": pattern_results, "rules": rule_results, "all_pass": all_pass}


@app.post("/inflect")
def api_inflect(req: InflectRequest):
    try:
        g = get_grammar()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Grammar not loaded: {e}")
    if g is None:
        raise HTTPException(status_code=503, detail="Grammar not loaded")

    if req.kind == "paradigm":
        if req.name not in g.paradigm_registry.data:
            raise HTTPException(status_code=404, detail=f"Paradigm '{req.name}' not found")
        p = g.paradigm_registry.data[req.name]
        if not req.stems:
            raise HTTPException(status_code=400, detail="Paradigm inflection requires a stem/root")
        stem = req.stems[0]
        try:
            inflected_fst = p.inflect(stem, req.features)
            forms = g.fst_orchestrator.fsm_strings(inflected_fst, strip_all_tags=True)
            stages = p.get_inflection_stages(stem, req.features)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    # TODO: MorphemeSequence is buggy so it is commented out for now
    # elif req.kind == "sequence":
    #     if req.name not in g.morpheme_sequence_registry.data:
    #         raise HTTPException(status_code=404, detail=f"Sequence '{req.name}' not found")
    #     seq = g.morpheme_sequence_registry.data[req.name]
    #     try:
    #         inflected_fst = seq.inflect(req.stems, req.features)
    #         forms = g.fst_orchestrator.fsm_strings(inflected_fst, strip_all_tags=True)
    #         raw_stages = seq.get_inflection_stages(req.stems, req.features)
    #         stages = [{k: v for k, v in stage.items() if k != "fst"} for stage in raw_stages]
    #     except Exception as e:
    #         raise HTTPException(status_code=400, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail="Invalid inflection type")

    return {
        "forms": forms,
        "stages": stages
    }

@app.post("/parse")
def api_parse(req: ParseRequest):
    try:
        g = get_grammar()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Grammar not loaded: {e}")
    if g is None:
        raise HTTPException(status_code=503, detail="Grammar not loaded")

    if req.kind == "paradigm":
        if req.name not in g.paradigm_registry.data:
            raise HTTPException(status_code=404, detail=f"Paradigm '{req.name}' not found")
        p = g.paradigm_registry.data[req.name]
        try:
            parses = p.get_parses(req.form)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    # TODO: MorphemeSequence is buggy so it is commented out for now
    # elif req.kind == "sequence":
    #     if req.name not in g.morpheme_sequence_registry.data:
    #         raise HTTPException(status_code=404, detail=f"Sequence '{req.name}' not found")
    #     seq = g.morpheme_sequence_registry.data[req.name]
    #     try:
    #         parses = seq.get_parses(req.form)
    #     except Exception as e:
    #         raise HTTPException(status_code=400, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail="Invalid parse type")

    return {
        "parses": parses
    }


app.mount("/", StaticFiles(directory="frontend", html=True), name="static")

