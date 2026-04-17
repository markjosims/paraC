"""
Watchdog file watcher for the Flask web app.

Invalidates the GrammarRegistry cache when YAML config files change on disk,
so the next request rebuilds the registry from fresh configs.
"""

from __future__ import annotations

from pathlib import Path

from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer, ObserverType


def start_watcher(config_dir: str, cache: dict) -> ObserverType:
    """Start a watchdog observer that clears *cache* when YAML files change."""
    handler = _YamlChangeHandler(config_dir, cache)
    observer = Observer()
    observer.schedule(handler, str(config_dir), recursive=True)
    observer.daemon = True
    observer.start()
    return observer


class _YamlChangeHandler(FileSystemEventHandler):
    def __init__(self, config_dir: str, cache: dict):
        self.config_dir = str(Path(config_dir))
        self.cache = cache

    def _invalidate(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        if event.src_path.endswith((".yaml", ".yml")):
            self.cache.pop(self.config_dir, None)

    on_modified = _invalidate  # type: ignore[assignment]
    on_created = _invalidate  # type: ignore[assignment]
    on_deleted = _invalidate  # type: ignore[assignment]
