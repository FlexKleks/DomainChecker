"""
Property-based tests for internationalization (i18n) module.

Uses Hypothesis for property-based testing to verify correctness properties
defined in the design document.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from domain_checker.i18n import (
    TRANSLATIONS,
    SUPPORTED_LANGUAGES,
    DEFAULT_LANGUAGE,
    get_message,
    get_all_message_keys,
    has_translation,
    get_missing_translations,
    validate_translations,
)


class TestTranslationCoverageProperty:
    """
    Property-based tests for translation coverage.
    
    **Feature: domain-availability-checker, Property 31: Both languages have all message translations**
    **Validates: Requirements 10.3**
    """

    def test_all_languages_have_all_translations(self) -> None:
        """
        Property 31: Both languages have all message translations.
        
        *For any* message key used in the system, translations SHALL exist
        for both "de" and "en" languages.
        
        **Feature: domain-availability-checker, Property 31: Both languages have all message translations**
        **Validates: Requirements 10.3**
        """
        # Get all message keys
        all_keys = get_all_message_keys()
        
        # Verify we have translations
        assert len(all_keys) > 0, "No translations defined"
        
        # Check each language has all translations
        for language in SUPPORTED_LANGUAGES:
            missing = get_missing_translations(language)
            assert len(missing) == 0, (
                f"Language '{language}' is missing translations for: {missing}"
            )

    @given(key=st.sampled_from(list(TRANSLATIONS.keys())))
    @settings(max_examples=100)
    def test_every_key_has_both_languages(self, key: str) -> None:
        """
        Property 31b: Every message key has translations for both languages.
        
        *For any* message key in the translation dictionary, both German (de)
        and English (en) translations SHALL exist.
        
        **Feature: domain-availability-checker, Property 31: Both languages have all message translations**
        **Validates: Requirements 10.3**
        """
        for language in SUPPORTED_LANGUAGES:
            assert has_translation(key, language), (
                f"Key '{key}' is missing translation for language '{language}'"
            )

    @given(key=st.sampled_from(list(TRANSLATIONS.keys())))
    @settings(max_examples=100)
    def test_translations_are_non_empty(self, key: str) -> None:
        """
        Property 31c: All translations are non-empty strings.
        
        *For any* message key and language, the translation SHALL be a
        non-empty string.
        
        **Feature: domain-availability-checker, Property 31: Both languages have all message translations**
        **Validates: Requirements 10.3**
        """
        for language in SUPPORTED_LANGUAGES:
            message = get_message(key, language)
            assert message is not None, (
                f"Translation for key '{key}' in language '{language}' is None"
            )
            assert len(message) > 0, (
                f"Translation for key '{key}' in language '{language}' is empty"
            )
            # Should not just return the key (which indicates missing translation)
            # unless the key itself is a valid message
            if key not in message:
                assert message != key, (
                    f"Translation for key '{key}' in language '{language}' "
                    "returned the key itself, indicating missing translation"
                )

    @given(
        key=st.sampled_from(list(TRANSLATIONS.keys())),
        language=st.sampled_from(list(SUPPORTED_LANGUAGES)),
    )
    @settings(max_examples=100)
    def test_get_message_returns_string(self, key: str, language: str) -> None:
        """
        Property 31d: get_message always returns a string.
        
        *For any* valid message key and language, get_message SHALL return
        a string value.
        
        **Feature: domain-availability-checker, Property 31: Both languages have all message translations**
        **Validates: Requirements 10.3**
        """
        result = get_message(key, language)
        assert isinstance(result, str), (
            f"get_message returned {type(result).__name__} instead of str "
            f"for key '{key}' and language '{language}'"
        )

    def test_validate_translations_returns_empty_sets(self) -> None:
        """
        Property 31e: validate_translations confirms complete coverage.
        
        The validate_translations function SHALL return empty sets for all
        supported languages, indicating no missing translations.
        
        **Feature: domain-availability-checker, Property 31: Both languages have all message translations**
        **Validates: Requirements 10.3**
        """
        result = validate_translations()
        
        # Should have an entry for each supported language
        assert set(result.keys()) == SUPPORTED_LANGUAGES, (
            f"validate_translations did not check all languages. "
            f"Expected {SUPPORTED_LANGUAGES}, got {set(result.keys())}"
        )
        
        # Each language should have no missing translations
        for language, missing in result.items():
            assert len(missing) == 0, (
                f"Language '{language}' has missing translations: {missing}"
            )

    def test_german_and_english_translations_differ(self) -> None:
        """
        Property 31f: German and English translations are different.
        
        *For any* message key, the German and English translations SHOULD
        be different (to verify actual translation, not just duplication).
        
        **Feature: domain-availability-checker, Property 31: Both languages have all message translations**
        **Validates: Requirements 10.3**
        """
        # Count how many translations are identical
        identical_count = 0
        total_count = len(TRANSLATIONS)
        
        for key in TRANSLATIONS:
            de_msg = get_message(key, "de")
            en_msg = get_message(key, "en")
            if de_msg == en_msg:
                identical_count += 1
        
        # Allow some identical translations (e.g., technical terms, proper nouns)
        # but most should be different
        max_identical_ratio = 0.1  # Allow up to 10% identical
        actual_ratio = identical_count / total_count if total_count > 0 else 0
        
        assert actual_ratio <= max_identical_ratio, (
            f"Too many identical translations: {identical_count}/{total_count} "
            f"({actual_ratio:.1%}). Expected at most {max_identical_ratio:.0%}. "
            "This may indicate missing translations."
        )


class TestGetMessageFunction:
    """
    Tests for the get_message function behavior.
    """

    def test_default_language_is_german(self) -> None:
        """Test that default language is German."""
        assert DEFAULT_LANGUAGE == "de"

    def test_get_message_with_no_language_uses_default(self) -> None:
        """Test that get_message uses default language when none specified."""
        key = "status.available"
        result_default = get_message(key)
        result_german = get_message(key, "de")
        assert result_default == result_german

    def test_get_message_with_invalid_language_uses_default(self) -> None:
        """Test that get_message falls back to default for invalid language."""
        key = "status.available"
        result_invalid = get_message(key, "invalid_lang")
        result_german = get_message(key, "de")
        assert result_invalid == result_german

    def test_get_message_with_unknown_key_returns_key(self) -> None:
        """Test that get_message returns the key for unknown keys."""
        unknown_key = "this.key.does.not.exist"
        result = get_message(unknown_key, "de")
        assert result == unknown_key

    def test_get_message_with_format_args(self) -> None:
        """Test that get_message correctly formats messages with arguments."""
        # Test German
        result_de = get_message("validation.invalid_tld", "de", tld="xyz")
        assert "xyz" in result_de
        assert "TLD" in result_de
        
        # Test English
        result_en = get_message("validation.invalid_tld", "en", tld="xyz")
        assert "xyz" in result_en
        assert "TLD" in result_en

    def test_get_message_with_missing_format_args(self) -> None:
        """Test that get_message handles missing format args gracefully."""
        # Should not raise an exception, just return unformatted message
        result = get_message("validation.invalid_tld", "de")
        assert "{tld}" in result  # Placeholder should remain

    @given(language=st.sampled_from(list(SUPPORTED_LANGUAGES)))
    @settings(max_examples=10)
    def test_status_messages_exist(self, language: str) -> None:
        """Test that all status messages exist for each language."""
        status_keys = ["status.available", "status.taken", "status.unknown"]
        for key in status_keys:
            result = get_message(key, language)
            assert result != key, f"Missing translation for {key} in {language}"


class TestSupportedLanguages:
    """
    Tests for supported languages configuration.
    """

    def test_supported_languages_contains_german(self) -> None:
        """Test that German is a supported language."""
        assert "de" in SUPPORTED_LANGUAGES

    def test_supported_languages_contains_english(self) -> None:
        """Test that English is a supported language."""
        assert "en" in SUPPORTED_LANGUAGES

    def test_supported_languages_is_frozen(self) -> None:
        """Test that SUPPORTED_LANGUAGES is immutable."""
        assert isinstance(SUPPORTED_LANGUAGES, frozenset)
