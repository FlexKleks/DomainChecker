"""
Property-based tests for scheduler module.

Uses Hypothesis for property-based testing to verify correctness properties
defined in the design document.
"""

from datetime import datetime

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from domain_checker.scheduler import (
    CronParser,
    CronParseError,
    CronSchedule,
    Scheduler,
)


# Strategy for valid cron field values
def valid_minute() -> st.SearchStrategy[str]:
    """Generate valid minute field (0-59)."""
    return st.one_of(
        st.just("*"),
        st.integers(min_value=0, max_value=59).map(str),
        # Range
        st.builds(
            lambda a, b: f"{min(a, b)}-{max(a, b)}",
            st.integers(min_value=0, max_value=59),
            st.integers(min_value=0, max_value=59),
        ),
        # Step
        st.builds(
            lambda step: f"*/{step}",
            st.integers(min_value=1, max_value=30),
        ),
        # List
        st.lists(
            st.integers(min_value=0, max_value=59),
            min_size=1,
            max_size=3,
            unique=True,
        ).map(lambda vals: ",".join(str(v) for v in sorted(vals))),
    )


def valid_hour() -> st.SearchStrategy[str]:
    """Generate valid hour field (0-23)."""
    return st.one_of(
        st.just("*"),
        st.integers(min_value=0, max_value=23).map(str),
        # Range
        st.builds(
            lambda a, b: f"{min(a, b)}-{max(a, b)}",
            st.integers(min_value=0, max_value=23),
            st.integers(min_value=0, max_value=23),
        ),
        # Step
        st.builds(
            lambda step: f"*/{step}",
            st.integers(min_value=1, max_value=12),
        ),
    )


def valid_day_of_month() -> st.SearchStrategy[str]:
    """Generate valid day of month field (1-31)."""
    return st.one_of(
        st.just("*"),
        st.integers(min_value=1, max_value=31).map(str),
        # Range
        st.builds(
            lambda a, b: f"{min(a, b)}-{max(a, b)}",
            st.integers(min_value=1, max_value=31),
            st.integers(min_value=1, max_value=31),
        ),
    )


def valid_month() -> st.SearchStrategy[str]:
    """Generate valid month field (1-12)."""
    return st.one_of(
        st.just("*"),
        st.integers(min_value=1, max_value=12).map(str),
        # Named months
        st.sampled_from(["jan", "feb", "mar", "apr", "may", "jun", 
                         "jul", "aug", "sep", "oct", "nov", "dec"]),
        # Range
        st.builds(
            lambda a, b: f"{min(a, b)}-{max(a, b)}",
            st.integers(min_value=1, max_value=12),
            st.integers(min_value=1, max_value=12),
        ),
    )


def valid_day_of_week() -> st.SearchStrategy[str]:
    """Generate valid day of week field (0-6)."""
    return st.one_of(
        st.just("*"),
        st.integers(min_value=0, max_value=6).map(str),
        # Named days
        st.sampled_from(["mon", "tue", "wed", "thu", "fri", "sat", "sun"]),
        # Range
        st.builds(
            lambda a, b: f"{min(a, b)}-{max(a, b)}",
            st.integers(min_value=0, max_value=6),
            st.integers(min_value=0, max_value=6),
        ),
    )


def valid_cron_expression_5_fields() -> st.SearchStrategy[str]:
    """Generate valid 5-field cron expressions."""
    return st.builds(
        lambda m, h, dom, mon, dow: f"{m} {h} {dom} {mon} {dow}",
        valid_minute(),
        valid_hour(),
        valid_day_of_month(),
        valid_month(),
        valid_day_of_week(),
    )


def valid_cron_expression_6_fields() -> st.SearchStrategy[str]:
    """Generate valid 6-field cron expressions (with seconds)."""
    return st.builds(
        lambda s, m, h, dom, mon, dow: f"{s} {m} {h} {dom} {mon} {dow}",
        st.one_of(st.just("*"), st.integers(min_value=0, max_value=59).map(str)),
        valid_minute(),
        valid_hour(),
        valid_day_of_month(),
        valid_month(),
        valid_day_of_week(),
    )


def valid_cron_expression() -> st.SearchStrategy[str]:
    """Generate any valid cron expression (5 or 6 fields)."""
    return st.one_of(
        valid_cron_expression_5_fields(),
        valid_cron_expression_6_fields(),
    )


