"""File system abstraction for the Raspberry Pi weather display.

Provides a consistent interface for file system operations across the application,
including file reading/writing, directory operations, and error handling. This
module works with path_utils.py to provide a comprehensive file system abstraction
layer that standardizes file access patterns throughout the project.
"""

import json
import os
import shutil
from pathlib import Path
from typing import Any, TypeVar

from rpi_weather_display.utils.path_utils import path_resolver

# Type aliases for clarity and documentation
PathLike = str | Path
JsonData = dict[str, Any] | list[Any]
FileContent = str | bytes
T = TypeVar("T")  # Generic type for type-preserving operations


def read_text(file_path: PathLike) -> str:
    """Read text content from a file.

    Provides a consistent interface for reading text from files, automatically
    handling path normalization and common error cases with appropriate exceptions.

    Args:
        file_path: Path to the file (string or Path object)

    Returns:
        The text content of the file

    Raises:
        FileNotFoundError: If the file does not exist
        PermissionError: If the file cannot be read due to permissions
        UnicodeDecodeError: If the file content cannot be decoded as text
    """
    normalized_path = path_resolver.normalize_path(file_path)
    with open(normalized_path, encoding="utf-8") as f:
        return f.read()


def read_bytes(file_path: PathLike) -> bytes:
    """Read binary content from a file.

    Provides a consistent interface for reading binary data from files, with
    standardized error handling and path normalization.

    Args:
        file_path: Path to the file (string or Path object)

    Returns:
        The binary content of the file

    Raises:
        FileNotFoundError: If the file does not exist
        PermissionError: If the file cannot be read due to permissions
    """
    normalized_path = path_resolver.normalize_path(file_path)
    with open(normalized_path, "rb") as f:
        return f.read()


def read_json(file_path: PathLike) -> JsonData:
    """Read and parse JSON content from a file.

    Reads a file and parses its content as JSON, providing a consistent
    interface for handling JSON data files with appropriate error handling.

    Args:
        file_path: Path to the JSON file (string or Path object)

    Returns:
        The parsed JSON data as a dictionary or list

    Raises:
        FileNotFoundError: If the file does not exist
        json.JSONDecodeError: If the file content is not valid JSON
        PermissionError: If the file cannot be read due to permissions
    """
    normalized_path = path_resolver.normalize_path(file_path)
    with open(normalized_path, encoding="utf-8") as f:
        return json.load(f)


def read_lines(file_path: PathLike) -> list[str]:
    """Read lines from a text file.

    Reads a text file and returns its content as a list of lines, with
    standardized error handling and path normalization.

    Args:
        file_path: Path to the file (string or Path object)

    Returns:
        List of lines from the file

    Raises:
        FileNotFoundError: If the file does not exist
        PermissionError: If the file cannot be read due to permissions
        UnicodeDecodeError: If the file content cannot be decoded as text
    """
    normalized_path = path_resolver.normalize_path(file_path)
    with open(normalized_path, encoding="utf-8") as f:
        return f.readlines()


def write_text(file_path: PathLike, content: str, make_dirs: bool = True) -> None:
    """Write text content to a file.

    Provides a consistent interface for writing text to files, automatically
    handling path normalization and directory creation if needed.

    Args:
        file_path: Path to the file (string or Path object)
        content: Text content to write
        make_dirs: Whether to create parent directories if they don't exist

    Raises:
        FileNotFoundError: If the parent directory does not exist and make_dirs is False
        PermissionError: If the file cannot be written due to permissions
    """
    normalized_path = path_resolver.normalize_path(file_path)

    if make_dirs:
        ensure_dir_exists(normalized_path.parent)

    with open(normalized_path, "w", encoding="utf-8") as f:
        f.write(content)


