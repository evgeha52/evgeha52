"""Render the activity card for the GitHub profile.

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
BORDER = "#272d35"
TEXT = "#f4f7fa"
MUTED = "#8d97a5"
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
            "User-Agent": "profile-card",
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
    """Current and longest run of days with at least one contribution."""
    longest = current = 0
    for _, count in days:
        if count > 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    if days and days[-1][1] == 0:
        current = 0
    return current, longest


def weekly(days: list[tuple[date, int]], weeks: int = 12) -> list[int]:
    buckets: dict[date, int] = {}
    for day, count in days:
        monday = day - timedelta(days=day.weekday())
        buckets[monday] = buckets.get(monday, 0) + count
    return [total for _, total in sorted(buckets.items())[-weeks:]]


def render(user: dict) -> str:
    calendar = user["contributionsCollection"]["contributionCalendar"]
    days = [
        (date.fromisoformat(day["date"]), day["contributionCount"])
        for week in calendar["weeks"]
        for day in week["contributionDays"]
    ]
    total = calendar["totalContributions"]
    current, longest = streaks(days)
    bars = weekly(days)
    peak = max(bars) or 1

    width, height = 860, 136
    metrics = [
        (str(total), "контрибуций за год"),
        (str(current), "дней подряд"),
        (str(longest), "лучшая серия"),
    ]

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Активность: {total} контрибуций за год, {current} дней подряд">',
        f'<rect width="{width}" height="{height}" fill="{BG}"/>',
        f'<rect x="0" y="0" width="3" height="{height}" fill="{BORDER}"/>',
        f'<rect x="0" y="0" width="3" height="76" fill="{ACCENT}"/>',
    ]

    x = 36
    for value, label in metrics:
        out.append(
            f'<text x="{x}" y="60" font-family="{FONT}" font-size="28" font-weight="600" '
            f'fill="{TEXT}">{value}</text>'
        )
        out.append(
            f'<text x="{x}" y="82" font-family="{FONT}" font-size="12" '
            f'fill="{MUTED}">{label}</text>'
        )
        x += 168

    # Weekly rhythm: quiet bars, the most recent one carries the accent.
    bar_x, base, bar_max, slot, bar_w = 560, 100, 38, 20, 15
    out.append(
        f'<text x="{bar_x}" y="60" font-family="{FONT}" font-size="12" fill="{MUTED}">'
        f"последние 12 недель</text>"
    )
    for index, value in enumerate(bars):
        bar_h = max(2, round(value / peak * bar_max))
        fill = ACCENT if index == len(bars) - 1 else "#1c232b"
        out.append(
            f'<rect x="{bar_x + index * slot}" y="{base - bar_h}" width="{bar_w}" '
            f'height="{bar_h}" rx="2" fill="{fill}"/>'
        )

    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    user = fetch()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(user) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()