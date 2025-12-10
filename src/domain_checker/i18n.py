"""
Internationalization (i18n) module for the domain checker system.

Provides translations for all user-facing messages in German (de) and English (en).
Implements Requirement 10.3: Support German and English language output.
"""

from typing import Optional


# Supported languages
SUPPORTED_LANGUAGES = frozenset({"de", "en"})
DEFAULT_LANGUAGE = "de"


# Translation dictionary with all messages
# Structure: {message_key: {language_code: translated_message}}
TRANSLATIONS: dict[str, dict[str, str]] = {
    # Domain validation messages
    "validation.empty_input": {
        "de": "Domain-Eingabe ist leer",
        "en": "Domain input is empty",
    },
    "validation.forbidden_chars": {
        "de": "Domain enthält ungültige Zeichen",
        "en": "Domain contains forbidden characters",
    },
    "validation.invalid_tld": {
        "de": "TLD '{tld}' ist nicht in der konfigurierten Liste erlaubt",
        "en": "TLD '{tld}' is not in the configured allowed list",
    },
    "validation.tld_extraction_failed": {
        "de": "TLD konnte nicht aus der Domain extrahiert werden",
        "en": "Could not extract TLD from domain",
    },
    "validation.idna_error": {
        "de": "IDNA-Kodierung fehlgeschlagen: {error}",
        "en": "IDNA encoding failed: {error}",
    },
    
    # Availability status messages
    "status.available": {
        "de": "Verfügbar",
        "en": "Available",
    },
    "status.taken": {
        "de": "Belegt",
        "en": "Taken",
    },
    "status.unknown": {
        "de": "Unbekannt",
        "en": "Unknown",
    },
    
    # Notification messages
    "notification.domain_available": {
        "de": "Domain verfügbar!",
        "en": "Domain available!",
    },
    "notification.domain_status_changed": {
        "de": "Domain-Status geändert",
        "en": "Domain status changed",
    },
    "notification.domain_label": {
        "de": "Domain",
        "en": "Domain",
    },
    "notification.status_label": {
        "de": "Status",
        "en": "Status",
    },
    "notification.time_label": {
        "de": "Zeit",
        "en": "Time",
    },
    "notification.email_subject_available": {
        "de": "Domain {domain} ist verfügbar!",
        "en": "Domain {domain} is available!",
    },
    "notification.email_subject_changed": {
        "de": "Domain-Status geändert: {domain}",
        "en": "Domain status changed: {domain}",
    },
    "notification.delivery_failed": {
        "de": "Benachrichtigung konnte nicht zugestellt werden",
        "en": "Notification delivery failed",
    },
    "notification.all_retries_failed": {
        "de": "Alle Benachrichtigungsversuche für Kanal '{channel}' fehlgeschlagen",
        "en": "All notification retries failed for channel '{channel}'",
    },
    
    # RDAP client messages
    "rdap.query_started": {
        "de": "RDAP-Abfrage gestartet für {domain}",
        "en": "RDAP query started for {domain}",
    },
    "rdap.query_completed": {
        "de": "RDAP-Abfrage abgeschlossen für {domain}",
        "en": "RDAP query completed for {domain}",
    },
    "rdap.network_error": {
        "de": "Netzwerkfehler bei RDAP-Abfrage",
        "en": "Network error during RDAP query",
    },
    "rdap.tls_error": {
        "de": "TLS-Verbindung abgelehnt - nur HTTPS erlaubt",
        "en": "TLS connection rejected - only HTTPS allowed",
    },
    "rdap.timeout": {
        "de": "RDAP-Abfrage Zeitüberschreitung",
        "en": "RDAP query timeout",
    },
    "rdap.parse_error": {
        "de": "RDAP-Antwort konnte nicht geparst werden",
        "en": "Failed to parse RDAP response",
    },
    "rdap.rate_limited": {
        "de": "RDAP-Anfrage wurde ratenbegrenzt",
        "en": "RDAP request was rate limited",
    },
    "rdap.server_error": {
        "de": "RDAP-Server-Fehler",
        "en": "RDAP server error",
    },
    "rdap.domain_found": {
        "de": "Domain ist registriert",
        "en": "Domain is registered",
    },
    "rdap.domain_not_found": {
        "de": "Domain ist möglicherweise verfügbar",
        "en": "Domain is potentially available",
    },
    
    # WHOIS client messages
    "whois.query_started": {
        "de": "WHOIS-Abfrage gestartet für {domain}",
        "en": "WHOIS query started for {domain}",
    },
    "whois.query_completed": {
        "de": "WHOIS-Abfrage abgeschlossen für {domain}",
        "en": "WHOIS query completed for {domain}",
    },
    "whois.network_error": {
        "de": "Netzwerkfehler bei WHOIS-Abfrage",
        "en": "Network error during WHOIS query",
    },
    "whois.timeout": {
        "de": "WHOIS-Abfrage Zeitüberschreitung",
        "en": "WHOIS query timeout",
    },
    "whois.parse_error": {
        "de": "WHOIS-Antwort konnte nicht geparst werden",
        "en": "Failed to parse WHOIS response",
    },
    "whois.ambiguous_response": {
        "de": "WHOIS-Antwort ist mehrdeutig",
        "en": "WHOIS response is ambiguous",
    },
    "whois.domain_found": {
        "de": "Domain ist registriert (WHOIS)",
        "en": "Domain is registered (WHOIS)",
    },
    "whois.domain_not_found": {
        "de": "Domain ist verfügbar (WHOIS)",
        "en": "Domain is available (WHOIS)",
    },
    
    # Rate limiter messages
    "ratelimit.waiting": {
        "de": "Warte {seconds:.1f} Sekunden wegen Ratenbegrenzung",
        "en": "Waiting {seconds:.1f} seconds due to rate limiting",
    },
    "ratelimit.limit_reached": {
        "de": "Ratenlimit erreicht für {registry}",
        "en": "Rate limit reached for {registry}",
    },
    "ratelimit.adaptive_delay": {
        "de": "Adaptive Verzögerung angewendet: {seconds:.1f} Sekunden",
        "en": "Adaptive delay applied: {seconds:.1f} seconds",
    },
    
    # Retry manager messages
    "retry.attempt": {
        "de": "Versuch {attempt} von {max_attempts}",
        "en": "Attempt {attempt} of {max_attempts}",
    },
    "retry.waiting": {
        "de": "Warte {seconds:.1f} Sekunden vor erneutem Versuch",
        "en": "Waiting {seconds:.1f} seconds before retry",
    },
    "retry.max_retries_exceeded": {
        "de": "Maximale Anzahl an Versuchen überschritten",
        "en": "Maximum retry attempts exceeded",
    },
    "retry.success": {
        "de": "Operation erfolgreich nach {attempts} Versuch(en)",
        "en": "Operation successful after {attempts} attempt(s)",
    },
    "retry.failed": {
        "de": "Operation fehlgeschlagen nach {attempts} Versuch(en)",
        "en": "Operation failed after {attempts} attempt(s)",
    },
    
    # Decision engine messages
    "decision.evaluating": {
        "de": "Bewerte Verfügbarkeit für {domain}",
        "en": "Evaluating availability for {domain}",
    },
    "decision.available": {
        "de": "Domain {domain} ist verfügbar (bestätigt durch mehrere Quellen)",
        "en": "Domain {domain} is available (confirmed by multiple sources)",
    },
    "decision.taken": {
        "de": "Domain {domain} ist belegt",
        "en": "Domain {domain} is taken",
    },
    "decision.uncertain": {
        "de": "Verfügbarkeit von {domain} ist unsicher - als belegt markiert",
        "en": "Availability of {domain} is uncertain - marked as taken",
    },
    "decision.source_disagreement": {
        "de": "Quellen sind sich uneinig - als belegt markiert",
        "en": "Sources disagree - marked as taken",
    },
    
    # State store messages
    "state.loading": {
        "de": "Lade gespeicherten Zustand",
        "en": "Loading stored state",
    },
    "state.loaded": {
        "de": "Zustand erfolgreich geladen",
        "en": "State loaded successfully",
    },
    "state.saving": {
        "de": "Speichere Zustand",
        "en": "Saving state",
    },
    "state.saved": {
        "de": "Zustand erfolgreich gespeichert",
        "en": "State saved successfully",
    },
    "state.hmac_invalid": {
        "de": "HMAC-Validierung fehlgeschlagen - mögliche Datenmanipulation",
        "en": "HMAC validation failed - possible data tampering",
    },
    "state.file_not_found": {
        "de": "Zustandsdatei nicht gefunden",
        "en": "State file not found",
    },
    "state.parse_error": {
        "de": "Zustandsdatei konnte nicht geparst werden",
        "en": "Failed to parse state file",
    },
    
    # Audit logger messages
    "audit.mode_enabled": {
        "de": "Audit-Modus aktiviert",
        "en": "Audit mode enabled",
    },
    "audit.mode_disabled": {
        "de": "Audit-Modus deaktiviert",
        "en": "Audit mode disabled",
    },
    "audit.signature_valid": {
        "de": "Log-Signatur gültig",
        "en": "Log signature valid",
    },
    "audit.signature_invalid": {
        "de": "Log-Signatur ungültig",
        "en": "Log signature invalid",
    },
    
    # Error messages
    "error.network": {
        "de": "Netzwerkfehler: {message}",
        "en": "Network error: {message}",
    },
    "error.timeout": {
        "de": "Zeitüberschreitung: {message}",
        "en": "Timeout: {message}",
    },
    "error.validation": {
        "de": "Validierungsfehler: {message}",
        "en": "Validation error: {message}",
    },
    "error.protocol": {
        "de": "Protokollfehler: {message}",
        "en": "Protocol error: {message}",
    },
    "error.persistence": {
        "de": "Persistenzfehler: {message}",
        "en": "Persistence error: {message}",
    },
    "error.tampering": {
        "de": "Datenmanipulation erkannt: {message}",
        "en": "Data tampering detected: {message}",
    },
    "error.notification": {
        "de": "Benachrichtigungsfehler: {message}",
        "en": "Notification error: {message}",
    },
    "error.rate_limit": {
        "de": "Ratenbegrenzungsfehler: {message}",
        "en": "Rate limit error: {message}",
    },
    "error.unknown": {
        "de": "Unbekannter Fehler: {message}",
        "en": "Unknown error: {message}",
    },
    
    # Configuration messages
    "config.loaded": {
        "de": "Konfiguration geladen",
        "en": "Configuration loaded",
    },
    "config.invalid": {
        "de": "Ungültige Konfiguration: {message}",
        "en": "Invalid configuration: {message}",
    },
    "config.missing_required": {
        "de": "Erforderliche Konfiguration fehlt: {field}",
        "en": "Required configuration missing: {field}",
    },
    
    # Scheduler messages
    "scheduler.started": {
        "de": "Scheduler gestartet",
        "en": "Scheduler started",
    },
    "scheduler.stopped": {
        "de": "Scheduler gestoppt",
        "en": "Scheduler stopped",
    },
    "scheduler.next_run": {
        "de": "Nächste Ausführung: {time}",
        "en": "Next run: {time}",
    },
    "scheduler.job_started": {
        "de": "Job gestartet: {job_id}",
        "en": "Job started: {job_id}",
    },
    "scheduler.job_completed": {
        "de": "Job abgeschlossen: {job_id}",
        "en": "Job completed: {job_id}",
    },
    "scheduler.job_failed": {
        "de": "Job fehlgeschlagen: {job_id}",
        "en": "Job failed: {job_id}",
    },
    
    # Simulation mode messages
    "simulation.enabled": {
        "de": "Simulationsmodus aktiviert - keine echten Netzwerkanfragen",
        "en": "Simulation mode enabled - no real network requests",
    },
    "simulation.mock_response": {
        "de": "Simulierte Antwort für {domain}",
        "en": "Simulated response for {domain}",
    },
    
    # Self-test messages
    "selftest.started": {
        "de": "Selbsttest gestartet",
        "en": "Self-test started",
    },
    "selftest.completed": {
        "de": "Selbsttest abgeschlossen",
        "en": "Self-test completed",
    },
    "selftest.failed": {
        "de": "Selbsttest fehlgeschlagen",
        "en": "Self-test failed",
    },
    "selftest.success": {
        "de": "Selbsttest erfolgreich abgeschlossen",
        "en": "Self-test completed successfully",
    },
    "selftest.endpoint_ok": {
        "de": "Endpoint erreichbar: {endpoint}",
        "en": "Endpoint reachable: {endpoint}",
    },
    "selftest.endpoint_failed": {
        "de": "Endpoint nicht erreichbar: {endpoint}",
        "en": "Endpoint unreachable: {endpoint}",
    },
    "selftest.header": {
        "de": "Domain-Checker Selbsttest",
        "en": "Domain Checker Self-Test",
    },
    "selftest.config_validation": {
        "de": "Konfigurationsvalidierung:",
        "en": "Configuration Validation:",
    },
    "selftest.config_valid": {
        "de": "Konfiguration ist gültig",
        "en": "Configuration is valid",
    },
    "selftest.config_invalid": {
        "de": "Konfiguration ist ungültig",
        "en": "Configuration is invalid",
    },
    "selftest.warnings": {
        "de": "Warnungen:",
        "en": "Warnings:",
    },
    "selftest.connectivity": {
        "de": "Endpoint-Konnektivität:",
        "en": "Endpoint Connectivity:",
    },
    "selftest.duration": {
        "de": "Gesamtdauer",
        "en": "Total duration",
    },
    
    # CLI messages
    "cli.checking_domain": {
        "de": "Prüfe Domain: {domain}",
        "en": "Checking domain: {domain}",
    },
    "cli.result": {
        "de": "Ergebnis: {status}",
        "en": "Result: {status}",
    },
    "cli.dry_run": {
        "de": "Trockenlauf - keine echten Aktionen",
        "en": "Dry run - no real actions",
    },
    "cli.help": {
        "de": "Zeige Hilfe",
        "en": "Show help",
    },
    "cli.version": {
        "de": "Version: {version}",
        "en": "Version: {version}",
    },
}


