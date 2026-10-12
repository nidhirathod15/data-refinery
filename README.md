# DataRefinery
![tests](https://github.com/nidhirathod15/data-refinery/actions/workflows/ci.yml/badge.svg)

Real-world spreadsheets are messy. Column names are inconsistent, dates are written five different ways, and the same value is spelled three different ways. Before you can analyse anything, you spend hours cleaning it.

DataRefinery does that first cleanup for you. Upload a CSV or Excel file, and you get back a cleaned file, a preview, and a short report of exactly what was changed.

## What it does
- **Fixes column names.** "Company Name", "Organisation" and "Firm" all become `company`.
- **Cleans text.** Removes stray symbols and extra spaces. Emails and phone numbers are left exactly as they are.
- **Fixes dates.** `02/09/2024`, `2024-03-05` and `5 Jan 2023` all become `YYYY-MM-DD`. Day comes first by default (2 September), and you can switch this in `engine.py`.
- **Splits ranges.** A value like `50,000-70,000` becomes two columns, a minimum and a maximum.
- **Merges spelling variants.** `Male`, `male`, `M` and `MALE` become one value.
- **Removes blank and duplicate rows.**
- **Blanks impossible values.** An age of -7 or 999 is removed instead of kept.
- **Reports missing values instead of guessing them.** Filling gaps is a decision for the person who knows the data, not for a tool.
- **Adds a category to each row** (for example "Healthcare" or "Web Development"). It compares the meaning of the text, not just keywords, so a row about "cooking recipe app for home chefs" can still land in "App Development". When the tool isn't confident, it falls back to simple keyword matching instead of guessing.

## Try it
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000 and upload `samples/messy_sample.csv` to see it work.
The first run downloads a small language model, so it takes a little longer.

You can also run it with Docker:
```bash
docker build -t datarefinery .
docker run -p 8000:8000 datarefinery
```

## Tests
```bash
pip install -r requirements-dev.txt
pytest -v
```
The tests cover the cleaning rules and the upload safety checks. Several of them exist because of real bugs I found while building this:
- A keyword like "ai" matched inside "Raipur", and "app" matched inside "appointment".
- A column that only held a year (2024) was turned into a made-up full date.
- Two different columns, "price" and "cost", were both renamed to "amount", leaving two columns with the same name.
- A column name like "corporate_type" was treated as a numeric range because it contains "rate".

## Check the categoriser
`eval/evaluate_categorization.py` compares keyword-only matching against the meaning-based method at different confidence thresholds, using the labelled examples in `eval/labeled_rows.csv`. Run it with:

```bash
python -m eval.evaluate_categorization
```
I use it to choose the confidence threshold from evidence instead of a guess.

## Limitations
I'd rather you hear these from me:
- There are only 8 built-in categories (listed in `app/core/schema.py`), and they lean towards tech and services. Other kinds of data, like retail, mostly come out as "Uncategorized". You can edit the categories to fit your data.
- Duplicate removal only catches exact copies. "Acme Corp" and "acme corp" are treated as different rows.
- Impossible-value checks only cover `age`, `quantity` and `shipping_cost`. Add your own columns in `VALID_RANGES` in `engine.py`.
- Only `.csv` and `.xlsx` files up to 10 MB are accepted, and files are deleted after an hour.

## How it's organised
```
app/main.py          the web routes: upload, process, download
app/core/engine.py   the cleaning and categorising steps
app/core/schema.py   column names, categories and the confidence threshold
app/templates/       the web page
tests/               automated tests
eval/                the categoriser evaluation
samples/             a small messy file to try
```

Built with Python, FastAPI, pandas, scikit-learn and sentence-transformers.
PROJECT BY, Nidhi Rathod.
