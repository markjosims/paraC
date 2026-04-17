import yaml
from pathlib import Path
import unicodedata
from jsonschema import validate, ValidationError
from loguru import logger
from src.config_utils.schema_validation import load_schema, CONFIG_KINDS
from src.constants import PROJECT_ROOT
from camel_converter import to_snake
import dotenv
import os

# TODO: in the future, desired behavior is for the user to specify the config dir via
# a GUI and have that persist across sessions
# for now, loading from environment variable
dotenv.load_dotenv()
CONFIG_DIR = os.environ.get("CONFIG_DIR", "./config")


class ConfigWalker:
    """
    Provides logic for reading and validating YAML files.
    """

    def __init__(self, config_dir: str | Path) -> "ConfigWalker":
        self.config_dir = Path(config_dir)
        self.config_data = self._get_all_config_data()
        self.config_filemap = self._get_config_filemap()

    def _get_config_filemap(self) -> dict[str, list[str]]:
        """
        Gets a mapping of config kind -> filenames from
        `self.config_data`, i.e.
        ```python
        {
            "inventory_configs": ["/path/to/file1.yaml", "path/to/file2.yaml"],
            "pattern_configs": ["/path/to/file1.yaml", "path/to/file2.yaml"],
            ...
        }
        ```
        """
        filemap = {}
        for kind, config_objects in self.config_data.items():
            filemap[kind] = list(config_objects.keys())
        return filemap

    def _get_all_config_data(self) -> dict[str, dict[str, dict]]:
        """
        Reads all YAML data in the config folder and returns
        as dict mapping config type to list of objects.

        Reformat kind name from PascalCase to snake_case, strip
        plural -s if present, and suffix + '_configs'
        to match format expected by `Grammar` class, e.g.
        FeatureMarkers -> feature_markers_configs.

        Return dict is of format
        ```python
        {
            'inventory_configs': {
                '/path/to/inventory/file.yaml': {
                    **YAML DATA
                },
                ...
            },
            'pattern_configs': {
                '/path/to/pattern/file.yaml': {
                    **YAML DATA
                },
                ...
            }
        }
        ```
        """
        config_map = {}
        for kind in CONFIG_KINDS:
            kind_name = to_snake(kind).removesuffix("s") + "_configs"
            configs = self.read_config_files(kind)
            config_map[kind_name] = configs
        return config_map

    def read_config_files(self, kind: str) -> dict[str, str]:
        """
        Load all `config` files for the specified kind within `config_dir`
        into a dict mapping filename to data.
        """
        schema = load_schema(kind)
        config_objects = {}
        for filename in self.glob_config_files():
            with open(filename, "r") as f:
                content = f.read()
                content_norm = unicodedata.normalize("NFKD", content)
                config_data = yaml.safe_load(content_norm)

                # store filepath for config
                config_data["source_path"] = str(filename)
                if config_data.get("kind") == kind:
                    try:
                        validate(instance=config_data, schema=schema)
                        config_objects[str(filename)] = config_data
                    except ValidationError as e:
                        logger.exception(f"Invalid config file {filename}: {e}")
                        raise ValidationError(f"Invalid config file {filename}: {e}")
        return config_objects

    def glob_config_files(self):
        return self.config_dir.glob("**/*.yaml")

    def find_config_file(self, name: str) -> Path:
        """Search all config subdirectories for <name>.yaml."""
        for filename in self.glob_config_files(name):
            if Path(filename).stem == name:
                return Path(filename)
        raise FileNotFoundError(
            f"Config file '{name}.yaml' not found in any config subdirectory."
        )

    def resolve_ref(self, name: str) -> dict:
        """
        Resolve a $name cross-file reference.

        Strips the leading '$', searches all config subdirectories for
        <name>.yaml, and returns the raw (un-resolved) YAML dict.
        """
        if name.startswith("$"):
            name = name[1:]
        path = self.find_config_file(name)
        with path.open(encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _resolve_values(self, obj) -> dict:
        """
        Recursively walk a deserialized YAML structure.
        Any string value starting with '$' is replaced by the fully-resolved
        content of the referenced config file.
        """
        if isinstance(obj, str):
            if obj.startswith("$"):
                ref_dict = self.resolve_ref(obj)
                return self._resolve_values(ref_dict)
            return obj
        elif isinstance(obj, list):
            return [self._resolve_values(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: self._resolve_values(value) for key, value in obj.items()}
        else:
            return obj

    def load_config(self, path: Path | str) -> dict:
        """
        Load a YAML config file and recursively resolve all $name references.

        Arguments:
            path: Path to the YAML config file.
        Returns:
            Fully-resolved config dict.
        """
        path = Path(path)
        with path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        return self._resolve_values(raw)


def get_config_dir() -> str | None:
    config_dir_path = _validated_config_dir(CONFIG_DIR)
    return config_dir_path


def _validated_config_dir(config_dir: str | None) -> str | None:
    """
    Normalize config directory path and check if path exists.
    If not, throws error.
    """
    if config_dir is None:
        return None

    normalized = _normalize_config_dir(config_dir)
    if normalized is None:
        raise ValueError(f"Directory not found: {config_dir}")
    return str(normalized)


def _normalize_config_dir(config_dir: str) -> Path | None:
    """
    Normalizes config directory path by expanding tildes and setting
    path to absolute if not already (assume relative to project root).
    If path does not exist, return None (does not throw error).
    """
    if not config_dir.strip():
        return None
    raw_path = Path(config_dir).expanduser()
    if not raw_path.is_absolute():
        raw_path = Path(PROJECT_ROOT) / raw_path
    resolved = raw_path.resolve()
    if not resolved.exists() or not resolved.is_dir():
        return None
    return resolved
