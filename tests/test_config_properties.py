"""
Property-based tests for configuration module.

Uses Hypothesis for property-based testing to verify correctness properties
defined in the design document.
"""

import json
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from domain_checker.config import (
    TLDConfig,
    RateLimitRule,
    RateLimitConfig,
    RetryConfig,
    TelegramConfig,
    DiscordConfig,
    EmailConfig,
    WebhookConfig,
    NotificationConfig,
    PersistenceConfig,
    LoggingConfig,
    SystemConfig,
)


# Strategies for generating valid configuration objects

@st.composite
def tld_config_strategy(draw) -> TLDConfig:
    """Generate valid TLDConfig objects."""
    tld = draw(st.sampled_from(["de", "com", "net", "org", "eu"]))
    rdap_endpoint = draw(st.text(min_size=10, max_size=50).map(
        lambda s: f"https://rdap.{tld}.example/{s.replace(' ', '')}"
    ))
    secondary = draw(st.one_of(
        st.none(),
        st.text(min_size=10, max_size=50).map(
            lambda s: f"https://rdap2.{tld}.example/{s.replace(' ', '')}"
        )
    ))
    whois_server = draw(st.one_of(
        st.none(),
        st.text(min_size=5, max_size=30).map(
            lambda s: f"whois.{s.replace(' ', '')}.example"
        )
    ))
    whois_enabled = draw(st.booleans())
    
    return TLDConfig(
        tld=tld,
        rdap_endpoint=rdap_endpoint,
        secondary_rdap_endpoint=secondary,
        whois_server=whois_server,
        whois_enabled=whois_enabled,
    )


@st.composite
def rate_limit_rule_strategy(draw) -> RateLimitRule:
    """Generate valid RateLimitRule objects."""
    return RateLimitRule(
        max_requests=draw(st.integers(min_value=1, max_value=1000)),
        window_seconds=draw(st.floats(min_value=0.1, max_value=3600.0)),
        min_delay_seconds=draw(st.floats(min_value=0.0, max_value=60.0)),
    )


@st.composite
def rate_limit_config_strategy(draw) -> RateLimitConfig:
    """Generate valid RateLimitConfig objects."""
    tlds = ["de", "com", "net", "org", "eu"]
    per_tld = {}
    for tld in draw(st.lists(st.sampled_from(tlds), max_size=3, unique=True)):
        per_tld[tld] = draw(rate_limit_rule_strategy())
    
    per_endpoint = {}
    for _ in range(draw(st.integers(min_value=0, max_value=2))):
        endpoint = draw(st.text(min_size=5, max_size=20).map(
            lambda s: f"https://{s.replace(' ', '')}.example"
        ))
        per_endpoint[endpoint] = draw(rate_limit_rule_strategy())
    
    return RateLimitConfig(
        per_tld=per_tld,
        per_endpoint=per_endpoint,
        global_limit=draw(st.one_of(st.none(), rate_limit_rule_strategy())),
        per_ip=draw(st.one_of(st.none(), rate_limit_rule_strategy())),
    )


@st.composite
def retry_config_strategy(draw) -> RetryConfig:
    """Generate valid RetryConfig objects."""
    return RetryConfig(
        max_retries=draw(st.integers(min_value=0, max_value=10)),
        base_delay_seconds=draw(st.floats(min_value=0.1, max_value=10.0)),
        max_delay_seconds=draw(st.floats(min_value=10.0, max_value=300.0)),
        retryable_errors=draw(st.lists(
            st.sampled_from(["timeout", "server_error", "rate_limited", "network_error"]),
            min_size=0,
            max_size=4,
            unique=True,
        )),
    )


@st.composite
def notification_config_strategy(draw) -> NotificationConfig:
    """Generate valid NotificationConfig objects."""
    telegram = None
    if draw(st.booleans()):
        telegram = TelegramConfig(
            bot_token=draw(st.text(min_size=10, max_size=50)),
            chat_id=draw(st.text(min_size=5, max_size=20)),
        )
    
    discord = None
    if draw(st.booleans()):
        discord = DiscordConfig(
            webhook_url=draw(st.text(min_size=20, max_size=100)),
        )
    
    email = None
    if draw(st.booleans()):
        email = EmailConfig(
            smtp_host=draw(st.text(min_size=5, max_size=30)),
            smtp_port=draw(st.integers(min_value=1, max_value=65535)),
            username=draw(st.text(min_size=1, max_size=30)),
            password=draw(st.text(min_size=1, max_size=30)),
            from_address=draw(st.emails()),
            to_addresses=draw(st.lists(st.emails(), min_size=1, max_size=3)),
        )
    
    webhook = None
    if draw(st.booleans()):
        headers = {}
        for _ in range(draw(st.integers(min_value=0, max_value=3))):
            key = draw(st.text(min_size=1, max_size=20))
            value = draw(st.text(min_size=1, max_size=50))
            headers[key] = value
        webhook = WebhookConfig(
            url=draw(st.text(min_size=10, max_size=100)),
            headers=headers,
        )
    
    return NotificationConfig(
        telegram=telegram,
        discord=discord,
        email=email,
        webhook=webhook,
    )


