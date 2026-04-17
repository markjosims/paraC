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
class InventoryMember(Acceptor):
    value: str = ""
    parent: Optional["InventoryClass"] = None
    source: os.PathLike | None = None


@dataclass
class InventoryItem(InventoryMember):
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

    type: Literal["phone", "flag"] = "phone"

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
class InventoryClass(InventoryMember):
    """
    Represents an inventory class, which is a node in the inventory tree whose
    children are phones, flags (i.e. InventoryItem objects) or other InventoryClasses
    (for "nested_class").

    Attributes:
        name: a descriptive name for the class
        value: The string value of the item (e.g. "<V>", "<Stop>", "<Tone>").
        type: The type of the item, one of "phone_class", "flag_class", or "nested_class".
        children: List of child InventoryItems.
        parent: Optional reference to parent InventoryItem (for upward traversal).
        source: Optional string indicating filepath item originates from.
        acceptor: pynini.Fst accepting the item (or, for classes, any member of the item).
            Note this should NOT be passed as an argument but instead be assigned by an
            InventoryRegistry class.
    """

    name: str = ""
    type: Literal["phone_class", "flag_class", "nested_class"] = "phone_class"
    children: list["InventoryMember"] = field(default_factory=list)

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
            expected_class_type = "phone_class"
        elif "_flags" in item_dict:
            expected_class_type = "flag_class"
        else:
            expected_class_type = "nested_class"
        cls.validate_class_type(class_type=expected_class_type, item_dict=item_dict)
        return expected_class_type

    @classmethod
    def validate_class_type(
        cls,
        class_type: Literal["phone_class", "flag_class", "nested_class"],
        item_dict: dict,
    ) -> list[str | dict]:
        """
        Returns a list of validated items if the data in `item_dict` matches the format expected
        for the given class type, else raise ValueError.
        """
        data_by_class_type = {
            "phone_class": ("_phones", str),
            "flag_class": ("_flags", str),
            "nested_class": ("_children", dict),
        }
        field, expected_type = data_by_class_type[class_type]
        if field not in item_dict:
            error = f"Expected field '{field}' not found for class type '{class_type}'"
            logger.error(error)
            raise ValueError(error)
        if not isinstance(item_dict[field], list):
            error = (
                f"Expected field '{field}' to be a list for class type '{class_type}'"
            )
            logger.error(error)
            raise ValueError(error)
        for item in item_dict[field]:
            if not isinstance(item, expected_type):
                error = (
                    f"Expected items in field '{field}' to be of type "
                    + f"'{expected_type.__name__}' for class type '{class_type}'"
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

        class_type = cls.infer_class_type(item_dict=item_dict)
        child_data = cls.validate_class_type(class_type=class_type, item_dict=item_dict)

        # initialize InventoryClass with empty children
        # will populate after recursively building children
        inventory_class = cls(
            name=item_dict.get("name", ""),
            value=item_dict["_ref"],
            type=class_type,
            children=[],
            parent=parent,
            source=source_path,
        )

        if class_type == "nested_class":
            children = [
                cls.from_config(child_config, parent=inventory_class)
                for child_config in child_data
            ]
        elif class_type == "phone_class":
            children = [
                InventoryItem(
                    value=child,
                    parent=inventory_class,
                    source=source_path,
                    type="phone",
                )
                for child in child_data
            ]
        else:  # class_type=="flag_class"
            children = [
                InventoryItem(
                    value=child,
                    parent=inventory_class,
                    source=source_path,
                    type="flag",
                )
                for child in child_data
            ]
        inventory_class.children = children

        return inventory_class

    def to_dict(self) -> dict:
        json = {"_ref": self.value, "name": self.name}
        if self.type == "phone_class":
            json["_phones"] = [item.value for item in self.children]
        elif self.type == "flag_class":
            json["_flags"] = [item.value for item in self.children]
        else:
            # self.type == "nested_class"
            json["_children"] = {
                child.value: child.to_dict() for child in self.children
            }
        return json

    def flatten(self) -> list[Union["InventoryItem", "InventoryClass"]]:
        """Recursively InventoryItem into a list including itself and all children."""
        items = [self]
        if self.type == "nested_class":
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
            if isinstance(item, InventoryItem) and item.type == "phone":
                phones[item.value] = item
            elif isinstance(item, InventoryItem) and item.type == "flag":
                flags[item.value] = item
            elif isinstance(item, InventoryClass):
                classes[item.value] = item
            else:
                raise ValueError(
                    f"Unrecognized inventory object {type(item)} of type {item.type}"
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
        """Recursively collect all phone/flag tokens from an InventoryItem subtree."""
        tokens = []
        if isinstance(item, InventoryItem):
            tokens.append(item.value)
        else:
            for child in item.children:
                tokens.extend(self._get_tokens_from_class(child))
        return tokens
