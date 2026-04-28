"""
Translation helpers for role labels and other standard fields.

For v1 we maintain a small hand-curated map of standard role labels with
French equivalents. Specific cabinet titles (e.g., "Minister of Foreign
Affairs") are NOT translated here — they remain in English until proper
bilingual data is sourced from official government translations.

To extend: add entries to STANDARD_ROLE_LABELS. Keep the scope narrow —
only translate roles that apply broadly and have unambiguous French
equivalents.
"""

# English role label → French equivalent.
# Match is case-sensitive on the English side but the lookup is case-insensitive.
STANDARD_ROLE_LABELS = {
    "MP": "député",
    "MPP": "député provincial",
    "Councillor": "Conseiller",
    "Mayor": "Maire",
    "Premier": "Premier ministre",
    "Prime Minister": "Premier ministre",
}

# Build a case-insensitive lookup for matching
_LABEL_LOOKUP = {k.lower(): (k, v) for k, v in STANDARD_ROLE_LABELS.items()}


def role_to_jsonb_dict(role_en: str) -> dict:
    """Build a {en, fr} dict for a role label.

    If the role matches a known standard label, populate the proper French
    equivalent. Otherwise, populate the same English string in both slots
    (the COALESCE fallback in queries handles this gracefully).

    Args:
        role_en: The English role label (e.g., "MP", "Councillor",
                 "Minister of Foreign Affairs").

    Returns:
        A dict suitable for inserting as a jsonb column:
        {"en": "MP", "fr": "député"}
    """
    if not role_en:
        return {"en": "", "fr": ""}

    role_en = role_en.strip()
    match = _LABEL_LOOKUP.get(role_en.lower())
    if match:
        # Match found — return canonical English with proper French
        canonical_en, fr = match
        return {"en": canonical_en, "fr": fr}

    # No match — same string in both slots
    return {"en": role_en, "fr": role_en}
