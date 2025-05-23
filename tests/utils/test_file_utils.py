"""Test module for file system utilities."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from rpi_weather_display.utils import file_utils
from rpi_weather_display.utils.path_utils import path_resolver


class TestFileUtils:
    """Test the file_utils module."""

    def test_read_text(self, tmpdir: Any):
        """Test reading text from a file."""
        # Create a temporary file with content
        temp_file = path_resolver.normalize_path(Path(tmpdir) / "test.txt")
        content = "Hello, world!"
        file_utils.write_text(temp_file, content)

        # Read the content using file_utils
        result = file_utils.read_text(temp_file)
        assert result == content

    def test_read_text_nonexistent_file(self):
        """Test reading text from a nonexistent file."""
        with pytest.raises(FileNotFoundError):
            file_utils.read_text("/nonexistent/file.txt")

    def test_read_bytes(self, tmpdir: Any):
        """Test reading binary data from a file."""
        # Create a temporary file with binary content
        temp_file = path_resolver.normalize_path(Path(tmpdir) / "test.bin")
        content = b"\x00\x01\x02\x03"
        file_utils.write_bytes(temp_file, content)

        # Read the content using file_utils
        result = file_utils.read_bytes(temp_file)
        assert result == content

    def test_read_json(self, tmpdir: Any):
        """Test reading and parsing JSON from a file."""
        # Create a temporary JSON file
        temp_file = path_resolver.normalize_path(Path(tmpdir) / "test.json")
        data: file_utils.JsonDict = {"name": "test", "value": 42, "items": [1, 2, 3]}
        file_utils.write_json(temp_file, data)

        # Read the JSON data using file_utils
        result = file_utils.read_json(temp_file)
        assert result == data

    def test_read_json_invalid(self, tmpdir: Any):
        """Test reading invalid JSON from a file."""
        # Create a temporary file with invalid JSON
        temp_file = path_resolver.normalize_path(Path(tmpdir) / "invalid.json")
        file_utils.write_text(temp_file, "This is not valid JSON")

        # Attempt to read the invalid JSON
        with pytest.raises(json.JSONDecodeError):
            file_utils.read_json(temp_file)

    def test_read_lines(self, tmpdir: Any):
        """Test reading lines from a file."""
        # Create a temporary file with multiple lines
        temp_file = path_resolver.normalize_path(Path(tmpdir) / "lines.txt")
        lines = ["Line 1\n", "Line 2\n", "Line 3"]
        file_utils.write_text(temp_file, "".join(lines))

        # Read the lines using file_utils
        result = file_utils.read_lines(temp_file)
        assert result == lines

    def test_write_text(self, tmpdir: Any):
        """Test writing text to a file."""
        # Set up a temporary file path
        temp_file = path_resolver.normalize_path(Path(tmpdir) / "output.txt")
        content = "Hello, world!"

        # Write content using file_utils
        file_utils.write_text(temp_file, content)

        # Verify the content was written correctly
        assert path_resolver.normalize_path(temp_file).exists()
        assert file_utils.read_text(temp_file) == content

    def test_write_text_with_make_dirs(self, tmpdir: Any):
        """Test writing text to a file with parent directory creation."""
        # Set up a temporary file path with nonexistent parent directories
        temp_dir = path_resolver.normalize_path(Path(tmpdir) / "new" / "nested" / "dir")
        temp_file = temp_dir / "output.txt"
        content = "Hello, world!"

        # Write content using file_utils with make_dirs=True
        file_utils.write_text(temp_file, content, make_dirs=True)

        # Verify the content was written correctly and directories were created
        assert file_utils.dir_exists(temp_dir)
        assert file_utils.file_exists(temp_file)
        assert file_utils.read_text(temp_file) == content

    def test_write_bytes(self, tmpdir: Any):
        """Test writing binary data to a file."""
        # Set up a temporary file path
        temp_file = Path(tmpdir) / "output.bin"
        content = b"\x00\x01\x02\x03"

        # Write content using file_utils
        file_utils.write_bytes(temp_file, content)

        # Verify the content was written correctly
        assert temp_file.exists()
        with open(temp_file, "rb") as f:
            assert f.read() == content

    def test_write_json(self, tmpdir: Any):
        """Test writing data as JSON to a file."""
        # Set up a temporary file path
        temp_file = Path(tmpdir) / "output.json"
        data: file_utils.JsonDict = {"name": "test", "value": 42, "items": [1, 2, 3]}

        # Write JSON data using file_utils
        file_utils.write_json(temp_file, data)

        # Verify the JSON was written correctly
        assert temp_file.exists()
        with open(temp_file, encoding="utf-8") as f:
            assert json.load(f) == data

    def test_write_json_with_indent(self, tmpdir: Any):
        """Test writing JSON with custom indentation."""
        # Set up a temporary file path
        temp_file = Path(tmpdir) / "pretty.json"
        data: file_utils.JsonDict = {"name": "test", "items": [1, 2, 3]}

        # Write JSON with custom indentation
        file_utils.write_json(temp_file, data, indent=4)

        # Verify the JSON was written with correct indentation
        assert temp_file.exists()
        with open(temp_file, encoding="utf-8") as f:
            content = f.read()
            assert json.loads(content) == data
            # Check for indentation (simple heuristic)
            assert "    " in content

    def test_append_text(self, tmpdir: Any):
        """Test appending text to a file."""
        # Create a temporary file with initial content
        temp_file = Path(tmpdir) / "append.txt"
        initial_content = "Initial content\n"
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(initial_content)

        # Append additional content
        additional_content = "Additional content"
        file_utils.append_text(temp_file, additional_content)

        # Verify the content was appended correctly
        with open(temp_file, encoding="utf-8") as f:
            assert f.read() == initial_content + additional_content

    def test_ensure_dir_exists(self, tmpdir: Any):
        """Test ensuring a directory exists."""
        # Set up a temporary directory path
        temp_dir = Path(tmpdir) / "new" / "nested" / "dir"

        # Call the function under test
        result = file_utils.ensure_dir_exists(temp_dir)

        # Verify the directory was created
        assert temp_dir.exists()
        assert temp_dir.is_dir()
        assert result == temp_dir

    def test_file_exists(self, tmpdir: Any):
        """Test checking if a file exists."""
        # Create a temporary file
        temp_file = Path(tmpdir) / "exists.txt"
        temp_file.touch()

        # Create a temporary directory (not a file)
        temp_dir = Path(tmpdir) / "dir"
        temp_dir.mkdir()

        # Check existence of existing file
        assert file_utils.file_exists(temp_file) is True

        # Check nonexistent file
        assert file_utils.file_exists(Path(tmpdir) / "nonexistent.txt") is False

        # Check directory (should return False as it's not a file)
        assert file_utils.file_exists(temp_dir) is False

    def test_dir_exists(self, tmpdir: Any):
        """Test checking if a directory exists."""
        # Create a temporary directory
        temp_dir = Path(tmpdir) / "exists"
        temp_dir.mkdir()

        # Create a temporary file (not a directory)
        temp_file = Path(tmpdir) / "file.txt"
        temp_file.touch()

        # Check existence of existing directory
        assert file_utils.dir_exists(temp_dir) is True

        # Check nonexistent directory
        assert file_utils.dir_exists(Path(tmpdir) / "nonexistent") is False

        # Check file (should return False as it's not a directory)
        assert file_utils.dir_exists(temp_file) is False

    def test_list_files(self, tmpdir: Any, mock_paths_exist: MagicMock):
        """Test listing files in a directory."""
        # Create a temporary directory with various files
        temp_dir = Path(tmpdir) / "files"
        temp_dir.mkdir()

        # Create some files
        (temp_dir / "file1.txt").touch()
        (temp_dir / "file2.txt").touch()
        (temp_dir / "image.png").touch()

        # Create a subdirectory with files
        sub_dir = temp_dir / "subdir"
        sub_dir.mkdir()
        (sub_dir / "subfile.txt").touch()

        # Test listing all files (non-recursive)
        with patch("pathlib.Path.is_dir", return_value=True):
            with patch("pathlib.Path.glob") as mock_glob:
                # Mock the glob result for non-recursive call
                mock_files = [
                    temp_dir / "file1.txt",
                    temp_dir / "file2.txt",
                    temp_dir / "image.png",
                ]
                mock_glob.return_value = mock_files

                # Mock is_file to return True for all files
                with patch("pathlib.Path.is_file", return_value=True):
                    files = file_utils.list_files(temp_dir)
                    assert len(files) == 3
                    mock_glob.assert_called_once_with("*")

        # Test listing with pattern
        with patch("pathlib.Path.is_dir", return_value=True):
            with patch("pathlib.Path.glob") as mock_glob:
                # Mock the glob result for pattern call
                mock_files = [temp_dir / "file1.txt", temp_dir / "file2.txt"]
                mock_glob.return_value = mock_files

                # Mock is_file to return True for all files
                with patch("pathlib.Path.is_file", return_value=True):
                    txt_files = file_utils.list_files(temp_dir, pattern="*.txt")
                    assert len(txt_files) == 2
                    mock_glob.assert_called_once_with("*.txt")

        # Test recursive listing
        with patch("pathlib.Path.is_dir", return_value=True):
            with patch("pathlib.Path.glob") as mock_glob:
                # Mock the glob result for recursive call
                mock_files = [
                    temp_dir / "file1.txt",
                    temp_dir / "file2.txt",
                    temp_dir / "image.png",
                    sub_dir / "subfile.txt",
                ]
                mock_glob.return_value = mock_files

                # Mock is_file to return True for all files
                with patch("pathlib.Path.is_file", return_value=True):
                    all_files = file_utils.list_files(temp_dir, recursive=True)
                    assert len(all_files) == 4  # 3 in root + 1 in subdir
                    mock_glob.assert_called_once_with("**/*")

        # Test with nonexistent directory
        mock_paths_exist.return_value = False
        with pytest.raises(FileNotFoundError):
            file_utils.list_files(temp_dir / "nonexistent")

        # Test with file instead of directory
        mock_paths_exist.return_value = True
        with patch("pathlib.Path.is_dir", return_value=False):
            with pytest.raises(NotADirectoryError):
                file_utils.list_files(temp_dir / "file1.txt")

    def test_copy_file(self, tmpdir: Any):
        """Test copying a file."""
        # Create a source file with content
        src_dir = Path(tmpdir) / "src"
        src_dir.mkdir()
        src_file = src_dir / "source.txt"
        content = "Test content"
        with open(src_file, "w", encoding="utf-8") as f:
            f.write(content)

        # Set up destination file path
        dst_dir = Path(tmpdir) / "dst"
        dst_file = dst_dir / "destination.txt"

        # Copy the file with make_dirs=True
        file_utils.copy_file(src_file, dst_file, make_dirs=True)

        # Verify the file was copied correctly
        assert dst_file.exists()
        assert dst_dir.exists()
        with open(dst_file, encoding="utf-8") as f:
            assert f.read() == content

        # Test copying nonexistent file
        with pytest.raises(FileNotFoundError):
            file_utils.copy_file(src_dir / "nonexistent.txt", dst_dir / "new.txt")

    def test_move_file(self, tmpdir: Any, mock_paths_exist: MagicMock):
        """Test moving a file."""
        # Create a source file with content
        src_dir = Path(tmpdir) / "src"
        src_dir.mkdir()
        src_file = src_dir / "source.txt"
        content = "Test content"
        with open(src_file, "w", encoding="utf-8") as f:
            f.write(content)

        # Set up destination file path
        dst_dir = Path(tmpdir) / "dst"
        dst_file = dst_dir / "destination.txt"

        # Move the file with make_dirs=True
        mock_paths_exist.return_value = True
        with patch("rpi_weather_display.utils.file_utils.ensure_dir_exists") as mock_ensure_dir:
            with patch("shutil.move") as mock_move:
                file_utils.move_file(src_file, dst_file, make_dirs=True)
                # Verify ensure_dir_exists was called
                mock_ensure_dir.assert_called_once()
                # Verify move was called
                mock_move.assert_called_once_with(src_file, dst_file)

        # Test moving nonexistent file
        mock_paths_exist.return_value = False
        with pytest.raises(FileNotFoundError):
            file_utils.move_file(src_dir / "nonexistent.txt", dst_dir / "new.txt")

    def test_delete_file(self, tmpdir: Any, mock_paths_exist: MagicMock):
        """Test deleting a file."""
        # Create a temporary file
        temp_file = Path(tmpdir) / "delete.txt"
        temp_file.touch()

        # Delete the file
        mock_paths_exist.return_value = True
        with patch("pathlib.Path.is_dir", return_value=False):
            with patch("pathlib.Path.unlink") as mock_unlink:
                file_utils.delete_file(temp_file)
                # Verify the file deletion was attempted
                mock_unlink.assert_called_once()

        # Try to delete a nonexistent file
        mock_paths_exist.return_value = False
        with pytest.raises(FileNotFoundError):
            file_utils.delete_file(Path(tmpdir) / "nonexistent.txt")

        # Try to delete a directory
        temp_dir = Path(tmpdir) / "dir"
        temp_dir.mkdir()

        mock_paths_exist.return_value = True
        with patch("pathlib.Path.is_dir", return_value=True):
            with pytest.raises(IsADirectoryError):
                file_utils.delete_file(temp_dir)

    def test_delete_dir(self, tmpdir: Any, mock_paths_exist: MagicMock):
        """Test deleting a directory."""
        # Create a temporary directory
        temp_dir = Path(tmpdir) / "delete_dir"
        temp_dir.mkdir()

        # Delete the empty directory
        mock_paths_exist.return_value = True
        with patch("pathlib.Path.is_dir", return_value=True):
            with patch("pathlib.Path.rmdir") as mock_rmdir:
                file_utils.delete_dir(temp_dir)
                # Verify directory deletion was attempted
                mock_rmdir.assert_called_once()

        # Create a directory with contents
        temp_dir = Path(tmpdir) / "non_empty_dir"
        temp_dir.mkdir()
        (temp_dir / "file.txt").touch()

        # Try to delete non-empty directory without recursive flag
        mock_paths_exist.return_value = True
        with patch("pathlib.Path.is_dir", return_value=True):
            with patch("pathlib.Path.rmdir", side_effect=OSError("Directory not empty")):
                with pytest.raises(OSError, match="Directory not empty"):
                    file_utils.delete_dir(temp_dir, recursive=False)

        # Delete with recursive flag
        mock_paths_exist.return_value = True
        with patch("pathlib.Path.is_dir", return_value=True):
            with patch("shutil.rmtree") as mock_rmtree:
                file_utils.delete_dir(temp_dir, recursive=True)
                # Verify rmtree was called
                mock_rmtree.assert_called_once()

        # Try to delete a nonexistent directory
        mock_paths_exist.return_value = False
        with pytest.raises(FileNotFoundError):
            file_utils.delete_dir(Path(tmpdir) / "nonexistent")

        # Try to delete a file
        temp_file = Path(tmpdir) / "file.txt"
        temp_file.touch()

        mock_paths_exist.return_value = True
        with patch("pathlib.Path.is_dir", return_value=False):
            with pytest.raises(NotADirectoryError):
                file_utils.delete_dir(temp_file)

    def test_get_file_size(self, tmpdir: Any):
        """Test getting file size."""
        # Create a file with known content
        temp_file = Path(tmpdir) / "size.txt"
        content = "1234567890"  # 10 bytes
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(content)

        # Get the file size
        size = file_utils.get_file_size(temp_file)

        # Check the size (note: size might be different due to encoding)
        assert size == len(content.encode("utf-8"))

        # Try with nonexistent file
        with pytest.raises(FileNotFoundError):
            file_utils.get_file_size(Path(tmpdir) / "nonexistent.txt")

        # Try with a directory
        temp_dir = Path(tmpdir) / "dir"
        temp_dir.mkdir()

        with pytest.raises(IsADirectoryError):
            file_utils.get_file_size(temp_dir)

    def test_get_file_mtime(self, tmpdir: Any):
        """Test getting file modification time."""
        # Create a temporary file
        temp_file = Path(tmpdir) / "mtime.txt"
        temp_file.touch()

        # Get the modification time
        mtime = file_utils.get_file_mtime(temp_file)

        # Verify it's a reasonable value (recent timestamp)
        assert isinstance(mtime, float)
        assert mtime > 0

        # Try with nonexistent file
        with pytest.raises(FileNotFoundError):
            file_utils.get_file_mtime(Path(tmpdir) / "nonexistent.txt")

    def test_create_temp_file(self):
        """Test creating a temporary file."""
        # Create a temporary file with default parameters
        temp_file = file_utils.create_temp_file()

        # Verify the file was created
        assert temp_file.exists()
        assert temp_file.is_file()

        # Clean up
        temp_file.unlink()

        # Test with suffix and prefix
        temp_file = file_utils.create_temp_file(suffix=".txt", prefix="test_")

        # Verify the file has the correct suffix and prefix
        assert temp_file.name.endswith(".txt")
        assert temp_file.name.startswith("test_")

        # Clean up
        temp_file.unlink()

    def test_create_temp_dir(self):
        """Test creating a temporary directory."""
        # Create a temporary directory with default parameters
        temp_dir = file_utils.create_temp_dir()

        # Verify the directory was created
        assert temp_dir.exists()
        assert temp_dir.is_dir()

        # Clean up
        temp_dir.rmdir()

        # Test with suffix and prefix
        temp_dir = file_utils.create_temp_dir(suffix="_test", prefix="dir_")

        # Verify the directory has the correct suffix and prefix
        assert temp_dir.name.endswith("_test")
        assert temp_dir.name.startswith("dir_")

        # Clean up
        temp_dir.rmdir()

    def test_safe_open_for_read(self, tmpdir: Any):
        """Test safely checking if a file can be opened."""
        # Create a readable file
        readable_file = Path(tmpdir) / "readable.txt"
        readable_file.touch()

        # Test with readable file
        result = file_utils.safe_open_for_read(readable_file)
        assert result == readable_file

        # Test with nonexistent file
        result = file_utils.safe_open_for_read(Path(tmpdir) / "nonexistent.txt")
        assert result is None

        # Test with directory
        temp_dir = Path(tmpdir) / "dir"
        temp_dir.mkdir()

        result = file_utils.safe_open_for_read(temp_dir)
        assert result is None

        # Mock a permission error
        with patch("builtins.open", side_effect=PermissionError):
            result = file_utils.safe_open_for_read(readable_file)
            assert result is None

    def test_atomic_write(self, tmpdir: Any):
        """Test writing to a file atomically."""
        # Set up a file path
        file_path = Path(tmpdir) / "atomic.txt"
        content = "Atomic write test"

        # Write the file atomically
        file_utils.atomic_write(file_path, content)

        # Verify the file was written correctly
        assert file_path.exists()
        with open(file_path, encoding="utf-8") as f:
            assert f.read() == content

        # Test with binary content
        bin_path = Path(tmpdir) / "atomic.bin"
        bin_content = b"\x00\x01\x02\x03"

        file_utils.atomic_write(bin_path, bin_content)

        assert bin_path.exists()
        with open(bin_path, "rb") as f:
            assert f.read() == bin_content

        # Test with nested directory creation
        nested_path = Path(tmpdir) / "nested" / "dir" / "atomic.txt"
        file_utils.atomic_write(nested_path, content, make_dirs=True)

        assert nested_path.exists()
        with open(nested_path, encoding="utf-8") as f:
            assert f.read() == content

        # Test error handling during write
        with patch("rpi_weather_display.utils.file_utils.write_text", side_effect=PermissionError):
            with patch("pathlib.Path.unlink") as mock_unlink:
                with patch("pathlib.Path.exists", return_value=True):
                    with pytest.raises(PermissionError):
                        file_utils.atomic_write(file_path, content)
                    # Verify temp file cleanup was attempted
                    assert mock_unlink.called