class TestCronParsingProperty:
    """
    Property-based tests for cron expression parsing.
    
    **Feature: domain-availability-checker, Property 32: Valid cron expressions parse successfully**
    **Validates: Requirements 12.1**
    """

    @given(expression=valid_cron_expression_5_fields())
    @settings(max_examples=100)
    def test_valid_5_field_cron_parses_successfully(self, expression: str) -> None:
        """
        Property 32a: Valid 5-field cron expressions parse successfully.
        
        *For any* valid cron expression with 5 fields (minute, hour, day of month,
        month, day of week), the scheduler SHALL parse it without error and 
        produce a valid schedule.
        
        **Feature: domain-availability-checker, Property 32: Valid cron expressions parse successfully**
        **Validates: Requirements 12.1**
        """
        parser = CronParser()
        
        # Parsing should not raise an exception
        schedule = parser.parse(expression)
        
        # Result should be a CronSchedule
        assert isinstance(schedule, CronSchedule), (
            f"Parse result should be CronSchedule, got {type(schedule)}"
        )
        
        # Original expression should be stored
        assert schedule.original_expression == expression, (
            f"Original expression should be preserved"
        )
        
        # All fields should have valid values
        assert len(schedule.minute.values) > 0, "Minute field should have values"
        assert len(schedule.hour.values) > 0, "Hour field should have values"
        assert len(schedule.day_of_month.values) > 0, "Day of month field should have values"
        assert len(schedule.month.values) > 0, "Month field should have values"
        assert len(schedule.day_of_week.values) > 0, "Day of week field should have values"
        
        # Values should be within valid ranges
        assert all(0 <= v <= 59 for v in schedule.minute.values), (
            f"Minute values out of range: {schedule.minute.values}"
        )
        assert all(0 <= v <= 23 for v in schedule.hour.values), (
            f"Hour values out of range: {schedule.hour.values}"
        )
        assert all(1 <= v <= 31 for v in schedule.day_of_month.values), (
            f"Day of month values out of range: {schedule.day_of_month.values}"
        )
        assert all(1 <= v <= 12 for v in schedule.month.values), (
            f"Month values out of range: {schedule.month.values}"
        )
        assert all(0 <= v <= 6 for v in schedule.day_of_week.values), (
            f"Day of week values out of range: {schedule.day_of_week.values}"
        )

    @given(expression=valid_cron_expression_6_fields())
    @settings(max_examples=100)
    def test_valid_6_field_cron_parses_successfully(self, expression: str) -> None:
        """
        Property 32b: Valid 6-field cron expressions parse successfully.
        
        *For any* valid cron expression with 6 fields (seconds, minute, hour, 
        day of month, month, day of week), the scheduler SHALL parse it without 
        error and produce a valid schedule.
        
        **Feature: domain-availability-checker, Property 32: Valid cron expressions parse successfully**
        **Validates: Requirements 12.1**
        """
        parser = CronParser()
        
        # Parsing should not raise an exception
        schedule = parser.parse(expression)
        
        # Result should be a CronSchedule
        assert isinstance(schedule, CronSchedule), (
            f"Parse result should be CronSchedule, got {type(schedule)}"
        )
        
        # All fields should have valid values within ranges
        assert all(0 <= v <= 59 for v in schedule.minute.values)
        assert all(0 <= v <= 23 for v in schedule.hour.values)
        assert all(1 <= v <= 31 for v in schedule.day_of_month.values)
        assert all(1 <= v <= 12 for v in schedule.month.values)
        assert all(0 <= v <= 6 for v in schedule.day_of_week.values)

    @given(expression=valid_cron_expression())
    @settings(max_examples=100)
    def test_parsed_schedule_can_match_datetime(self, expression: str) -> None:
        """
        Property 32c: Parsed schedules can match datetimes.
        
        *For any* valid cron expression, the parsed schedule SHALL be able to
        evaluate whether a datetime matches the schedule.
        
        **Feature: domain-availability-checker, Property 32: Valid cron expressions parse successfully**
        **Validates: Requirements 12.1**
        """
        parser = CronParser()
        schedule = parser.parse(expression)
        
        # Should be able to call matches() without error
        now = datetime.now()
        result = schedule.matches(now)
        
        # Result should be a boolean
        assert isinstance(result, bool), (
            f"matches() should return bool, got {type(result)}"
        )

    @given(expression=valid_cron_expression())
    @settings(max_examples=100)
    def test_scheduler_can_schedule_with_valid_expression(self, expression: str) -> None:
        """
        Property 32d: Scheduler accepts valid cron expressions.
        
        *For any* valid cron expression, the Scheduler.schedule() method SHALL
        accept it and return a valid CronSchedule.
        
        **Feature: domain-availability-checker, Property 32: Valid cron expressions parse successfully**
        **Validates: Requirements 12.1**
        """
        scheduler = Scheduler()
        
        async def dummy_callback() -> None:
            pass
        
        # Should be able to schedule without error
        schedule = scheduler.schedule("test_task", expression, dummy_callback)
        
        # Result should be a CronSchedule
        assert isinstance(schedule, CronSchedule)
        
        # Task should be registered
        task = scheduler.get_task("test_task")
        assert task is not None
        assert task.name == "test_task"
        assert task.schedule == schedule

    def test_common_cron_expressions_parse(self) -> None:
        """
        Test that common real-world cron expressions parse correctly.
        
        **Feature: domain-availability-checker, Property 32: Valid cron expressions parse successfully**
        **Validates: Requirements 12.1**
        """
        parser = CronParser()
        
        # Common cron expressions
        common_expressions = [
            "* * * * *",           # Every minute
            "0 * * * *",           # Every hour
            "0 0 * * *",           # Every day at midnight
            "0 0 * * 0",           # Every Sunday at midnight
            "0 0 1 * *",           # First day of every month
            "*/5 * * * *",         # Every 5 minutes
            "0 */2 * * *",         # Every 2 hours
            "0 9-17 * * 1-5",      # 9am-5pm on weekdays
            "30 4 1,15 * *",       # 4:30am on 1st and 15th
            "0 0 * * mon",         # Every Monday at midnight
            "0 0 1 jan *",         # January 1st at midnight
            "0 0 * * mon-fri",     # Every weekday at midnight
        ]
        
        for expr in common_expressions:
            schedule = parser.parse(expr)
            assert isinstance(schedule, CronSchedule), (
                f"Failed to parse common expression: {expr}"
            )

    def test_wildcard_matches_all_values(self) -> None:
        """
        Test that wildcard (*) matches all values in a field.
        
        **Feature: domain-availability-checker, Property 32: Valid cron expressions parse successfully**
        **Validates: Requirements 12.1**
        """
        parser = CronParser()
        schedule = parser.parse("* * * * *")
        
        # All minutes should match
        assert schedule.minute.values == set(range(0, 60))
        # All hours should match
        assert schedule.hour.values == set(range(0, 24))
        # All days of month should match
        assert schedule.day_of_month.values == set(range(1, 32))
        # All months should match
        assert schedule.month.values == set(range(1, 13))
        # All days of week should match
        assert schedule.day_of_week.values == set(range(0, 7))

    def test_step_values_generate_correct_sequence(self) -> None:
        """
        Test that step values (*/n) generate correct sequences.
        
        **Feature: domain-availability-checker, Property 32: Valid cron expressions parse successfully**
        **Validates: Requirements 12.1**
        """
        parser = CronParser()
        
        # Every 5 minutes
        schedule = parser.parse("*/5 * * * *")
        assert schedule.minute.values == {0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}
        
        # Every 2 hours
        schedule = parser.parse("0 */2 * * *")
        assert schedule.hour.values == {0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22}
        
        # Every 15 minutes
        schedule = parser.parse("*/15 * * * *")
        assert schedule.minute.values == {0, 15, 30, 45}

    def test_range_values_generate_correct_sequence(self) -> None:
        """
        Test that range values (a-b) generate correct sequences.
        
        **Feature: domain-availability-checker, Property 32: Valid cron expressions parse successfully**
        **Validates: Requirements 12.1**
        """
        parser = CronParser()
        
        # 9am to 5pm
        schedule = parser.parse("0 9-17 * * *")
        assert schedule.hour.values == {9, 10, 11, 12, 13, 14, 15, 16, 17}
        
        # Monday to Friday (0-4 in our system)
        schedule = parser.parse("0 0 * * 0-4")
        assert schedule.day_of_week.values == {0, 1, 2, 3, 4}

    def test_list_values_generate_correct_set(self) -> None:
        """
        Test that list values (a,b,c) generate correct sets.
        
        **Feature: domain-availability-checker, Property 32: Valid cron expressions parse successfully**
        **Validates: Requirements 12.1**
        """
        parser = CronParser()
        
        # Specific minutes
        schedule = parser.parse("0,15,30,45 * * * *")
        assert schedule.minute.values == {0, 15, 30, 45}
        
        # Specific days
        schedule = parser.parse("0 0 1,15 * *")
        assert schedule.day_of_month.values == {1, 15}


