"""Render the QUP-style activity card for the GitHub profile.

Runs in GitHub Actions with the repo token, so the profile never depends on a
third-party image service (those rate-limit and break the page).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

LOGIN = os.environ.get("PROFILE_LOGIN", "evgeha52")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = Path(os.environ.get("OUT_PATH", "assets/stats.svg"))

QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(privacy: PUBLIC) { totalCount }
    followers { totalCount }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

BG = "#0a0c0f"
SURFACE = "#111419"
BORDER = "#272d35"
TEXT = "#f4f7fa"
MUTED = "#8d97a5"
SECONDARY = "#b6c1cd"
ACCENT = "#19b9f1"
FONT = "Inter, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "'SFMono-Regular', Consolas, 'Liberation Mono', monospace"


def fetch() -> dict:
    body = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode()
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "qup-profile-card",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        raise SystemExit(f"GitHub API error: {error.code} {error.read()[:200]!r}") from None
    if "errors" in payload:
        raise SystemExit(f"GraphQL errors: {payload['errors']}")
    return payload["data"]["user"]


def streaks(days: list[tuple[date, int]]) -> tuple[int, int]:
    """Return the current and longest run of days with at least one contribution."""
    longest = current = 0
    for _, count in days:
        if count > 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    # The current streak only counts if it reaches today or yesterday.
    if days and days[-1][1] == 0:
        current = 0
    return current, longest


def bars(days: list[tuple[date, int]], weeks: int = 12) -> list[int]:
    """Weekly totals for the last N weeks, oldest first."""
    buckets: dict[date, int] = {}
    for day, count in days:
        week = day - timedelta(days=day.weekday())
        buckets[week] = buckets.get(week, 0) + count
    ordered = sorted(buckets.items())[-weeks:]
    return [total for _, total in ordered]


def render(user: dict) -> str:
    calendar = user["contributionsCollection"]["contributionCalendar"]
    days = [
        (date.fromisoformat(day["date"]), day["contributionCount"])
        for week in calendar["weeks"]
        for day in week["contributionDays"]
    ]
    total = calendar["totalContributions"]
    current, longest = streaks(days)
    weekly = bars(days)
    peak = max(weekly) or 1

    width, height = 900, 240
    columns = [
        ("CONTRIBUTIONS / YEAR", str(total)),
        ("CURRENT STREAK", f"{current}d"),
        ("LONGEST STREAK", f"{longest}d"),
        ("PUBLIC REPOS", str(user["repositories"]["totalCount"])),
    ]

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Activity: {total} contributions, current streak {current} days">',
        f'<rect width="{width}" height="{height}" rx="16" fill="{BG}"/>',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="16" '
        f'fill="none" stroke="{BORDER}"/>',
        f'<rect x="0" y="0" width="3" height="72" fill="{ACCENT}"/>',
        f'<text x="36" y="46" font-family="{MONO}" font-size="10" letter-spacing="2.4" '
        f'fill="{MUTED}">ACTIVITY 2026</text>',
    ]

    x = 36
    for label, value in columns:
        parts.append(
            f'<text x="{x}" y="92" font-family="{FONT}" font-size="30" font-weight="600" '
            f'fill="{TEXT}">{value}</text>'
        )
        parts.append(
            f'<text x="{x}" y="114" font-family="{MONO}" font-size="9" letter-spacing="1.6" '
            f'fill="{MUTED}">{label}</text>'
        )
        x += 212

    # Weekly rhythm: quiet bars, only the last one carries the accent.
    bar_x, bar_base, bar_max, slot = 36, 200, 44, 68
    parts.append(
        f'<text x="{bar_x}" y="150" font-family="{MONO}" font-size="9" letter-spacing="1.6" '
        f'fill="{MUTED}">LAST 12 WEEKS</text>'
    )
    for index, value in enumerate(weekly):
        bar_height = max(3, round(value / peak * bar_max))
        fill = ACCENT if index == len(weekly) - 1 else SURFACE
        stroke = "" if index == len(weekly) - 1 else f' stroke="{BORDER}"'
        parts.append(
            f'<rect x="{bar_x + index * slot}" y="{bar_base - bar_height}" width="30" '
            f'height="{bar_height}" rx="3" fill="{fill}"{stroke}/>'
        )

    parts.append(
        f'<text x="{width - 36}" y="{bar_base}" text-anchor="end" font-family="{MONO}" '
        f'font-size="9" letter-spacing="1.6" fill="{MUTED}">PEAK {peak}/WK</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    user = fetch()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(user) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()