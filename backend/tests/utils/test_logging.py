"""Tests for app/utils/logging.py (PII-safe logging utilities)."""

import pytest
from app.utils.logging import (
    hash_user_id,
    hash_appointment_id,
    safe_len,
    safe_type,
    safe_keys,
    safe_summary,
)


class TestHashUserID:
    """Tests for hash_user_id()."""

    def test_hash_user_id_returns_hashed_value(self):
        """Test: hash_user_id returns a hashed value with user_ prefix."""
        result = hash_user_id("550e8400-e29b-41d4-a716-446655440000")
        assert result.startswith("user_")
        assert len(result) == 13  # "user_" (5) + 8 chars

    def test_hash_user_id_consistent(self):
        """Test: Same user ID always produces same hash."""
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        hash1 = hash_user_id(user_id)
        hash2 = hash_user_id(user_id)
        assert hash1 == hash2

    def test_hash_user_id_different_users_different_hashes(self):
        """Test: Different user IDs produce different hashes."""
        hash1 = hash_user_id("user-1")
        hash2 = hash_user_id("user-2")
        assert hash1 != hash2

    def test_hash_user_id_custom_prefix(self):
        """Test: hash_user_id accepts custom prefix."""
        result = hash_user_id("test-id", prefix="custom_")
        assert result.startswith("custom_")
        assert len(result) == 15  # "custom_" (7) + 8 chars

    def test_hash_user_id_not_plaintext(self):
        """Test: Hashed output doesn't contain original user ID."""
        user_id = "my-secret-user-id"
        result = hash_user_id(user_id)
        assert user_id not in result


class TestHashAppointmentID:
    """Tests for hash_appointment_id()."""

    def test_hash_appointment_id_returns_appt_prefix(self):
        """Test: hash_appointment_id uses appt_ prefix."""
        result = hash_appointment_id("appointment-123")
        assert result.startswith("appt_")
        assert len(result) == 13  # "appt_" (5) + 8 chars

    def test_hash_appointment_id_consistent(self):
        """Test: Same appointment ID always produces same hash."""
        appt_id = "appointment-456"
        hash1 = hash_appointment_id(appt_id)
        hash2 = hash_appointment_id(appt_id)
        assert hash1 == hash2

    def test_hash_appointment_id_not_plaintext(self):
        """Test: Hashed output doesn't contain original appointment ID."""
        appt_id = "my-secret-appointment"
        result = hash_appointment_id(appt_id)
        assert appt_id not in result


class TestSafeLen:
    """Tests for safe_len()."""

    def test_safe_len_string(self):
        """Test: safe_len returns length of string."""
        assert safe_len("hello") == 5

    def test_safe_len_empty_string(self):
        """Test: safe_len returns 0 for empty string."""
        assert safe_len("") == 0

    def test_safe_len_bytes(self):
        """Test: safe_len works with bytes."""
        assert safe_len(b"hello") == 5

    def test_safe_len_list(self):
        """Test: safe_len works with lists."""
        assert safe_len([1, 2, 3]) == 3

    def test_safe_len_dict(self):
        """Test: safe_len works with dicts (returns key count)."""
        assert safe_len({"a": 1, "b": 2}) == 2

    def test_safe_len_none_returns_zero(self):
        """Test: safe_len returns 0 for None."""
        assert safe_len(None) == 0

    def test_safe_len_object_without_len_returns_zero(self):
        """Test: safe_len returns 0 for objects without __len__."""
        assert safe_len(12345) == 0  # int has no __len__

    def test_safe_len_exception_returns_zero(self):
        """Test: safe_len gracefully handles exceptions."""
        obj = object()  # object() doesn't have __len__
        assert safe_len(obj) == 0


class TestSafeType:
    """Tests for safe_type()."""

    def test_safe_type_string(self):
        """Test: safe_type returns 'str' for strings."""
        assert safe_type("hello") == "str"

    def test_safe_type_dict(self):
        """Test: safe_type returns 'dict' for dicts."""
        assert safe_type({"a": 1}) == "dict"

    def test_safe_type_list(self):
        """Test: safe_type returns 'list' for lists."""
        assert safe_type([1, 2, 3]) == "list"

    def test_safe_type_int(self):
        """Test: safe_type returns 'int' for integers."""
        assert safe_type(42) == "int"

    def test_safe_type_none(self):
        """Test: safe_type returns 'NoneType' for None."""
        assert safe_type(None) == "NoneType"

    def test_safe_type_custom_object(self):
        """Test: safe_type returns class name for custom objects."""

        class CustomClass:
            pass

        obj = CustomClass()
        assert safe_type(obj) == "CustomClass"


class TestSafeKeys:
    """Tests for safe_keys()."""

    def test_safe_keys_returns_comma_separated(self):
        """Test: safe_keys returns comma-separated keys."""
        result = safe_keys({"id": 1, "name": "test", "age": 25})
        keys_list = [k.strip() for k in result.split(",")]
        assert set(keys_list) == {"id", "name", "age"}

    def test_safe_keys_empty_dict(self):
        """Test: safe_keys returns empty string for empty dict."""
        assert safe_keys({}) == ""

    def test_safe_keys_single_key(self):
        """Test: safe_keys with single key."""
        assert safe_keys({"id": 123}) == "id"

    def test_safe_keys_non_dict_returns_message(self):
        """Test: safe_keys returns 'not a dict' for non-dict."""
        assert safe_keys("not a dict") == "not a dict"
        assert safe_keys([1, 2, 3]) == "not a dict"
        assert safe_keys(None) == "not a dict"

    def test_safe_keys_does_not_reveal_values(self):
        """Test: safe_keys doesn't include values."""
        result = safe_keys({"secret": "password123", "api_key": "sk-xyz"})
        assert "password123" not in result
        assert "sk-xyz" not in result
        assert "secret" in result
        assert "api_key" in result


class TestSafeSummary:
    """Tests for safe_summary()."""

    def test_safe_summary_operation_and_status_only(self):
        """Test: safe_summary with just operation and status."""
        result = safe_summary("fetch user", "success")
        assert result == "fetch user: success"

    def test_safe_summary_with_count(self):
        """Test: safe_summary includes count."""
        result = safe_summary("process logs", "success", count=47)
        assert result == "process logs: success (47 items)"

    def test_safe_summary_with_duration(self):
        """Test: safe_summary includes duration."""
        result = safe_summary("generate narrative", "success", duration_ms=234.5)
        assert result == "generate narrative: success (234.5ms)"

    def test_safe_summary_with_count_and_duration(self):
        """Test: safe_summary includes both count and duration."""
        result = safe_summary("fetch logs", "success", count=50, duration_ms=123.45)
        assert "fetch logs: success" in result
        assert "50 items" in result
        assert "123.5ms" in result  # 123.45 rounds to 123.5 with 1 decimal place

    def test_safe_summary_different_statuses(self):
        """Test: safe_summary works with different status values."""
        result1 = safe_summary("operation", "error")
        assert "error" in result1

        result2 = safe_summary("operation", "timeout")
        assert "timeout" in result2

        result3 = safe_summary("operation", "retry 1/3")
        assert "retry 1/3" in result3

    def test_safe_summary_count_zero(self):
        """Test: safe_summary includes count=0."""
        result = safe_summary("query", "success", count=0)
        assert "0 items" in result

    def test_safe_summary_duration_formatting(self):
        """Test: safe_summary formats duration with 1 decimal place."""
        result = safe_summary("op", "ok", duration_ms=123.456789)
        assert "123.5ms" in result  # Should be rounded to 1 decimal
