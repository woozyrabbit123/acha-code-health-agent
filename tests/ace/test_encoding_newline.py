"""Tests for encoding and newline handling."""

import tempfile
from pathlib import Path

from ace.fileio import (
    detect_newline_style,
    normalize_newlines,
    read_text_file,
    read_text_preserving_style,
    write_text_file,
    write_text_preserving_style,
)


class TestNewlineDetection:
    """Test newline style detection."""

    def test_detect_lf(self):
        """Test detection of LF (Unix) newlines."""
        content = "line1\nline2\nline3\n"
        assert detect_newline_style(content) == "LF"

    def test_detect_crlf(self):
        """Test detection of CRLF (Windows) newlines."""
        content = "line1\r\nline2\r\nline3\r\n"
        assert detect_newline_style(content) == "CRLF"

    def test_detect_cr(self):
        """Test detection of CR (old Mac) newlines."""
        content = "line1\rline2\rline3\r"
        assert detect_newline_style(content) == "CR"

    def test_detect_mixed(self):
        """Test detection of mixed newlines."""
        content = "line1\nline2\r\nline3\r"
        assert detect_newline_style(content) == "MIXED"

    def test_detect_no_newlines(self):
        """Test file with no newlines defaults to LF."""
        content = "single line"
        assert detect_newline_style(content) == "LF"


class TestNewlineNormalization:
    """Test newline normalization."""

    def test_normalize_crlf_to_lf(self):
        """Test converting CRLF to LF."""
        content = "line1\r\nline2\r\n"
        result = normalize_newlines(content, "LF")
        assert result == "line1\nline2\n"
        assert "\r" not in result

    def test_normalize_lf_to_crlf(self):
        """Test converting LF to CRLF."""
        content = "line1\nline2\n"
        result = normalize_newlines(content, "CRLF")
        assert result == "line1\r\nline2\r\n"
        assert "\r\n" in result

    def test_normalize_mixed_to_lf(self):
        """Test normalizing mixed newlines to LF."""
        content = "line1\r\nline2\nline3\r"
        result = normalize_newlines(content, "LF")
        assert result == "line1\nline2\nline3\n"

    def test_normalize_mixed_to_crlf(self):
        """Test normalizing mixed newlines to CRLF."""
        content = "line1\r\nline2\nline3\r"
        result = normalize_newlines(content, "CRLF")
        assert result == "line1\r\nline2\r\nline3\r\n"


class TestFileReadWrite:
    """Test file reading and writing with newline preservation."""

    def test_read_lf_file(self):
        """Test reading file with LF newlines."""
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
            f.write(b"line1\nline2\nline3\n")
            temp_path = f.name

        try:
            content, style = read_text_file(temp_path)
            assert style == "LF"
            assert content == "line1\nline2\nline3\n"
        finally:
            Path(temp_path).unlink()

    def test_read_crlf_file(self):
        """Test reading file with CRLF newlines."""
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
            f.write(b"line1\r\nline2\r\nline3\r\n")
            temp_path = f.name

        try:
            content, style = read_text_file(temp_path)
            assert style == "CRLF"
            # Content normalized to LF internally
            assert content == "line1\nline2\nline3\n"
            assert "\r" not in content
        finally:
            Path(temp_path).unlink()

    def test_write_lf_file(self):
        """Test writing file with LF newlines."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            temp_path = f.name

        try:
            content = "line1\nline2\nline3\n"
            write_text_file(temp_path, content, newline_style="LF")

            # Read back in binary to check actual bytes
            with open(temp_path, "rb") as f:
                raw = f.read()

            assert b"\r\n" not in raw
            assert b"\n" in raw
        finally:
            Path(temp_path).unlink()

    def test_write_crlf_file(self):
        """Test writing file with CRLF newlines."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            temp_path = f.name

        try:
            content = "line1\nline2\nline3\n"
            write_text_file(temp_path, content, newline_style="CRLF")

            # Read back in binary to check actual bytes
            with open(temp_path, "rb") as f:
                raw = f.read()

            assert b"\r\n" in raw
            assert raw == b"line1\r\nline2\r\nline3\r\n"
        finally:
            Path(temp_path).unlink()


