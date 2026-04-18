from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from .client import PronoteAuthError, PronoteConfigError, get_client
from .formatters import (
    average_to_dict,
    averages_to_markdown,
    content_to_dict,
    grade_to_dict,
    grades_to_markdown,
    homework_to_dict,
    homework_to_markdown,
    lesson_to_dict,
    lesson_with_content_to_markdown,
    lessons_to_markdown,
    today_summary_to_markdown,
)

logger = logging.getLogger(__name__)

ResponseFormat = Literal["markdown", "json"]


def _parse_date(s: str | None, default: date) -> date:
    if not s:
        return default
    return date.fromisoformat(s)


def _error_response(msg: str) -> dict:
    return {"ok": False, "error": msg}


def _fetch_lessons(client, d_from: date, d_to: date) -> list[dict]:
    return [lesson_to_dict(ls) for ls in client.lessons(d_from, d_to)]


def _fetch_homework(client, d_from: date, d_to: date, only_pending: bool = True) -> list[dict]:
    hws = [homework_to_dict(hw) for hw in client.homework(d_from, date_to=d_to)]
    if only_pending:
        hws = [hw for hw in hws if not hw["done"]]
    return hws


def _fetch_all_grades(client, subject_contains: str | None = None) -> list[dict]:
    all_grades = []
    for period in client.periods:
        for g in period.grades:
            all_grades.append(grade_to_dict(g))
    if subject_contains:
        needle = subject_contains.lower()
        all_grades = [g for g in all_grades if g["subject"] and needle in g["subject"].lower()]
    all_grades.sort(key=lambda x: x["date"] or "", reverse=True)
    return all_grades


def _find_period(client, period_name: str | None):
    periods = client.periods
    if not periods:
        return None
    if period_name:
        needle = period_name.lower()
        for p in periods:
            if needle in p.name.lower():
                return p
        return None
    today = date.today()
    for p in periods:
        try:
            p_start = p.start.date() if hasattr(p.start, "date") else p.start
            p_end = p.end.date() if hasattr(p.end, "date") else p.end
            if p_start <= today <= p_end:
                return p
        except Exception:
            continue
    return periods[-1]


