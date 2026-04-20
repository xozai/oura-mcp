#!/usr/bin/env python3
"""
Oura Ring MCP Server

Provides Claude with access to your Oura Ring health data via the Oura API v2.
Covers: personal info, daily sleep, sleep sessions, readiness, activity,
heart rate, SpO2, stress, workouts, and mindfulness sessions.

Authentication: Set OURA_ACCESS_TOKEN environment variable with your
Personal Access Token from https://cloud.ouraring.com/personal-access-tokens
"""

import json
import os
import sys
from datetime import date, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Server initialization
# ---------------------------------------------------------------------------

mcp = FastMCP("oura_mcp")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_BASE_URL = "https://api.ouraring.com/v2/usercollection"
DEFAULT_DAYS = 7


# ---------------------------------------------------------------------------
# Shared enums & helpers
# ---------------------------------------------------------------------------


class ResponseFormat(str, Enum):
    """Output format for tool responses."""
    MARKDOWN = "markdown"
    JSON = "json"


def _get_token() -> str:
    token = os.environ.get("OURA_ACCESS_TOKEN", "")
    if not token:
        raise ValueError(
            "OURA_ACCESS_TOKEN environment variable is not set. "
            "Get your token at https://cloud.ouraring.com/personal-access-tokens"
        )
    return token


