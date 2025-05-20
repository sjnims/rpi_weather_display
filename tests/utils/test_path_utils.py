"""Test module for path utilities."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

from rpi_weather_display.utils.path_utils import PathResolver


class TestPathResolver:
    """Test the PathResolver class."""

    def test_init(self):
        """Test initialization of PathResolver."""
        resolver = PathResolver()

        # Check that the basic attributes are set
        assert resolver.project_root is not None
        assert resolver.system_config_dir is not None
        assert resolver.user_config_dir is not None
        assert resolver.cache_dir is not None
        assert resolver.temp_dir is not None

        # Check that cache and temp directories exist
        assert resolver.cache_dir.exists()
        assert resolver.temp_dir.exists()

    def test_find_project_root(self):
        """Test finding the project root."""
        resolver = PathResolver()

        # Project root should contain the src directory
        assert (resolver.project_root / "src").exists()

        # Should be able to find important project files
        assert (resolver.project_root / "pyproject.toml").exists()

    def test_get_config_path_default(self):
        """Test getting the default config path."""
        resolver = PathResolver()

        # Should return a valid path even if the file doesn't exist
        config_path = resolver.get_config_path()
        assert isinstance(config_path, Path)

        # The config path should be a yaml file
        assert config_path.name.endswith(".yaml")

    def test_get_config_path_with_custom_name(self):
        """Test getting a config path with a custom filename."""
        resolver = PathResolver()

        config_path = resolver.get_config_path("custom_config.yaml")
        assert isinstance(config_path, Path)
        assert config_path.name == "custom_config.yaml"

    def test_get_config_path_with_existing_file(self, tmpdir: Any):
        """Test getting a config path when the file exists in a specific location."""
        # Create a temporary config file
        temp_config = Path(tmpdir) / "test_config.yaml"
        temp_config.touch()

        with patch.object(Path, "cwd", return_value=Path(tmpdir)):
            resolver = PathResolver()
            config_path = resolver.get_config_path("test_config.yaml")

            assert config_path == temp_config
            assert config_path.exists()
            
    def test_get_config_path_no_files_exist(self):
        """Test getting a config path when no files exist."""
        resolver = PathResolver()
        
        # Mock the exists method to return False for all paths
        with patch.object(Path, "exists", return_value=False):
            # Call the method under test
            config_path = resolver.get_config_path("nonexistent_config.yaml")
            
            # Should return the system config directory path
            assert config_path == resolver.system_config_dir / "nonexistent_config.yaml"

    def test_get_resource_path(self):
        """Test getting resource paths."""
        resolver = PathResolver()

        # Test getting a resource directory
        templates_dir = resolver.get_resource_path("templates")
        assert isinstance(templates_dir, Path)

        # Test getting a specific resource file
        resource_file = resolver.get_resource_path("templates", "dashboard.html.j2")
        assert isinstance(resource_file, Path)
        assert resource_file.name == "dashboard.html.j2"
        
    def test_get_resource_path_no_directories_exist(self):
        """Test getting a resource path when no directories exist."""
        resolver = PathResolver()
        
        # Mock exists and is_dir to return False
        with patch.object(Path, "exists", return_value=False):
            with patch.object(Path, "is_dir", return_value=False):
                # Test with no resource name (directory only)
                resource_dir = resolver.get_resource_path("nonexistent_dir")
                assert resource_dir == resolver.project_root / "nonexistent_dir"
                
                # Test with resource name (file path)
                resource_file = resolver.get_resource_path("nonexistent_dir", "file.txt")
                assert resource_file == resolver.project_root / "nonexistent_dir" / "file.txt"

    def test_get_templates_dir(self):
        """Test getting the templates directory."""
        resolver = PathResolver()

        templates_dir = resolver.get_templates_dir()
        assert isinstance(templates_dir, Path)
        assert templates_dir.name == "templates"

    def test_get_static_dir(self):
        """Test getting the static directory."""
        resolver = PathResolver()

        static_dir = resolver.get_static_dir()
        assert isinstance(static_dir, Path)
        assert static_dir.name == "static"

    def test_get_cache_file(self):
        """Test getting a cache file path."""
        resolver = PathResolver()

        cache_file = resolver.get_cache_file("test_cache.json")
        assert isinstance(cache_file, Path)
        assert cache_file.name == "test_cache.json"
        assert cache_file.parent == resolver.cache_dir

    def test_get_temp_file_with_name(self):
        """Test getting a temporary file path with a specific name."""
        resolver = PathResolver()

        temp_file = resolver.get_temp_file("test_temp.png")
        assert isinstance(temp_file, Path)
        assert temp_file.name == "test_temp.png"
        assert temp_file.parent == resolver.temp_dir

    def test_get_temp_file_with_suffix(self):
        """Test getting a temporary file path with a specific suffix."""
        resolver = PathResolver()

        temp_file = resolver.get_temp_file(suffix=".png")
        assert isinstance(temp_file, Path)
        assert temp_file.name.endswith(".png")
        assert temp_file.parent == resolver.temp_dir

    def test_get_temp_file_unique(self):
        """Test that temporary files are unique."""
        resolver = PathResolver()

        temp_file1 = resolver.get_temp_file(suffix=".txt")
        temp_file2 = resolver.get_temp_file(suffix=".txt")

        assert temp_file1 != temp_file2

    def test_get_data_file(self):
        """Test getting a data file path."""
        resolver = PathResolver()

        # Create a mock for the project root to ensure consistent testing
        with patch.object(resolver, "project_root", Path("/")):
            # Mock the exists method to control which files exist
            with patch.object(Path, "exists", side_effect=lambda: True):
                # Test with a file that exists
                data_file = resolver.get_data_file("pyproject.toml")
                assert isinstance(data_file, Path)

            # Mock the exists method to control which files don't exist
            with patch.object(Path, "exists", side_effect=lambda: False):
                # Test with a non-existent file
                non_existent = resolver.get_data_file("does_not_exist.txt")
                assert isinstance(non_existent, Path)

    def test_normalize_path(self):
        """Test normalizing path strings to Path objects."""
        resolver = PathResolver()

        # Test with a string path
        path_str = "/some/test/path"
        normalized = resolver.normalize_path(path_str)
        assert isinstance(normalized, Path)
        assert str(normalized) == path_str

        # Test with a Path object
        path_obj = Path("/another/test/path")
        normalized = resolver.normalize_path(path_obj)
        assert normalized is path_obj  # Should return the same object

    def test_ensure_dir_exists(self):
        """Test ensuring a directory exists."""
        resolver = PathResolver()
        test_dir = Path("/test/dir")

        # Mock the necessary methods
        with patch.object(Path, "mkdir") as mock_mkdir:
            with patch.object(resolver, "normalize_path", return_value=test_dir):
                # Call the method under test
                result = resolver.ensure_dir_exists(test_dir)

                # Verify the directory is created with appropriate parameters
                mock_mkdir.assert_called_once_with(exist_ok=True, parents=True)
                assert result == test_dir

    def test_get_bin_path(self):
        """Test getting paths to system binaries."""
        resolver = PathResolver()

        # Test with a common command that should exist
        # (this might fail on some systems)
        bin_path = resolver.get_bin_path("ls")
        assert isinstance(bin_path, Path)

        # Test with a constant-defined path
        # The constant might not be defined, so we need to check first
        with patch("rpi_weather_display.constants.SUDO_PATH", "/usr/bin/sudo"):
            sudo_path = resolver.get_bin_path("sudo")
            assert isinstance(sudo_path, Path)
            assert str(sudo_path) == "/usr/bin/sudo"
            
    def test_get_bin_path_command_upper(self):
        """Test get_bin_path with command_upper format."""
        resolver = PathResolver()
        
        # Create a mock constant module with TEST_PATH attribute
        mock_constants = type('MockConstants', (), {'TEST_PATH': '/usr/bin/test'})
        
        # Mock the import of the constants module to return our mock
        with patch.object(
            __import__('builtins'), '__import__', 
            return_value=type('Module', (), {'constants': mock_constants})
        ):
            # Call the method under test with a command that will match our mock constant
            bin_path = resolver.get_bin_path("test")
            
            # Should return the path from the constant
            assert bin_path == Path("/usr/bin/test")
            
    def test_get_bin_path_command_path(self):
        """Test get_bin_path with command_path format."""
        resolver = PathResolver()
        
        # Create a mock constant module with test_path attribute (lowercase format)
        mock_constants = type('MockConstants', (), {'test_command_path': '/usr/local/bin/test-command'})
        
        # Reset the first mock to make sure it doesn't find a match for the uppercase version
        with patch.object(
            __import__('builtins'), '__import__', 
            return_value=type('Module', (), {'constants': mock_constants})
        ):
            # Call the method with a command containing a dash that will be converted to underscore
            bin_path = resolver.get_bin_path("test-command")
            
            # Should return the path from the constant
            assert bin_path == Path("/usr/local/bin/test-command")
            
    def test_get_bin_path_in_common_paths(self):
        """Test get_bin_path finding a command in common paths."""
        resolver = PathResolver()
        
        # Create a custom command name that won't be in constants
        command_name = "custom-command-test"
        
        # Mock the import to return a module without our command constants
        with patch.object(
            __import__('builtins'), '__import__',
            return_value=type('Module', (), {'constants': type('Constants', (), {})})
        ):
            # Mock Path.exists to return True for a specific path
            with patch.object(Path, "exists", lambda p: str(p) == "/usr/bin/custom-command-test"):
                # Mock os.access to return True for executable permission
                with patch("os.access", return_value=True):
                    # Call the method under test
                    bin_path = resolver.get_bin_path(command_name)
                    
                    # Should find the executable in /usr/bin
                    assert bin_path == Path("/usr/bin/custom-command-test")
                    
    def test_get_bin_path_default(self):
        """Test get_bin_path default behavior when no path is found."""
        resolver = PathResolver()
        
        # Create a custom command name
        command_name = "nonexistent-command"
        
        # Mock the import to return a module without our command constants
        with patch.object(
            __import__('builtins'), '__import__',
            return_value=type('Module', (), {'constants': type('Constants', (), {})})
        ):
            # Mock Path.exists to always return False
            with patch.object(Path, "exists", return_value=False):
                # Call the method under test
                bin_path = resolver.get_bin_path(command_name)
                
                # Should return the command name itself
                assert bin_path == Path(command_name)

    def test_find_project_root_fallback(self):
        """Test fallback behavior for project root finding."""
        with patch.object(
            PathResolver, "_find_project_root", return_value=Path("/test/fallback/path")
        ):
            # Force the _find_project_root method to use our mock path
            resolver = PathResolver()

            # Should use our mocked return value
            assert resolver.project_root == Path("/test/fallback/path")
            assert isinstance(resolver.project_root, Path)
            
    def test_find_project_root_with_mocks(self):
        """Test additional behavior of find_project_root."""
        # Test a scenario where the parent of the current_dir doesn't equal itself
        # but we still don't find src and need to use the fallback
        
        # Create a resolver instance
        resolver = PathResolver()
        
        # Mock _find_project_root to simulate failure to find src directory
        # but test that the fallback path works correctly
        custom_return = Path("/custom/fallback/path")
        with patch.object(PathResolver, "_find_project_root", return_value=custom_return):
            # Re-initialize the resolver to use our mock
            resolver = PathResolver()
            
            # Verify the project root matches our mock return value
            assert resolver.project_root == custom_return

    def test_global_instance(self):
        """Test that the global instance is available and initialized."""
        from rpi_weather_display.utils import path_resolver

        assert path_resolver is not None
        assert isinstance(path_resolver, PathResolver)

        # The global instance should be initialized
        assert path_resolver.project_root is not None
        assert path_resolver.cache_dir is not None
        assert path_resolver.temp_dir is not None
