from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any


def _iso(dt: datetime | date | None) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat(timespec="minutes")
    return dt.isoformat()


def lesson_to_dict(lesson) -> dict[str, Any]:
    return {
        "start": _iso(lesson.start),
        "end": _iso(lesson.end),
        "subject": lesson.subject.name if lesson.subject else None,
        "teachers": list(lesson.teacher_names) if lesson.teacher_names else [],
        "room": lesson.classroom or None,
        "canceled": bool(lesson.canceled),
        "status": lesson.status,
        "group": getattr(lesson, "group_name", None) or None,
    }


def homework_to_dict(hw) -> dict[str, Any]:
    return {
        "subject": hw.subject.name if hw.subject else None,
        "description": (hw.description or "").strip(),
        "due_date": _iso(hw.date),
        "done": bool(hw.done),
        "given_on": _iso(getattr(hw, "given_date", None)),
        "files": [
            {"name": f.name, "url": f.url}
            for f in (getattr(hw, "files", None) or [])
        ],
    }


def grade_to_dict(grade) -> dict[str, Any]:
    return {
        "subject": grade.subject.name if grade.subject else None,
        "grade": str(grade.grade),
        "out_of": str(grade.out_of) if grade.out_of else None,
        "coefficient": float(grade.coefficient) if grade.coefficient else 1.0,
        "average": str(grade.average) if grade.average else None,
        "min": str(grade.min) if grade.min else None,
        "max": str(grade.max) if grade.max else None,
        "date": _iso(grade.date),
        "comment": (grade.comment or "").strip() or None,
    }


def average_to_dict(avg) -> dict[str, Any]:
    return {
        "subject": avg.subject.name if avg.subject else None,
        "student": str(avg.student) if avg.student is not None else None,
        "class_average": str(avg.class_average) if avg.class_average is not None else None,
        "min": str(avg.min) if avg.min is not None else None,
        "max": str(avg.max) if avg.max is not None else None,
        "out_of": str(avg.out_of) if avg.out_of is not None else None,
    }


def content_to_dict(content) -> dict[str, Any]:
    if content is None:
        return {"description": None, "category": None, "files": []}
    return {
        "description": (content.description or "").strip() or None,
        "category": getattr(content, "category", None),
        "files": [{"name": f.name, "url": f.url} for f in (content.files or [])],
    }


def lessons_to_markdown(lessons: list[dict]) -> str:
    if not lessons:
        return "_No lessons in this period._"

    by_day: dict[str, list[dict]] = {}
    for ls in lessons:
        day = (ls["start"] or "")[:10]
        by_day.setdefault(day, []).append(ls)

    parts = []
    for day in sorted(by_day):
        parts.append(f"### {day}")
        for ls in sorted(by_day[day], key=lambda x: x["start"] or ""):
            time_range = f"{(ls['start'] or '')[11:16]}–{(ls['end'] or '')[11:16]}"
            mark = " ❌" if ls["canceled"] else ""
            teacher = ls["teachers"][0] if ls["teachers"] else "?"
            room = ls["room"] or "?"
            parts.append(f"- **{time_range}** {ls['subject']} — {teacher} — `{room}`{mark}")
        parts.append("")
    return "\n".join(parts).strip()


def homework_to_markdown(hws: list[dict]) -> str:
    if not hws:
        return "_No homework in this range._"

    parts = []
    for hw in sorted(hws, key=lambda x: x["due_date"] or ""):
        check = "✅" if hw["done"] else "⏳"
        parts.append(
            f"- {check} **{hw['due_date']}** [{hw['subject']}] {hw['description'][:200]}"
        )
    return "\n".join(parts)


