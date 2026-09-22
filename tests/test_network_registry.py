import pytest

import aeolus
import aeolus.sources  # noqa: F401  (registers the sources)
from aeolus.network_registry import SOURCE_ROUTES, get_network_spec, list_network_specs, route_for
from aeolus.qa import INSTRUMENT_CLASSES, QA_MODELS, QA_TIERS, RATIFICATION_STAGES

CODES = {
    "AURN", "LAQN", "AQE", "SAQN", "WAQN", "NI", "BREATHE_LONDON", "LMAM", "AIRQO",
    "PURPLEAIR", "SENSOR_COMMUNITY", "AIRNOW", "EEA", "SONITUS", "OPENAQ",
}


def test_the_fifteen_networks_load():
    assert {spec.code for spec in list_network_specs()} == CODES


@pytest.mark.parametrize("code", sorted(CODES))
def test_every_value_is_a_frozen_enum_member(code):
    spec = get_network_spec(code)
    assert spec.qa_model in QA_MODELS
    assert spec.instrument_class in INSTRUMENT_CLASSES
    assert spec.default_ratification_stage in (*RATIFICATION_STAGES, None)
    for entry in spec.qa_code_vocabulary.values():
        assert entry["qa_tier"] in QA_TIERS
        assert entry.get("ratification_stage") in (*RATIFICATION_STAGES, None)
    assert all(isinstance(k, str) for k in spec.qa_code_vocabulary)


def test_lookup_is_case_insensitive_and_unknown_codes_say_so():
    assert get_network_spec("aurn").code == "AURN"
    with pytest.raises(KeyError, match="NOPE"):
        get_network_spec("NOPE")


def test_every_registered_source_has_a_route_to_a_known_network():
    for source in aeolus.list_sources(include_all=True):
        network, backend = route_for(source)
        assert network in CODES, source
        assert backend


@pytest.mark.parametrize(
    "source, expected",
    [
        ("AURN", ("AURN", "RDATA")), ("AURN-SOS", ("AURN", "SOS")), ("LAQN-ERG", ("LAQN", "ERG_REST")),
        ("SAQD", ("SAQN", "RDATA")), ("BREATHE_LONDON", ("BREATHE_LONDON", "BREATHE_LONDON")),
        ("OPENAQ", ("OPENAQ", "OPENAQ")),
    ],
)
def test_routes(source, expected):
    assert route_for(source) == expected
    assert SOURCE_ROUTES[source] == expected