def write_bytes(file_path: PathLike, content: bytes, make_dirs: bool = True) -> None:
    """Write binary content to a file.

    Provides a consistent interface for writing binary data to files, with
    standardized error handling, path normalization, and optional directory creation.

    Args:
        file_path: Path to the file (string or Path object)
        content: Binary content to write
        make_dirs: Whether to create parent directories if they don't exist

    Raises:
        FileNotFoundError: If the parent directory does not exist and make_dirs is False
        PermissionError: If the file cannot be written due to permissions
    """
    normalized_path = path_resolver.normalize_path(file_path)

    if make_dirs:
        ensure_dir_exists(normalized_path.parent)

    with open(normalized_path, "wb") as f:
        f.write(content)


def write_json(
    file_path: PathLike, data: JsonData, make_dirs: bool = True, indent: int = 2
) -> None:
    """Write data as JSON to a file.

    Serializes data to JSON format and writes it to a file, providing a consistent
    interface for handling JSON data files with appropriate error handling and
    formatting options.

    Args:
        file_path: Path to the output JSON file (string or Path object)
        data: Data to be serialized as JSON (dict or list)
        make_dirs: Whether to create parent directories if they don't exist
        indent: Number of spaces for indentation in the JSON output

    Raises:
        FileNotFoundError: If the parent directory does not exist and make_dirs is False
        PermissionError: If the file cannot be written due to permissions
        TypeError: If the data contains objects that cannot be serialized to JSON
    """
    normalized_path = path_resolver.normalize_path(file_path)

    if make_dirs:
        ensure_dir_exists(normalized_path.parent)

    with open(normalized_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent)


def append_text(file_path: PathLike, content: str, make_dirs: bool = True) -> None:
    """Append text content to a file.

    Provides a consistent interface for appending text to files, automatically
    handling path normalization and directory creation if needed.

    Args:
        file_path: Path to the file (string or Path object)
        content: Text content to append
        make_dirs: Whether to create parent directories if they don't exist

    Raises:
        FileNotFoundError: If the parent directory does not exist and make_dirs is False
        PermissionError: If the file cannot be written due to permissions
    """
    normalized_path = path_resolver.normalize_path(file_path)

    if make_dirs:
        ensure_dir_exists(normalized_path.parent)

    with open(normalized_path, "a", encoding="utf-8") as f:
        f.write(content)


def ensure_dir_exists(dir_path: PathLike) -> Path:
    """Ensure a directory exists, creating it if necessary.

    Wrapper around path_resolver.ensure_dir_exists for API consistency.

    Args:
        dir_path: Directory path (string or Path object)

    Returns:
        Path to the directory

    Raises:
        PermissionError: If the directory cannot be created due to permissions
    """
    return path_resolver.ensure_dir_exists(dir_path)


def file_exists(file_path: PathLike) -> bool:
    """Check if a file exists.

    Args:
        file_path: Path to the file (string or Path object)

    Returns:
        True if the file exists, False otherwise
    """
    normalized_path = path_resolver.normalize_path(file_path)
    return normalized_path.exists() and normalized_path.is_file()


def dir_exists(dir_path: PathLike) -> bool:
    """Check if a directory exists.

    Args:
        dir_path: Path to the directory (string or Path object)

    Returns:
        True if the directory exists, False otherwise
    """
    normalized_path = path_resolver.normalize_path(dir_path)
    return normalized_path.exists() and normalized_path.is_dir()


def list_files(dir_path: PathLike, pattern: str = "*", recursive: bool = False) -> list[Path]:
    """List files in a directory matching a pattern.

    Args:
        dir_path: Path to the directory (string or Path object)
        pattern: Glob pattern to match files
        recursive: Whether to search recursively

    Returns:
        List of Path objects for matching files (directories excluded)

    Raises:
        FileNotFoundError: If the directory does not exist
        NotADirectoryError: If the path exists but is not a directory
    """
    normalized_path = path_resolver.normalize_path(dir_path)

    if not normalized_path.exists():
        raise FileNotFoundError(f"Directory not found: {normalized_path}")

    if not normalized_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {normalized_path}")

    if recursive:
        paths = list(normalized_path.glob(f"**/{pattern}"))
    else:
        paths = list(normalized_path.glob(pattern))

    # Filter out directories, return only files
    return [p for p in paths if p.is_file()]


