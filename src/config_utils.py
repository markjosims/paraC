import yaml
import json
from loguru import logger
from jsonschema import validate, ValidationError
from pathlib import Path

CONFIG_KINDS = [
    'ContingentFeatureMarkers', 'FeatureCombinations', 'FeatureDefinitions',
    'FeatureMarkers', 'Inventory', 'Paradigm', 'PartOfSpeech', 'Patterns'
]

def validate_by_kind(target_kind, config_dir="config", schema_dir="config/schemas"):
    """
    Iterates through all YAML files and validates only those matching the target_kind.
    The schema is expected to be named '{hammer_case_kind}.schema.json'.
    """
    config_path = Path(config_dir)
    schema_path = Path(schema_dir)
    
    # Generate schema filename from kind
    schema_filename = f"{target_kind}.json"
    schema_file_path = schema_path / schema_filename

    if not schema_file_path.exists():
        logger.error(f"Schema file not found: {schema_file_path}")
        return

    try:
        with open(schema_file_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load schema {schema_filename}: {e}")
        return

    # Find all YAML files
    yaml_files = list(config_path.glob('**/*.yaml')) + list(config_path.glob('**/*.yml'))
    
    logger.info(f"Searching for files of kind '{target_kind}' in {config_dir}...")
    logger.info(f"Using schema: {schema_filename}")
    
    stats = {"matched": 0, "passed": 0, "failed": 0}

    for file_path in yaml_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            # Skip if file is empty or missing 'kind'
            if not data or 'kind' not in data:
                continue
                
            # Filter by the requested kind
            if data['kind'] != target_kind:
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
            logger.error(f"ERROR processing {file_path.relative_to(config_path)}: {e}")

    # Final Summary
    logger.info(f"--- Summary for {target_kind} ---")
    logger.info(f"Files Matched: {stats['matched']}")
    
    if stats['passed'] > 0:
        logger.success(f"Passed:        {stats['passed']}")
    else:
        logger.info(f"Passed:        {stats['passed']}")
        
    if stats['failed'] > 0:
        logger.error(f"Failed:        {stats['failed']}")
    else:
        logger.info(f"Failed:        {stats['failed']}")

def main():
    for kind in CONFIG_KINDS:
        print(f"Validating {kind}...")
        validate_by_kind(kind)


if __name__ == '__main__':
    main()