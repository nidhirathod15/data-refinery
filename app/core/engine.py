import re
from functools import lru_cache

import numpy as np
import pandas as pd
from dateutil import parser
from sklearn.metrics.pairwise import cosine_similarity

from .schema import COLUMN_MAPPING, CATEGORIES, CATEGORY_DESCRIPTIONS, SIMILARITY_THRESHOLD

# ── SETTINGS YOU CAN CHANGE ─────────────────────────────────────
# Dates like 02/09/2024: True = 2 September (India/UK style), False = February 9 (US).
DAYFIRST = True

# Values outside these limits are impossible, so they get blanked (low, high).
VALID_RANGES = {
    "age": (0, 120),
    "quantity": (0, None),
    "shipping_cost": (0, None),
}

# Only columns with this many distinct values or fewer get spelling variants merged.
MAX_DISTINCT_FOR_MERGE = 30

GENDER_ALIASES = {"m": "Male", "male": "Male", "f": "Female", "female": "Female"}
# ────────────────────────────────────────────────────────────────

_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_YEAR_FIRST = re.compile(r"^\s*\d{4}[-/.]\d{1,2}[-/.]\d{1,2}")
_YEAR_ONLY = re.compile(r"^\s*\d{4}\s*$")
_ISO_DATE = r"^\d{4}-\d{2}-\d{2}$"

_NON_DESCRIPTIVE = {
    "id", "name", "email", "phone", "mobile", "city", "country", "region",
    "date", "status", "gender", "sex", "payment", "company", "contact",
}
_CONTACT_TOKENS = {"contact", "email", "phone", "mobile"}
_TEXT_TOKENS = {"company", "name", "city", "country", "title"}
_RANGE_TOKENS = {"size", "rate", "price", "team", "cost", "amount"}


@lru_cache(maxsize=1)
def _load_embeddings():
    """Load the sentence-transformer once, on first use (not at import time).
    Returns (model, category_names, category_embeddings) or None if unavailable."""
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        names = list(CATEGORY_DESCRIPTIONS.keys())
        embeddings = model.encode(list(CATEGORY_DESCRIPTIONS.values()))
        return model, names, embeddings
    except Exception as e:  # no internet on first run, package missing, ...
        print(f"[WARNING] Embedding model not available ({e}). Using keyword matching only.")
        return None


def _col_tokens(col):
    return set(str(col).lower().split("_"))


def _is_text(series):
    return series.dtype == object or pd.api.types.is_string_dtype(series)


def _holds_only_strings(series):
    values = series.dropna()
    return _is_text(series) and not values.empty and values.map(lambda v: isinstance(v, str)).all()


def is_supported_file(path):
    """Case-insensitive, so DATA.CSV and Report.XLSX work."""
    return str(path).lower().endswith((".csv", ".xlsx"))


