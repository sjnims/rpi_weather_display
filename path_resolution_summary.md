# Path Resolution in Raspberry Pi Weather Display

## Current Path Resolution Methods

### Client Component

1. **Using pathlib.Path for path manipulation**
   - `client/main.py`: Uses Path for configuration, tempfiles, and cache directories
   - `client/display.py`: Uses Path for image file handling
   
2. **Image Caching**
   - Temp directory paths with `Path(tempfile.gettempdir()) / CLIENT_CACHE_DIR_NAME`
   - Current image stored at `self.cache_dir / "current.png"`

3. **Command Line Arguments**
   - Uses `argparse` with `type=Path` for config arguments

### Server Component

1. **Directory Resolution Strategy in server/main.py**
   - Uses a `_find_directory` method to search for templates and static files
   - Tries multiple candidate paths in order:
     ```python
     self.template_dir = self._find_directory(
         "templates",
         [
             Path(__file__).parent.parent.parent.parent / "templates",
             Path(f"/etc/{CLIENT_CACHE_DIR_NAME}/templates"),
         ],
     )
     ```

2. **Temporary File Handling**
   - Uses Python's `tempfile` module with `NamedTemporaryFile` for image rendering

3. **Weather Icon Mapping in renderer.py**
   - Uses multiple search paths for icon mapping CSV:
     ```python
     possible_paths = [
         Path("owm_icon_map.csv"),  # Current working directory
         Path(__file__).parent.parent.parent.parent / "owm_icon_map.csv",  # Project root
     ]
     ```

### Common Components

1. **Configuration Loading**
   - `models/config.py`: Uses `from_yaml` method accepting both string and Path objects
   - Both client and server convert string paths to Path objects

2. **Logging**
   - `utils/logging.py`: Creates parent directories for log files using `Path.mkdir(parents=True)`
   - Uses Path to handle log file paths

3. **UVI Cache**
   - `renderer.py`: Uses Path for cache file of UV index data

4. **Path-Related Constants**
   - Various path constants are defined in the constants module
   - `CLIENT_CACHE_DIR_NAME` used consistently across modules

## Inconsistencies and Patterns

1. **Mixed Use of os.path and pathlib**
   - `os.path.join` in `config.py` for cache_dir default
   - `os.path.join` in test fixtures
   - `pathlib.Path` used for most other path operations

2. **Multiple Strategies for Finding Directories**
   - Server component uses `_find_directory` with candidates
   - Icon mapping uses direct list of possible paths

3. **Path Creation Patterns**
   - Relative pathing: `Path(__file__).parent.parent.parent.parent / "templates"`
   - Direct pathing: `Path(f"/etc/{CLIENT_CACHE_DIR_NAME}/templates")`

4. **Testing Approach**
   - `mock_paths_exist` fixture patches Path.exists
   - `test_config_path` fixture uses os.path.join

## Recommendations

1. Move toward consistent use of pathlib.Path
2. Create a centralized path resolution utility
3. Reduce the depth of relative paths (parent.parent.parent.parent)
4. Standardize the approach to finding project resources (templates, static files, etc.)
5. Use Path.resolve() for absolute path resolution