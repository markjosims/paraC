"""
Implements the `InventoryItem` and `InventoryRegistry` classes.
`InventoryItem` reflects a single node in an inventory tree, and
`InventoryRegistry` aggregates inventory items from across multiple
config files and allows for mapping between `InventoryItems` and their
string representations.
"""

from src.grammar.classes import Registry
from src.fst_utils import Acceptor, ReservedSymbolMixin
from typing import Literal, Optional, Union
from dataclasses import dataclass, field
import os
from loguru import logger
from uuid import uuid4

# TODO: update Fst registry and orchestrator family to expect
# new InventoryItem/Class API


@dataclass
class InventoryMember(Acceptor):
    value: str = ""
    parent: Optional["InventoryClass"] = None
    source: os.PathLike | None = None


@dataclass
class InventoryItem(InventoryMember):
    """
    Represents a single phone or tag in the inventory.
    Attributes:
        value: The string value of the item (e.g. "a", "[TBU]",).
        kind: The kind of the item, either "phone" or "tag"
        parent: reference to parent InventoryItem (for upward traversal).
        source: Optional string indicating filepath item originates from.
        acceptor: pynini.Fst accepting the item (or, for classes, any member of the item).
            Note this should NOT be passed as an argument but instead be assigned by an
            InventoryRegistry class.
    """

    kind: Literal["phone", "tag"] = "phone"

    def __post_init__(self):
        super().__post_init__()

        if self.value in ReservedSymbolMixin.reserved_symbols:
            raise ValueError(
                f"Inventory item value '{self.value}' is a reserved symbol and cannot be used."
            )

        if (self.kind == "tag") and (
            not self.value.startswith("[") or not self.value.endswith("]")
        ):
            raise ValueError(
                "tag items must have values that start with '[' and end with ']'"
            )
        if (self.kind == "phone") and (
            "[" in self.value or "]" in self.value or "<" in self.value or ">" in self.value
        ):
            raise ValueError(
                "Phone items cannot contain '[', ']', '<', or '>'"
            )

    def __str__(self):
        return f"InventoryItem(value='{self.value}')"

    def __repr__(self):
        return self.__str__()


@dataclass
class InventoryClass(InventoryMember):
    """
    Represents an inventory class, which is a node in the inventory tree whose
    children are phones, flags (i.e. InventoryItem objects) or other InventoryClasses
    (for "nested_class").

    Attributes:
        name: a descriptive name for the class
        value: The string value of the item (e.g. "<V>", "<Stop>", "<Tone>").
        kind: The kind of the item, one of "phone_class", "flag_class", or "nested_class".
        children: List of child InventoryItems.
        parent: Optional reference to parent InventoryItem (for upward traversal).
        source: Optional string indicating filepath item originates from.
        acceptor: pynini.Fst accepting the item (or, for classes, any member of the item).
            Note this should NOT be passed as an argument but instead be assigned by an
            InventoryRegistry class.
    """

    ref: str = field(init=False, default="")  # set ref to value of `value` field on init
    # for compatibility with Pattern class and parsing logic in InventoryRegistry
    name: str = ""
    kind: Literal["phone_class", "flag_class", "nested_class"] = "phone_class"
    children: list["InventoryMember"] = field(default_factory=list)
    uuid: str = field(default_factory=lambda: str(uuid4()), init=False)

    def __post_init__(self):
        super().__post_init__()
        self.ref = self.value

        if self.value in ReservedSymbolMixin.reserved_symbols:
            error = f"Inventory item value '{self.value}' is a reserved symbol and cannot be used."
            logger.error(error)
            raise ValueError(error)

        if self.kind == "class" and self.children is None:
            raise ValueError("Class items must have children")

        if not self.value.startswith("<") or not self.value.endswith(">"):
            raise ValueError(
                "Class items must have values that start with '<' and end with '>'"
            )

    @classmethod
    def infer_class_kind(
        cls,
        item_dict: dict,
    ) -> Literal["phone_class", "flag_class", "nested_class"]:
        if "phones" in item_dict:
            expected_class_kind = "phone_class"
        elif "tags" in item_dict:
            expected_class_kind = "flag_class"
        else:
            expected_class_kind = "nested_class"
        cls.validate_class_kind(class_kind=expected_class_kind, item_dict=item_dict)
        return expected_class_kind

    @classmethod
    def validate_class_kind(
        cls,
        class_kind: Literal["phone_class", "flag_class", "nested_class"],
        item_dict: dict,
    ) -> list[str | dict]:
        """
        Returns a list of validated items if the data in `item_dict` matches the format expected
        for the given class type, else raise ValueError.
        """
        data_by_class_kind = {
            "phone_class": ("phones", str),
            "flag_class": ("tags", str),
            "nested_class": ("children", dict),
        }
        field, expected_kind = data_by_class_kind[class_kind]
        if field not in item_dict:
            error = f"Expected field '{field}' not found for class type '{class_kind}'"
            logger.error(error)
            raise ValueError(error)
        if not isinstance(item_dict[field], list):
            error = (
                f"Expected field '{field}' to be a list for class type '{class_kind}'"
            )
            logger.error(error)
            raise ValueError(error)
        for item in item_dict[field]:
            if not isinstance(item, expected_kind):
                error = (
                    f"Expected items in field '{field}' to be of type "
                    + f"'{expected_kind.__name__}' for class type '{class_kind}'"
                )
                logger.error(error)
                raise ValueError(error)
        return item_dict[field]

    @classmethod
    def from_config(
        cls,
        item_dict: dict,
        parent: Optional["InventoryClass"] = None,
    ) -> "InventoryClass":
        """
        Builds an InventoryClass from a config dict
        If config has children (nested dicts), recursively
        build child InventoryClass and attach to parent
        """

        # get source filepath if specified
        source_path = item_dict.get("source", None)

        class_kind = cls.infer_class_kind(item_dict=item_dict)
        child_data = cls.validate_class_kind(class_kind=class_kind, item_dict=item_dict)

        # initialize InventoryClass with empty children
        # will populate after recursively building children
        inventory_class = cls(
            name=item_dict.get("name", ""),
            value=item_dict["ref"],
            kind=class_kind,
            children=[],
            parent=parent,
            source=source_path,
        )

        if class_kind == "nested_class":
            children = [
                cls.from_config(child_config, parent=inventory_class)
                for child_config in child_data
            ]
        elif class_kind == "phone_class":
            children = [
                InventoryItem(
                    value=child,
                    parent=inventory_class,
                    source=source_path,
                    kind="phone",
                )
                for child in child_data
            ]
        else:  # class_kind=="flag_class"
            children = [
                InventoryItem(
                    value=child,
                    parent=inventory_class,
                    source=source_path,
                    kind="tag",
                )
                for child in child_data
            ]
        inventory_class.children = children

        return inventory_class

    def to_dict(self) -> dict:
        json = {"ref": self.value, "name": self.name}
        if self.kind == "phone_class":
            json["phones"] = [item.value for item in self.children]
        elif self.kind == "flag_class":
            json["tags"] = [item.value for item in self.children]
        else:
            # self.kind == "nested_class"
            json["children"] = [child.to_dict() for child in self.children]
        return json

    def flatten(self) -> list[Union["InventoryItem", "InventoryClass"]]:
        """Recursively InventoryItem into a list including itself and all children."""
        items = [self]
        if self.kind == "nested_class":
            for child in self.children:
                items.extend(child.flatten())
        else:
            items.extend(self.children)
        return items

    def item_strs(self):
        return [child.value for child in self.children]

    def __str__(self):
        return f"InventoryClass(value='{self.value}')"

    def __repr__(self):
        return self.__str__()


