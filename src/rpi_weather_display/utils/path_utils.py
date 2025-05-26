"""Path utility module for Raspberry Pi weather display.

Provides centralized path resolution and management utilities to ensure consistent
path handling across client and server components. This module abstracts platform-specific
path details and implements a consistent approach to resolving various types of paths
used throughout the application.
"""

import os
import tempfile
from pathlib import Path

from rpi_weather_display.constants import CLIENT_CACHE_DIR_NAME
from rpi_weather_display.exceptions import ConfigFileNotFoundError


class PathResolver:
    """Centralized utility for path resolution and management.

    Provides methods to resolve various types of paths consistently across
    the application, including configuration files, templates, static assets,
    cache directories, and temporary files.

    This class helps standardize path handling between client and server
    components, implement fallback strategies for resource directories,
    and abstract platform-specific path details.

    Attributes:
        project_root: The project root directory
        system_config_dir: System-wide configuration directory
        user_config_dir: User-specific configuration directory
        cache_dir: Application cache directory
        temp_dir: Temporary file directory
    """

    def __init__(self) -> None:
        """Initialize the path resolver.

        Sets up base directories using project structure detection.
        Determines project root, configuration directories, and cache locations.
        """
        # Determine project root directory
        # Paths are resolved from the location of this module
        self.project_root = self._find_project_root()

        # System configuration directory
        self.system_config_dir = Path(f"/etc/{CLIENT_CACHE_DIR_NAME}")

        # User configuration directory
        self.user_config_dir = Path.home() / f".config/{CLIENT_CACHE_DIR_NAME}"

        # Cache directory
        self.cache_dir = Path(tempfile.gettempdir()) / CLIENT_CACHE_DIR_NAME

        # Temporary directory
        self.temp_dir = Path(tempfile.gettempdir()) / f"{CLIENT_CACHE_DIR_NAME}-temp"

        # Ensure cache and temp directories exist
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        self.temp_dir.mkdir(exist_ok=True, parents=True)

    def _find_project_root(self) -> Path:
        """Find the project root directory.

        Uses the module location to determine the project root by climbing up
        the directory tree to find the src directory's parent.

        Returns:
            The project root directory path.
        """
        # Start from this module's directory
        current_dir = Path(__file__).parent

        # Climb up until we find the project root (parent of src dir)
        while current_dir.name != "src" and current_dir.parent != current_dir:
            current_dir = current_dir.parent

        # If we found the src directory, return its parent
        if current_dir.name == "src":
            return current_dir.parent

        # Fallback to the directory containing this module
        return Path(__file__).parent.parent.parent.parent

    def get_config_path(self, config_filename: str = "config.yaml") -> Path:
        """Get the path to a configuration file.

        Implements a search strategy for configuration files, checking multiple
        locations in priority order:
        1. Current working directory
        2. User's configuration directory
        3. System-wide configuration directory
        4. Project root directory

        Args:
            config_filename: Name of the configuration file

        Returns:
            Path to the configuration file if found, or the default path otherwise.
        """
        # Check multiple locations in priority order
        candidate_paths = [
            Path.cwd() / config_filename,
            self.user_config_dir / config_filename,
            self.system_config_dir / config_filename,
            self.project_root / config_filename,
        ]

        for path in candidate_paths:
            if path.exists():
                return path

        # Return the system config path as default
        return self.system_config_dir / config_filename

    def get_resource_path(self, resource_type: str, resource_name: str | None = None) -> Path:
        """Get path to a resource directory or file.

        Handles resources like templates, static files, and other assets.
        Implements a search strategy checking multiple locations in priority order.

        Args:
            resource_type: Type of resource (templates, static, etc.)
            resource_name: Optional specific resource filename within the directory

        Returns:
            Path to the resource directory or file.
        """
        # Check multiple locations in priority order
        candidate_paths = [
            self.project_root / resource_type,
            self.system_config_dir / resource_type,
        ]

        # Find the first existing directory
        for base_path in candidate_paths:
            if base_path.exists() and base_path.is_dir():
                if resource_name:
                    return base_path / resource_name
                return base_path

        # Return the project root path as default
        if resource_name:
            return self.project_root / resource_type / resource_name
        return self.project_root / resource_type

    def get_templates_dir(self) -> Path:
        """Get path to the templates directory.

        Returns:
            Path to the templates directory.
        """
        return self.get_resource_path("templates")

    def get_static_dir(self) -> Path:
        """Get path to the static assets directory.

        Returns:
            Path to the static assets directory.
        """
        return self.get_resource_path("static")

    def get_cache_file(self, filename: str) -> Path:
        """Get path to a cache file.

        Creates the cache directory if it doesn't exist.

        Args:
            filename: Name of the cache file

        Returns:
            Path to the cache file.
        """
        return self.cache_dir / filename

    def get_temp_file(self, filename: str | None = None, suffix: str | None = None) -> Path:
        """Get path to a temporary file.

        Creates a temporary file with an optional name or suffix.
        If no filename is provided, a unique name is generated.

        Args:
            filename: Optional specific filename
            suffix: Optional file suffix (like .png)

        Returns:
            Path to the temporary file.
        """
        if filename:
            return self.temp_dir / filename

        # Generate a unique temporary file
        temp_file = tempfile.NamedTemporaryFile(dir=self.temp_dir, suffix=suffix, delete=False)
        return Path(temp_file.name)

    def get_data_file(self, filename: str) -> Path:
        """Get path to a data file.

        Searches for data files (like CSV data) in multiple locations.

        Args:
            filename: Name of the data file

        Returns:
            Path to the data file if found, or the default path.
        """
        # Check multiple locations in priority order
        candidate_paths = [
            Path.cwd() / filename,
            self.project_root / filename,
            self.system_config_dir / filename,
        ]

        for path in candidate_paths:
            if path.exists():
                return path

        # Return project root as default
        return self.project_root / filename

    def normalize_path(self, path: str | Path) -> Path:
        """Convert a string path to a Path object.

        Ensures consistent Path object usage throughout the application.

        Args:
            path: String or Path object

        Returns:
            A Path object.
        """
        return Path(path) if isinstance(path, str) else path

    def ensure_dir_exists(self, path: str | Path) -> Path:
        """Ensure a directory exists, creating it if necessary.

        Args:
            path: Directory path

        Returns:
            Path to the directory.
        """
        dir_path = self.normalize_path(path)
        dir_path.mkdir(exist_ok=True, parents=True)
        return dir_path

    def get_bin_path(self, command: str) -> Path:
        """Get the full path to a system binary or command.

        Used for resolving paths to system utilities like shutdown, iwconfig, etc.

        Args:
            command: Command name

        Returns:
            Path to the command binary.
        """
        # Common locations to check
        common_paths = [
            "/usr/bin",
            "/usr/sbin",
            "/bin",
            "/sbin",
            "/usr/local/bin",
            "/usr/local/sbin",
        ]

        # Check if command has a hardcoded path in constants
        # First, look for an uppercase version of the command
        command_upper = command.upper() + "_PATH"
        if hasattr(const := __import__("rpi_weather_display.constants").constants, command_upper):
            return Path(getattr(const, command_upper))

        # Next, check the more specific format if available
        command_path = command.replace("-", "_") + "_path"
        if hasattr(const := __import__("rpi_weather_display.constants").constants, command_path):
            return Path(getattr(const, command_path))

        # Search common paths
        for base_path in common_paths:
            full_path = Path(base_path) / command
            if full_path.exists() and os.access(full_path, os.X_OK):
                return full_path

        # Default to the command name itself, letting PATH resolve it
        return Path(command)