class TestCronParsingInvalidExpressions:
    """
    Tests for invalid cron expression handling.
    """

    def test_empty_expression_raises_error(self) -> None:
        """Test that empty expressions raise CronParseError."""
        parser = CronParser()
        
        try:
            parser.parse("")
            assert False, "Should have raised CronParseError"
        except CronParseError as e:
            assert "Empty" in e.message

    def test_wrong_field_count_raises_error(self) -> None:
        """Test that wrong number of fields raises CronParseError."""
        parser = CronParser()
        
        invalid_expressions = [
            "* * *",           # Too few fields
            "* * * *",         # Too few fields
            "* * * * * * *",   # Too many fields
        ]
        
        for expr in invalid_expressions:
            try:
                parser.parse(expr)
                assert False, f"Should have raised CronParseError for: {expr}"
            except CronParseError:
                pass

    def test_out_of_range_values_raise_error(self) -> None:
        """Test that out-of-range values raise CronParseError."""
        parser = CronParser()
        
        invalid_expressions = [
            "60 * * * *",      # Minute > 59
            "* 24 * * *",      # Hour > 23
            "* * 32 * *",      # Day > 31
            "* * 0 * *",       # Day < 1
            "* * * 13 *",      # Month > 12
            "* * * 0 *",       # Month < 1
            "* * * * 7",       # Day of week > 6
        ]
        
        for expr in invalid_expressions:
            try:
                parser.parse(expr)
                assert False, f"Should have raised CronParseError for: {expr}"
            except CronParseError:
                pass
