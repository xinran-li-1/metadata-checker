# README

`readme_extractor.py` is used to batch-parse `README.pdf` files and automatically extract key information such as **declarations** and **data availability/source details** (dataset names, years, source institutions, URLs), exporting the results as **CSV / JSONL**.
It supports **up to 200 sampled files** and optional **visualization outputs**.

## Recent Updates

### Sample Expansion and Sampling Control

* Added `--max-samples` (default `200`): processes up to N matching PDFs; use `0` for no limit.
* Added `--sample-mode`: `random` (default) or `first`; also added `--seed` for reproducible randomness.
* The list of processed files is saved to `outputs/sampled_files.txt` for verification.

### Visualization Output (Optional)

* Added `--viz` flag; generates summary charts in `outputs/figs/` (PNG):

  * `sources_top20.png` (Top 20 source institutions)
  * `datasets_top20.png` (Top 20 candidate dataset names)
  * `domains_top20.png` (Top 20 URL domains)
  * `urls_per_file_hist.png` (Histogram of URLs per file)
  * `years_hist.png` (Histogram of mentioned years)
  * `needs_review_bar.png` (Bar chart of review-needed ratio)
* **Graceful fallback** when `matplotlib` is missing: only warnings, no interruption.

### Runtime Feedback and Robustness

* Console output includes summary of success / scanned / error / declaration hits / data availability hits / `needs_review` counts.
* Flatten list-type fields **only before export** to avoid double-parsing errors when reloading CSV.
* Unified handling of URL domain and year extraction for visualization consistency.

> Note: This update **does not modify** the core extraction logic (regex and parsing remain fully compatible). It is an enhancement in *sample scalability, visualization, and runtime UX*.


## Completed Features

* PDF → Text (prefers `pdfminer.six`, falls back to `PyPDF2`)
* Detect **declaration** (`I/We certify ...`) and **data availability** sections
* Extract **dataset candidates**, **year mentions** (year/range/month+year), **source institutions** (via whitelist keywords), and **URLs**
* **Batch process & export** to CSV/JSONL with `needs_review` flag
* **Sampling control** (`--max-samples`, `--sample-mode`, `--seed`)
* **Visualization output** (`--viz`)


## README Structure and Regex Mapping

### 1. Text Preprocessing (`normalize_text`)

* Merges line breaks (`-\n`), normalizes dashes (`– / — / − → -`), compresses multiple blank lines, and standardizes line endings.
* Purpose: **reduce PDF-induced tokenization errors**, preparing for reliable section and pattern matching.


### 2. Section Localization: Data Availability / Source Blocks

**Pattern:** `RE_AVAILABILITY_SECT`

```regex
^\s*(?:\d+\.\s*)?(Data Availability|Availability Statement|Data and Materials|Data Access|Data Sources|Input Data Files|Data and Code|Data description)\b.*?(?:\n\s*\n|\Z)
```

**Key design:**

* Uses `^` and `MULTILINE` to anchor section headers;
* `DOTALL` captures until blank paragraph or EOF;
* Covers common title variants (expandable as needed).

**Logic:**
README files often describe dataset sources under “Data Availability / Data Sources”; extraction prioritizes this section, with a full-text fallback if not found.


### 3. Declaration Sentences (Authorship/Data/Work Certification)

**Pattern:** `RE_DECLARATION`

```regex
\b(?:I\s*/?\s*We|We|I)\s+certify\b.*?(?:authors?|work|data|analysis)[^.]{0,300}\.
```

**Key design:**

* Matches subject (`I/We`) + trigger word `certify`;
* Allows multi-line matching until period;
* Captures up to 400 characters for summary.

**Logic:**
Typical README sentences like “I/We certify …” are used to identify statements of academic or data-use integrity.


### 4. Dataset Name Detection

* **Quoted form:** `RE_DATASET_QUOTED`

  > e.g., “the datasets **‘Household Survey 2019’** and **‘Admin Panel’**”

* **Unquoted form:** `RE_DATASET_NAME`

  * Matches keywords such as `dataset / data set / database / corpus / survey / panel / registry / index / indicator`
  * Uses lookahead for typical boundaries (`was / were / collected / from / ; , : ( ) .`)

* **Filename form:** `RE_DATA_FILE`

  * Matches suffixes like `.csv / .dta / .xlsx / .tsv / .zip / .rds`

**Logic:**
All three forms run in parallel, with deduplication to maximize recall.


### 5. Temporal Mentions (Collection/Coverage Period)

* Range of years: `RE_RANGE_YEAR_Y` (e.g., `2010–2019`)
* Month + year: `RE_MONTH_YEAR` (e.g., `September 2020`)
* Single year: `RE_YEAR` (e.g., `2018`)

**Logic:**
All extracted time mentions are deduplicated and used for year histogram visualization.


### 6. URL and Domain Extraction

* **URL:** `RE_URL` (starts with `http(s)://`)
* **Domain:** extracted at runtime via `urlparse().netloc` for Top 20 domain stats.

**Logic:**
Data availability sections often include download or homepage links; domain distribution helps profile common data sources (e.g., `worldbank.org`, `oecd.org`).

### 7. Source Institution Whitelist

**Pattern:** `RE_SOURCE` (World Bank / IMF / OECD / UN / National Statistics Offices / Ministries / Universities)

**Logic:**
Whitelist ensures high-precision matching; localized names can be added later.


## Extraction Pipeline (README → Regex → Results)

1. **Parse text:** PDF → plain text (`pdfminer.six` preferred, `PyPDF2` fallback)
2. **Preprocess:** clean line breaks and symbols via `normalize_text`
3. **Locate section:** extract with `RE_AVAILABILITY_SECT`; fallback to full-text
4. **Extract elements:** URL / year / dataset / source (both section + full text)
5. **Health check:** if key info missing → `needs_review=True`
6. **Export & visualize:** CSV/JSONL + charts generated in-memory (to avoid drift)


## Example Usage

```bash
# Random sample (max 200) with visualization
python readme_extractor.py \
  --input-dir data/readmes --glob "*.pdf" \
  --out-csv outputs/results.csv --out-jsonl outputs/results.jsonl \
  --save-text --max-samples 200 --sample-mode random --seed 42 --viz

# Sequential processing (first N = 200)
python readme_extractor.py --max-samples 200 --sample-mode first --viz

# Process all (no limit)
python readme_extractor.py --max-samples 0 --viz
```

**Output directories:**

* Tables: `outputs/results.csv`, `outputs/results.jsonl`
* Text: `outputs/txt/*.txt` (when `--save-text` is used)
* Sample list: `outputs/sampled_files.txt`
* Figures: `outputs/figs/*.png` (when `--viz` is enabled)


## To Be Improved / Modified (Regex & Parsing Layer)

* **Declaration variants:** add `attest | confirm | declare | affirm | acknowledge`
* **Section aliases:** add `Data Accessibility | Availability of Data and Materials | Data sharing | Source of data`
* **Source recognition:** extend to longer and localized institution names
* **Time formats:** support `FY2018 | 2019/20 | Q1–Q4 | H1/H2 | Week 12, 2020`
* **Proximity pairing:** link “Dataset ⇄ Year/Source/URL” via sliding window
* **OCR extension:** integrate `ocrmypdf` or `tesseract` preprocessing

