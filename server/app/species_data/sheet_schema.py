"""JSON Schema d'une fiche rédactionnelle `species-data/sheets/<Genre_espece>.json`.

Copié tel quel du contrat (`docs/api-contract.md` §8.3) — ne pas diverger sans mettre à
jour les deux en même temps.
"""

SHEET_JSON_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "bird-frame/species-sheet-v1",
    "title": "Fiche rédactionnelle bird-frame v1",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "scientific_name",
        "summary_fr",
        "habitat",
        "diet",
        "activity_pattern",
        "migration",
        "seasonality_fr",
        "song_fr",
        "lookalikes",
        "rarity_note",
        "fun_facts",
        "sources",
        "generated_at",
        "generator_model",
    ],
    "properties": {
        "schema_version": {"const": 1},
        "scientific_name": {"type": "string", "minLength": 3, "maxLength": 200},
        "summary_fr": {"type": "string", "minLength": 500, "maxLength": 1800},
        "habitat": {"type": "string", "minLength": 10, "maxLength": 400},
        "diet": {"type": "string", "minLength": 5, "maxLength": 400},
        "activity_pattern": {"enum": ["diurne", "nocturne", "crépusculaire", "mixte"]},
        "migration": {
            "type": "object",
            "additionalProperties": False,
            "required": ["statut", "hiverne", "niche", "passage"],
            "properties": {
                "statut": {
                    "enum": [
                        "sédentaire",
                        "migrateur partiel",
                        "migrateur",
                        "hivernant",
                        "estivant",
                        "de passage",
                    ]
                },
                "hiverne": {"type": ["string", "null"], "maxLength": 300},
                "niche": {"type": ["string", "null"], "maxLength": 300},
                "passage": {"type": ["string", "null"], "maxLength": 300},
            },
        },
        "seasonality_fr": {"type": "string", "minLength": 10, "maxLength": 400},
        "song_fr": {"type": "string", "minLength": 10, "maxLength": 400},
        "lookalikes": {
            "type": "array",
            "maxItems": 5,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["scientific_name", "common_name_fr", "why_fr"],
                "properties": {
                    "scientific_name": {"type": "string", "minLength": 3, "maxLength": 200},
                    "common_name_fr": {"type": ["string", "null"], "maxLength": 100},
                    "why_fr": {"type": "string", "minLength": 5, "maxLength": 200},
                },
            },
        },
        "rarity_note": {"type": "string", "minLength": 5, "maxLength": 300},
        "fun_facts": {
            "type": "array",
            "minItems": 2,
            "maxItems": 3,
            "items": {"type": "string", "minLength": 10, "maxLength": 250},
        },
        "sources": {
            "type": "array",
            "minItems": 1,
            "maxItems": 10,
            "uniqueItems": True,
            "items": {"type": "string", "pattern": "^https://\\S+$"},
        },
        "generated_at": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$"},
        "generator_model": {"type": "string", "minLength": 3, "maxLength": 100},
        "reviewed_by_human": {"type": "boolean"},
    },
}
