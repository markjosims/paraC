import pytest
from src.grammar.registry.inventory_registry import InventoryItem, InventoryClass
from src.fst_utils import ReservedSymbolMixin

def test_inventory_item_validation():
    # Valid phone
    InventoryItem(value="a", type="phone")
    # Valid flag
    InventoryItem(value="[FLAG]", type="flag")
    
    # Invalid phone (contains square brackets)
    with pytest.raises(ValueError, match="cannot contain"):
        InventoryItem(value="a[", type="phone")
    
    # Invalid phone (contains angle brackets)
    with pytest.raises(ValueError, match="cannot contain"):
        InventoryItem(value="a<", type="phone")
        
    # Invalid flag (missing brackets)
    with pytest.raises(ValueError, match=r"Flag items must have values that start with '\[' and end with '\]'"):
        InventoryItem(value="FLAG", type="flag")
        
    # Reserved symbol
    with pytest.raises(ValueError, match="reserved symbol"):
        InventoryItem(value="*", type="phone")

    # Reserved edit flag
    with pytest.raises(ValueError, match="reserved symbol"):
        InventoryItem(value="[INSERT]", type="flag")

def test_inventory_class_validation():
    # Valid class
    InventoryClass(value="<V>", type="phone_class")
    
    # Invalid class (missing brackets)
    with pytest.raises(ValueError, match=r"Class items must have values that start with '<' and end with '>'"):
        InventoryClass(value="V", type="phone_class")
        
    # Reserved symbol
    with pytest.raises(ValueError, match="reserved symbol"):
        InventoryClass(value="*", type="phone_class")
