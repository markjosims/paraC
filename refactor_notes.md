# refactor_notes
## TODO list
- Define class for registries
- Define new FST factory function that reads a symbol table from a registry object
- Standardize representation for repr strings and flags

## Inventory config
How is inventory loaded?
Symbol table needs to be declared programmatically from Yaml files.

- `_build_registry_from_node`: compiles a single FSA for all for all members of a node
- `build_inventory_registry`: creates a dictionary mapping strings to fsas


## Config readers


## Pattern compilation
- `_tokenize_pattern`: Tokenized the pattern string into tuple of token type and string value
    - Token types are '!', 'special', 'op', 'paren', 'literal'
    - Current behavior combines combining diacritics with the previous character. Change this so that combining diacritics are their ow'n token. (line 275)
- `_PatternParser`: Class handling recursive descent parsing for pattern strings
    - Mainly exposed via `parse_expr` which only takes `self` as an argument

