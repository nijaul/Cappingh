from __future__ import annotations

from pathlib import Path
import html
import json
import sys

from bris_parser import parse_bris_pdf
from scorer import handicap_horses


ROOT = Path(__file__).resolve().parent
INPUT_DIR = ROOT / "input"
RESULTS_DIR = ROOT / "results"


def find_pdf() -> Path:
    pdfs = sorted(INPUT_DIR.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(
            "No PDF found in input/. Upload one BRISNET Ultimate PP PDF to input/."
        )
    # Use the most recently modified PDF if multiple exist.
    return max(pdfs, key=lambda p: p.stat().st_mtime)


def fmt(value, decimals=1):
    if value is None:
        return "—"
    try:
        number = float(value)
    except (ValueError, TypeError):
        return str(value)
    if number != number:
        return "—"
    return f"{number:.{decimals}f}"


def make_html(races, scored, source_name):
    track = races.iloc[0]["track"] if not races.empty else ""
    date = races.iloc[0]["date"] if not races.empty else ""

    options = "\n".join(
        f'<option value="{html.escape(str(r.race_number))}">'
        f'Race {html.escape(str(r.race_number))} — '
        f'{html.escape(str(r.distance or ""))}</option>'
        for _, r in races.iterrows()
    )

    # Store all scores in a JS data object so the static page can switch races.
    records = scored.to_dict(orient="records")

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BRISNET Handicap Results</title>
<style>
body{{font-family:system-ui,sans-serif;background:#f4f6f9;margin:0;color:#172033}}
main{{max-width:1500px;margin:auto;padding:24px}}
.card{{background:#fff;border:1px solid #dde3eb;border-radius:14px;padding:18px;margin-bottom:18px}}
h1,h2{{margin-top:0}}
.muted{{color:#617087}}
select,button{{padding:10px;border-radius:8px;border:1px solid #ccd4df}}
.toolbar{{display:flex;justify-content:space-between;gap:16px;align-items:end}}
.table{{overflow:auto;border:1px solid #e1e5eb;border-radius:10px}}
table{{border-collapse:collapse;width:100%;min-width:1100px}}
th,td{{padding:8px 10px;border-bottom:1px solid #edf0f3;white-space:nowrap;text-align:right}}
th{{background:#f6f8fb}}
th:nth-child(3),td:nth-child(3),th:last-child,td:last-child{{text-align:left}}
.metrics{{display:flex;gap:12px;flex-wrap:wrap}}
.metric{{padding:12px 16px;background:#f5f7fa;border-radius:9px}}
.metric b{{font-size:1.3rem;display:block}}
.warn{{background:#fff8e6;padding:12px;border-radius:9px}}
</style>
</head>
<body>
<main>
<div class="card">
<h1>🐎 BRISNET Handicap Results</h1>
<p class="muted">Generated automatically by GitHub Actions from <b>{html.escape(source_name)}</b>.</p>
<div class="metrics">
<div class="metric"><b>{html.escape(str(track or "—"))}</b>Track</div>
<div class="metric"><b>{len(races)}</b>Races</div>
<div class="metric"><b>{len(scored)}</b>Horses</div>
<div class="metric"><b>{html.escape(str(date or "—"))}</b>Date</div>
</div>
</div>

<div class="card">
<div class="toolbar">
<div>
<h2 id="raceTitle">Race</h2>
<p id="raceHeader" class="muted"></p>
</div>
<select id="raceSelect">{options}</select>
</div>
<div class="table">
<table>
<thead><tr>
<th>Rank</th><th>Post</th><th>Horse</th><th>ML</th><th>Style</th>
<th>Prime</th><th>Pace</th><th>E1</th><th>E2</th><th>Late</th>
<th>Speed</th><th>Class</th><th>Model %</th><th>Top Factors</th>
</tr></thead>
<tbody id="body"></tbody>
</table>
</div>
</div>

<div class="card">
<h2>Card Overview</h2>
<div class="table">
<table>
<thead><tr><th>Race</th><th>Post</th><th>Horse</th><th>Rank</th><th>ML</th><th>Model %</th></tr></thead>
<tbody>
{''.join(
    f'<tr><td>{html.escape(str(r.race_number))}</td>'
    f'<td>{int(r.post)}</td>'
    f'<td style="text-align:left">{html.escape(str(r.horse))}</td>'
    f'<td>{int(r.handicap_rank)}</td>'
    f'<td>{html.escape(str(r.morning_line))}</td>'
    f'<td>{fmt(r.model_percent)}%</td></tr>'
    for _, r in scored[scored.handicap_rank <= 3].iterrows()
)}
</tbody>
</table>
</div>
</div>

<div class="card">
<p class="warn"><b>Important:</b> Model % is a normalized handicapping score within each race,
not a calibrated probability and not a guarantee of the outcome.</p>
</div>

<script>
const DATA = {json.dumps(records, default=str)};
const RACES = {json.dumps(races.to_dict(orient="records"), default=str)};
const select = document.getElementById("raceSelect");
const body = document.getElementById("body");
const title = document.getElementById("raceTitle");
const header = document.getElementById("raceHeader");

function val(v) {{
  if (v === null || v === undefined || v === "" || v === "nan") return "—";
  const n = Number(v);
  return Number.isFinite(n) ? (Number.isInteger(n) ? String(n) : n.toFixed(1)) : String(v);
}}

function esc(v) {{
  return String(v ?? "").replaceAll("&","&amp;").replaceAll("<","&lt;")
    .replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");
}}

function render() {{
  const rn = select.value;
  const race = RACES.find(r => String(r.race_number) === rn);
  const rows = DATA.filter(r => String(r.race_number) === rn)
    .sort((a,b) => Number(a.handicap_rank) - Number(b.handicap_rank));

  title.textContent = "Race " + rn;
  header.textContent = race ? (race.header || race.distance || "") : "";

  body.innerHTML = rows.map(r => `
    <tr>
      <td>${{r.handicap_rank}}</td>
      <td>${{r.post}}</td>
      <td style="text-align:left"><b>${{esc(r.horse)}}</b></td>
      <td>${{esc(r.morning_line)}}</td>
      <td>${{esc(r.run_style)}}</td>
      <td>${{val(r.prime_power)}}</td>
      <td>${{val(r.pace_speed)}}</td>
      <td>${{val(r.e1)}}</td>
      <td>${{val(r.e2)}}</td>
      <td>${{val(r.late_speed)}}</td>
      <td>${{val(r.speed)}}</td>
      <td>${{val(r.avg_class)}}</td>
      <td><b>${{Number(r.model_percent).toFixed(1)}}%</b></td>
      <td style="text-align:left">${{esc(r.top_factors)}}</td>
    </tr>
  `).join("");
}}

select.addEventListener("change", render);
render();
</script>
</main>
</body>
</html>
"""
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "index.html").write_text(page, encoding="utf-8")
    scored.to_csv(RESULTS_DIR / "handicap_results.csv", index=False)
    scored.to_csv(RESULTS_DIR / "extracted_horses.csv", index=False)


def main():
    pdf = find_pdf()
    races, horses = parse_bris_pdf(pdf)
    scored = handicap_horses(horses)

    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "status.txt").write_text(
        f"Processed {pdf.name}: {len(races)} races / {len(horses)} horses\n"
    )
    make_html(races, scored, pdf.name)
    print(f"Processed {pdf.name}: {len(races)} races / {len(horses)} horses")


if __name__ == "__main__":
    main()