def copy_file(src_path: PathLike, dst_path: PathLike, make_dirs: bool = True) -> None:
    """Copy a file from source to destination.

    Args:
        src_path: Path to the source file (string or Path object)
        dst_path: Path to the destination file (string or Path object)
        make_dirs: Whether to create parent directories for the destination if they don't exist

    Raises:
        FileNotFoundError: If the source file does not exist
        PermissionError: If the source cannot be read or the destination cannot be written
    """
    src = path_resolver.normalize_path(src_path)
    dst = path_resolver.normalize_path(dst_path)

    if not src.exists():
        raise FileNotFoundError(f"Source file not found: {src}")

    if make_dirs:
        ensure_dir_exists(dst.parent)

    shutil.copy2(src, dst)


def move_file(src_path: PathLike, dst_path: PathLike, make_dirs: bool = True) -> None:
    """Move a file from source to destination.

    Args:
        src_path: Path to the source file (string or Path object)
        dst_path: Path to the destination file (string or Path object)
        make_dirs: Whether to create parent directories for the destination if they don't exist

    Raises:
        FileNotFoundError: If the source file does not exist
        PermissionError: If the source cannot be accessed or the destination cannot be written
    """
    src = path_resolver.normalize_path(src_path)
    dst = path_resolver.normalize_path(dst_path)

    if not src.exists():
        raise FileNotFoundError(f"Source file not found: {src}")

    if make_dirs:
        ensure_dir_exists(dst.parent)

    shutil.move(src, dst)


def delete_file(file_path: PathLike) -> None:
    """Delete a file.

    Args:
        file_path: Path to the file (string or Path object)

    Raises:
        FileNotFoundError: If the file does not exist
        PermissionError: If the file cannot be deleted due to permissions
        IsADirectoryError: If the path points to a directory instead of a file
    """
    normalized_path = path_resolver.normalize_path(file_path)

    if not normalized_path.exists():
        raise FileNotFoundError(f"File not found: {normalized_path}")

    if normalized_path.is_dir():
        raise IsADirectoryError(
            f"Expected a file but found a directory: {normalized_path}. "
            "Use delete_dir() to remove directories."
        )

    normalized_path.unlink()


def delete_dir(dir_path: PathLike, recursive: bool = False) -> None:
    """Delete a directory.

    Args:
        dir_path: Path to the directory (string or Path object)
        recursive: Whether to recursively delete the directory and its contents

    Raises:
        FileNotFoundError: If the directory does not exist
        NotADirectoryError: If the path exists but is not a directory
        OSError: If the directory is not empty and recursive is False
        PermissionError: If the directory cannot be deleted due to permissions
    """
    normalized_path = path_resolver.normalize_path(dir_path)

    if not normalized_path.exists():
        raise FileNotFoundError(f"Directory not found: {normalized_path}")

    if not normalized_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {normalized_path}")

    if recursive:
        shutil.rmtree(normalized_path)
    else:
        normalized_path.rmdir()  # Raises if directory is not empty


def get_file_size(file_path: PathLike) -> int:
    """Get the size of a file in bytes.

    Args:
        file_path: Path to the file (string or Path object)

    Returns:
        Size of the file in bytes

    Raises:
        FileNotFoundError: If the file does not exist
        IsADirectoryError: If the path points to a directory
    """
    normalized_path = path_resolver.normalize_path(file_path)

    if not normalized_path.exists():
        raise FileNotFoundError(f"File not found: {normalized_path}")

    if normalized_path.is_dir():
        raise IsADirectoryError(f"Expected a file but found a directory: {normalized_path}")

    return normalized_path.stat().st_size


def get_file_mtime(file_path: PathLike) -> float:
    """Get the last modification time of a file.

    Args:
        file_path: Path to the file (string or Path object)

    Returns:
        Modification time as seconds since epoch

    Raises:
        FileNotFoundError: If the file does not exist
    """
    normalized_path = path_resolver.normalize_path(file_path)

    if not normalized_path.exists():
        raise FileNotFoundError(f"File not found: {normalized_path}")

    return normalized_path.stat().st_mtime