@st.composite
def persistence_config_strategy(draw) -> PersistenceConfig:
    """Generate valid PersistenceConfig objects."""
    return PersistenceConfig(
        state_file_path=Path(draw(st.text(min_size=5, max_size=50).map(
            lambda s: f"/tmp/{s.replace(' ', '_').replace('/', '_')}.json"
        ))),
        hmac_secret=draw(st.text(min_size=16, max_size=64)),
    )


@st.composite
def logging_config_strategy(draw) -> LoggingConfig:
    """Generate valid LoggingConfig objects."""
    audit_mode = draw(st.booleans())
    return LoggingConfig(
        level=draw(st.sampled_from(["debug", "info", "warn", "error"])),
        audit_mode=audit_mode,
        audit_signing_key=draw(st.text(min_size=16, max_size=64)) if audit_mode else None,
        output_format=draw(st.sampled_from(["json", "text", "both"])),
    )


@st.composite
def system_config_strategy(draw) -> SystemConfig:
    """Generate valid SystemConfig objects."""
    return SystemConfig(
        tlds=draw(st.lists(tld_config_strategy(), min_size=1, max_size=3)),
        rate_limits=draw(rate_limit_config_strategy()),
        retry=draw(retry_config_strategy()),
        notifications=draw(notification_config_strategy()),
        persistence=draw(persistence_config_strategy()),
        logging=draw(logging_config_strategy()),
        language=draw(st.sampled_from(["de", "en"])),
        simulation_mode=draw(st.booleans()),
        startup_self_test=draw(st.booleans()),
    )


