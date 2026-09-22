# aeolus.schema, aeolus.qa, aeolus.network_registry

The v0.5.0 contract: the public column set, the QA enums, and the registry that maps each network's own quality tokens onto them.

## Schema

::: aeolus.schema
    options:
      members: [DATA_COLUMNS, METADATA_COLUMNS, public_data_columns, finalise_data_frame, finalise_metadata_frame]
      show_if_no_docstring: true
      show_root_heading: false

## QA enums and derivation

::: aeolus.qa
    options:
      members: [QA_TIERS, RATIFICATION_STAGES, QA_MODELS, INSTRUMENT_CLASSES, derive_qa, legacy_ratification]
      show_if_no_docstring: true
      show_root_heading: false

## Network registry

Each network's identity, QA vocabulary, when its data gets ratified, and its licence live in `src/aeolus/data/qa_vocabularies/<CODE>.yaml` and are read through this module.

::: aeolus.network_registry
    options:
      members: [NetworkSpec, SOURCE_ROUTES, get_network_spec, list_network_specs, route_for, spec_for_source]
      show_if_no_docstring: true
      show_root_heading: false

## Units and cache

::: aeolus.units
    options:
      show_root_heading: false

::: aeolus.cache
    options:
      members: [enable_cache, disable_cache, clear_cache, cache_info, is_enabled]
      show_root_heading: false