class RefineryEngine:
    def __init__(self, file_path, use_embeddings=True, threshold=SIMILARITY_THRESHOLD):
        self.file_path = str(file_path)
        self.use_embeddings = use_embeddings
        self.threshold = threshold
        self.df = None
        self.report = {}

    # ── LOADING ─────────────────────────────────────────────────
    def load_data(self):
        path = self.file_path.lower()
        if path.endswith(".csv"):
            try:
                self.df = pd.read_csv(self.file_path, encoding="utf-8", on_bad_lines="skip")
            except UnicodeDecodeError:
                self.df = pd.read_csv(self.file_path, encoding="latin1", on_bad_lines="skip")
        elif path.endswith(".xlsx"):
            self.df = pd.read_excel(self.file_path, engine="openpyxl")
        else:
            raise ValueError("File format not supported by the Refinery (use .csv or .xlsx).")

    def map_columns(self):
        """Rename known variants to a standard name, but never create duplicate
        column names (e.g. a file with both 'price' and 'cost')."""
        rename_dict = {}
        existing = set(self.df.columns)
        used_targets = set()
        skipped = []
        for col in self.df.columns:
            for standard_name, variants in COLUMN_MAPPING.items():
                normalized = [v.lower().replace(" ", "_") for v in variants]
                if col == standard_name or col in normalized:
                    if col == standard_name:
                        used_targets.add(standard_name)
                    elif standard_name in used_targets or standard_name in existing:
                        skipped.append(col)          # would collide: keep original name
                    else:
                        rename_dict[col] = standard_name
                        used_targets.add(standard_name)
                    break
        self.df = self.df.rename(columns=rename_dict)
        self.report["columns_not_renamed_to_avoid_clash"] = skipped

    # ── CELL-LEVEL CLEANERS ─────────────────────────────────────
    def clean_text(self, text):
        if pd.isna(text):
            return text
        text = re.sub(r"[^a-zA-Z0-9\s'&.,()/\-]", "", str(text))
        return re.sub(r"\s+", " ", text).strip()

    def parse_numbers(self, value):
        """'50,000-70,000' -> (50000.0, 70000.0). '12.5' -> (12.5, 12.5)."""
        if pd.isna(value):
            return None, None
        nums = [float(n) for n in _NUMBER.findall(str(value).replace(",", ""))]
        if not nums:
            return None, None
        return nums[0], nums[-1]

    def fix_dates(self, value):
        if pd.isna(value):
            return value
        text = str(value).strip()
        if _YEAR_ONLY.match(text):
            return text        # a bare year is a year, not a date: dateutil would invent a month/day
        try:
            if _YEAR_FIRST.match(text):
                parsed = parser.parse(text, yearfirst=True, dayfirst=False)
            else:
                parsed = parser.parse(text, dayfirst=DAYFIRST)
            return parsed.strftime("%Y-%m-%d")
        except Exception:
            return value       # unreadable: left as-is and counted in the report

    def keyword_match(self, text):
        # Whole words only ("ai" must not match "Raipur", "app" must not match "appointment").
        for category, keywords in CATEGORIES.items():
            if any(re.search(rf"\b{re.escape(kw)}s?\b", text) for kw in keywords):
                return category
        return "Uncategorized"

    # ── DATASET-LEVEL STEPS ─────────────────────────────────────
    def drop_empty_rows(self):
        self.df = self.df.replace(r"^\s*$", np.nan, regex=True)
        before = len(self.df)
        self.df = self.df.dropna(how="all").reset_index(drop=True)
        self.report["empty_rows_removed"] = before - len(self.df)

    def clean_columns(self):
        dates_fixed = dates_unparsed = 0
        for col in list(self.df.columns):
            tokens = _col_tokens(col)          # whole-word match, not substring
            is_text = _is_text(self.df[col])

            if tokens & _CONTACT_TOKENS:
                continue                       # keep emails / phone numbers as written
            elif tokens & _TEXT_TOKENS:
                if is_text:
                    self.df[col] = self.df[col].apply(self.clean_text)
            elif "date" in tokens:
                original = self.df[col].copy()
                self.df[col] = original.apply(self.fix_dates)
                has_value = original.notna()
                changed = has_value & (original.astype(str) != self.df[col].astype(str))
                as_text = self.df[col].astype(str)
                still_bad = has_value & ~(as_text.str.match(_ISO_DATE) | as_text.str.match(r"^\s*\d{4}\s*$"))
                dates_fixed += int(changed.sum())
                dates_unparsed += int(still_bad.sum())
            elif tokens & _RANGE_TOKENS:
                if is_text:
                    pairs = [self.parse_numbers(v) for v in self.df[col]]
                    self.df[f"{col}_min"] = [p[0] for p in pairs]
                    self.df[f"{col}_max"] = [p[1] for p in pairs]

        self.report["dates_standardised"] = dates_fixed
        self.report["dates_unreadable"] = dates_unparsed

    def merge_spelling_variants(self):
        """Male / male / MALE / m -> Male. delivered / Delivered -> one value."""
        merged = 0
        for col in self.df.columns:
            tokens = _col_tokens(col)
            if tokens & {"id", "name", "email", "phone", "mobile", "contact", "date", "company"}:
                continue
            s = self.df[col]
            if not _is_text(s):
                continue
            non_null = s.dropna()
            if non_null.empty or not non_null.map(lambda v: isinstance(v, str)).all():
                continue
            if non_null.nunique() > MAX_DISTINCT_FOR_MERGE:
                continue

            before = non_null.nunique()
            key = s.str.strip().str.casefold()

            if tokens & {"gender", "sex"}:
                mapped = key.map(GENDER_ALIASES)
                canon = mapped.where(mapped.notna(), s.str.strip())
            else:
                most_common = s.groupby(key).agg(lambda x: x.value_counts().idxmax())
                canon = key.map(most_common)

            self.df[col] = canon.where(s.notna(), np.nan)
            merged += before - self.df[col].dropna().nunique()
        self.report["spelling_variants_merged"] = merged

    def blank_impossible_values(self):
        blanked = {}
        for col, (low, high) in VALID_RANGES.items():
            if col not in self.df.columns or not pd.api.types.is_numeric_dtype(self.df[col]):
                continue
            bad = pd.Series(False, index=self.df.index)
            if low is not None:
                bad |= self.df[col] < low
            if high is not None:
                bad |= self.df[col] > high
            if bad.sum():
                blanked[col] = int(bad.sum())
                self.df.loc[bad, col] = np.nan
        self.report["impossible_values_blanked"] = blanked

    def drop_duplicate_rows(self):
        before = len(self.df)
        self.df = self.df.drop_duplicates().reset_index(drop=True)
        self.report["duplicate_rows_removed"] = before - len(self.df)

    def _category_text_columns(self):
        if "service" in self.df.columns:
            return ["service"]
        text_cols = [c for c in self.df.columns if _holds_only_strings(self.df[c])]
        useful = [c for c in text_cols if not (_col_tokens(c) & _NON_DESCRIPTIVE)]
        return useful or text_cols

    def categorize_texts(self, texts):
        """Categorise a list of lower-case strings. Returns (labels, rows_using_keyword_fallback, method)."""
        emb = _load_embeddings() if self.use_embeddings else None
        if emb is None:
            return [self.keyword_match(t) for t in texts], len(texts), "keywords only"
        model, names, cat_embeddings = emb
        sims = cosine_similarity(model.encode(list(texts)), cat_embeddings)
        labels, fallback = [], 0
        for text, row in zip(texts, sims):
            best = row.argmax()
            if row[best] >= self.threshold:
                labels.append(names[best])
            else:
                fallback += 1
                labels.append(self.keyword_match(text))
        return labels, fallback, "embeddings, keyword fallback"

    def categorize_dataset(self):
        text_cols = self._category_text_columns()
        if len(text_cols) == 0:
            self.df["category"] = "Uncategorized"
            self.report["category_method"] = "none (no text columns)"
            self.report["uncategorized_pct"] = 100.0
            return

        combined = self.df[text_cols].fillna("").astype(str).apply(" ".join, axis=1).str.lower()
        self.report["category_columns_used"] = text_cols
        labels, fallback, method = self.categorize_texts(combined.tolist())
        self.df["category"] = labels
        self.report["category_method"] = method
        self.report["rows_sent_to_keyword_fallback"] = fallback

        share = float((self.df["category"] == "Uncategorized").mean() * 100)
        self.report["uncategorized_pct"] = round(share, 1)
        if share > 50:
            print(f"[NOTE] {share:.0f}% of rows are 'Uncategorized'. The built-in categories "
                  f"(schema.py) probably don't match this kind of data.")

    # ── MAIN ENTRY ──────────────────────────────────────────────
    def process(self):
        self.load_data()
        self.report = {"rows_in": len(self.df), "columns_in": len(self.df.columns)}

        self.df.columns = self.df.columns.astype(str).str.strip().str.lower().str.replace(" ", "_")
        self.map_columns()

        for col in self.df.columns:
            if _is_text(self.df[col]):
                self.df[col] = self.df[col].map(lambda v: v.strip() if isinstance(v, str) else v)

        self.drop_empty_rows()
        self.clean_columns()
        self.merge_spelling_variants()
        self.blank_impossible_values()
        self.drop_duplicate_rows()

        missing = self.df.isna().sum()      # reported, not filled: guessing is the analyst's call
        self.report["missing_values"] = {c: int(n) for c, n in missing.items() if n > 0}

        self.categorize_dataset()

        self.report["rows_out"] = len(self.df)
        self.report["columns_out"] = len(self.df.columns)
        return self.df
