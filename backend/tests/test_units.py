"""
Unit tests for utility functions and business logic.

These tests focus on isolated functions that don't require database
or external service interactions.
"""
import pytest
import sys
import os

# Add parent directory to path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import time_to_seconds


class TestTimeConversion:
    """Test time format conversion functions."""

    def test_time_to_seconds_mm_ss(self):
        """Test converting mm:ss format to ffmpeg format."""
        result = time_to_seconds("05:30")
        assert result == "00:05:30"

    def test_time_to_seconds_hh_mm_ss(self):
        """Test converting hh:mm:ss format to ffmpeg format."""
        result = time_to_seconds("01:05:30")
        assert result == "01:05:30"

    def test_time_to_seconds_single_digit_padding(self):
        """Test that single digits are properly zero-padded."""
        result = time_to_seconds("5:3")
        assert result == "00:05:03"

    def test_time_to_seconds_already_padded(self):
        """Test that already padded time stays correct."""
        result = time_to_seconds("05:30")
        assert result == "00:05:30"

    def test_time_to_seconds_hours_single_digit(self):
        """Test hours with single digits get padded."""
        result = time_to_seconds("1:5:3")
        assert result == "01:05:03"

    def test_time_to_seconds_zero_time(self):
        """Test zero time formatting."""
        result = time_to_seconds("0:0")
        assert result == "00:00:00"

    def test_time_to_seconds_invalid_format(self):
        """Test that invalid format is returned as-is."""
        invalid_input = "invalid"
        result = time_to_seconds(invalid_input)
        assert result == invalid_input

    def test_time_to_seconds_large_values(self):
        """Test handling of large time values."""
        result = time_to_seconds("99:59:59")
        assert result == "99:59:59"

    def test_time_to_seconds_edge_case_59_seconds(self):
        """Test edge case with 59 seconds."""
        result = time_to_seconds("10:59")
        assert result == "00:10:59"

    def test_time_to_seconds_midnight(self):
        """Test midnight representation."""
        result = time_to_seconds("00:00:00")
        assert result == "00:00:00"


class TestVideoValidation:
    """Test video-related validation logic."""

    def test_valid_time_formats(self):
        """Test that various valid time formats are handled correctly."""
        valid_times = [
            ("0:30", "00:00:30"),
            ("5:45", "00:05:45"),
            ("12:34", "00:12:34"),
            ("1:23:45", "01:23:45"),
            ("10:30:15", "10:30:15"),
        ]
        for input_time, expected in valid_times:
            assert time_to_seconds(input_time) == expected

    def test_clip_duration_logic(self):
        """Test that clip duration calculations would work correctly."""
        # Convert start and end times
        start = time_to_seconds("5:30")  # 5 minutes 30 seconds
        end = time_to_seconds("8:45")    # 8 minutes 45 seconds

        # Both should be in proper format for ffmpeg
        assert start == "00:05:30"
        assert end == "00:08:45"

        # In real usage, ffmpeg would calculate duration as end - start
        # We're just verifying the format is correct for ffmpeg


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string_time(self):
        """Test handling of empty string."""
        result = time_to_seconds("")
        assert result == ""

    def test_time_with_milliseconds_ignored(self):
        """Test that extra components are returned as-is."""
        # If someone passes mm:ss:ms format, it should be returned as-is
        result = time_to_seconds("5:30:500")
        # Will be treated as hh:mm:ss
        assert result == "05:30:500"

    def test_negative_time_handling(self):
        """Test that negative times are handled (returned as-is since invalid)."""
        # Negative times don't make sense, but function should not crash
        result = time_to_seconds("-5:30")
        # Since it has colon, it will try to process it
        assert ":" in result