def register_tools(mcp: FastMCP) -> None:

    @mcp.tool(annotations={"title": "Get Pronote schedule", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    def pronote_get_schedule(
        date_from: Annotated[str | None, Field(description="Start date (YYYY-MM-DD). Defaults to today.", examples=["2026-04-17"])] = None,
        date_to: Annotated[str | None, Field(description="End date inclusive (YYYY-MM-DD). Defaults to today + 7 days.")] = None,
        response_format: Annotated[ResponseFormat, Field(description="'markdown' (default) or 'json'.")] = "markdown",
    ) -> str | dict:
        """Get the user's Pronote schedule (lessons) over a date range.

        Returns lessons grouped by day with start/end time, subject, teacher,
        classroom, and cancellation status.
        """
        try:
            d_from = _parse_date(date_from, date.today())
            d_to = _parse_date(date_to, date.today() + timedelta(days=7))
            if d_to < d_from:
                return _error_response("date_to must be >= date_from")

            client = get_client()
            lessons = _fetch_lessons(client, d_from, d_to)
            logger.info("Fetched %d lessons for %s..%s", len(lessons), d_from, d_to)

            if response_format == "json":
                return {"ok": True, "count": len(lessons), "lessons": lessons,
                        "date_from": d_from.isoformat(), "date_to": d_to.isoformat()}
            return lessons_to_markdown(lessons)

        except (PronoteConfigError, PronoteAuthError) as e:
            return _error_response(str(e))
        except ValueError as e:
            return _error_response(f"Invalid date format (expected YYYY-MM-DD): {e}")
        except Exception as e:
            logger.exception("pronote_get_schedule failed")
            return _error_response(f"Internal error ({type(e).__name__}). Check server logs.")

    @mcp.tool(annotations={"title": "Get Pronote homework", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    def pronote_get_homework(
        date_from: Annotated[str | None, Field(description="Start date (YYYY-MM-DD). Defaults to today.")] = None,
        date_to: Annotated[str | None, Field(description="End date inclusive (YYYY-MM-DD). Defaults to today + 14 days.")] = None,
        only_pending: Annotated[bool, Field(description="If true, exclude homework already marked done. Defaults to true.")] = True,
        response_format: Annotated[ResponseFormat, Field(description="'markdown' (default) or 'json'.")] = "markdown",
    ) -> str | dict:
        """Get homework assignments due in a date range.

        By default returns only pending (not-done) homework — what the user
        actually needs to do.
        """
        try:
            d_from = _parse_date(date_from, date.today())
            d_to = _parse_date(date_to, date.today() + timedelta(days=14))
            if d_to < d_from:
                return _error_response("date_to must be >= date_from")

            client = get_client()
            hws = _fetch_homework(client, d_from, d_to, only_pending)
            logger.info("Fetched %d homework items (pending=%s)", len(hws), only_pending)

            if response_format == "json":
                return {"ok": True, "count": len(hws), "homework": hws,
                        "date_from": d_from.isoformat(), "date_to": d_to.isoformat(),
                        "only_pending": only_pending}
            return homework_to_markdown(hws)

        except (PronoteConfigError, PronoteAuthError) as e:
            return _error_response(str(e))
        except ValueError as e:
            return _error_response(f"Invalid date format (expected YYYY-MM-DD): {e}")
        except Exception as e:
            logger.exception("pronote_get_homework failed")
            return _error_response(f"Internal error ({type(e).__name__}). Check server logs.")

    @mcp.tool(annotations={"title": "Get recent Pronote grades", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    def pronote_get_recent_grades(
        limit: Annotated[int, Field(description="Maximum number of grades to return (most recent first).", ge=1, le=100)] = 10,
        subject_contains: Annotated[str | None, Field(description="Optional case-insensitive filter on the subject name (e.g. 'maths').")] = None,
        response_format: Annotated[ResponseFormat, Field(description="'markdown' (default) or 'json'.")] = "markdown",
    ) -> str | dict:
        """Get the user's most recent grades across all periods.

        Returns date, subject, grade/out_of, class average, coefficient and
        teacher comment.
        """
        try:
            client = get_client()
            grades = _fetch_all_grades(client, subject_contains)[:limit]
            logger.info("Fetched %d grades (filter=%r, limit=%d)", len(grades), subject_contains, limit)

            if response_format == "json":
                return {"ok": True, "count": len(grades), "grades": grades,
                        "filter": subject_contains, "limit": limit}
            return grades_to_markdown(grades)

        except (PronoteConfigError, PronoteAuthError) as e:
            return _error_response(str(e))
        except Exception as e:
            logger.exception("pronote_get_recent_grades failed")
            return _error_response(f"Internal error ({type(e).__name__}). Check server logs.")

    @mcp.tool(annotations={"title": "Today's summary", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    def pronote_get_today_summary() -> str:
        """One-shot daily briefing: today's schedule, homework due today and tomorrow,
        and grades received in the last 7 days.

        Fetches everything in a single authenticated session — faster than calling
        the individual tools separately.
        """
        try:
            today = date.today()
            client = get_client()
            lessons = _fetch_lessons(client, today, today)
            homework = _fetch_homework(client, today, today + timedelta(days=1), only_pending=True)
            grades = _fetch_all_grades(client)
            logger.info("Today summary: %d lessons, %d hw, %d grades total", len(lessons), len(homework), len(grades))
            return today_summary_to_markdown(today, lessons, homework, grades)

        except (PronoteConfigError, PronoteAuthError) as e:
            return _error_response(str(e))
        except Exception as e:
            logger.exception("pronote_get_today_summary failed")
            return _error_response(f"Internal error ({type(e).__name__}). Check server logs.")

    @mcp.tool(annotations={"title": "Get period averages", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    def pronote_get_period_averages(
        period_name: Annotated[str | None, Field(description="Period name (e.g. 'Trimestre 2'). Defaults to current period.", examples=["Trimestre 1", "Trimestre 2", "Semestre 1"])] = None,
        response_format: Annotated[ResponseFormat, Field(description="'markdown' (default) or 'json'.")] = "markdown",
    ) -> str | dict:
        """Get subject averages for a grading period.

        Returns your average, class average, min, max, and out_of for each subject.
        Defaults to the current period; pass period_name to query a past period.
        """
        try:
            client = get_client()
            period = _find_period(client, period_name)
            if period is None:
                return _error_response(
                    f"Period '{period_name}' not found. Available: {[p.name for p in client.periods]}"
                )

            averages = [average_to_dict(a) for a in period.averages]
            logger.info("Fetched %d averages for period '%s'", len(averages), period.name)

            if response_format == "json":
                return {"ok": True, "period": period.name, "count": len(averages), "averages": averages}
            return averages_to_markdown(averages, period.name)

        except (PronoteConfigError, PronoteAuthError) as e:
            return _error_response(str(e))
        except Exception as e:
            logger.exception("pronote_get_period_averages failed")
            return _error_response(f"Internal error ({type(e).__name__}). Check server logs.")

    @mcp.tool(annotations={"title": "Get lesson content", "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
    def pronote_get_lesson_content(
        lesson_date: Annotated[str, Field(description="Date of the lesson (YYYY-MM-DD).", examples=["2026-04-18"])],
        subject_contains: Annotated[str, Field(description="Case-insensitive substring to identify the subject.", examples=["maths", "français", "histoire"])],
        response_format: Annotated[ResponseFormat, Field(description="'markdown' (default) or 'json'.")] = "markdown",
    ) -> str | dict:
        """Get the pedagogical content of a specific lesson: description, category,
        and attached files (metadata only — name + URL, no download).

        Slower than other tools: fetching content fires an extra Pronote request per lesson.
        """
        try:
            d = _parse_date(lesson_date, date.today())
            client = get_client()

            needle = subject_contains.lower()
            matching = [
                ls for ls in client.lessons(d, d)
                if ls.subject and needle in ls.subject.name.lower()
            ]
            if not matching:
                return _error_response(f"No lesson matching '{subject_contains}' on {d.isoformat()}.")

            lesson = matching[0]
            lesson_dict = lesson_to_dict(lesson)

            try:
                raw_content = lesson.content
            except Exception:
                logger.exception("Failed to fetch lesson.content")
                raw_content = None

            content_dict = content_to_dict(raw_content)
            logger.info("Fetched content for '%s' on %s", lesson.subject.name, d)

            if response_format == "json":
                return {"ok": True, "lesson": lesson_dict, "content": content_dict}
            return lesson_with_content_to_markdown(lesson_dict, content_dict)

        except (PronoteConfigError, PronoteAuthError) as e:
            return _error_response(str(e))
        except ValueError as e:
            return _error_response(f"Invalid date format (expected YYYY-MM-DD): {e}")
        except Exception as e:
            logger.exception("pronote_get_lesson_content failed")
            return _error_response(f"Internal error ({type(e).__name__}). Check server logs.")
