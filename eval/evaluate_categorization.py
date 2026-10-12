"""Compare keyword-only vs embedding categorisation on hand-labelled rows.

    python -m eval.evaluate_categorization

Edit eval/labeled_rows.csv (columns: text,label). Aim for 100+ rows that YOU wrote or
collected from real data, with a few rows per category plus some 'Uncategorized'.
Prints a table and writes eval/results.md, so the threshold in schema.py is chosen
from evidence instead of a guess.
"""
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score

from app.core.engine import RefineryEngine, _load_embeddings

HERE = Path(__file__).parent
THRESHOLDS = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]


def score(labels, preds):
    return accuracy_score(labels, preds), f1_score(labels, preds, average="macro", zero_division=0)


def main():
    data = pd.read_csv(HERE / "labeled_rows.csv")
    texts = data["text"].str.lower().tolist()
    labels = data["label"].tolist()
    rows = []

    kw = RefineryEngine("x.csv", use_embeddings=False)
    acc, f1 = score(labels, kw.categorize_texts(texts)[0])
    rows.append(("keywords only", "-", acc, f1, "-"))

    if _load_embeddings() is None:
        print("Embedding model unavailable here: run this where sentence-transformers can download the model.")
    else:
        for t in THRESHOLDS:
            eng = RefineryEngine("x.csv", use_embeddings=True, threshold=t)
            preds, fallback, _ = eng.categorize_texts(texts)
            acc, f1 = score(labels, preds)
            rows.append(("embeddings + keyword fallback", t, acc, f1, f"{fallback / len(texts):.0%}"))

    table = pd.DataFrame(rows, columns=["method", "threshold", "accuracy", "macro_f1", "rows_to_fallback"])
    table["accuracy"] = table["accuracy"].map("{:.2f}".format)
    table["macro_f1"] = table["macro_f1"].map("{:.2f}".format)
    print(f"\n{len(data)} labelled rows\n")
    print(table.to_string(index=False))
    (HERE / "results.md").write_text(f"{len(data)} labelled rows\n\n```\n{table.to_string(index=False)}\n```\n")


if __name__ == "__main__":
    main()
