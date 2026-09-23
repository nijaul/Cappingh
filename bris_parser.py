from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import pandas as pd
from pypdf import PdfReader


def clean_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def odds_to_float(value: str) -> float:
    value = value.strip()
    m = re.fullmatch(r"(\d+)\s*/\s*(\d+)", value)
    if m:
        n, d = map(float, m.groups())
        return n / d + 1 if d else np.nan
    try:
        return float(value)
    except ValueError:
        return np.nan


def race_number(text: str) -> int | None:
    m = re.search(r"\bRace\s+(\d+)\b", text[:2000])
    return int(m.group(1)) if m else None


def race_header(text: str, race_num: int) -> dict[str, str]:
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    title = next((x for x in lines if re.search(rf"\bRace\s+{race_num}\b", x)), "")
    track = ""
    distance = ""
    date_text = ""

    m = re.search(r"Ultimate PP's\s+(.+?)\s+Race\s+\d+", title)
    if m:
        descriptor = m.group(1).strip()
        parts = descriptor.split()
        track = parts[0] if parts else ""
        dm = re.search(
            r"(\d+(?:[¼½¾])?\s*(?:Furlongs?|Mile|Miles))",
            descriptor,
            flags=re.I,
        )
        if dm:
            distance = clean_spaces(dm.group(1))

    m = re.search(
        r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
        r"([A-Za-z]+\s+\d{1,2},\s+\d{4})",
        title,
    )
    if m:
        date_text = m.group(1)

    return {
        "race_id": f"{track or 'Race'}-R{race_num}",
        "race_number": str(race_num),
        "track": track,
        "date": date_text,
        "distance": distance,
        "header": title,
    }


def numeric_sequence(value: str) -> list[float]:
    return [
        float(x)
        for x in re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", value)
    ]


def prime_powers_by_race_and_post(pages: list[str]) -> dict[tuple[int, int], float]:
    out: dict[tuple[int, int], float] = {}
    for text in pages:
        rn = race_number(text)
        if rn is None:
            continue

        lines = text.splitlines()
        for i, line in enumerate(lines):
            m = re.search(r"Prime Power:\s*([0-9.]+)", line)
            if not m:
                continue

            pp = float(m.group(1))
            for j in range(i - 1, max(-1, i - 15), -1):
                hm = re.match(
                    r"^\s*(\d{1,2})\s+(.+?)\s+\([^)]*\)",
                    lines[j],
                )
                if hm:
                    out[(rn, int(hm.group(1)))] = pp
                    break
    return out


def parse_summary_rows(summary_text: str, meta: dict[str, str]) -> list[dict]:
    rows = []

    for raw in summary_text.splitlines():
        line = clean_spaces(raw)

        if not re.match(r"^\d{1,2}\s+", line):
            continue
        if line.startswith(("Days ", "ML ", "# ")):
            continue

        m = re.match(
            r"^(\d{1,2})\s+(.+?)\s+(\d+\s*/\s*\d+)(.*)$",
            line,
        )
        if not m:
            continue

        post = int(m.group(1))
        horse = clean_spaces(m.group(2))
        ml_text = clean_spaces(m.group(3))
        tail = m.group(4)

        # Extract the days-since-race value that follows the ML.
        tail = re.sub(r"^[^A-Za-z0-9]+", " ", tail)
        days_match = re.search(r"\b(\d+(?:\.\d+)?)\b", tail)
        days_since = float(days_match.group(1)) if days_match else np.nan
        after_days = (
            tail[days_match.end():].strip() if days_match else tail
        )

        style_match = re.search(
            r"\b(\+*E\/P|\+*E|\+*P|\+*S|NA)\b",
            after_days,
        )
        style = (
            style_match.group(1).lstrip("+")
            if style_match
            else ""
        )
        numeric_part = (
            after_days[style_match.end():].strip()
            if style_match
            else after_days
        )
        nums = numeric_sequence(numeric_part)

        # In BRIS summaries, a small style index can appear immediately before
        # the pace figures. Remove it when it is clearly the style index.
        if len(nums) >= 2 and nums[0] <= 8 and nums[1] >= 40:
            nums = nums[1:]

        rows.append({
            **meta,
            "post": post,
            "horse": horse,
            "morning_line": ml_text,
            "morning_line_decimal": odds_to_float(ml_text),
            "days_since": days_since,
            "run_style": style,
            "pace_speed": nums[0] if len(nums) > 0 else np.nan,
            "e1": nums[1] if len(nums) > 1 else np.nan,
            "e2": nums[2] if len(nums) > 2 else np.nan,
            "late_speed": nums[3] if len(nums) > 3 else np.nan,
            "speed": nums[4] if len(nums) > 4 else np.nan,
            "race_rating": nums[5] if len(nums) > 5 else np.nan,
            "best_e1": nums[6] if len(nums) > 6 else np.nan,
            "best_e2": nums[7] if len(nums) > 7 else np.nan,
            "sp1": nums[8] if len(nums) > 8 else np.nan,
            "sp2": nums[9] if len(nums) > 9 else np.nan,
            "sp3": nums[10] if len(nums) > 10 else np.nan,
            "sp4": nums[11] if len(nums) > 11 else np.nan,
            "avg_class": nums[12] if len(nums) > 12 else np.nan,
        })

    return rows


def parse_bris_pdf(pdf_path: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    path = Path(pdf_path)
    reader = PdfReader(str(path))

    pages = [(page.extract_text() or "") for page in reader.pages]
    if not any(p.strip() for p in pages):
        raise ValueError("The PDF contains no extractable text.")

    summaries = []
    for text in pages:
        if "Race Summary" not in text:
            continue
        rn = race_number(text)
        if rn is not None:
            summaries.append((rn, text))

    if not summaries:
        raise ValueError(
            "No BRISNET Race Summary sections were found. "
            "Use a text-based BRISNET Ultimate PP PDF."
        )

    pp_map = prime_powers_by_race_and_post(pages)
    horses: list[dict] = []
    races: list[dict] = []

    for rn, text in summaries:
        meta = race_header(text, rn)
        summary = text.split("Race Summary", 1)[1]
        summary = summary.split("Speed Last Race", 1)[0]
        rows = parse_summary_rows(summary, meta)

        for row in rows:
            row["prime_power"] = pp_map.get((rn, int(row["post"])), np.nan)
            horses.append(row)

        races.append({
            "race_id": meta["race_id"],
            "race_number": meta["race_number"],
            "track": meta["track"],
            "date": meta["date"],
            "distance": meta["distance"],
            "header": meta["header"],
            "horse_count": len(rows),
        })

    if not horses:
        raise ValueError("No horses were extracted from the PDF.")

    horses_df = pd.DataFrame(horses)
    races_df = (
        pd.DataFrame(races)
        .drop_duplicates("race_id")
        .sort_values("race_number")
        .reset_index(drop=True)
    )
    horses_df = (
        horses_df
        .sort_values(["race_number", "post"])
        .reset_index(drop=True)
    )

    return races_df, horses_df
