from __future__ import annotations

import copy
import uuid
from typing import Any

import yaml

from src.web.editor_base import BaseEditor
from src.registry.grammar_registry import GrammarRegistry


class RulesEditor(BaseEditor):
    kind = "Rules"
    dir_name = "rules"
    collection_key = "rules"

    def load_state(self, config_dir: str, relative_path: str) -> dict[str, Any]:
        path = self.safe_path(config_dir, relative_path)
        if path is None or not path.exists():
            raise FileNotFoundError(relative_path)

        with path.open("r", encoding="utf-8") as handle:
            document = yaml.safe_load(handle) or {}

        if document.get("kind") != "Rules":
            raise ValueError(f"{relative_path} is not a Rules config")

        return {
            "path": relative_path,
            "kind": "Rules",
            "rules": _rules_from_document(document.get("rules", {})),
        }

    def to_yaml(self, state: dict[str, Any]) -> str:
        document = {
            "kind": "Rules",
            "rules": _document_rules(state.get("rules", [])),
        }
        return yaml.safe_dump(document, sort_keys=False, allow_unicode=True)

    def _blank_item(self) -> dict[str, Any]:
        return {
            "id": uuid.uuid4().hex,
            "name": "",
            "rule_type": "simple_rule",
            "description": "",
            "input_pattern": "",
            "output_pattern": "",
            "string_map_text": "",
            "rule_sequence_text": "",
            "left_context": "",
            "right_context": "",
            "direction": "",
            "sigma_star": "",
            "test_mappings_text": "",
            "test_results": None,
        }

    def _run_test(self, item: dict[str, Any], registry: GrammarRegistry) -> dict:
        fst_reg = registry.fst_registry
        name = item.get("name", "").strip()
        mappings = _split_pairs(item.get("test_mappings_text", ""))
        return fst_reg.test_rule(name, mappings)

    def _update_items_from_form(
        self, rules: list[dict[str, Any]], form: Any
    ) -> list[dict[str, Any]]:
        updated: list[dict[str, Any]] = []
        for rule in rules:
            rule_id = rule["id"]
            current = copy.deepcopy(rule)
            for attr in (
                "name",
                "rule_type",
                "description",
                "input_pattern",
                "output_pattern",
                "string_map_text",
                "rule_sequence_text",
                "left_context",
                "right_context",
                "direction",
                "sigma_star",
                "test_mappings_text",
            ):
                current[attr] = form.get(
                    f"{attr}-{rule_id}", current.get(attr, "")
                ).strip()
            updated.append(current)
        return updated


def _rules_from_document(document_rules: dict[str, Any]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for name, value in document_rules.items():
        if not isinstance(value, dict):
            continue
        rule: dict[str, Any] = {
            "id": uuid.uuid4().hex,
            "name": str(name),
            "rule_type": "simple_rule",
            "description": str(value.get("description", "") or ""),
            "input_pattern": "",
            "output_pattern": "",
            "string_map_text": "",
            "rule_sequence_text": "",
            "left_context": str(value.get("left_context", "") or ""),
            "right_context": str(value.get("right_context", "") or ""),
            "direction": str(value.get("direction", "") or ""),
            "sigma_star": str(value.get("sigma_star", "") or ""),
            "test_mappings_text": "\n".join(
                f"{source} => {target}"
                for source, target in value.get("test_mappings", [])
            ),
        }

        if "string_map" in value:
            rule["rule_type"] = "string_map"
            rule["string_map_text"] = "\n".join(
                f"{source} => {target}"
                for source, target in value.get("string_map", [])
            )
        elif "rule_sequence" in value:
            rule["rule_type"] = "rule_sequence"
            rule["rule_sequence_text"] = "\n".join(
                str(item) for item in value.get("rule_sequence", [])
            )
        else:
            rule["input_pattern"] = _serialize_nullable(value.get("input_pattern", ""))
            rule["output_pattern"] = _serialize_nullable(
                value.get("output_pattern", "")
            )

        rules.append(rule)
    return rules


def _document_rules(rules: list[dict[str, Any]]) -> dict[str, Any]:
    document_rules: dict[str, Any] = {}
    for rule in rules:
        name = rule.get("name", "").strip()
        if not name:
            continue

        entry: dict[str, Any] = {}
        description = rule.get("description", "").strip()
        if description:
            entry["description"] = description

        rule_type = rule.get("rule_type", "simple_rule")
        if rule_type == "string_map":
            string_map = _split_pairs(rule.get("string_map_text", ""))
            if string_map:
                entry["string_map"] = string_map
        elif rule_type == "rule_sequence":
            rule_sequence = _split_lines(rule.get("rule_sequence_text", ""))
            entry["rule_sequence"] = rule_sequence
        else:
            entry["input_pattern"] = _coerce_nullable_pattern(
                rule.get("input_pattern", "")
            )
            entry["output_pattern"] = _coerce_nullable_pattern(
                rule.get("output_pattern", "")
            )

        for attr in ("left_context", "right_context", "direction", "sigma_star"):
            value = rule.get(attr, "").strip()
            if value:
                entry[attr] = value

        test_mappings = _split_pairs(rule.get("test_mappings_text", ""))
        if test_mappings:
            entry["test_mappings"] = test_mappings

        document_rules[name] = entry
    return document_rules


def _split_pairs(value: str) -> list[list[str]]:
    pairs: list[list[str]] = []
    for line in _split_lines(value):
        if "=>" in line:
            source, target = line.split("=>", 1)
        elif "," in line:
            source, target = line.split(",", 1)
        else:
            continue
        pairs.append([source.strip(), target.strip()])
    return pairs


def _split_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _serialize_nullable(value: Any) -> str:
    if value is None:
        return "null"
    return str(value)


def _coerce_nullable_pattern(value: str) -> Any:
    stripped = value.strip()
    if stripped.lower() == "null":
        return None
    return stripped
