# DataRefinery

Upload a messy CSV or Excel file, get back a clean one plus a report of exactly what changed.

![screenshot](docs/screenshot.png) <!-- TODO: add a screenshot -->
**Live demo:** <!-- TODO: paste your Render / Hugging Face Spaces link -->

## What it does
1. **Rule-based cleaning:** standardises column names, strips stray symbols, parses mixed date formats
   (day-first by default), splits ranges like `15-20` into min/max columns, merges spelling variants
   (`Male / male / m`), removes blank and duplicate rows, and blanks impossible values (age `-7`, `999`).
2. **Missing values are reported, never guessed.** Imputation is the analyst's decision.
3. **Semantic categorisation:** each row is compared to category descriptions using sentence embeddings
   (`all-MiniLM-L6-v2`); low-confidence rows fall back to whole-word keyword matching.
4. **A change report** (rows removed, dates fixed, values blanked, ...) is shown with every result.

## Run it
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload        # http://127.0.0.1:8000
```
Try `samples/messy_sample.csv`. Or with Docker: `docker build -t datarefinery . && docker run -p 8000:8000 datarefinery`

## Tests
```bash
pip install -r requirements-dev.txt
pytest -v
```
`tests/test_engine.py` covers the cleaning rules plus regression tests for bugs found during development
(substring keyword matches such as "ai" in "Raipur", year-only values turned into fake dates,
duplicate column names after renaming, substring column matching). `tests/test_api.py` covers upload
safety (random server-side filenames, extension and size checks, download path whitelist).

## Evaluating the categoriser
`python -m eval.evaluate_categorization` compares keyword-only vs embeddings across similarity thresholds on
`eval/labeled_rows.csv`. **Results:** <!-- TODO: paste your table from eval/results.md after labelling 100+ rows -->

## Known limitations
- Categories are 8 fixed tech-service categories (`app/core/schema.py`); other kinds of data mostly end up "Uncategorized".
- Duplicate removal is exact-match: `Acme Corp` and `acme corp` are not treated as the same row.
- `VALID_RANGES` covers only `age`, `quantity`, `shipping_cost`; extend it for your data.
- Files are deleted after one hour; no user accounts.

## Layout
```
app/main.py            FastAPI routes (upload, process, download)
app/core/engine.py     cleaning + categorisation pipeline
app/core/schema.py     column mappings, categories, threshold
app/templates/         Bootstrap UI
tests/  eval/  samples/
```
