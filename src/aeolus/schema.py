"""
The public wire format, and the one step that produces it.

Adapters emit ``types.ADAPTER_DATA_COLUMNS``. ``finalise_data_frame`` runs where
every download converges and adds the network identity and the QA model. It is
the only code that knows both schemas — do not add these columns in adapters.
"""

import pandas as pd

from .network_registry import get_network_spec, route_for
from .qa import derive_qa, legacy_ratification

DATA_COLUMNS = [
    "site_code", "network", "date_time", "measurand", "value", "units",
    "qa_code", "qa_tier", "ratification_stage", "backend",
    "source_network", "ratification", "created_at",
]
LEGACY_DATA_COLUMNS = ("source_network", "ratification")  # mirrors, dropped in v1.0


def empty_public_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=DATA_COLUMNS)


def finalise_data_frame(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Turn an adapter frame for *source* into the public schema. Idempotent."""
    attrs = dict(df.attrs)
    if df.empty:
        out = empty_public_frame()
        out.attrs = attrs
        return out

    network, backend = route_for(source)
    spec = get_network_spec(network)
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

    out = out[DATA_COLUMNS]
    out.attrs = attrs
    return out