def create_temp_file(
    suffix: str | None = None, prefix: str | None = None, directory: PathLike | None = None
) -> Path:
    """Create a temporary file with an optional suffix, prefix and directory.

    Uses the path_resolver's temp_dir as the default location if no directory is specified.

    Args:
        suffix: Optional suffix for the filename
        prefix: Optional prefix for the filename
        directory: Optional directory to create the file in

    Returns:
        Path to the created temporary file
    """
    import tempfile

    # Use default temp directory or the provided directory
    temp_dir = (
        path_resolver.temp_dir if directory is None else path_resolver.normalize_path(directory)
    )

    # Ensure the directory exists
    ensure_dir_exists(temp_dir)

    # Create a temporary file using Python's tempfile module
    temp_file = tempfile.NamedTemporaryFile(
        dir=temp_dir, prefix=prefix, suffix=suffix, delete=False
    )

    # Close the file handle but keep the file
    temp_file.close()

    return Path(temp_file.name)


def create_temp_dir(
    suffix: str | None = None, prefix: str | None = None, directory: PathLike | None = None
) -> Path:
    """Create a temporary directory with an optional suffix, prefix and parent directory.

    Uses the path_resolver's temp_dir as the default location if no directory is specified.

    Args:
        suffix: Optional suffix for the directory name
        prefix: Optional prefix for the directory name
        directory: Optional parent directory to create the directory in

    Returns:
        Path to the created temporary directory
    """
    import tempfile

    # Use default temp directory or the provided directory
    temp_dir = (
        path_resolver.temp_dir if directory is None else path_resolver.normalize_path(directory)
    )

    # Ensure the parent directory exists
    ensure_dir_exists(temp_dir)

    # Create a temporary directory using Python's tempfile module
    temp_dir_path = tempfile.mkdtemp(dir=temp_dir, prefix=prefix, suffix=suffix)

    return Path(temp_dir_path)


def safe_open_for_read(file_path: PathLike, binary: bool = False) -> Path | None:
    """Safely check if a file can be opened for reading.

    Tests if a file exists and can be opened for reading without actually reading it.

    Args:
        file_path: Path to the file (string or Path object)
        binary: Whether to open in binary mode

    Returns:
        Path object if the file can be opened, None otherwise
    """
    normalized_path = path_resolver.normalize_path(file_path)

    if not normalized_path.exists() or not normalized_path.is_file():
        return None

    try:
        mode = "rb" if binary else "r"
        with open(normalized_path, mode):
            pass
        return normalized_path
    except (PermissionError, OSError):
        return None


def atomic_write(file_path: PathLike, content: str | bytes, make_dirs: bool = True) -> None:
    """Write to a file atomically by using a temporary file.

    This ensures that the file is either completely written or not changed,
    preventing corruption if the operation is interrupted.

    Args:
        file_path: Path to the file (string or Path object)
        content: Content to write (string or bytes)
        make_dirs: Whether to create parent directories if they don't exist

    Raises:
        FileNotFoundError: If the parent directory does not exist and make_dirs is False
        PermissionError: If the file cannot be written due to permissions
    """
    normalized_path = path_resolver.normalize_path(file_path)

    if make_dirs:
        ensure_dir_exists(normalized_path.parent)

    # Determine if we're writing text or binary data
    is_binary = isinstance(content, bytes)
    suffix = Path(normalized_path).suffix

    # Create a temporary file in the same directory
    temp_file = create_temp_file(suffix=suffix, directory=normalized_path.parent)

    try:
        # Write the content to the temporary file
        if is_binary:
            # We know content is bytes if is_binary is True
            write_bytes(temp_file, content, make_dirs=False)
        else:
            # We know content is str if is_binary is False
            write_text(temp_file, content, make_dirs=False)

        # Move the temporary file to the target location (atomic on POSIX systems)
        # On Windows, this will first try to use os.replace() which is atomic
        os.replace(temp_file, normalized_path)
    except Exception:
        # Clean up the temporary file if anything went wrong
        if temp_file.exists():
            temp_file.unlink()
        raise
