import yaml
import json

from deprecated.web import create_app
from src.editors.configs import list_config_yaml_files, normalize_config_dir
from src.editors.inventory import InventoryEditor
from src.editors.patterns import PatternsEditor
from src.editors.rules import RulesEditor


CONFIG_DIR = "config/spanish"

_inventory = InventoryEditor()
_patterns = PatternsEditor()
_rules = RulesEditor()


def _client():
    app = create_app(CONFIG_DIR)
    app.config["TESTING"] = True
    return app.test_client()


def test_safe_inventory_path_rejects_non_inventory_files():
    assert _inventory.safe_path(CONFIG_DIR, "markers/present_ind_ar_suffixes.yaml") is None


def test_load_inventory_state_reads_existing_inventory():
    state = _inventory.load_state(CONFIG_DIR, "inventory/segments.yaml")

    assert state["kind"] == "Inventory"
    assert state["nodes"]
    assert state["nodes"][0]["name"] == "consonants"


def test_inventory_yaml_round_trip_uses_inventory_shape():
    state = _inventory.load_state(CONFIG_DIR, "inventory/segments.yaml")

    document = yaml.safe_load(_inventory.to_yaml(state))

    assert document["kind"] == "Inventory"
    assert "consonants" in document["data"]
    assert document["data"]["vowels"]["plain"]["_phones"] == ["a", "e", "i", "o", "u"]


def test_list_config_yaml_files_scans_selected_directory():
    files = list_config_yaml_files(CONFIG_DIR)

    assert normalize_config_dir(CONFIG_DIR) is not None
    assert any(item["path"] == "inventory/segments.yaml" for item in files)

# TODO: change to reflect local-only directory management
# def test_manifest_session_stores_yaml_entries():
#     manifest = json.dumps(
#         {
#             "label": "Selected directory",
#             "files": [
#                 {
#                     "path": "inventory/segments.yaml",
#                     "content": "kind: Inventory\ndata:\n  vowels:\n    _ref: '<V>'\n",
#                 }
#             ],
#         }
#     )
#     token = create_manifest_session(manifest)
#     session = get_upload_session(token)

#     assert session is not None
#     assert "inventory/segments.yaml" in session["files"]
#     assert session["files"]["inventory/segments.yaml"]["kind"] == "Inventory"


def test_scan_config_route_accepts_manifest():
    client = _client()
    response = client.post(
        "/scan-config",
        data={
            "manifest": json.dumps(
                {
                    "label": "Selected directory",
                    "files": [
                        {
                            "path": "inventory/segments.yaml",
                            "content": "kind: Inventory\ndata:\n  vowels:\n    _ref: '<V>'\n",
                        }
                    ],
                }
            )
        },
    )

    assert response.status_code == 302
    assert "config_token=" in response.headers["Location"]


def test_index_supports_non_inventory_yaml_editor():
    client = _client()

    response = client.get(
        "/",
        query_string={
            "path": "markers/present_ind_ar_suffixes.yaml",
        },
    )

    assert response.status_code == 200
    assert b"Marker editor" in response.data
    assert b"Non-Inventory config types are editable as raw YAML." in response.data

# TODO: change to reflect local-only directory management
# def test_config_editor_saves_uploaded_non_inventory_yaml():
#     token = create_manifest_session(
#         json.dumps(
#             {
#                 "label": "Selected directory",
#                 "files": [
#                     {
#                         "path": "markers/demo.yaml",
#                         "content": "kind: Marker\nvalue: old\n",
#                     }
#                 ],
#             }
#         )
#     )

#     client = _client()
#     response = client.post(
#         "/config",
#         data={
#             "config_token": token,
#             "editor_kind": "Marker",
#             "path": "markers/demo.yaml",
#             "content": "kind: Marker\nvalue: new\n",
#             "action": "save",
#         },
#     )

#     session = get_upload_session(token)

#     assert response.status_code == 200
#     assert session is not None
#     assert session["files"]["markers/demo.yaml"]["content"] == "kind: Marker\nvalue: new\n"


def test_load_patterns_state_reads_existing_patterns():
    state = _patterns.load_state(CONFIG_DIR, "patterns/vowel_classes.yaml")

    assert state["kind"] == "Patterns"
    assert state["patterns"]
    assert state["patterns"][0]["name"] == "Front vowel"


def test_patterns_yaml_round_trip_uses_patterns_shape():
    state = _patterns.load_state(CONFIG_DIR, "patterns/vowel_classes.yaml")

    document = yaml.safe_load(_patterns.to_yaml(state))

    assert document["kind"] == "Patterns"
    assert document["patterns"][0]["Front vowel"]["_ref"] == "<V_Front>"


def test_index_supports_patterns_editor():
    client = _client()

    response = client.get(
        "/",
        query_string={
            "path": "patterns/vowel_classes.yaml",
        },
    )

    assert response.status_code == 200
    assert b"Pattern editor" in response.data
    assert b"Add pattern" in response.data


def test_load_rules_state_reads_existing_rules():
    state = _rules.load_state(CONFIG_DIR, "rules/accentuation.yaml")

    assert state["kind"] == "Rules"
    assert state["rules"]
    assert state["rules"][0]["name"] == "diphthongization"


def test_rules_yaml_round_trip_uses_rules_shape():
    state = _rules.load_state(CONFIG_DIR, "rules/accentuation.yaml")

    document = yaml.safe_load(_rules.to_yaml(state))

    assert document["kind"] == "Rules"
    assert "diphthongization" in document["rules"]


def test_index_supports_rules_editor():
    client = _client()

    response = client.get(
        "/",
        query_string={
            "path": "rules/accentuation.yaml",
        },
    )

    assert response.status_code == 200
    assert b"Rules editor" in response.data
    assert b"Add rule" in response.data
