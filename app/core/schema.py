# app/core/schema.py: the RULES

# Maps messy real-world column name variants -> one standard column name.
# NOTE: "year" was removed from "date" on purpose: a bare year like 2024 is not a date.
COLUMN_MAPPING = {
    "company": ["company name", "organisation", "firm", "comp name", "entity"],
    "team_size": ["team size", "employees", "staff", "no of people", "headcount"],
    "service": ["service", "service type", "offering", "category", "what they do"],
    "amount": ["price", "rate", "cost", "charges", "budget", "revenue", "salary", "transaction"],
    "date": ["timestamp", "created_at", "date_hired"],
    "title": ["name", "movie", "show", "product_name"],
    "contact": ["email", "phone", "mobile", "lead_source"],
}

# Fallback for when the embedding model isn't confident about a row.
CATEGORIES = {
    "Web Development": ["web", "frontend", "backend", "website", "react", "node"],
    "Digital Marketing": ["seo", "marketing", "ads", "ppc", "social media", "content"],
    "App Development": ["android", "ios", "mobile", "app", "flutter", "swift"],
    "Data & AI": ["data", "ai", "ml", "analytics", "machine learning", "python"],
    "Financial": ["bank", "invoice", "payment", "crypto", "stock", "tax"],
    "Healthcare": ["patient", "doctor", "clinic", "medical", "hospital"],
    "Technology": ["software", "hardware", "saas", "cloud", "code"],
    "Entertainment": ["movie", "film", "cinema", "studio", "actor", "director", "music", "game"],
}

# One plain-language sentence per category; rows are compared against these
# with sentence embeddings + cosine similarity.
CATEGORY_DESCRIPTIONS = {
    "Web Development": "building websites, frontend or backend code, hosting, react, node",
    "Digital Marketing": "advertising, seo, social media campaigns, marketing content",
    "App Development": "mobile apps for android or ios, flutter, swift development",
    "Data & AI": "data science, machine learning, analytics, artificial intelligence, python",
    "Financial": "banking, invoices, payments, taxes, stock trading, crypto",
    "Healthcare": "patients, doctors, hospitals, clinics, medical treatment",
    "Technology": "software, hardware, cloud infrastructure, saas products",
    "Entertainment": "movies, films, music, studios, actors, games",
}

# Below this similarity score the embedding guess is not trusted and keyword
# matching is used instead. Pick it with eval/evaluate_categorization.py.
SIMILARITY_THRESHOLD = 0.35