def config_to_dict(config: SystemConfig) -> dict:
    """Convert SystemConfig to a JSON-serializable dictionary."""
    def serialize(obj):
        if hasattr(obj, '__dataclass_fields__'):
            result = {}
            for field_name in obj.__dataclass_fields__:
                value = getattr(obj, field_name)
                result[field_name] = serialize(value)
            return result
        elif isinstance(obj, Path):
            return str(obj)
        elif isinstance(obj, dict):
            return {k: serialize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [serialize(item) for item in obj]
        else:
            return obj
    
    return serialize(config)


def dict_to_config(data: dict) -> SystemConfig:
    """Convert a dictionary back to SystemConfig."""
    # Reconstruct TLDConfig list
    tlds = [
        TLDConfig(
            tld=t["tld"],
            rdap_endpoint=t["rdap_endpoint"],
            secondary_rdap_endpoint=t.get("secondary_rdap_endpoint"),
            whois_server=t.get("whois_server"),
            whois_enabled=t.get("whois_enabled", False),
        )
        for t in data["tlds"]
    ]
    
    # Reconstruct RateLimitConfig
    rate_limits_data = data["rate_limits"]
    per_tld = {
        k: RateLimitRule(**v) for k, v in rate_limits_data.get("per_tld", {}).items()
    }
    per_endpoint = {
        k: RateLimitRule(**v) for k, v in rate_limits_data.get("per_endpoint", {}).items()
    }
    global_limit = None
    if rate_limits_data.get("global_limit"):
        global_limit = RateLimitRule(**rate_limits_data["global_limit"])
    per_ip = None
    if rate_limits_data.get("per_ip"):
        per_ip = RateLimitRule(**rate_limits_data["per_ip"])
    
    rate_limits = RateLimitConfig(
        per_tld=per_tld,
        per_endpoint=per_endpoint,
        global_limit=global_limit,
        per_ip=per_ip,
    )
    
    # Reconstruct RetryConfig
    retry = RetryConfig(**data["retry"])
    
    # Reconstruct NotificationConfig
    notif_data = data["notifications"]
    telegram = TelegramConfig(**notif_data["telegram"]) if notif_data.get("telegram") else None
    discord = DiscordConfig(**notif_data["discord"]) if notif_data.get("discord") else None
    email = EmailConfig(**notif_data["email"]) if notif_data.get("email") else None
    webhook = WebhookConfig(**notif_data["webhook"]) if notif_data.get("webhook") else None
    
    notifications = NotificationConfig(
        telegram=telegram,
        discord=discord,
        email=email,
        webhook=webhook,
    )
    
    # Reconstruct PersistenceConfig
    persistence = PersistenceConfig(
        state_file_path=Path(data["persistence"]["state_file_path"]),
        hmac_secret=data["persistence"]["hmac_secret"],
    )
    
    # Reconstruct LoggingConfig
    logging_cfg = LoggingConfig(**data["logging"])
    
    return SystemConfig(
        tlds=tlds,
        rate_limits=rate_limits,
        retry=retry,
        notifications=notifications,
        persistence=persistence,
        logging=logging_cfg,
        language=data.get("language", "de"),
        simulation_mode=data.get("simulation_mode", False),
        startup_self_test=data.get("startup_self_test", True),
    )


class TestConfigurationRoundTripProperty:
    """
    Property-based tests for configuration serialization round-trip.
    
    **Feature: domain-availability-checker, Property 21: Configuration round-trips without data loss**
    **Validates: Requirements 13.3**
    """

    @given(config=system_config_strategy())
    @settings(max_examples=100)
    def test_config_round_trip_preserves_data(self, config: SystemConfig) -> None:
        """
        Property 21: Configuration round-trips without data loss.
        
        *For any* valid SystemConfig object, serializing to JSON and deserializing
        back SHALL produce an equivalent SystemConfig object.
        
        **Feature: domain-availability-checker, Property 21: Configuration round-trips without data loss**
        **Validates: Requirements 13.3**
        """
        # Serialize to dict
        serialized = config_to_dict(config)
        
        # Convert to JSON string and back (simulates file storage)
        json_str = json.dumps(serialized, sort_keys=True)
        deserialized_dict = json.loads(json_str)
        
        # Reconstruct config
        reconstructed = dict_to_config(deserialized_dict)
        
        # Verify all fields match
        assert reconstructed.language == config.language
        assert reconstructed.simulation_mode == config.simulation_mode
        assert reconstructed.startup_self_test == config.startup_self_test
        
        # Verify TLDs
        assert len(reconstructed.tlds) == len(config.tlds)
        for orig, recon in zip(config.tlds, reconstructed.tlds):
            assert recon.tld == orig.tld
            assert recon.rdap_endpoint == orig.rdap_endpoint
            assert recon.secondary_rdap_endpoint == orig.secondary_rdap_endpoint
            assert recon.whois_server == orig.whois_server
            assert recon.whois_enabled == orig.whois_enabled
        
        # Verify rate limits
        assert reconstructed.rate_limits.per_tld.keys() == config.rate_limits.per_tld.keys()
        for tld in config.rate_limits.per_tld:
            orig_rule = config.rate_limits.per_tld[tld]
            recon_rule = reconstructed.rate_limits.per_tld[tld]
            assert recon_rule.max_requests == orig_rule.max_requests
            assert recon_rule.window_seconds == orig_rule.window_seconds
            assert recon_rule.min_delay_seconds == orig_rule.min_delay_seconds
        
        # Verify retry config
        assert reconstructed.retry.max_retries == config.retry.max_retries
        assert reconstructed.retry.base_delay_seconds == config.retry.base_delay_seconds
        assert reconstructed.retry.max_delay_seconds == config.retry.max_delay_seconds
        assert reconstructed.retry.retryable_errors == config.retry.retryable_errors
        
        # Verify persistence config
        assert str(reconstructed.persistence.state_file_path) == str(config.persistence.state_file_path)
        assert reconstructed.persistence.hmac_secret == config.persistence.hmac_secret
        
        # Verify logging config
        assert reconstructed.logging.level == config.logging.level
        assert reconstructed.logging.audit_mode == config.logging.audit_mode
        assert reconstructed.logging.audit_signing_key == config.logging.audit_signing_key
        assert reconstructed.logging.output_format == config.logging.output_format

    @given(config=system_config_strategy())
    @settings(max_examples=100)
    def test_config_serialization_produces_valid_json(self, config: SystemConfig) -> None:
        """
        Property 21b: Configuration serialization produces valid JSON.
        
        *For any* valid SystemConfig object, serialization SHALL produce
        a valid JSON string that can be parsed without errors.
        
        **Feature: domain-availability-checker, Property 21: Configuration round-trips without data loss**
        **Validates: Requirements 13.3**
        """
        serialized = config_to_dict(config)
        
        # Must produce valid JSON
        json_str = json.dumps(serialized)
        assert json_str is not None
        assert len(json_str) > 0
        
        # Must be parseable
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        
        # Must contain all top-level keys
        expected_keys = {
            "tlds", "rate_limits", "retry", "notifications",
            "persistence", "logging", "language", "simulation_mode", "startup_self_test"
        }
        assert expected_keys == set(parsed.keys())

    @given(config=system_config_strategy())
    @settings(max_examples=100)
    def test_config_round_trip_is_idempotent(self, config: SystemConfig) -> None:
        """
        Property 21c: Configuration round-trip is idempotent.
        
        *For any* valid SystemConfig, round-tripping twice produces the same
        result as round-tripping once.
        
        **Feature: domain-availability-checker, Property 21: Configuration round-trips without data loss**
        **Validates: Requirements 13.3**
        """
        # First round-trip
        serialized1 = config_to_dict(config)
        json_str1 = json.dumps(serialized1, sort_keys=True)
        reconstructed1 = dict_to_config(json.loads(json_str1))
        
        # Second round-trip
        serialized2 = config_to_dict(reconstructed1)
        json_str2 = json.dumps(serialized2, sort_keys=True)
        
        # JSON strings should be identical
        assert json_str1 == json_str2, (
            "Round-trip is not idempotent: JSON differs after second round-trip"
        )
