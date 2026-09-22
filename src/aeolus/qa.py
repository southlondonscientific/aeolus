"""
The v0.5.0 data-quality model: frozen enums and pure derivation functions.

The enum values are permanent public keys (renaming one is a major breaking
change), shared with Argus. ``qa_code`` is whatever the upstream wrote;
``qa_tier`` and ``ratification_stage`` are derived from it through the
network's vocabulary (see ``aeolus.network_registry``).
"""

import pandas as pd

QA_TIERS = (
    "reference_full_qc", "reference_provisional", "lcs_calibrated",
    "lcs_factory_only", "flagged", "unknown",
)
RATIFICATION_STAGES = ("unratified", "ratified", "supplied", "not_applicable")
QA_MODELS = (
    "regulatory_temporal_ratification", "staged_calibration",
    "point_in_time_validation", "none", "mixed", "unknown",
)
INSTRUMENT_CLASSES = ("reference", "equivalent", "indicative", "LCS", "mixed", "unknown")


def derive_qa(
    qa_codes: pd.Series, vocabulary: dict[str, dict], default_stage: str | None
) -> tuple[pd.Series, pd.Series]:
    """Return ``(qa_tier, ratification_stage)`` for a series of upstream codes.

    A missing code means the upstream said nothing: tier ``unknown`` and the
    network's *default_stage*. A code the vocabulary does not list is also
    ``unknown``, with a null stage — an unrecognised token must not be
    silently promoted to the network default.
    """
    codes = qa_codes.astype(object)
    missing = codes.isna()
    tier_map = {code: entry["qa_tier"] for code, entry in vocabulary.items()}
    stage_map = {code: entry.get("ratification_stage") for code, entry in vocabulary.items()}

    tier = codes.map(tier_map).where(~missing, "unknown").fillna("unknown")
    stage = codes.map(stage_map).astype(object)
    stage = stage.where(~missing, default_stage)
    return tier.astype(object), stage.where(stage.notna(), None)


_LEGACY_BY_TIER = {
    "lcs_calibrated": "Indicative",
    "lcs_factory_only": "Validated",
    "flagged": "Invalid",
}


def legacy_ratification(qa_tier: pd.Series, stage: pd.Series) -> pd.Series:
    """The pre-0.5.0 ``ratification`` string, derived from the new columns (spec §4.3)."""
    out = pd.Series("None", index=qa_tier.index, dtype=object)
    out = out.where(~(qa_tier == "unknown") | stage.isna(), "Unvalidated")
    for tier, label in _LEGACY_BY_TIER.items():
        out = out.where(qa_tier != tier, label)
    out = out.where(stage != "ratified", "Ratified")
    out = out.where(stage != "unratified", "Provisional")
    return out
