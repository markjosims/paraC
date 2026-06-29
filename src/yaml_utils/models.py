from typing import Any, Literal, NamedTuple

class InventoryItemContents(NamedTuple):
    """
    Single inventory item contents (phones and tags)
    """

    phones: tuple[str]
    tags: tuple[str]


# Mapping of <ref> strs to inventory item contents.
InventoryItemMapType = dict[str, InventoryItemContents]


class Inventory(NamedTuple):
    """
    Inventory of all items.
    """

    item_map: InventoryItemMapType
    phones: tuple[str]
    tags: tuple[str]


class Pattern(NamedTuple):
    """
    A regular expression pattern and, optionally, 'include' and 'exclude'
    strings for unit testing.
    """

    pattern: str
    test_includes: tuple[str] | None = None
    test_excludes: tuple[str] | None = None
    name: str | None = None


class SimpleRule(NamedTuple):
    """
    A context-sensitive rewrite rule.
    """

    input_pattern: str
    output_pattern: str
    description: str = ""
    left_context: str = ""
    right_context: str = ""


class StringMapRule(NamedTuple):
    """
    A rule for mapping strings.
    """

    string_map: tuple[tuple[str, str], ...]
    description: str = ""
    left_context: str = ""
    right_context: str = ""


class RuleSequence(NamedTuple):
    """
    A sequence of rules to be applied.
    Here just stored as a list of strings indicating rule names,
    which are resolved to rule data up in `fst_compilation.compile_rule`
    """

    rules: tuple[str, ...]
    description: str = ""


# A mapping of rule names to their corresponding rule objects.
Rule = SimpleRule | StringMapRule | RuleSequence

def resolve_rule(data: dict) -> Rule: 
    for rule_class in (SimpleRule, StringMapRule, RuleSequence):
        try:
            return rule_class(**data)
        except:
            pass
    raise ValueError(f"Could not resolve rule with data {data}")

class FeatureValue(NamedTuple):
    """
    A value for a specific feature.
    """

    feature: str
    value: str


class Feature(NamedTuple):
    """
    A feature with a name and a list of possible values.
    """

    name: str
    values: tuple[str, ...]

OperationTypeSingleString = Literal["prefix", "suffix", "suppletion", "rule"]
OperationTypeStringTuple = Literal["replace"]
UnorderedOperation = Literal["principle_part"]


class SingleStringMarker(NamedTuple):
    """
    A marker for a single string operation.
    """

    operation: OperationTypeSingleString
    value: str
    order: str | None = None


class StringTupleMarker(NamedTuple):
    """
    A marker for a string tuple operation.
    """

    operation: OperationTypeStringTuple
    value: tuple[str, str]
    order: str | None = None


class UnorderedMarker(NamedTuple):
    """
    A marker for an unordered morphological operation.
    """

    operation: UnorderedOperation
    value: str


class StringMapMarker(NamedTuple):
    operation: Literal["string_map"]
    value: tuple[tuple[str, str], ...]
    order: str | None = None


Marker = SingleStringMarker | StringTupleMarker | UnorderedMarker | StringMapMarker

def resolve_marker(data: dict) -> Marker:
    for marker_class in (SingleStringMarker, StringTupleMarker, UnorderedMarker):
        try:
            return marker_class(**data)
        except:
            pass
    raise ValueError(f"Could not resolve marker with data {data}")


class Token(NamedTuple):
    value: str
    kind: Literal[
        "phone", "tag", "class_ref", "pattern_ref", "bow_eow", "edit_flag",
        "special_ref", "unary_operator", "pipe_operator", "caret_operator",
        "boundary", "left_delimiter", "right_delimiter",
    ]
    fsa: Any = None  # pynini.Fst | None; Any avoids hard pynini dep here

    def __len__(self) -> int:
        return len(self.value)