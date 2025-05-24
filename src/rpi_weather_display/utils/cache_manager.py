"""Memory-aware caching utilities with size limits.

Provides cache management with memory constraints to prevent excessive
memory usage, especially important for resource-constrained environments.
"""

import logging
import time
from collections import OrderedDict
from pathlib import Path
from typing import Generic, TypeVar

from rpi_weather_display.constants import (
    BYTES_PER_KILOBYTE,
    BYTES_PER_MEGABYTE,
    DEFAULT_CACHE_TTL_SECONDS,
    DEFAULT_FILE_CACHE_SIZE_MB,
    DEFAULT_FILE_CACHE_TTL_SECONDS,
    DEFAULT_MEMORY_CACHE_SIZE_MB,
)
from rpi_weather_display.utils.error_utils import get_error_location

T = TypeVar("T")


class MemoryAwareCache(Generic[T]):
    """LRU cache with memory size limits.

    Implements a Least Recently Used (LRU) cache that tracks the memory
    size of cached items and evicts old items when size limits are exceeded.

    Attributes:
        max_size_bytes: Maximum cache size in bytes
        ttl_seconds: Time-to-live for cache entries in seconds
        _cache: OrderedDict storing cache entries
        _sizes: Dictionary tracking size of each entry
        _timestamps: Dictionary tracking insertion time of each entry
        _current_size: Current total size of cached items
        logger: Logger instance
    """

    def __init__(
        self,
        max_size_mb: float = DEFAULT_MEMORY_CACHE_SIZE_MB,
        ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    ) -> None:
        """Initialize the cache.

        Args:
            max_size_mb: Maximum cache size in megabytes
            ttl_seconds: Time-to-live for cache entries in seconds
        """
        self.max_size_bytes = int(max_size_mb * BYTES_PER_MEGABYTE)
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, T] = OrderedDict()
        self._sizes: dict[str, int] = {}
        self._timestamps: dict[str, float] = {}
        self._current_size = 0
        self.logger = logging.getLogger(__name__)

    def get(self, key: str) -> T | None:
        """Get an item from the cache.

        Args:
            key: Cache key

        Returns:
            Cached item or None if not found/expired
        """
        if key not in self._cache:
            return None

        # Check if expired
        if time.time() - self._timestamps[key] > self.ttl_seconds:
            self._remove(key)
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        return self._cache[key]

    def put(self, key: str, value: T, size_bytes: int) -> None:
        """Put an item in the cache.

        Args:
            key: Cache key
            value: Item to cache
            size_bytes: Size of the item in bytes
        """
        # Remove if already exists
        if key in self._cache:
            self._remove(key)

        # Evict items if necessary
        while self._current_size + size_bytes > self.max_size_bytes and self._cache:
            self._evict_oldest()

        # Add new item
        self._cache[key] = value
        self._sizes[key] = size_bytes
        self._timestamps[key] = time.time()
        self._current_size += size_bytes

        self.logger.debug(
            f"Cached {key} ({size_bytes / BYTES_PER_KILOBYTE:.1f}KB), "
            f"total size: {self._current_size / BYTES_PER_MEGABYTE:.1f}MB"
        )

    def _remove(self, key: str) -> None:
        """Remove an item from the cache.

        Args:
            key: Cache key to remove
        """
        if key in self._cache:
            del self._cache[key]
            self._current_size -= self._sizes[key]
            del self._sizes[key]
            del self._timestamps[key]

    def _evict_oldest(self) -> None:
        """Evict the least recently used item."""
        if self._cache:
            key = next(iter(self._cache))
            self.logger.debug(f"Evicting {key} from cache")
            self._remove(key)

    def clear(self) -> None:
        """Clear all cached items."""
        self._cache.clear()
        self._sizes.clear()
        self._timestamps.clear()
        self._current_size = 0

    @property
    def size_mb(self) -> float:
        """Get current cache size in megabytes."""
        return self._current_size / BYTES_PER_MEGABYTE

    @property
    def item_count(self) -> int:
        """Get number of items in cache."""
        return len(self._cache)


class FileCache:
    """File-based cache with size limits and TTL.

    Manages cached files on disk with automatic cleanup based on
    size limits and time-to-live settings.

    Attributes:
        cache_dir: Directory for cached files
        max_size_mb: Maximum total size of cached files
        ttl_seconds: Time-to-live for cached files
        logger: Logger instance
    """

    def __init__(
        self,
        cache_dir: Path,
        max_size_mb: float = DEFAULT_FILE_CACHE_SIZE_MB,
        ttl_seconds: int = DEFAULT_FILE_CACHE_TTL_SECONDS,
    ) -> None:
        """Initialize file cache.

        Args:
            cache_dir: Directory for cached files
            max_size_mb: Maximum total size in megabytes
            ttl_seconds: Time-to-live in seconds
        """
        self.cache_dir = cache_dir
        self.max_size_bytes = int(max_size_mb * BYTES_PER_MEGABYTE)
        self.ttl_seconds = ttl_seconds
        self.logger = logging.getLogger(__name__)

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cache_path(self, key: str) -> Path:
        """Get the path for a cache key.

        Args:
            key: Cache key

        Returns:
            Path to the cached file
        """
        # Sanitize key for filesystem
        safe_key = key.replace("/", "_").replace("\\", "_")
        return self.cache_dir / safe_key

    def is_valid(self, path: Path) -> bool:
        """Check if a cached file is still valid.

        Args:
            path: Path to cached file

        Returns:
            True if file exists and is not expired
        """
        if not path.exists():
            return False

        # Check age
        age = time.time() - path.stat().st_mtime
        return age < self.ttl_seconds

    def cleanup(self) -> None:
        """Clean up old and oversized cache entries."""
        try:
            # Get all cache files with stats
            cache_files: list[tuple[Path, int, float]] = []
            total_size = 0

            for path in self.cache_dir.iterdir():
                if path.is_file():
                    stat = path.stat()
                    age = time.time() - stat.st_mtime

                    # Remove expired files
                    if age > self.ttl_seconds:
                        self.logger.debug(f"Removing expired cache file: {path.name}")
                        path.unlink()
                        continue

                    cache_files.append((path, stat.st_size, stat.st_mtime))
                    total_size += stat.st_size

            # Sort by modification time (oldest first)
            cache_files.sort(key=lambda x: x[2])

            # Remove oldest files if over size limit
            while total_size > self.max_size_bytes and cache_files:
                path, size, _ = cache_files.pop(0)
                self.logger.debug(
                    f"Removing cache file to free space: {path.name} "
                    f"({size / BYTES_PER_KILOBYTE:.1f}KB)"
                )
                path.unlink()
                total_size -= size

            self.logger.info(
                f"Cache cleanup complete. Size: {total_size / BYTES_PER_MEGABYTE:.1f}MB, "
                f"Files: {len(cache_files)}"
            )

        except Exception as e:
            error_location = get_error_location()
            self.logger.error(f"Error during cache cleanup [{error_location}]: {e}")

    def put_file(self, key: str, source_path: Path) -> Path:
        """Copy a file into the cache.

        Args:
            key: Cache key
            source_path: Path to source file

        Returns:
            Path to cached file
        """
        import shutil

        cache_path = self.get_cache_path(key)
        shutil.copy2(source_path, cache_path)

        # Trigger cleanup
        self.cleanup()

        return cache_path
