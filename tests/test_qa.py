"""QA enums are frozen public keys; derivation is pure and total."""

import pandas as pd
import pytest

from aeolus.qa import (
    INSTRUMENT_CLASSES, QA_MODELS, QA_TIERS, RATIFICATION_STAGES, derive_qa, legacy_ratification,
)


def test_enums_are_exactly_the_frozen_values():
    assert QA_TIERS == (
        "reference_full_qc", "reference_provisional", "lcs_calibrated",
        "lcs_factory_only", "flagged", "unknown",
    )
    assert RATIFICATION_STAGES == ("unratified", "ratified", "supplied", "not_applicable")
    assert QA_MODELS == (
        "regulatory_temporal_ratification", "staged_calibration",
        "point_in_time_validation", "none", "mixed", "unknown",
    )
    assert INSTRUMENT_CLASSES == ("reference", "equivalent", "indicative", "LCS", "mixed", "unknown")


VOCAB = {
    "verified": {"qa_tier": "reference_full_qc", "ratification_stage": "ratified"},
    "unverified": {"qa_tier": "reference_provisional", "ratification_stage": "unratified"},
}


def test_known_codes_map_through_the_vocabulary():
    tier, stage = derive_qa(pd.Series(["verified", "unverified"]), VOCAB, default_stage=None)
    assert tier.tolist() == ["reference_full_qc", "reference_provisional"]
    assert stage.tolist() == ["ratified", "unratified"]


def test_missing_code_is_unknown_with_the_network_default_stage():
    tier, stage = derive_qa(pd.Series([None, float("nan")]), VOCAB, default_stage="supplied")
    assert tier.tolist() == ["unknown", "unknown"]
    assert stage.tolist() == ["supplied", "supplied"]


def test_code_not_in_vocabulary_is_unknown_and_stage_null():
    tier, stage = derive_qa(pd.Series(["mystery"]), VOCAB, default_stage=None)
    assert tier.tolist() == ["unknown"]
    assert stage.isna().all()


@pytest.mark.parametrize(
    "tier, stage, expected",
    [
        ("reference_full_qc", "ratified", "Ratified"),
        ("reference_provisional", "unratified", "Provisional"),
        ("lcs_calibrated", "not_applicable", "Indicative"),
        ("lcs_factory_only", "not_applicable", "Validated"),
        ("flagged", "not_applicable", "Invalid"),
        ("unknown", "not_applicable", "Unvalidated"),
        ("unknown", None, "None"),
    ],
)
def test_legacy_ratification_mirror(tier, stage, expected):
    out = legacy_ratification(pd.Series([tier]), pd.Series([stage], dtype=object))
    assert out.tolist() == [expected]