class InventoryRegistry(Registry):
    """
    Registry for storing inventory items (phones, flags, classes).
    Instantiated directly with a pre-built `data` dict mapping inventory
    item names to `InventoryMember` objects, or a `config_objects` dict mapping
    filenames to YAML config objects.
    """

    def __init__(
        self,
        data: dict[str, InventoryMember] | None = None,
        config_objects: dict[str, dict] | None = None,
    ):
        super().__init__(kind="Inventory", data=data, config_objects=config_objects)

        if not hasattr(self, "top_items"):
            # top items initialized by 'load_data_from_configs'
            # if InventoryRegistry is built from data dict directly,
            # this attr will not be initialized yet
            # if so, initialize by getting list of all classes with no parent class
            self.top_items = list(
                item
                for item in self.data.values()
                if isinstance(item, InventoryClass) and item.parent is None
            )

        self._populate_subdicts()

    def _populate_subdicts(self):
        phones = {}
        flags = {}
        classes = {}
        for item in self.data.values():
            if isinstance(item, InventoryItem) and item.kind == "phone":
                phones[item.value] = item
            elif isinstance(item, InventoryItem) and item.kind == "tag":
                flags[item.value] = item
            elif isinstance(item, InventoryClass):
                classes[item.value] = item
            else:
                raise ValueError(
                    f"Unrecognized inventory object {type(item)} of type {item.kind}"
                )
        self.phones = phones
        self.flags = flags
        self.classes = classes

    def load_all_configs(
        self,
    ) -> tuple[list[InventoryClass], dict[str, InventoryMember]]:
        inventory_item_map = {}
        top_inventory_items = []
        for config in self.config_objects.values():
            config_top_items, config_data = self.load_data_from_config(config)
            # check for collisions
            for key in config_data:
                if key in inventory_item_map:
                    error = f"Duplicate inventory item '{key}' found in multiple config files."
                    logger.error(error)
                    raise ValueError(error)
            inventory_item_map.update(config_data)
            top_inventory_items.extend(config_top_items)
        return inventory_item_map

    def load_data_from_config(
        self,
        config: dict,
    ) -> dict[str, InventoryMember]:
        top_data = config.get("data", [])
        if not top_data:
            logger.error("No top-level inventory classes found in config")
            return {}

        # get flat list of items
        flat_items = []
        top_items = []
        for item_config in top_data:
            item = InventoryClass.from_config(item_config)
            flat_item = item.flatten()
            flat_items.extend(flat_item)
            top_items.append(item)

        # check for item collisions
        item_values = [item.value for item in flat_items]
        if len(item_values) != len(set(item_values)):
            duplicate_items = set([x for x in item_values if item_values.count(x) > 1])
            error = (
                f"Collision found among item values: {item_values} "
                + f"Duplicate items: {duplicate_items}"
            )
            logger.error(error)
            raise ValueError(error)

        # make dict mapping ref to item
        item_dict = {item.value: item for item in flat_items}

        return top_items, item_dict

    def _get_tokens_from_class(self, item: InventoryMember) -> list[str]:
        """Recursively collect all phone/tag tokens from an InventoryItem subtree."""
        tokens = []
        if isinstance(item, InventoryItem):
            tokens.append(item.value)
        else:
            for child in item.children:
                tokens.extend(self._get_tokens_from_class(child))
        return tokens