async def _api_get(endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Shared async GET request to the Oura API."""
    headers = {"Authorization": f"Bearer {_get_token()}"}
    url = f"{API_BASE_URL}/{endpoint}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers, params=params or {})
        response.raise_for_status()
        return response.json()


async def _api_get_single(endpoint: str) -> Dict[str, Any]:
    """GET for single-object endpoints (e.g. personal_info)."""
    headers = {"Authorization": f"Bearer {_get_token()}"}
    url = f"https://api.ouraring.com/v2/usercollection/{endpoint}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()


def _handle_error(e: Exception) -> str:
    """Return a clear, actionable error string."""
    if isinstance(e, ValueError):
        return f"Configuration error: {e}"
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 401:
            return (
                "Error: Unauthorized. Check that OURA_ACCESS_TOKEN is set correctly "
                "and has not expired."
            )
        if status == 403:
            return "Error: Forbidden. Your token may lack the required scope."
        if status == 404:
            return "Error: Resource not found. Check any IDs or date ranges."
        if status == 429:
            return "Error: Rate limit exceeded. Wait a moment and retry."
        return f"Error: Oura API returned HTTP {status}."
    if isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. Check your internet connection and retry."
    return f"Error: {type(e).__name__}: {e}"


def _default_dates(start_date: Optional[str], end_date: Optional[str]) -> tuple[str, str]:
    """Return (start_date, end_date) defaulting to the last DEFAULT_DAYS days."""
    today = date.today()
    end = end_date or today.isoformat()
    start = start_date or (today - timedelta(days=DEFAULT_DAYS - 1)).isoformat()
    return start, end


def _build_date_params(
    start_date: Optional[str],
    end_date: Optional[str],
    next_token: Optional[str] = None,
) -> Dict[str, str]:
    start, end = _default_dates(start_date, end_date)
    params: Dict[str, str] = {"start_date": start, "end_date": end}
    if next_token:
        params["next_token"] = next_token
    return params


# ---------------------------------------------------------------------------
# Pydantic input models
# ---------------------------------------------------------------------------


class DateRangeInput(BaseModel):
    """Common date-range input shared by most collection endpoints."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    start_date: Optional[str] = Field(
        default=None,
        description=(
            "Start date in YYYY-MM-DD format (inclusive). "
            f"Defaults to {DEFAULT_DAYS} days ago."
        ),
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    end_date: Optional[str] = Field(
        default=None,
        description="End date in YYYY-MM-DD format (inclusive). Defaults to today.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    next_token: Optional[str] = Field(
        default=None,
        description="Pagination token returned by a previous call to retrieve the next page.",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable, 'json' for raw data.",
    )


class HeartRateInput(BaseModel):
    """Heart rate queries use datetime range instead of date range."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    start_datetime: Optional[str] = Field(
        default=None,
        description=(
            "Start datetime in ISO 8601 format, e.g. '2024-01-01T00:00:00'. "
            f"Defaults to {DEFAULT_DAYS} days ago at midnight."
        ),
    )
    end_datetime: Optional[str] = Field(
        default=None,
        description=(
            "End datetime in ISO 8601 format, e.g. '2024-01-07T23:59:59'. "
            "Defaults to now."
        ),
    )
    next_token: Optional[str] = Field(default=None, description="Pagination token.")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'.",
    )


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _fmt_score(label: str, value: Any) -> str:
    if value is None:
        return f"- **{label}**: N/A"
    return f"- **{label}**: {value}"


def _fmt_list_header(title: str, items: List, start: str, end: str) -> List[str]:
    lines = [f"# {title}", f"*{start} → {end}*", f"**{len(items)} record(s)**", ""]
    return lines


# ---------------------------------------------------------------------------
# Tool: Personal Info
# ---------------------------------------------------------------------------


@mcp.tool(
    name="oura_get_personal_info",
    annotations={
        "title": "Get Oura Personal Info",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def oura_get_personal_info() -> str:
    """
    Retrieve personal profile information from Oura, including age, weight,
    height, biological sex, and email address associated with the account.

    Returns:
        str: Markdown summary of the user's personal information.

    Examples:
        - "What's my Oura profile?"
        - "Show me my personal info from Oura"
    """
    try:
        data = await _api_get_single("personal_info")
        lines = [
            "# Oura Personal Info",
            "",
            f"- **Email**: {data.get('email', 'N/A')}",
            f"- **Age**: {data.get('age', 'N/A')}",
            f"- **Weight**: {data.get('weight', 'N/A')} kg",
            f"- **Height**: {data.get('height', 'N/A')} m",
            f"- **Biological Sex**: {data.get('biological_sex', 'N/A')}",
        ]
        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)


# ---------------------------------------------------------------------------
# Tool: Daily Sleep
# ---------------------------------------------------------------------------


@mcp.tool(
    name="oura_get_daily_sleep",
    annotations={
        "title": "Get Daily Sleep Scores",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def oura_get_daily_sleep(params: DateRangeInput) -> str:
    """
    Retrieve Oura daily sleep scores and contributing factors for a date range.

    Returns one record per night with an overall sleep score plus sub-scores for
    total sleep, efficiency, restfulness, REM sleep, deep sleep, latency, and timing.

    Args:
        params (DateRangeInput): start_date, end_date, next_token, response_format.

    Returns:
        str: Formatted daily sleep scores.

    Examples:
        - "How did I sleep last week?"
        - "Show my sleep score for the past 7 days"
    """
    try:
        query_params = _build_date_params(params.start_date, params.end_date, params.next_token)
        data = await _api_get("daily_sleep", query_params)
        items = data.get("data", [])

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(data, indent=2)

        if not items:
            return "No daily sleep data found for the specified date range."

        start, end = _default_dates(params.start_date, params.end_date)
        lines = _fmt_list_header("Daily Sleep Scores", items, start, end)

        for item in items:
            score = item.get("score")
            contributors = item.get("contributors", {})
            lines += [
                f"## {item.get('day', 'N/A')}  —  Score: **{score if score is not None else 'N/A'}**",
                _fmt_score("Total Sleep", contributors.get("total_sleep")),
                _fmt_score("Efficiency", contributors.get("efficiency")),
                _fmt_score("Restfulness", contributors.get("restfulness")),
                _fmt_score("REM Sleep", contributors.get("rem_sleep")),
                _fmt_score("Deep Sleep", contributors.get("deep_sleep")),
                _fmt_score("Latency", contributors.get("latency")),
                _fmt_score("Timing", contributors.get("timing")),
                "",
            ]

        if data.get("next_token"):
            lines.append(f"*More data available — next_token: `{data['next_token']}`*")

        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)


# ---------------------------------------------------------------------------
# Tool: Sleep Sessions
# ---------------------------------------------------------------------------


@mcp.tool(
    name="oura_get_sleep_sessions",
    annotations={
        "title": "Get Detailed Sleep Sessions",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def oura_get_sleep_sessions(params: DateRangeInput) -> str:
    """
    Retrieve detailed sleep session data from Oura for a date range.

    Each session includes bedtime start/end, total sleep duration, time awake,
    light/deep/REM sleep durations, sleep efficiency, heart rate, HRV, and
    respiratory rate. Multiple sessions can occur per night (naps included).

    Args:
        params (DateRangeInput): start_date, end_date, next_token, response_format.

    Returns:
        str: Formatted detailed sleep session data.
    """
    try:
        query_params = _build_date_params(params.start_date, params.end_date, params.next_token)
        data = await _api_get("sleep", query_params)
        items = data.get("data", [])

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(data, indent=2)

        if not items:
            return "No sleep session data found for the specified date range."

        start, end = _default_dates(params.start_date, params.end_date)
        lines = _fmt_list_header("Sleep Sessions", items, start, end)

        for item in items:
            def mins(secs: Any) -> str:
                if secs is None:
                    return "N/A"
                return f"{int(secs) // 60}m"

            lines += [
                f"## {item.get('day', 'N/A')}  ({item.get('type', 'unknown')})",
                f"- **Bedtime**: {item.get('bedtime_start', 'N/A')} → {item.get('bedtime_end', 'N/A')}",
                f"- **Total Sleep**: {mins(item.get('total_sleep_duration'))}",
                f"- **Time Awake**: {mins(item.get('awake_time'))}",
                f"- **Light Sleep**: {mins(item.get('light_sleep_duration'))}",
                f"- **Deep Sleep**: {mins(item.get('deep_sleep_duration'))}",
                f"- **REM Sleep**: {mins(item.get('rem_sleep_duration'))}",
                f"- **Efficiency**: {item.get('efficiency', 'N/A')}%",
                f"- **Avg Heart Rate**: {item.get('average_heart_rate', 'N/A')} bpm",
                f"- **Avg HRV**: {item.get('average_hrv', 'N/A')} ms",
                f"- **Respiratory Rate**: {item.get('average_breath', 'N/A')} breaths/min",
                "",
            ]

        if data.get("next_token"):
            lines.append(f"*More data available — next_token: `{data['next_token']}`*")

        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)


# ---------------------------------------------------------------------------
# Tool: Daily Readiness
# ---------------------------------------------------------------------------


@mcp.tool(
    name="oura_get_daily_readiness",
    annotations={
        "title": "Get Daily Readiness Scores",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def oura_get_daily_readiness(params: DateRangeInput) -> str:
    """
    Retrieve Oura daily readiness scores and contributing factors for a date range.

    Each record includes an overall readiness score plus sub-scores for activity
    balance, body temperature, HRV balance, previous day activity, previous night
    sleep, recovery index, resting heart rate, and sleep balance.

    Args:
        params (DateRangeInput): start_date, end_date, next_token, response_format.

    Returns:
        str: Formatted daily readiness scores.
    """
    try:
        query_params = _build_date_params(params.start_date, params.end_date, params.next_token)
        data = await _api_get("daily_readiness", query_params)
        items = data.get("data", [])

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(data, indent=2)

        if not items:
            return "No readiness data found for the specified date range."

        start, end = _default_dates(params.start_date, params.end_date)
        lines = _fmt_list_header("Daily Readiness Scores", items, start, end)

        for item in items:
            score = item.get("score")
            temp = item.get("temperature_deviation")
            temp_str = f"{temp:+.2f}°C" if temp is not None else "N/A"
            contributors = item.get("contributors", {})
            lines += [
                f"## {item.get('day', 'N/A')}  —  Score: **{score if score is not None else 'N/A'}**",
                _fmt_score("Activity Balance", contributors.get("activity_balance")),
                _fmt_score("Body Temperature", contributors.get("body_temperature")),
                _fmt_score("HRV Balance", contributors.get("hrv_balance")),
                _fmt_score("Previous Day Activity", contributors.get("previous_day_activity")),
                _fmt_score("Previous Night", contributors.get("previous_night")),
                _fmt_score("Recovery Index", contributors.get("recovery_index")),
                _fmt_score("Resting HR", contributors.get("resting_heart_rate")),
                _fmt_score("Sleep Balance", contributors.get("sleep_balance")),
                f"- **Temperature Deviation**: {temp_str}",
                "",
            ]

        if data.get("next_token"):
            lines.append(f"*More data available — next_token: `{data['next_token']}`*")

        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)


# ---------------------------------------------------------------------------
# Tool: Daily Activity
# ---------------------------------------------------------------------------


@mcp.tool(
    name="oura_get_daily_activity",
    annotations={
        "title": "Get Daily Activity Data",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def oura_get_daily_activity(params: DateRangeInput) -> str:
    """
    Retrieve Oura daily activity scores and metrics for a date range.

    Each record includes steps, active/total calories, equivalent walking distance,
    active time by intensity level, and activity score with contributors.

    Args:
        params (DateRangeInput): start_date, end_date, next_token, response_format.

    Returns:
        str: Formatted daily activity data.
    """
    try:
        query_params = _build_date_params(params.start_date, params.end_date, params.next_token)
        data = await _api_get("daily_activity", query_params)
        items = data.get("data", [])

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(data, indent=2)

        if not items:
            return "No daily activity data found for the specified date range."

        start, end = _default_dates(params.start_date, params.end_date)
        lines = _fmt_list_header("Daily Activity", items, start, end)

        for item in items:
            score = item.get("score")
            contributors = item.get("contributors", {})
            steps = item.get("steps")
            steps_str = f"{steps:,}" if isinstance(steps, int) else str(steps or "N/A")
            lines += [
                f"## {item.get('day', 'N/A')}  —  Score: **{score if score is not None else 'N/A'}**",
                f"- **Steps**: {steps_str}",
                f"- **Active Calories**: {item.get('active_calories', 'N/A')} kcal",
                f"- **Total Calories**: {item.get('total_calories', 'N/A')} kcal",
                f"- **Equiv. Walking Distance**: {item.get('equivalent_walking_distance', 'N/A')} m",
                f"- **Low Activity**: {item.get('low_activity_time', 'N/A')} min",
                f"- **Medium Activity**: {item.get('medium_activity_time', 'N/A')} min",
                f"- **High Activity**: {item.get('high_activity_time', 'N/A')} min",
                f"- **Sedentary Time**: {item.get('sedentary_time', 'N/A')} min",
                _fmt_score("Meet Daily Targets", contributors.get("meet_daily_targets")),
                _fmt_score("Move Every Hour", contributors.get("move_every_hour")),
                _fmt_score("Stay Active", contributors.get("stay_active")),
                _fmt_score("Training Frequency", contributors.get("training_frequency")),
                _fmt_score("Training Volume", contributors.get("training_volume")),
                "",
            ]

        if data.get("next_token"):
            lines.append(f"*More data available — next_token: `{data['next_token']}`*")

        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)


# ---------------------------------------------------------------------------
# Tool: Heart Rate
# ---------------------------------------------------------------------------


@mcp.tool(
    name="oura_get_heart_rate",
    annotations={
        "title": "Get Heart Rate Data",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def oura_get_heart_rate(params: HeartRateInput) -> str:
    """
    Retrieve time-series heart rate measurements from Oura for a datetime range.

    Returns BPM readings sampled every ~5 minutes with source (awake, sleep, rest,
    session, live) and timestamp. Summarises stats and shows last 10 samples.
    Use short ranges (≤3 days) or JSON format for large datasets.

    Args:
        params (HeartRateInput): start_datetime, end_datetime, next_token, response_format.

    Returns:
        str: Heart rate summary with min/avg/max and recent samples.
    """
    try:
        today = date.today()
        start = params.start_datetime or f"{(today - timedelta(days=1)).isoformat()}T00:00:00"
        end = params.end_datetime or f"{today.isoformat()}T23:59:59"

        query_params: Dict[str, str] = {"start_datetime": start, "end_datetime": end}
        if params.next_token:
            query_params["next_token"] = params.next_token

        data = await _api_get("heartrate", query_params)
        items = data.get("data", [])

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(data, indent=2)

        if not items:
            return "No heart rate data found for the specified datetime range."

        bpm_values = [r["bpm"] for r in items if r.get("bpm")]
        avg_bpm = round(sum(bpm_values) / len(bpm_values), 1) if bpm_values else None

        lines = [
            "# Heart Rate Data",
            f"*{start} → {end}*",
            f"**{len(items)} sample(s)**",
            "",
            f"- **Average BPM**: {avg_bpm}",
            f"- **Min BPM**: {min(bpm_values) if bpm_values else 'N/A'}",
            f"- **Max BPM**: {max(bpm_values) if bpm_values else 'N/A'}",
            "",
            "## Last 10 Readings",
        ]
        for r in items[-10:]:
            lines.append(
                f"- `{r.get('timestamp', 'N/A')}` — **{r.get('bpm', 'N/A')} bpm** ({r.get('source', 'N/A')})"
            )

        if data.get("next_token"):
            lines.append(f"\n*More data available — next_token: `{data['next_token']}`*")

        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)


# ---------------------------------------------------------------------------
# Tool: Daily SpO2
# ---------------------------------------------------------------------------


@mcp.tool(
    name="oura_get_daily_spo2",
    annotations={
        "title": "Get Daily SpO2 (Blood Oxygen)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def oura_get_daily_spo2(params: DateRangeInput) -> str:
    """
    Retrieve average nightly SpO2 (blood oxygen saturation) from Oura.
    Requires Oura Ring Generation 3 or later.

    Args:
        params (DateRangeInput): start_date, end_date, next_token, response_format.

    Returns:
        str: Daily SpO2 averages.
    """
    try:
        query_params = _build_date_params(params.start_date, params.end_date, params.next_token)
        data = await _api_get("daily_spo2", query_params)
        items = data.get("data", [])

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(data, indent=2)

        if not items:
            return "No SpO2 data found for the specified date range."

        start, end = _default_dates(params.start_date, params.end_date)
        lines = _fmt_list_header("Daily SpO2 (Blood Oxygen)", items, start, end)

        for item in items:
            avg = item.get("spo2_percentage", {})
            lines.append(f"- **{item.get('day', 'N/A')}**: avg {avg.get('average', 'N/A')}%")

        if data.get("next_token"):
            lines.append(f"\n*More data available — next_token: `{data['next_token']}`*")

        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)


# ---------------------------------------------------------------------------
# Tool: Daily Stress
# ---------------------------------------------------------------------------


@mcp.tool(
    name="oura_get_daily_stress",
    annotations={
        "title": "Get Daily Stress Data",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def oura_get_daily_stress(params: DateRangeInput) -> str:
    """
    Retrieve Oura daily stress and recovery data. Requires Oura Ring Generation 3+.

    Args:
        params (DateRangeInput): start_date, end_date, next_token, response_format.

    Returns:
        str: Daily stress and recovery summary.
    """
    try:
        query_params = _build_date_params(params.start_date, params.end_date, params.next_token)
        data = await _api_get("daily_stress", query_params)
        items = data.get("data", [])

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(data, indent=2)

        if not items:
            return "No stress data found for the specified date range."

        start, end = _default_dates(params.start_date, params.end_date)
        lines = _fmt_list_header("Daily Stress & Recovery", items, start, end)

        for item in items:
            lines += [
                f"## {item.get('day', 'N/A')}",
                f"- **Stress High**: {item.get('stress_high', 'N/A')} min",
                f"- **Recovery High**: {item.get('recovery_high', 'N/A')} min",
                f"- **Day Summary**: {item.get('day_summary', 'N/A')}",
                "",
            ]

        if data.get("next_token"):
            lines.append(f"*More data available — next_token: `{data['next_token']}`*")

        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)


# ---------------------------------------------------------------------------
# Tool: Workouts
# ---------------------------------------------------------------------------


@mcp.tool(
    name="oura_get_workouts",
    annotations={
        "title": "Get Workout Sessions",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def oura_get_workouts(params: DateRangeInput) -> str:
    """
    Retrieve workout session data tracked by Oura for a date range.

    Each session includes activity type, start/end time, duration, distance,
    calories burned, and average/max heart rate.

    Args:
        params (DateRangeInput): start_date, end_date, next_token, response_format.

    Returns:
        str: Formatted workout session data.
    """
    try:
        query_params = _build_date_params(params.start_date, params.end_date, params.next_token)
        data = await _api_get("workout", query_params)
        items = data.get("data", [])

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(data, indent=2)

        if not items:
            return "No workout sessions found for the specified date range."

        start, end = _default_dates(params.start_date, params.end_date)
        lines = _fmt_list_header("Workout Sessions", items, start, end)

        for item in items:
            duration_min = round(item["duration"] / 60, 1) if item.get("duration") else None
            lines += [
                f"## {item.get('day', 'N/A')}  —  {item.get('activity', 'Unknown')}",
                f"- **Time**: {item.get('start_datetime', 'N/A')} → {item.get('end_datetime', 'N/A')}",
                f"- **Duration**: {duration_min} min" if duration_min else "- **Duration**: N/A",
                f"- **Distance**: {item.get('distance', 'N/A')} m",
                f"- **Calories**: {item.get('calories', 'N/A')} kcal",
                f"- **Avg Heart Rate**: {item.get('average_heart_rate', 'N/A')} bpm",
                f"- **Max Heart Rate**: {item.get('max_heart_rate', 'N/A')} bpm",
                f"- **Intensity**: {item.get('intensity', 'N/A')}",
                "",
            ]

        if data.get("next_token"):
            lines.append(f"*More data available — next_token: `{data['next_token']}`*")

        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)


# ---------------------------------------------------------------------------
# Tool: Mindfulness / Sessions
# ---------------------------------------------------------------------------


@mcp.tool(
    name="oura_get_sessions",
    annotations={
        "title": "Get Mindfulness & Meditation Sessions",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def oura_get_sessions(params: DateRangeInput) -> str:
    """
    Retrieve mindfulness and guided session data logged in the Oura app.

    Each session includes type (meditation, breathing, nap), start/end time,
    and mood before/after if recorded.

    Args:
        params (DateRangeInput): start_date, end_date, next_token, response_format.

    Returns:
        str: Formatted mindfulness/session data.
    """
    try:
        query_params = _build_date_params(params.start_date, params.end_date, params.next_token)
        data = await _api_get("session", query_params)
        items = data.get("data", [])

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(data, indent=2)

        if not items:
            return "No mindfulness sessions found for the specified date range."

        start, end = _default_dates(params.start_date, params.end_date)
        lines = _fmt_list_header("Mindfulness & Sessions", items, start, end)

        for item in items:
            mood = item.get("mood", {})
            mood_before = mood.get("before", "N/A") if isinstance(mood, dict) else "N/A"
            mood_after = mood.get("after", "N/A") if isinstance(mood, dict) else "N/A"
            lines += [
                f"## {item.get('day', 'N/A')}  —  {item.get('type', 'Unknown')}",
                f"- **Time**: {item.get('start_datetime', 'N/A')} → {item.get('end_datetime', 'N/A')}",
                f"- **Mood Before**: {mood_before}",
                f"- **Mood After**: {mood_after}",
                "",
            ]

        if data.get("next_token"):
            lines.append(f"*More data available — next_token: `{data['next_token']}`*")

        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    token = os.environ.get("OURA_ACCESS_TOKEN", "")
    if not token:
        print(
            "Warning: OURA_ACCESS_TOKEN is not set. "
            "Get your token at https://cloud.ouraring.com/personal-access-tokens",
            file=sys.stderr,
        )
    mcp.run()
