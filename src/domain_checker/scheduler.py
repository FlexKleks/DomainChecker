"""
Scheduler module for the domain checker system.

This module provides cron-compatible scheduling for periodic domain checks.

Requirements covered:
- 12.1: Support cron-compatible scheduling expressions
"""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Awaitable, Callable, Optional


class CronParseError(Exception):
    """Raised when a cron expression cannot be parsed."""

    def __init__(self, message: str, expression: str) -> None:
        self.message = message
        self.expression = expression
        super().__init__(f"{message}: '{expression}'")


@dataclass
class CronField:
    """Represents a parsed cron field with allowed values."""

    values: set[int]
    min_value: int
    max_value: int

    def matches(self, value: int) -> bool:
        """Check if a value matches this field."""
        return value in self.values


@dataclass
class CronSchedule:
    """Represents a parsed cron schedule."""

    minute: CronField
    hour: CronField
    day_of_month: CronField
    month: CronField
    day_of_week: CronField
    original_expression: str

    def matches(self, dt: datetime) -> bool:
        """Check if a datetime matches this schedule."""
        # Day matching: either day_of_month OR day_of_week must match
        # (unless both are restricted, then both must match)
        day_of_month_all = self.day_of_month.values == set(
            range(self.day_of_month.min_value, self.day_of_month.max_value + 1)
        )
        day_of_week_all = self.day_of_week.values == set(
            range(self.day_of_week.min_value, self.day_of_week.max_value + 1)
        )

        minute_match = self.minute.matches(dt.minute)
        hour_match = self.hour.matches(dt.hour)
        month_match = self.month.matches(dt.month)

        if day_of_month_all and day_of_week_all:
            # Both are wildcards, any day matches
            day_match = True
        elif day_of_month_all:
            # Only day_of_week is restricted
            day_match = self.day_of_week.matches(dt.weekday())
        elif day_of_week_all:
            # Only day_of_month is restricted
            day_match = self.day_of_month.matches(dt.day)
        else:
            # Both are restricted, either must match (OR logic per cron standard)
            day_match = self.day_of_month.matches(dt.day) or self.day_of_week.matches(
                dt.weekday()
            )

        return minute_match and hour_match and day_match and month_match


class CronParser:
    """Parser for cron expressions."""

    # Field definitions: (min, max, name)
    FIELD_DEFS = [
        (0, 59, "minute"),
        (0, 23, "hour"),
        (1, 31, "day_of_month"),
        (1, 12, "month"),
        (0, 6, "day_of_week"),  # 0 = Monday in Python's weekday()
    ]

    # Month name mappings
    MONTH_NAMES = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4,
        "may": 5, "jun": 6, "jul": 7, "aug": 8,
        "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }

    # Day of week name mappings (0 = Monday to match Python's weekday())
    DOW_NAMES = {
        "mon": 0, "tue": 1, "wed": 2, "thu": 3,
        "fri": 4, "sat": 5, "sun": 6,
    }

    def parse(self, expression: str) -> CronSchedule:
        """
        Parse a cron expression into a CronSchedule.

        Supports standard 5-field cron expressions:
        - minute (0-59)
        - hour (0-23)
        - day of month (1-31)
        - month (1-12)
        - day of week (0-6, where 0=Monday)

        Also supports 6-field expressions where the first field is seconds
        (which is ignored for this implementation).

        Special characters supported:
        - * : any value
        - , : value list separator
        - - : range of values
        - / : step values

        Args:
            expression: The cron expression to parse

        Returns:
            A CronSchedule object

        Raises:
            CronParseError: If the expression is invalid
        """
        expression = expression.strip()
        if not expression:
            raise CronParseError("Empty cron expression", expression)

        fields = expression.split()

        # Support both 5-field and 6-field (with seconds) expressions
        if len(fields) == 6:
            # Skip the seconds field (first field)
            fields = fields[1:]
        elif len(fields) != 5:
            raise CronParseError(
                f"Invalid number of fields (expected 5 or 6, got {len(fields)})",
                expression,
            )

        parsed_fields = []
        for i, (field_str, (min_val, max_val, name)) in enumerate(
            zip(fields, self.FIELD_DEFS)
        ):
            try:
                parsed = self._parse_field(field_str, min_val, max_val, name)
                parsed_fields.append(parsed)
            except ValueError as e:
                raise CronParseError(f"Invalid {name} field: {e}", expression) from e

        return CronSchedule(
            minute=parsed_fields[0],
            hour=parsed_fields[1],
            day_of_month=parsed_fields[2],
            month=parsed_fields[3],
            day_of_week=parsed_fields[4],
            original_expression=expression,
        )

    def _parse_field(
        self, field_str: str, min_val: int, max_val: int, field_name: str
    ) -> CronField:
        """Parse a single cron field."""
        values: set[int] = set()

        # Handle name substitutions for month and day_of_week
        field_str_lower = field_str.lower()
        if field_name == "month":
            for name, num in self.MONTH_NAMES.items():
                field_str_lower = field_str_lower.replace(name, str(num))
            field_str = field_str_lower
        elif field_name == "day_of_week":
            for name, num in self.DOW_NAMES.items():
                field_str_lower = field_str_lower.replace(name, str(num))
            field_str = field_str_lower

        # Split by comma for multiple values/ranges
        parts = field_str.split(",")

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Handle step values (e.g., */5, 0-30/5)
            step = 1
            if "/" in part:
                part, step_str = part.split("/", 1)
                try:
                    step = int(step_str)
                    if step < 1:
                        raise ValueError(f"Step must be >= 1, got {step}")
                except ValueError as e:
                    raise ValueError(f"Invalid step value: {step_str}") from e

            # Handle wildcard
            if part == "*":
                values.update(range(min_val, max_val + 1, step))
                continue

            # Handle range (e.g., 1-5)
            if "-" in part:
                range_parts = part.split("-", 1)
                try:
                    start = int(range_parts[0])
                    end = int(range_parts[1])
                except ValueError as e:
                    raise ValueError(f"Invalid range: {part}") from e

                if start < min_val or start > max_val:
                    raise ValueError(
                        f"Range start {start} out of bounds [{min_val}-{max_val}]"
                    )
                if end < min_val or end > max_val:
                    raise ValueError(
                        f"Range end {end} out of bounds [{min_val}-{max_val}]"
                    )
                if start > end:
                    raise ValueError(f"Range start {start} > end {end}")

                values.update(range(start, end + 1, step))
                continue

            # Handle single value
            try:
                val = int(part)
            except ValueError as e:
                raise ValueError(f"Invalid value: {part}") from e

            if val < min_val or val > max_val:
                raise ValueError(f"Value {val} out of bounds [{min_val}-{max_val}]")

            values.add(val)

        if not values:
            raise ValueError("No values parsed from field")

        return CronField(values=values, min_value=min_val, max_value=max_val)