class TestRoundTripPreservation:
    """Test that reading and writing preserves newline styles."""

    def test_round_trip_lf(self):
        """Test LF newlines are preserved in round-trip."""
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
            f.write(b"line1\nline2\nline3\n")
            temp_path = f.name

        try:
            # Read with style preservation
            content, style = read_text_preserving_style(temp_path)
            assert style == "LF"

            # Modify content
            modified = content.replace("line2", "LINE2")

            # Write back preserving style
            write_text_preserving_style(temp_path, modified, style)

            # Read back in binary to verify newlines preserved
            with open(temp_path, "rb") as f:
                raw = f.read()

            assert raw == b"line1\nLINE2\nline3\n"
            assert b"\r\n" not in raw
        finally:
            Path(temp_path).unlink()

    def test_round_trip_crlf(self):
        """Test CRLF newlines are preserved in round-trip."""
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
            f.write(b"line1\r\nline2\r\nline3\r\n")
            temp_path = f.name

        try:
            # Read with style preservation
            content, style = read_text_preserving_style(temp_path)
            assert style == "CRLF"

            # Modify content
            modified = content.replace("line2", "LINE2")

            # Write back preserving style
            write_text_preserving_style(temp_path, modified, style)

            # Read back in binary to verify newlines preserved
            with open(temp_path, "rb") as f:
                raw = f.read()

            assert raw == b"line1\r\nLINE2\r\nline3\r\n"
            assert b"\r\n" in raw
        finally:
            Path(temp_path).unlink()

    def test_round_trip_mixed_defaults_to_lf(self):
        """Test mixed newlines default to LF in round-trip."""
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
            f.write(b"line1\nline2\r\nline3\r")
            temp_path = f.name

        try:
            content, style = read_text_preserving_style(temp_path)
            assert style == "MIXED"

            modified = content.replace("line2", "LINE2")
            write_text_preserving_style(temp_path, modified, style)

            # Mixed should convert to LF
            with open(temp_path, "rb") as f:
                raw = f.read()

            assert b"\r\n" not in raw
            assert b"\n" in raw
        finally:
            Path(temp_path).unlink()


class TestEncodingHandling:
    """Test UTF-8 encoding with surrogateescape."""

    def test_read_utf8_with_bom(self):
        """Test reading UTF-8 file with BOM."""
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
            # UTF-8 BOM + content
            f.write(b"\xef\xbb\xbfline1\nline2\n")
            temp_path = f.name

        try:
            content, style = read_text_file(temp_path)
            # BOM should be preserved in content for determinism
            assert content.startswith("\ufeff")
            assert "line1" in content
        finally:
            Path(temp_path).unlink()

    def test_read_write_round_trip_utf8(self):
        """Test round-trip preserves UTF-8 content."""
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
            f.write("Hello 世界\nПривет мир\n".encode())
            temp_path = f.name

        try:
            content, style = read_text_file(temp_path)
            assert "世界" in content
            assert "Привет" in content

            write_text_file(temp_path, content, newline_style=style)

            # Read back and verify
            content2, _ = read_text_file(temp_path)
            assert content == content2
        finally:
            Path(temp_path).unlink()


class TestDeterminism:
    """Test that file I/O is deterministic across runs."""

    def test_deterministic_newline_detection(self):
        """Test newline detection is deterministic."""
        content = "line1\r\nline2\r\n"
        result1 = detect_newline_style(content)
        result2 = detect_newline_style(content)
        assert result1 == result2 == "CRLF"

    def test_deterministic_read_write(self):
        """Test reading and writing produces identical results."""
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".txt") as f:
            f.write(b"line1\nline2\nline3\n")
            temp_path = f.name

        try:
            # Read twice
            content1, style1 = read_text_file(temp_path)
            content2, style2 = read_text_file(temp_path)

            assert content1 == content2
            assert style1 == style2

            # Write and read back
            write_text_file(temp_path, content1, newline_style=style1)
            content3, style3 = read_text_file(temp_path)

            assert content1 == content3
            assert style1 == style3
        finally:
            Path(temp_path).unlink()
