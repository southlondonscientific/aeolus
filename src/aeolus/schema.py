"""
The public wire format, and the one step that produces it.

Adapters emit ``types.ADAPTER_DATA_COLUMNS``. ``finalise_data_frame`` runs where
every download converges and adds the network identity and the QA model. It is
the only code that knows both schemas — do not add these columns in adapters.
"""

import warnings

import pandas as pd

from . import options
from .network_registry import spec_for_source
from .qa import derive_qa, legacy_ratification

DATA_COLUMNS = [
    "site_code", "network", "date_time", "measurand", "value", "units",
    "qa_code", "qa_tier", "ratification_stage", "backend",
    "source_network", "ratification", "created_at",
]
LEGACY_DATA_COLUMNS = ("source_network", "ratification")  # mirrors, dropped in v1.0

_warned_legacy = False


def public_data_columns() -> list[str]:
    """The column list in force: with or without the legacy mirrors."""
    if options.legacy_columns:
        return list(DATA_COLUMNS)
    return [c for c in DATA_COLUMNS if c not in LEGACY_DATA_COLUMNS]


def empty_public_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=public_data_columns())


def finalise_data_frame(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Turn an adapter frame for *source* into the public schema. Idempotent."""
    attrs = dict(df.attrs)
    if df.empty:
        out = empty_public_frame()
        out.attrs = attrs
        return out

    network, backend, spec = spec_for_source(source)
    out = df.copy()
    out["network"] = network
    out["backend"] = backend
    out["source_network"] = network

    wired = "qa_code" in out.columns
    codes = out["qa_code"] if wired else pd.Series(None, index=out.index, dtype=object)
    out["qa_code"] = codes.astype(object).where(codes.notna(), None)
    out["qa_tier"], out["ratification_stage"] = derive_qa(
        out["qa_code"], spec.qa_code_vocabulary, spec.default_ratification_stage
    )
    if wired or "ratification" not in out.columns:
        out["ratification"] = legacy_ratification(out["qa_tier"], out["ratification_stage"])

    global _warned_legacy
    if options.legacy_columns and not _warned_legacy:
        _warned_legacy = True
        warnings.warn(
            "The `source_network` and `ratification` columns are deprecated mirrors of "
            "`network` and of `qa_code`/`qa_tier`/`ratification_stage`; they will be removed "
            "in aeolus 1.0. Set AEOLUS_LEGACY_COLUMNS=0 (or aeolus.options.legacy_columns = "
            "False) to drop them now and check your code has migrated.",
            DeprecationWarning,
            stacklevel=4,
        )
    out = out[public_data_columns()]
    out.attrs = attrs
    return out