def get_message(
    key: str,
    language: Optional[str] = None,
    **kwargs,
) -> str:
    """
    Get a translated message by key.
    
    Args:
        key: The message key (e.g., 'validation.empty_input')
        language: Language code ('de' or 'en'). Defaults to DEFAULT_LANGUAGE.
        **kwargs: Format arguments for the message template
    
    Returns:
        The translated and formatted message string.
        If the key is not found, returns the key itself.
        If the language is not found, falls back to DEFAULT_LANGUAGE.
    
    Examples:
        >>> get_message('status.available', 'en')
        'Available'
        >>> get_message('validation.invalid_tld', 'de', tld='xyz')
        "TLD 'xyz' ist nicht in der konfigurierten Liste erlaubt"
    """
    # Use default language if not specified or invalid
    if language is None or language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE
    
    # Get translations for the key
    translations = TRANSLATIONS.get(key)
    
    if translations is None:
        # Key not found, return the key itself
        return key
    
    # Get message for the requested language
    message = translations.get(language)
    
    if message is None:
        # Language not found, try default language
        message = translations.get(DEFAULT_LANGUAGE)
    
    if message is None:
        # No translation available, return the key
        return key
    
    # Format the message with provided arguments
    if kwargs:
        try:
            message = message.format(**kwargs)
        except KeyError:
            # If formatting fails, return the unformatted message
            pass
    
    return message


def get_all_message_keys() -> set[str]:
    """
    Get all available message keys.
    
    Returns:
        Set of all message keys in the translation dictionary.
    """
    return set(TRANSLATIONS.keys())


def has_translation(key: str, language: str) -> bool:
    """
    Check if a translation exists for a key and language.
    
    Args:
        key: The message key
        language: The language code
    
    Returns:
        True if translation exists, False otherwise.
    """
    translations = TRANSLATIONS.get(key)
    if translations is None:
        return False
    return language in translations


def get_missing_translations(language: str) -> set[str]:
    """
    Get all message keys that are missing translations for a language.
    
    Args:
        language: The language code to check
    
    Returns:
        Set of message keys missing translations for the specified language.
    """
    missing = set()
    for key, translations in TRANSLATIONS.items():
        if language not in translations:
            missing.add(key)
    return missing


def validate_translations() -> dict[str, set[str]]:
    """
    Validate that all languages have all translations.
    
    Returns:
        Dictionary mapping language codes to sets of missing message keys.
        Empty sets indicate complete translations.
    """
    result = {}
    for language in SUPPORTED_LANGUAGES:
        result[language] = get_missing_translations(language)
    return result
