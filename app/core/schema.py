# app/core/schema.py: the RULES

COLUMN_MAPPING = {
    "company": ["company name", "organisation", "firm", "comp name", "entity"],
    "team_size": ["team size", "employees", "staff", "no of people", "headcount"],
    "service": ["service", "service type", "offering", "category", "what they do"],
    "pricing": ["price", "rate", "cost", "charges", "budget"]
}

# Standard Categories for Rule-Based Engine
CATEGORIES = {
    "Web Development": ["web", "frontend", "backend", "website", "react", "node"],
    "Digital Marketing": ["seo", "marketing", "ads", "ppc", "social media", "content"],
    "App Development": ["android", "ios", "mobile", "app", "flutter", "swift"],
    "Data & AI": ["data", "ai", "ml", "analytics", "machine learning", "python"]
}

# Movie Category for your logic
CATEGORIES.update({
    "Entertainment": ["movie", "film", "cinema", "studio", "actor", "director"]
})

# Expand to cover various industries
COLUMN_MAPPING = {
    # Finance/General
    "amount": ["price", "cost", "budget", "revenue", "salary", "transaction"],
    "date": ["timestamp", "year", "created_at", "date_hired"],
    # Entertainment/Media
    "title": ["name", "movie", "show", "product_name"],
    # Contact
    "contact": ["email", "phone", "mobile", "lead_source"]
}

CATEGORIES = {
    "Financial": ["bank", "invoice", "payment", "crypto", "stock", "tax"],
    "Healthcare": ["patient", "doctor", "clinic", "medical", "hospital"],
    "Technology": ["software", "hardware", "saas", "cloud", "code"],
    "Entertainment": ["movie", "music", "game", "film", "studio"]
}