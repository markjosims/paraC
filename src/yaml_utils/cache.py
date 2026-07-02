import os

import pynini
from loguru import logger

from src.constants import get_yaml_dir
from functools import lru_cache, wraps
from glob import glob

CACHE_DIR = os.path.join(get_yaml_dir(), ".cache")
_SYMS_PATH = os.path.join(CACHE_DIR, "symbol_table.syms")


def _fst_path(kind: str, name: str, fst_kind: str) -> str:
    return os.path.join(CACHE_DIR, kind, f"{name}.{fst_kind}.fst")


def _is_valid(path: str, *source_dirs: str) -> bool:

    if not os.path.exists(path):
        return False
    mtime = os.path.getmtime(path)
    return all(mtime >= os.path.getmtime(d) for d in source_dirs)


def is_syms_cache_valid(*source_dirs: str) -> bool:
    return _is_valid(_SYMS_PATH, *source_dirs)


def is_fst_cache_valid(kind: str, name: str, fst_kind: str, *source_dirs: str) -> bool:
    return _is_valid(_fst_path(kind, name, fst_kind), *source_dirs)


def save_symbol_table(syms: pynini.SymbolTable) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    syms.write(_SYMS_PATH)


def load_symbol_table() -> pynini.SymbolTable | None:
    if not os.path.exists(_SYMS_PATH):
        return None
    try:
        return pynini.SymbolTable.read(_SYMS_PATH)
    except Exception:
        logger.warning(f"Failed to load symbol table from {_SYMS_PATH}")
        return None


def save_fst(kind: str, name: str, fst_kind: str, fst: pynini.Fst) -> None:
    path = _fst_path(kind, name, fst_kind)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fst.write(path)


def load_fst(kind: str, name: str, fst_kind: str) -> pynini.Fst | None:
    path = _fst_path(kind, name, fst_kind)
    if not os.path.exists(path):
        return None
    try:
        return pynini.Fst.read(path)
    except Exception:
        logger.warning(f"Failed to load FST from {path}")
        return None


def max_directory_mtime(directory: str):
    yaml_glob = glob(os.path.join(directory, "*.yaml"))
    csv_glob = glob(os.path.join(directory, "*.csv"))
    return max(os.path.getmtime(f) for f in yaml_glob + csv_glob + [directory])


def observed_cache(directories: list[str]):
    """
    Decorator to invalidate an entire function cache when file
    inside the specified directories changes.
    """

    directory_mtimes = {
        directory: max_directory_mtime(directory) for directory in directories
    }

    def decorator(func):
        cached_func = lru_cache(maxsize=128)(func)

        @wraps(func)
        def wrapper(*args, **kwargs):

            clear_cache = False
            for directory, mtime in directory_mtimes.items():
                new_mtime = max_directory_mtime(directory)
                if new_mtime > mtime:
                    directory_mtimes[directory] = new_mtime
                    clear_cache = True
            if clear_cache:
                logger.info(
                    f"Invalidated cache for {func.__name__}, rebuilding output..."
                )
                cached_func.cache_clear()

            return cached_func(*args, **kwargs)

        # Expose cache operations upstream (allows manual clearing if needed)
        wrapper.cache_clear = cached_func.cache_clear
        wrapper.cache_info = cached_func.cache_info
        return wrapper

    return decorator
