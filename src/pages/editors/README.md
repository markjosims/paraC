# Editor pages

This folder implements pages for editing grammar files.
[editor_base.py](./editor_base.py) defines an abstract class `EditorBase` and helper methods for each editor page.
The page for each specific editor type is given in its own file, e.g. the `Inventory` editor is specified in [inventory.py](./inventory.py).

The `EditorBase` abstract class owns logic for 