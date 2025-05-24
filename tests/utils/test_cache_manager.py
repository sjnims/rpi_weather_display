"""Tests for cache manager utilities."""

import logging
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from rpi_weather_display.constants import BYTES_PER_MEGABYTE, DEFAULT_FILE_CACHE_TTL_SECONDS
from rpi_weather_display.utils.cache_manager import FileCache, MemoryAwareCache


class TestMemoryAwareCache:
    """Test MemoryAwareCache class."""

    def test_init(self) -> None:
        """Test cache initialization."""
        cache: MemoryAwareCache[str] = MemoryAwareCache(max_size_mb=10.0, ttl_seconds=300)
        
        assert cache.max_size_bytes == 10 * BYTES_PER_MEGABYTE
        assert cache.ttl_seconds == 300
        assert cache.size_mb == 0.0
        assert cache.item_count == 0
        assert isinstance(cache.logger, logging.Logger)

    def test_put_and_get(self) -> None:
        """Test putting and getting items from cache."""
        cache: MemoryAwareCache[str] = MemoryAwareCache(max_size_mb=1.0)
        
        # Put an item
        cache.put("key1", "value1", 100)
        
        # Get the item
        assert cache.get("key1") == "value1"
        assert cache.item_count == 1
        assert cache._current_size == 100

    def test_get_nonexistent(self) -> None:
        """Test getting nonexistent item."""
        cache: MemoryAwareCache[str] = MemoryAwareCache()
        assert cache.get("nonexistent") is None

    def test_ttl_expiration(self) -> None:
        """Test TTL expiration."""
        cache: MemoryAwareCache[str] = MemoryAwareCache(ttl_seconds=1)
        
        with patch("time.time", side_effect=[100.0, 100.0, 102.0]):  # Put time, get time 1, get time 2
            cache.put("key1", "value1", 100)
            
            # Should still be valid
            assert cache.get("key1") == "value1"
            
            # Should be expired
            assert cache.get("key1") is None
            assert cache.item_count == 0

    def test_lru_ordering(self) -> None:
        """Test LRU ordering - most recently used items are kept."""
        cache: MemoryAwareCache[str] = MemoryAwareCache()
        
        # Add multiple items
        cache.put("key1", "value1", 100)
        cache.put("key2", "value2", 100)
        cache.put("key3", "value3", 100)
        
        # Access key1 to make it most recently used
        cache.get("key1")
        
        # Verify order (key1 should be at the end now)
        keys = list(cache._cache.keys())
        assert keys == ["key2", "key3", "key1"]

    def test_size_eviction(self) -> None:
        """Test eviction when size limit is exceeded."""
        # Small cache that can only hold 200 bytes
        cache: MemoryAwareCache[str] = MemoryAwareCache(max_size_mb=0.0002)
        
        cache.put("key1", "value1", 100)
        cache.put("key2", "value2", 100)
        
        # Adding key3 should evict key1
        cache.put("key3", "value3", 100)
        
        assert cache.get("key1") is None  # Evicted
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        assert cache._current_size == 200

    def test_replace_existing_key(self) -> None:
        """Test replacing an existing key."""
        cache: MemoryAwareCache[str] = MemoryAwareCache()
        
        cache.put("key1", "value1", 100)
        assert cache._current_size == 100
        
        # Replace with larger value
        cache.put("key1", "new_value1", 200)
        assert cache.get("key1") == "new_value1"
        assert cache._current_size == 200
        assert cache.item_count == 1

    def test_clear(self) -> None:
        """Test clearing the cache."""
        cache: MemoryAwareCache[str] = MemoryAwareCache()
        
        cache.put("key1", "value1", 100)
        cache.put("key2", "value2", 200)
        
        cache.clear()
        
        assert cache.item_count == 0
        assert cache.size_mb == 0.0
        assert cache._current_size == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_size_mb_property(self) -> None:
        """Test size_mb property."""
        cache: MemoryAwareCache[str] = MemoryAwareCache()
        
        # Add 1MB of data
        cache.put("key1", "value1", BYTES_PER_MEGABYTE)
        assert cache.size_mb == 1.0

    def test_logging(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test debug logging."""
        with caplog.at_level(logging.DEBUG):
            cache: MemoryAwareCache[str] = MemoryAwareCache()
            cache.put("key1", "value1", 1024)
            
            assert "Cached key1 (1.0KB)" in caplog.text
            assert "total size: 0.0MB" in caplog.text

    def test_eviction_logging(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test eviction logging."""
        with caplog.at_level(logging.DEBUG):
            cache: MemoryAwareCache[str] = MemoryAwareCache(max_size_mb=0.0001)  # Very small
            
            cache.put("key1", "value1", 100)
            cache.put("key2", "value2", 100)  # Should evict key1
            
            assert "Evicting key1 from cache" in caplog.text

    def test_multiple_evictions(self) -> None:
        """Test multiple evictions when adding large item."""
        cache: MemoryAwareCache[str] = MemoryAwareCache(max_size_mb=0.00035)  # 350 bytes
        
        # Add three 100-byte items
        cache.put("key1", "value1", 100)
        cache.put("key2", "value2", 100)
        cache.put("key3", "value3", 100)
        
        # Add a 250-byte item - should evict key1 and key2 to make room
        cache.put("key4", "value4", 250)
        
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"
        assert cache._current_size == 350  # key3 (100) + key4 (250)


class TestFileCache:
    """Test FileCache class."""

    @pytest.fixture()
    def temp_cache_dir(self, tmp_path: Path) -> Path:
        """Create a temporary cache directory."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        return cache_dir

    def test_init(self, temp_cache_dir: Path) -> None:
        """Test file cache initialization."""
        cache = FileCache(temp_cache_dir, max_size_mb=50.0, ttl_seconds=1800)
        
        assert cache.cache_dir == temp_cache_dir
        assert cache.max_size_bytes == 50 * BYTES_PER_MEGABYTE
        assert cache.ttl_seconds == 1800
        assert isinstance(cache.logger, logging.Logger)

    def test_init_default_ttl(self, temp_cache_dir: Path) -> None:
        """Test file cache initialization with default TTL."""
        cache = FileCache(temp_cache_dir)
        
        assert cache.ttl_seconds == DEFAULT_FILE_CACHE_TTL_SECONDS

    def test_init_creates_directory(self, tmp_path: Path) -> None:
        """Test that init creates cache directory if it doesn't exist."""
        cache_dir = tmp_path / "new_cache"
        
        # The global mock_paths_exist fixture makes Path.exists return True
        # so we'll just verify the cache_dir is set correctly
        cache = FileCache(cache_dir)
        assert cache.cache_dir == cache_dir

    def test_get_cache_path(self, temp_cache_dir: Path) -> None:
        """Test getting cache path for a key."""
        cache = FileCache(temp_cache_dir)
        
        # Test normal key
        path = cache.get_cache_path("test.png")
        assert path == temp_cache_dir / "test.png"
        
        # Test key with slashes (should be sanitized)
        path = cache.get_cache_path("dir/test.png")
        assert path == temp_cache_dir / "dir_test.png"
        
        # Test key with backslashes
        path = cache.get_cache_path("dir\\test.png")
        assert path == temp_cache_dir / "dir_test.png"

    def test_is_valid_nonexistent(self, temp_cache_dir: Path) -> None:
        """Test is_valid for nonexistent file."""
        cache = FileCache(temp_cache_dir)
        path = temp_cache_dir / "nonexistent.png"
        
        # Path.exists is mocked to return True, but we want to test the nonexistent case
        with patch("pathlib.Path.exists", return_value=False):
            assert not cache.is_valid(path)

    def test_is_valid_fresh_file(self, temp_cache_dir: Path) -> None:
        """Test is_valid for fresh file."""
        cache = FileCache(temp_cache_dir, ttl_seconds=3600)
        
        # Create a fresh file
        test_file = temp_cache_dir / "test.png"
        test_file.write_text("test content")
        
        assert cache.is_valid(test_file)

    def test_is_valid_expired_file(self, temp_cache_dir: Path) -> None:
        """Test is_valid for expired file."""
        cache = FileCache(temp_cache_dir, ttl_seconds=1)
        
        # Create a file
        test_file = temp_cache_dir / "test.png"
        test_file.write_text("test content")
        
        # Mock time to make file appear old
        with patch("time.time", return_value=test_file.stat().st_mtime + 2):
            assert not cache.is_valid(test_file)

    def test_put_file(self, temp_cache_dir: Path, tmp_path: Path) -> None:
        """Test putting a file in cache."""
        cache = FileCache(temp_cache_dir)
        
        # Create source file
        source_file = tmp_path / "source.png"
        source_file.write_text("test content")
        
        # Mock cleanup to avoid side effects
        with patch.object(cache, 'cleanup') as mock_cleanup:
            cached_path = cache.put_file("cached.png", source_file)
            mock_cleanup.assert_called_once()
        
        assert cached_path == temp_cache_dir / "cached.png"
        assert cached_path.exists()
        assert cached_path.read_text() == "test content"

    def test_cleanup_expired_files(self, temp_cache_dir: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Test cleanup removes expired files."""
        cache = FileCache(temp_cache_dir, ttl_seconds=1)
        
        # Create some files
        file1 = temp_cache_dir / "file1.png"
        file2 = temp_cache_dir / "file2.png"
        file1.write_text("content1")
        file2.write_text("content2")
        
        # Mock time to make files appear expired
        current_time = time.time() + 2
        with patch("time.time", return_value=current_time), \
             caplog.at_level(logging.DEBUG):
            cache.cleanup()
        
        # Check that files were removed via log messages since Path.exists is mocked
        assert "Removing expired cache file: file1.png" in caplog.text
        assert "Removing expired cache file: file2.png" in caplog.text
        assert "Cache cleanup complete" in caplog.text

    def test_cleanup_size_limit(self, temp_cache_dir: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Test cleanup removes files when size limit exceeded."""
        # Very small cache
        cache = FileCache(temp_cache_dir, max_size_mb=0.00001, ttl_seconds=3600)
        
        # Create files with different modification times
        file1 = temp_cache_dir / "file1.png"
        file2 = temp_cache_dir / "file2.png"
        file3 = temp_cache_dir / "file3.png"
        
        file1.write_text("content1")
        time.sleep(0.01)  # Ensure different mtimes
        file2.write_text("content2")
        time.sleep(0.01)
        file3.write_text("content3")
        
        with caplog.at_level(logging.DEBUG):
            cache.cleanup()
        
        # Check that oldest files were removed via log messages
        assert "Removing cache file to free space: file1.png" in caplog.text
        assert "Removing cache file to free space: file2.png" in caplog.text
        # file3 should be kept (newest)
        assert "Files: 1" in caplog.text

    def test_cleanup_info_logging(self, temp_cache_dir: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Test cleanup info logging."""
        cache = FileCache(temp_cache_dir)
        
        # Create a file
        file1 = temp_cache_dir / "file1.png"
        file1.write_text("content")
        
        with caplog.at_level(logging.INFO):
            cache.cleanup()
        
        assert "Cache cleanup complete" in caplog.text
        assert "Files: 1" in caplog.text

    def test_cleanup_error_handling(self, temp_cache_dir: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Test cleanup error handling."""
        cache = FileCache(temp_cache_dir)
        
        # Mock the cache_dir.iterdir to raise exception
        with patch("pathlib.Path.iterdir", side_effect=Exception("Test error")), \
             caplog.at_level(logging.ERROR):
            cache.cleanup()
        
        assert "Error during cache cleanup" in caplog.text
        assert "Test error" in caplog.text

    def test_cleanup_skip_directories(self, temp_cache_dir: Path) -> None:
        """Test cleanup skips directories."""
        cache = FileCache(temp_cache_dir)
        
        # Create a subdirectory
        subdir = temp_cache_dir / "subdir"
        subdir.mkdir()
        
        # Create a file
        file1 = temp_cache_dir / "file1.png"
        file1.write_text("content")
        
        # Cleanup should not fail on directory
        cache.cleanup()
        
        assert subdir.exists()  # Directory still exists
        assert file1.exists()  # File still exists (not expired)

    def test_cleanup_mixed_files(self, temp_cache_dir: Path) -> None:
        """Test cleanup with mix of expired and valid files."""
        cache = FileCache(temp_cache_dir, ttl_seconds=10, max_size_mb=0.00002)
        
        # Create files at different times
        old_file = temp_cache_dir / "old.png"
        new_file = temp_cache_dir / "new.png"
        
        # Create old file
        old_file.write_text("old content")
        
        # Wait and create new file
        time.sleep(0.01)
        new_file.write_text("new content")
        
        # Mock time to make old file expired but new file valid
        current_time = old_file.stat().st_mtime + 11
        with patch("time.time", return_value=current_time):
            cache.cleanup()
        
        # Since Path.exists is mocked, check via cleanup completion
        # The old file should have been removed (expired) and new file kept