@dataclass
class ScheduledTask:
    """Represents a scheduled task."""

    name: str
    schedule: CronSchedule
    callback: Callable[[], Awaitable[None]]
    last_run: Optional[datetime] = None
    enabled: bool = True


class Scheduler:
    """
    Cron-compatible scheduler for periodic domain checks.

    Requirement 12.1: Support cron-compatible scheduling expressions.
    """

    def __init__(self) -> None:
        """Initialize the scheduler."""
        self._parser = CronParser()
        self._tasks: dict[str, ScheduledTask] = {}
        self._running = False
        self._check_interval_seconds = 60  # Check every minute

    def schedule(
        self,
        name: str,
        cron_expression: str,
        callback: Callable[[], Awaitable[None]],
    ) -> CronSchedule:
        """
        Schedule a task with a cron expression.

        Args:
            name: Unique name for the task
            cron_expression: Cron expression (5 or 6 fields)
            callback: Async function to call when schedule matches

        Returns:
            The parsed CronSchedule

        Raises:
            CronParseError: If the cron expression is invalid
            ValueError: If a task with the same name already exists
        """
        if name in self._tasks:
            raise ValueError(f"Task '{name}' already exists")

        schedule = self._parser.parse(cron_expression)
        task = ScheduledTask(
            name=name,
            schedule=schedule,
            callback=callback,
        )
        self._tasks[name] = task
        return schedule

    def unschedule(self, name: str) -> bool:
        """
        Remove a scheduled task.

        Args:
            name: Name of the task to remove

        Returns:
            True if the task was removed, False if it didn't exist
        """
        if name in self._tasks:
            del self._tasks[name]
            return True
        return False

    def get_task(self, name: str) -> Optional[ScheduledTask]:
        """Get a scheduled task by name."""
        return self._tasks.get(name)

    def list_tasks(self) -> list[ScheduledTask]:
        """List all scheduled tasks."""
        return list(self._tasks.values())

    def enable_task(self, name: str) -> bool:
        """Enable a task. Returns True if task exists."""
        if name in self._tasks:
            self._tasks[name].enabled = True
            return True
        return False

    def disable_task(self, name: str) -> bool:
        """Disable a task. Returns True if task exists."""
        if name in self._tasks:
            self._tasks[name].enabled = False
            return True
        return False

    async def run(self, stop_event: Optional[asyncio.Event] = None) -> None:
        """
        Run the scheduler loop.

        This method runs indefinitely, checking every minute if any
        scheduled tasks should be executed.

        Args:
            stop_event: Optional event to signal the scheduler to stop
        """
        self._running = True

        while self._running:
            now = datetime.now()
            # Truncate to minute precision for matching
            now_minute = now.replace(second=0, microsecond=0)

            for task in self._tasks.values():
                if not task.enabled:
                    continue

                # Check if this task should run now
                if task.schedule.matches(now_minute):
                    # Avoid running the same task multiple times in the same minute
                    if task.last_run is None or task.last_run < now_minute:
                        task.last_run = now_minute
                        try:
                            await task.callback()
                        except Exception:
                            # Log error but continue running other tasks
                            pass

            # Check if we should stop
            if stop_event is not None and stop_event.is_set():
                break

            # Wait until the next minute
            await asyncio.sleep(self._check_interval_seconds)

        self._running = False

    def stop(self) -> None:
        """Signal the scheduler to stop."""
        self._running = False

    def is_running(self) -> bool:
        """Check if the scheduler is running."""
        return self._running

    def parse_cron(self, expression: str) -> CronSchedule:
        """
        Parse a cron expression without scheduling a task.

        Useful for validation.

        Args:
            expression: The cron expression to parse

        Returns:
            The parsed CronSchedule

        Raises:
            CronParseError: If the expression is invalid
        """
        return self._parser.parse(expression)
