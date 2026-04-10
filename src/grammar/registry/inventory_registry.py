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

# TODO: update Fst registry and orchestrator family to expect
# new InventoryItem/Class API


@dataclass
class InventoryItem(Acceptor):
    """
    Represents a single phone or flag in the inventory.
    Attributes:
        value: The string value of the item (e.g. "a", "[TBU]",).
        type: The type of the item, either "phone" or "flag"
        parent: reference to parent InventoryItem (for upward traversal).
        source: Optional string indicating filepath item originates from.
        acceptor: pynini.Fst accepting the item (or, for classes, any member of the item).
            Note this should NOT be passed as an argument but instead be assigned by an
            InventoryRegistry class.
    """

    value: str = ""
    type: Literal["phone", "flag"] = "phone"
    parent: Optional["InventoryClass"] = None
    source: os.PathLike | None = None

    def __post_init__(self):
        super().__post_init__()

        if (self.type == "flag") and (
            not self.value.startswith("[") or not self.value.endswith("]")
        ):
            raise ValueError(
                "Flag items must have values that start with '[' and end with ']'"
            )
        if (self.type == "phone") and (
            self.value.startswith("<") or self.value.startswith("[")
        ):
            raise ValueError(
                "Phone items cannot have values that start with '<' or '['"
            )

    def __str__(self):
        return f"InventoryItem(value='{self.value}')"

    def __repr__(self):
        return self.__str__()


@dataclass
class InventoryClass(Acceptor):
    """
    Represents an inventory class, which is a node in the inventory tree whose
    children are phones, flags (i.e. InventoryItem objects) or other InventoryClasses
    (for "nested_class").

    Attributes:
        value: The string value of the item (e.g. "<V>", "<Stop>", "<Tone>").
        type: The type of the item, one of "phone_class", "flag_class", or "nested_class".
        children: List of child InventoryItems.
        parent: Optional reference to parent InventoryItem (for upward traversal).
        source: Optional string indicating filepath item originates from.
        acceptor: pynini.Fst accepting the item (or, for classes, any member of the item).
            Note this should NOT be passed as an argument but instead be assigned by an
            InventoryRegistry class.
    """

    value: str = ""
    type: Literal["phone_class", "flag_class", "nested_class"] = "phone_class"
    children: list["InventoryItem"] = field(default_factory=list)
    parent: Optional["InventoryItem"] = None
    source: os.PathLike | None = None

    def __post_init__(self):
        super().__post_init__()

        if self.value in ReservedSymbolMixin.reserved_symbols:
            error = f"Inventory item value '{self.value}' is a reserved symbol and cannot be used."
            logger.error(error)
            raise ValueError(error)

        if self.type == "class" and self.children is None:
            raise ValueError("Class items must have children")

        if not self.value.startswith("<") or not self.value.endswith(">"):
            raise ValueError(
                "Class items must have values that start with '<' and end with '>'"
            )

    @classmethod
    def infer_class_type(
        cls,
        item_dict: dict,
    ) -> Literal["phone_class", "flag_class", "nested_class"]:
        if "_phones" in item_dict:
            ...

    @classmethod
    def validate_class_type(
        cls,
        class_type: Literal["phone_class", "flag_class", "nested_class"],
        item_dict: dict,
    ) ->

    @classmethod
    def from_config(
        cls,
        item_dict: dict,
        parent: Optional["InventoryItem"] = None,
    ) -> "InventoryItem":
        """
        Builds an InventoryItem from a config dict
        If config has children (nested dicts), recursively
        build child InventoryItems and attach to parent
        """

        # get source filepath if specified
        source_path = item_dict.get("source", None)

        inventory_item = cls(
            value=item_dict["_ref"],
            type="class",
            children=[],
            parent=parent,
            source=source_path,
        )

        children = []
        for key, value in item_dict.items():
            if key == "_phones":
                for phone in value:
                    child = InventoryItem(
                        value=phone, type="phone", parent=inventory_item
                    )
                    children.append(child)
            elif key == "_flags":
                for flag in value:
                    child = InventoryItem(
                        value=flag, type="flag", parent=inventory_item
                    )
                    children.append(child)
            elif isinstance(value, dict):
                child = cls.from_config(value, parent=inventory_item)
                children.append(child)

        inventory_item.children = children
        return inventory_item
    
    def serialize_to_config(self) -> dict:


    def flatten(self) -> list["InventoryItem" | "InventoryClass"]:
        """Recursively InventoryItem into a list including itself and all children."""
        items = [self]
        for child in self.children:
            items.extend(child.flatten())
        return items

    def __str__(self):
        return f"InventoryClass(value='{self.value}')"

    def __repr__(self):
        return self.__str__()


InventoryMemberType = Union[InventoryItem, InventoryClass]


class InventoryRegistry(Registry):
    """
    Registry for storing inventory items (phones, flags, classes).
    Instantiated directly with a pre-built `data` dict mapping inventory
    item names to `InventoryMemberType` objects, or a `config_objects` dict mapping
    filenames to YAML config objects.
    """

    def __init__(
        self,
        data: dict[str, InventoryMemberType] | None = None,
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
            if item.type == "phone":
                phones[item.value] = item
            elif item.type == "flag":
                flags[item.value] = item
            elif item.type == "class":
                classes[item.value] = item
        self.phones = phones
        self.flags = flags
        self.classes = classes

    def load_all_configs(
        self,
    ) -> tuple[list[InventoryClass], dict[str, InventoryMemberType]]:
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
    ) -> dict[str, InventoryMemberType]:
        top_data = config.get("data", [])
        if not top_data:
            logger.error("No top-level inventory classes found in config")
            return {}

        # get flat list of items
        items_flat = []
        items_top = []
        for item_config in top_data.values():
            item = InventoryClass.from_config(item_config)
            flat_item = item.flatten()
            items_flat.extend(flat_item)
            items_top.append(item)

        # check for item collisions
        item_values = [item.value for item in items_flat]
        if len(item_values) != len(set(item_values)):
            duplicate_items = set([x for x in item_values if item_values.count(x) > 1])
            error = (
                f"Collision found among item values: {item_values} "
                + f"Duplicate items: {duplicate_items}"
            )
            logger.error(error)
            raise ValueError(error)

        # make dict mapping ref to item
        item_dict = {item.value: item for item in items_flat}

        # set top items attr
        self.top_items = self.top_items

        return item_dict

    def _get_tokens_from_class(self, item: InventoryMemberType) -> list[str]:
        """Recursively collect all phone/flag tokens from an InventoryItem subtree."""
        tokens = []
        if isinstance(item, InventoryItem):
            tokens.append(item.value)
        else:
            for child in item.children:
                tokens.extend(self._get_tokens_from_class(child))
        return tokens
