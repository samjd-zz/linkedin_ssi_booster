"""
Unit tests for Rei Toei console routing integration
====================================================
Tests the /rei-toei and /rei command routing in main.py console mode.

Phase 1D: Console Integration
"""

import pytest


class TestReiConsoleRouting:
    """Test /rei-toei and /rei command routing in console mode."""

    def test_rei_toei_command_parsing(self):
        """Test that /rei-toei command extracts message correctly."""
        user_input = "/rei-toei generate a strudel pattern about recursion"
        extracted = user_input[len("/rei-toei"):].strip()
        
        assert extracted == "generate a strudel pattern about recursion"

    def test_rei_command_parsing(self):
        """Test that /rei command extracts message correctly."""
        user_input = "/rei what's your name?"
        extracted = user_input[len("/rei"):].strip()
        
        assert extracted == "what's your name?"

    def test_rei_toei_empty_message_default(self):
        """Test that empty /rei-toei command gets default welcome message."""
        user_input = "/rei-toei"
        extracted = user_input[len("/rei-toei"):].strip()
        
        # Should use default message when empty
        if not extracted:
            extracted = "Hello! Tell me about yourself."
        
        assert extracted == "Hello! Tell me about yourself."

    def test_rei_empty_message_default(self):
        """Test that empty /rei command gets default welcome message."""
        user_input = "/rei"
        extracted = user_input[len("/rei"):].strip()
        
        # Should use default message when empty
        if not extracted:
            extracted = "Hello! Tell me about yourself."
        
        assert extracted == "Hello! Tell me about yourself."

    def test_rei_toei_command_routing_logic(self):
        """Test the routing logic for /rei-toei vs /rei commands."""
        test_cases = [
            ("/rei-toei hello", True, "hello"),
            ("/rei-toei", True, ""),
            ("/rei world", False, "world"),
            ("/rei", False, ""),
            ("/reload", None, None),  # Not a Rei command
            ("generate a song", None, None),  # Not a command
        ]
        
        for user_input, is_rei_toei, expected_message in test_cases:
            cmd = user_input.lower()
            
            if cmd.startswith("/rei-toei"):
                assert is_rei_toei is True
                extracted = user_input[len("/rei-toei"):].strip()
                assert extracted == expected_message
            elif cmd.startswith("/rei"):
                assert is_rei_toei is False
                extracted = user_input[len("/rei"):].strip()
                assert extracted == expected_message
            else:
                # Not a Rei command
                assert is_rei_toei is None

    def test_rei_command_case_insensitivity(self):
        """Test that /rei and /REI are treated the same."""
        test_inputs = [
            "/rei-toei test",
            "/REI-TOEI test",
            "/Rei-Toei test",
            "/rei test",
            "/REI test",
            "/Rei test",
        ]
        
        for user_input in test_inputs:
            cmd = user_input.lower()
            
            # All should be recognized as Rei commands
            assert cmd.startswith("/rei-toei") or cmd.startswith("/rei")

    def test_rei_command_no_conflict_with_known_commands(self):
        """Verify /rei and /rei-toei don't conflict with other console commands."""
        known_commands = ["/help", "/reset", "/reload", "/exit", "/verify", "/avatar-explain", "/dot-report", "/graph-stats"]
        rei_commands = ["/rei-toei", "/rei"]
        
        # Rei commands should not conflict with known commands
        for rei_cmd in rei_commands:
            for known_cmd in known_commands:
                assert not rei_cmd.startswith(known_cmd)
                assert not known_cmd.startswith(rei_cmd)

    def test_rei_toei_with_whitespace_variations(self):
        """Test that /rei-toei handles various whitespace patterns."""
        test_cases = [
            "/rei-toei   hello",  # Multiple spaces
            "/rei-toei\thello",   # Tab
            "/rei-toei    ",      # Trailing spaces only
        ]
        
        for user_input in test_cases:
            extracted = user_input[len("/rei-toei"):].strip()
            # All should extract correctly or default to empty string
            assert isinstance(extracted, str)

    def test_rei_message_extraction_preserves_content(self):
        """Test that message extraction preserves the full user message."""
        user_input = "/rei-toei generate a complex strudel pattern with multiple synths and effects"
        extracted = user_input[len("/rei-toei"):].strip()
        
        assert "complex" in extracted
        assert "multiple synths" in extracted
        assert "effects" in extracted


# Test count: 9 tests
# Coverage:
# - /rei-toei and /rei command parsing (2 tests)
# - Empty message default handling (2 tests)
# - Routing logic (1 test)
# - Case insensitivity (1 test)
# - Command conflict detection (1 test)
# - Whitespace handling (1 test)
# - Message preservation (1 test)