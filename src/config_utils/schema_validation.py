import yaml
import json
from loguru import logger
from jsonschema import validate, ValidationError
from pathlib import Path
from src.constants import SCHEMA_DIR
from typing import Literal, get_args

ConfigKindType = Literal[
    # TODO: FeatureCombinations, MorphemeSet and MorphemeSequence are buggy
    # so they are commented out for now
    "ContingentFeatureMarkers",
    # "FeatureCombinations",
    "FeatureDefinitions",
    "FeatureMarkers",
    "Inventory",
    # "MorphemeSequence",
    # "MorphemeSet",
    "Paradigm",
    "PartOfSpeech",
    "Patterns",
    "Rules",
]
CONFIG_KINDS: tuple[str, ...] = get_args(ConfigKindType)

def fix_refs_safe(schema: dict, schema_dir: Path) -> dict:
    """
    Safely resolves external $ref in a JSON schema by copying the
    referenced content directly into the schema definitions and
    changing the $ref to a local reference. Avoids RecursionError
    caused by `jsonref` package.
    """

    node_stack = [schema]
    inserted_content = {}

    while node_stack:
        current_node = node_stack.pop()
        if isinstance(current_node, dict):
            node_stack.extend(current_node.values())

            if "$ref" in current_node:
                ref_path = current_node["$ref"]
                if ref_path.startswith("#"):
                    continue  # Local reference, skip
                rel_path, object_path = ref_path.split("#")
                ref_file_path = schema_dir / rel_path

                # get referenced content to be added to schema later
                content, object_name = get_referenced_content(
                    ref_file_path, object_path
                )
                inserted_content[object_name] = content

                # change $ref to local reference
                current_node["$ref"] = f"#{object_path}"

        elif isinstance(current_node, list):
            # lists may contain objects with $ref
            # so we need to check them as well
            node_stack.extend(current_node)

    # insert referenced content into schema
    if "definitions" not in schema:
        schema["definitions"] = {}
    for object_name, content in inserted_content.items():
        if object_name in schema["definitions"]:
            logger.warning(
                f"Object '{object_name}' already exists in schema definitions. Overwriting with content from {ref_file_path}."
            )
        schema["definitions"][object_name] = content
    return schema


def get_referenced_content(ref_file_path: Path, object_path: str) -> tuple[dict, str]:
    # JSON path should be in the format "definitions/{OBJECT_NAME}"
    path_parts = object_path.strip("/").split("/")
    assert (
        len(path_parts) == 2 and path_parts[0] == "definitions"
    ), "Only references to definitions are supported"
    definitions_key, object_name = path_parts

    if not ref_file_path.exists():
        raise FileNotFoundError(f"Referenced schema file not found: {ref_file_path}")

    with open(ref_file_path, "r", encoding="utf-8") as f:
        ref_content = json.load(f)
    content = ref_content.get(definitions_key, {}).get(object_name, None)
    if content is None:
        raise ValueError(
            f"Referenced object '{object_name}' not found in '{ref_file_path}'"
        )
    return content, object_name


def load_schema(target_kind: str, schema_dir=SCHEMA_DIR):
    # Generate schema filename from kind
    schema_filename = f"{target_kind}.json"
    schema_path = Path(schema_dir)
    schema_file_path = schema_path / schema_filename

    if not schema_file_path.exists():
        logger.error(f"Schema file not found: {schema_file_path}")
        return

    try:
        with open(schema_file_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        schema = fix_refs_safe(schema, schema_path)
        return schema
    except Exception as e:
        logger.exception(f"Failed to load schema {schema_filename}: {e}")
        return


def validate_files_by_kind(
    target_kind, config_dir="config", schema_dir="schemas/"
):
    """
    Iterates through all YAML files and validates only those matching the target_kind.
    The schema is expected to be named '{hammer_case_kind}.schema.json'.
    """
    config_path = Path(config_dir)
    schema = load_schema(target_kind, schema_dir)
    if not schema:
        logger.error(f"Cannot validate {target_kind} due to missing schema.")
        return

    # Find all YAML files
    yaml_files = list(config_path.glob("**/*.yaml")) + list(
        config_path.glob("**/*.yml")
    )

    logger.info(f"Searching for files of kind '{target_kind}' in {config_dir}...")

    stats = {"matched": 0, "passed": 0, "failed": 0}

    for file_path in yaml_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            # Skip if file is empty or missing 'kind'
            if not data or "kind" not in data:
                continue

            # Filter by the requested kind
            if data["kind"] != target_kind:
                continue

            stats["matched"] += 1
            relative_path = file_path.relative_to(config_path)

            # Validate against the schema
            validate(instance=data, schema=schema)
            logger.success(f"PASS: {relative_path}")
            stats["passed"] += 1

        except ValidationError as ve:
            stats["failed"] += 1
            logger.error(f"FAIL: {file_path.relative_to(config_path)}")
            logger.error(f"      Reason: {ve.message}")
            if ve.path:
                logger.error(f"      Path: {' -> '.join([str(p) for p in ve.path])}")
        except Exception as e:
            logger.exception(
                f"ERROR processing {file_path.relative_to(config_path)}: {e}"
            )

    # Final Summary
    logger.info(f"--- Summary for {target_kind} ---")
    logger.info(f"Files Matched: {stats['matched']}")

    if stats["passed"] > 0:
        logger.success(f"Passed:        {stats['passed']}")
    else:
        logger.info(f"Passed:        {stats['passed']}")

    if stats["failed"] > 0:
        logger.error(f"Failed:        {stats['failed']}")
    else:
        logger.info(f"Failed:        {stats['failed']}")


def main():
    for kind in CONFIG_KINDS:
        print(f"Validating {kind}...")
        validate_files_by_kind(kind)


if __name__ == "__main__":
    main()
