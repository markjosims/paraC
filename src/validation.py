"""
Functions for validating form input for editor pages.
"""

import streamlit as st
from typing import Any, Callable, Literal

from src.grammar.orchestrator.fst_orchestrator import Rule
from src.fst_utils import Acceptor

ErrorCallback = Callable[[str], None]


def validate_file_reference_str(val: str) -> str:
    """Ensure string starts with $ prefix if not empty."""
    if val and not val.startswith("$"):
        return f"${val}"
    return val


def validate_pattern(add_error: ErrorCallback, value: str, label: str = "Pattern") -> str:
    """
    Validate that a string is a valid FST acceptor pattern.
    Adds an error through the callback if invalid.
    Returns the original string.
    """
    grammar = st.session_state.get("grammar")
    if grammar:
        try:
            grammar.fst_orchestrator.acceptor(value)
        except Exception as e:
            add_error(f"Invalid {label} '{value}': {str(e)}")
    return value


def validate_no_reserved_symbols(
    add_error: ErrorCallback, value: str, label: str = "Item"
) -> str:
    """Check if value is a reserved symbol."""
    from src.fst_utils import ReservedSymbolMixin

    if value in ReservedSymbolMixin.reserved_symbols:
        add_error(f"{label} '{value}' is a reserved symbol and cannot be used.")
    return value


def validate_inventory_item(
    add_error: ErrorCallback,
    value: str,
    item_type: Literal["phone", "flag"],
    label: str = "Item",
) -> str:
    """Validate phone/flag formatting and reserved symbols."""
    validate_no_reserved_symbols(add_error, value, label)
    if item_type == "flag":
        if not value.startswith("[") or not value.endswith("]"):
            add_error(
                f"Flag {label} '{value}' must start with '[' and end with ']'"
            )
    elif item_type == "phone":
        if any(c in value for c in "[]<>"):
            add_error(
                f"Phone {label} '{value}' cannot contain '[', ']', '<', or '>'"
            )
    return value


def validate_items_str(
    add_error: ErrorCallback,
    value: str,
    item_type: Literal["phone", "flag"],
    label: str = "Items",
) -> list[str]:
    """Validate a comma-separated list of inventory items."""
    raw_items = [s.strip() for s in value.split(",") if s.strip()]
    validated_items = []
    for v in raw_items:
        validated = validate_inventory_item(add_error, v, item_type, label)
        if validated:
            validated_items.append(validated)
    return validated_items


def validate_ref_str(add_error: ErrorCallback, value: str, label: str = "Class") -> str:
    """Validate string indicating a _ref (for an inventory item or pattern)"""
    validate_no_reserved_symbols(add_error, value, label)
    if not value.startswith("<") or not value.endswith(">"):
        add_error(f"Class {label} '{value}' must start with '<' and end with '>'")
    return value


def validate_acceptor(
    add_error: ErrorCallback, value: str, label: str = "Pattern"
) -> Acceptor:
    """
    Validate that a string is a valid FST acceptor pattern.
    Adds an error through the callback if invalid.
    Returns an Acceptor object.
    """
    value = validate_pattern(add_error, value, label)
    return Acceptor(value)


def validate_rule(add_error: ErrorCallback, rule: Rule) -> Rule:
    """
    Validate and compile a Rule object.
    Adds an error through the callback if compilation fails.
    Returns the Rule object.
    """
    grammar = st.session_state.get("grammar")
    if grammar:
        try:
            # Compile FST for the rule
            grammar.fst_orchestrator.compile_rule(rule)
        except Exception as e:
            add_error(f"Rule '{rule._ref}' compilation failed: {str(e)}")
    return rule


def validate_feature_name(
    add_error: ErrorCallback, name: str, uid: str, id_map: dict[str, Any]
) -> None:
    """Check for empty or duplicate feature names."""
    name = name.strip()
    if not name:
        add_error("Feature name cannot be empty.")
        return

    for other_uid, other_feat in id_map.items():
        # Use hasattr to survive module reloads
        if other_uid != uid and hasattr(other_feat, "name") and other_feat.name == name:
            add_error(f"Duplicate feature name: '{name}'")
            return


def validate_feature_values(
    add_error: ErrorCallback, values_str: str, feat_name: str
) -> None:
    """Check for empty values list."""
    if not values_str.strip():
        add_error(f"Feature '{feat_name}' must have at least one value.")