# Create a global instance for easy import
path_resolver = PathResolver()


def validate_config_path(config_path: str | Path | None = None) -> Path:
    """Validate and resolve the configuration file path.
    
    Checks if the provided config path exists, and if not, searches for a config
    file in standard locations. Provides informative error messages if the config
    file cannot be found.
    
    Args:
        config_path: Optional path to configuration file
        
    Returns:
        Resolved Path to the configuration file
        
    Raises:
        SystemExit: If the configuration file cannot be found (in production mode)
                    Does not exit in test environments (when 'pytest' is detected)
    """
    # Resolve config path
    if config_path is None:
        # Use path resolver to find config file
        resolved_path = path_resolver.get_config_path("config.yaml")
    else:
        # User provided a specific path, normalize it
        resolved_path = path_resolver.normalize_path(config_path)
    
    # Check if config file exists
    if not resolved_path.exists():
        # Prepare search locations for error message
        search_locations = []
        if config_path is None:
            search_locations = [
                str(Path.cwd() / 'config.yaml'),
                str(path_resolver.user_config_dir / 'config.yaml'),
                str(path_resolver.system_config_dir / 'config.yaml'),
                str(path_resolver.project_root / 'config.yaml')
            ]
        
        # Raise appropriate exception
        error_details = {
            "path": str(resolved_path),
            "cwd": str(Path.cwd()),
            "searched_locations": search_locations if search_locations else None
        }
        
        error_msg = f"Configuration file not found: {resolved_path}"
        if search_locations:
            error_msg += "\n\nSearched in the following locations:\n"
            error_msg += "\n".join(f"  - {loc}" for loc in search_locations)
        
        raise ConfigFileNotFoundError(error_msg, error_details)
    
    return resolved_path
