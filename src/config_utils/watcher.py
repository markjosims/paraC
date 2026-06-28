"""
Watchdog file watcher for config YAML files.

Sets a thread-safe threading.Event when YAML files change on disk.
Consumers poll _config_changed (e.g. in get_grammar()) to trigger rebuild.
"""

from __future__ import annotations

import threading
from pathlib import Path

from loguru import logger
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer, ObserverType


# Module-level tag set by the watcher thread, consumed by the main thread.
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
