"""
Network registry: who each network is and how to read its QA codes.

A *network* is who produced the data (AURN, LAQN, ...). A *source* is a way
aeolus fetches it (``AURN`` via RData, ``AURN-SOS`` via the SOS API). Several
sources can serve one network; ``SOURCE_ROUTES`` records which. The routing
*engine* (choosing a backend) is v0.6.0 — this is only the lookup table.
"""

from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources

import yaml

from .qa import INSTRUMENT_CLASSES, QA_MODELS, QA_TIERS, RATIFICATION_STAGES


@dataclass(frozen=True)
class NetworkSpec:
    code: str
    name: str
    country: str
    regulatory: bool
    instrument_class: str
    qa_model: str
    default_ratification_stage: str | None
    qa_code_vocabulary: dict = field(default_factory=dict)
    operators: tuple = ()
    ratification_cadence_months: int | None = None
    first_ratification_latency_months: int | None = None
    full_year_ratified_by: str | None = None
    ratification_overrides: str = ""
    data_licence: str = ""
    homepage_url: str = ""
    notes: str = ""


def _validate(spec: NetworkSpec) -> None:
    if spec.qa_model not in QA_MODELS:
        raise ValueError(f"{spec.code}: qa_model {spec.qa_model!r} is not one of {QA_MODELS}")
    if spec.instrument_class not in INSTRUMENT_CLASSES:
        raise ValueError(f"{spec.code}: instrument_class {spec.instrument_class!r}")
    if spec.default_ratification_stage not in (*RATIFICATION_STAGES, None):
        raise ValueError(f"{spec.code}: default_ratification_stage {spec.default_ratification_stage!r}")
    for code, entry in spec.qa_code_vocabulary.items():
        if not isinstance(code, str):
            raise ValueError(f"{spec.code}: qa code {code!r} must be a string (quote it in the YAML)")
        if entry["qa_tier"] not in QA_TIERS:
            raise ValueError(f"{spec.code}: {code!r} has qa_tier {entry['qa_tier']!r}")
        if entry.get("ratification_stage") not in (*RATIFICATION_STAGES, None):
            raise ValueError(f"{spec.code}: {code!r} has stage {entry.get('ratification_stage')!r}")


@lru_cache(maxsize=1)
def _load() -> dict[str, NetworkSpec]:
    specs = {}
    folder = resources.files("aeolus") / "data" / "qa_vocabularies"
    for path in sorted(folder.iterdir(), key=lambda p: p.name):
        if not path.name.endswith(".yaml"):
            continue
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        raw["operators"] = tuple(raw.get("operators") or ())
        raw["qa_code_vocabulary"] = raw.get("qa_code_vocabulary") or {}
        spec = NetworkSpec(**raw)
        _validate(spec)
        specs[spec.code] = spec
    return specs


def list_network_specs() -> list[NetworkSpec]:
    return list(_load().values())


def get_network_spec(code: str) -> NetworkSpec:
    try:
        return _load()[code.upper()]
    except KeyError:
        raise KeyError(f"Unknown network {code.upper()!r}. Known: {sorted(_load())}") from None


# source name -> (network code, backend). Every registered source must appear.
SOURCE_ROUTES: dict[str, tuple[str, str]] = {
    **{n: (n, "RDATA") for n in ("AURN", "SAQN", "WAQN", "NI", "AQE", "LMAM", "LAQN")},
    "SAQD": ("SAQN", "RDATA"),
    **{f"{n}-SOS": (n, "SOS") for n in ("AURN", "SAQN", "WAQN", "NI", "AQE")},
    "LAQN-ERG": ("LAQN", "ERG_REST"),
    **{n: (n, n) for n in (
        "BREATHE_LONDON", "AIRQO", "AIRNOW", "EEA", "SONITUS",
        "SENSOR_COMMUNITY", "OPENAQ", "PURPLEAIR",
    )},
}


def spec_for_source(source: str) -> tuple[str, str, NetworkSpec]:
    """``(network, backend, spec)`` for a source — including one aeolus has never
    heard of.

    A source registered with ``register_source`` but absent from
    ``SOURCE_ROUTES`` (a user's own adapter) is treated as its own network with
    nothing known about it: ``qa_tier`` is ``unknown`` and no stage is assumed.
    """
    name = source.upper()
    if name in SOURCE_ROUTES:
        network, backend = SOURCE_ROUTES[name]
        return network, backend, get_network_spec(network)
    return name, name, NetworkSpec(
        code=name, name=name, country="*", regulatory=False,
        instrument_class="unknown", qa_model="unknown", default_ratification_stage=None,
    )


def route_for(source: str) -> tuple[str, str]:
    try:
        return SOURCE_ROUTES[source.upper()]
    except KeyError:
        raise KeyError(
            f"Source {source.upper()!r} has no entry in network_registry.SOURCE_ROUTES"
        ) from None