def grades_to_markdown(grades: list[dict]) -> str:
    if not grades:
        return "_No grades._"

    parts = ["| Date | Subject | Grade | Avg(class) | Coef | Comment |",
             "|---|---|---|---|---|---|"]
    for g in sorted(grades, key=lambda x: x["date"] or "", reverse=True):
        comment = (g["comment"] or "")[:60]
        parts.append(
            f"| {g['date'] or '—'} | {g['subject']} | "
            f"{g['grade']}/{g['out_of'] or '?'} | {g['average'] or '—'} | "
            f"{g['coefficient']} | {comment} |"
        )
    return "\n".join(parts)


def averages_to_markdown(averages: list[dict], period_name: str | None = None) -> str:
    if not averages:
        return "_No averages for this period._"
    header = f"### {period_name}\n\n" if period_name else ""
    rows = [
        header + "| Subject | Your avg | Class avg | Min | Max | /Out of |",
        "|---|---|---|---|---|---|",
    ]
    for a in sorted(averages, key=lambda x: x["subject"] or ""):
        rows.append(
            f"| {a['subject'] or '—'} | {a['student'] or '—'} | "
            f"{a['class_average'] or '—'} | {a['min'] or '—'} | "
            f"{a['max'] or '—'} | {a['out_of'] or '?'} |"
        )
    return "\n".join(rows)


def lesson_with_content_to_markdown(lesson: dict, content: dict) -> str:
    canceled = " ❌" if lesson.get("canceled") else ""
    time_range = f"{(lesson['start'] or '')[11:16]}–{(lesson['end'] or '')[11:16]}"
    teacher = lesson["teachers"][0] if lesson.get("teachers") else "?"
    room = f" — `{lesson['room']}`" if lesson.get("room") else ""
    parts = [
        f"### {lesson['subject']}{canceled}",
        f"**{time_range}**{room} — {teacher}",
    ]
    if content.get("category"):
        parts.append(f"**Category:** {content['category']}")
    if content.get("description"):
        parts.append(f"\n{content['description']}")
    files = content.get("files", [])
    if files:
        parts.append("\n**Attachments:**")
        for f in files:
            parts.append(f"- [{f['name']}]({f['url']})")
    if not any([content.get("description"), content.get("category"), files]):
        parts.append("_No content available for this lesson._")
    return "\n".join(parts)


def today_summary_to_markdown(
    today: date,
    lessons: list[dict],
    homework: list[dict],
    grades: list[dict],
) -> str:
    week_ago = (today - timedelta(days=7)).isoformat()
    recent_grades = [g for g in grades if g["date"] and g["date"] >= week_ago]

    parts = [f"## Today — {today.isoformat()}", ""]

    parts.append("### Schedule")
    if lessons:
        for ls in sorted(lessons, key=lambda x: x["start"] or ""):
            time_range = f"{(ls['start'] or '')[11:16]}–{(ls['end'] or '')[11:16]}"
            mark = " ❌" if ls["canceled"] else ""
            teacher = ls["teachers"][0] if ls["teachers"] else "?"
            room = ls["room"] or "?"
            parts.append(f"- **{time_range}** {ls['subject']} — {teacher} — `{room}`{mark}")
    else:
        parts.append("_No lessons today._")
    parts.append("")

    parts.append("### Homework due today & tomorrow")
    if homework:
        for hw in sorted(homework, key=lambda x: x["due_date"] or ""):
            parts.append(f"- ⏳ **{hw['due_date']}** [{hw['subject']}] {hw['description'][:200]}")
    else:
        parts.append("_Nothing due._")
    parts.append("")

    parts.append("### Recent grades (last 7 days)")
    if recent_grades:
        parts.append("| Date | Subject | Grade | Class avg | Coef |")
        parts.append("|---|---|---|---|---|")
        for g in recent_grades:
            parts.append(
                f"| {g['date'] or '—'} | {g['subject']} | "
                f"{g['grade']}/{g['out_of'] or '?'} | {g['average'] or '—'} | {g['coefficient']} |"
            )
    else:
        parts.append("_No new grades this week._")

    return "\n".join(parts)
