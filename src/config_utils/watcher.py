"""
Watchdog file watcher for the Streamlit app.

Signals that YAML config files have changed on disk so the next Streamlit
rerun can rebuild the config walker and grammar from fresh state.

Design note: watchdog runs in a daemon thread; Streamlit session state is
only accessible from the main script thread.  The watcher therefore sets a
thread-safe threading.Event flag rather than touching st.session_state
directly.  Call check_and_apply_invalidation() at the top of each page
rerun to act on the flag from the main thread.

BUG: `check_and_apply_invalidation` does not seem to be triggering correctly
"""

from __future__ import annotations

import threading
from pathlib import Path

from loguru import logger
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer, ObserverType
import streamlit as st


# Module-level flag set by the watcher thread, consumed by the main thread.
_config_changed = threading.Event()


def start_watcher(config_dir: str) -> ObserverType:
    """Start a watchdog observer that signals _config_changed on YAML edits."""
    logger.info(f"Starting config watcher for directory: {config_dir}")
    handler = _YamlChangeHandler(config_dir)
    observer = Observer()
    observer.schedule(handler, str(config_dir), recursive=True)
    observer.daemon = True
    observer.start()
    return observer


def check_and_apply_invalidation(invalidate_keys: list[str]) -> bool:
    """
    Call from the main Streamlit thread at the top of each rerun.
    If the watcher flagged a change, clears the given session state keys
    and returns True (caller should st.rerun() to reload).
    Returns False if no change was detected.
    """

    logger.info(f"Invalidation check: {invalidate_keys}")

    if _config_changed.is_set():
        _config_changed.clear()
        for key in invalidate_keys:
            st.session_state.pop(key, None)
        logger.info("Config change detected — invalidated: %s", invalidate_keys)
        return True
    return False


class _YamlChangeHandler(FileSystemEventHandler):
    def __init__(self, config_dir: str):
        logger.info(f"File watcher active for: {config_dir}")
        self.config_dir = str(Path(config_dir))

    def _invalidate(self, event: FileSystemEvent) -> None:
        logger.debug(f"File system event: {event}")
        if event.is_directory:
            return
        if event.src_path.endswith((".yaml", ".yml", ".csv")):
            logger.info(f"Config change detected: {event.src_path}")
            _config_changed.set()

    on_modified = _invalidate  # type: ignore[assignment]
    on_created = _invalidate  # type: ignore[assignment]
    on_deleted = _invalidate  # type: ignore[assignment]
