# BRISNET Horse Race Handicapper — GitHub-only Edition

This is the version designed to solve the PDF-upload problem permanently.

## Architecture

```text
GitHub repository
      |
      | upload BRISNET PDF to input/
      v
GitHub Actions
      |
      | Python + pypdf parses PDF
      | handicap calculations run on GitHub runner
      v
results/index.html + CSV
      |
      v
GitHub Pages
```

There is **no separate server, VPS, Streamlit process, or backend hosting account**.

## One-time GitHub Pages setup

1. Put this repository on GitHub.
2. Keep the default branch as `main`.
3. Go to **Settings → Pages**.
4. Choose **Deploy from a branch**.
5. Select **main** and **/ (root)**.
6. Save.

The repository's root `index.html` is the upload/instructions page, and `results/index.html` is the generated handicap report.

## Daily use

1. Open your GitHub repository.
2. Open `input/`.
3. Click **Add file → Upload files**.
4. Select the BRISNET Ultimate PP PDF.
5. Commit directly to `main`.
6. GitHub Actions automatically processes the PDF.
7. Open your Pages site and click **Open latest handicap results**.

The provided `index.html` also contains an **Open repository upload page** link to make step 3 easier.

## What the action generates

- `results/index.html` — browser-readable handicap report
- `results/handicap_results.csv` — handicap scores/rankings
- `results/extracted_horses.csv` — extracted BRISNET summary fields
- `results/status.txt` — processing status

## Supported PDF

The parser targets text-based **BRISNET Ultimate PP** PDFs matching the example card supplied for this project.

Scanned/image-only PDFs are not supported by the current parser.

## Handicap score

The baseline score uses:

- Prime Power: 32%
- Speed: 20%
- Late Speed: 13%
- Pace-Speed: 8%
- E1: 7%
- E2: 7%
- Race Rating: 5%
- Average Class: 4%
- Morning-line market signal: 4%

Missing values are reweighted rather than automatically treated as poor.

The `Model %` is a race-relative normalized score. It is not statistically calibrated.

## Important data note

BRISNET/Equibase information may be proprietary. Keep source PDFs and derived data in accordance with your applicable data-provider terms.
