"""Regression tests for RefineryEngine. Run with:  pytest -v

Every test builds a tiny CSV on the fly so it is obvious what is being checked.
Embeddings are switched off so tests are fast and need no model download.
"""
import pandas as pd

from app.core.engine import RefineryEngine


def run(tmp_path, rows, **kwargs):
    path = tmp_path / "data.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    engine = RefineryEngine(path, use_embeddings=False, **kwargs)
    return engine.process(), engine.report


# ── cleaning basics ─────────────────────────────────────────────
def test_blank_rows_are_removed(tmp_path):
    rows = [{"company": "A", "city": "Pune"}, {"company": "", "city": " "}, {"company": "B", "city": "Mumbai"}]
    df, report = run(tmp_path, rows)
    assert len(df) == 2
    assert report["empty_rows_removed"] == 1


def test_duplicate_rows_are_removed(tmp_path):
    rows = [{"company": "A", "city": "Pune"}] * 3 + [{"company": "B", "city": "Mumbai"}]
    df, report = run(tmp_path, rows)
    assert len(df) == 2
    assert report["duplicate_rows_removed"] == 2


def test_column_name_variants_are_mapped(tmp_path):
    df, _ = run(tmp_path, [{"Company Name": "A", "Team Size": "10"}])
    assert "company" in df.columns and "team_size" in df.columns


def test_stray_symbols_removed_from_text(tmp_path):
    df, _ = run(tmp_path, [{"company": "  Acme @@ Corp!!  ", "city": "Pune"}])
    assert df.loc[0, "company"] == "Acme Corp"


def test_email_and_phone_untouched(tmp_path):
    df, _ = run(tmp_path, [{"company": "A", "email": "a+test@x.com", "phone": "+91-98765 43210"}])
    assert "a+test@x.com" in df.values and "+91-98765 43210" in df.values


# ── dates ───────────────────────────────────────────────────────
def test_dates_are_standardised_dayfirst(tmp_path):
    df, report = run(tmp_path, [{"company": "A", "date": "02/09/2024"}, {"company": "B", "date": "2024-03-05"},
                                {"company": "C", "date": "5 Jan 2023"}])
    assert list(df["date"]) == ["2024-09-02", "2024-03-05", "2023-01-05"]
    assert report["dates_unreadable"] == 0


def test_unreadable_dates_are_counted_not_invented(tmp_path):
    df, report = run(tmp_path, [{"company": "A", "date": "not a date"}, {"company": "B", "date": "2024-01-01"}])
    assert df.loc[0, "date"] == "not a date"
    assert report["dates_unreadable"] == 1


def test_year_only_is_not_turned_into_a_fake_date(tmp_path):
    """BUG FIX: dateutil turns '2024' into today's month/day (e.g. 2024-10-12)."""
    df, report = run(tmp_path, [{"company": "A", "date": "2024"}, {"company": "B", "date": "2023"}])
    assert list(df["date"]) == ["2024", "2023"]
    assert report["dates_unreadable"] == 0


def test_year_column_is_not_renamed_to_date(tmp_path):
    df, _ = run(tmp_path, [{"company": "A", "year": 2024}])
    assert "year" in df.columns and "date" not in df.columns


# ── numbers and ranges ──────────────────────────────────────────
def test_text_ranges_split_into_min_max(tmp_path):
    df, _ = run(tmp_path, [{"company": "A", "amount": "50,000-70,000"}, {"company": "B", "amount": "12.5"}])
    assert list(df["amount_min"]) == [50000.0, 12.5]
    assert list(df["amount_max"]) == [70000.0, 12.5]


def test_substring_column_names_do_not_trigger_range_split(tmp_path):
    """BUG FIX: 'rate' used to match inside 'corporate_type'."""
    df, _ = run(tmp_path, [{"company": "A", "corporate_type": "private limited"}])
    assert "corporate_type_min" not in df.columns


def test_impossible_values_are_blanked(tmp_path):
    df, report = run(tmp_path, [{"company": "A", "age": -7, "quantity": 5}, {"company": "B", "age": 999, "quantity": -2},
                                {"company": "C", "age": 30, "quantity": 1}])
    assert df["age"].isna().sum() == 2 and df["quantity"].isna().sum() == 1
    assert report["impossible_values_blanked"] == {"age": 2, "quantity": 1}


def test_missing_values_are_reported_not_filled(tmp_path):
    df, report = run(tmp_path, [{"company": "A", "age": None}, {"company": "B", "age": 30}])
    assert df["age"].isna().sum() == 1
    assert report["missing_values"] == {"age": 1}


# ── spelling variants ───────────────────────────────────────────
def test_gender_spellings_merge(tmp_path):
    rows = [{"company": c, "gender": g} for c, g in zip("ABCDEF", ["M", "male", "MALE", "f", "Female", "Other"])]
    df, _ = run(tmp_path, rows)
    assert set(df["gender"]) == {"Male", "Female", "Other"}


def test_status_spellings_merge(tmp_path):
    rows = [{"company": c, "order_status": s} for c, s in zip("ABCD", ["delivered", "Delivered", "DELIVERED", "pending"])]
    df, _ = run(tmp_path, rows)
    assert df["order_status"].nunique() == 2


# ── column-mapping collisions ───────────────────────────────────
def test_price_and_cost_do_not_create_duplicate_columns(tmp_path):
    """BUG FIX: both used to be renamed to 'amount', giving two columns with one name."""
    df, report = run(tmp_path, [{"company": "A", "price": 10, "cost": 4}])
    assert df.columns.is_unique
    assert "amount" in df.columns
    assert len(report["columns_not_renamed_to_avoid_clash"]) == 1


# ── categorisation (keyword path) ───────────────────────────────
def test_keywords_match_whole_words_only(tmp_path):
    """BUG FIX: 'ai' matched 'Raipur' and 'app' matched 'appointment'."""
    engine = RefineryEngine(tmp_path / "x.csv", use_embeddings=False)
    assert engine.keyword_match("transport company in raipur") == "Uncategorized"
    assert engine.keyword_match("dentist appointment booking") == "Uncategorized"
    assert engine.keyword_match("we build an ai platform") == "Data & AI"


def test_categories_are_assigned(tmp_path):
    rows = [{"company": "A", "service": "react website development"},
            {"company": "B", "service": "hospital and clinic software"}]
    df, report = run(tmp_path, rows)
    assert df.loc[0, "category"] == "Web Development"
    assert report["category_method"] == "keywords only"


# ── file handling ───────────────────────────────────────────────
def test_uppercase_extension_is_accepted(tmp_path):
    path = tmp_path / "DATA.CSV"
    pd.DataFrame([{"company": "A", "city": "Pune"}]).to_csv(path, index=False)
    df = RefineryEngine(path, use_embeddings=False).process()
    assert len(df) == 1


def test_unsupported_format_raises(tmp_path):
    path = tmp_path / "data.json"
    path.write_text("{}")
    try:
        RefineryEngine(path, use_embeddings=False).process()
        assert False, "should have raised"
    except ValueError:
        pass


def test_excel_roundtrip(tmp_path):
    path = tmp_path / "data.xlsx"
    pd.DataFrame([{"company": "A", "age": 30}, {"company": "A", "age": 30}]).to_excel(path, index=False)
    df = RefineryEngine(path, use_embeddings=False).process()
    assert len(df) == 1
