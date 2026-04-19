# Validation

Evidence that aeolus produces numerically correct output, cross-checked
against authoritative reference implementations. Each document here is
gated by a pytest in the main test suite — if a comparison ever stops
matching, the test fails and this document stops rendering.

## Documents

- **`openair-parity.qmd`** — aeolus metrics vs R openair on a canonical
  AURN dataset (Marylebone Road, 2023). Built with Quarto; renders to
  HTML showing side-by-side comparison tables and overlay plots.

  Backed by [`tests/test_openair_parity.py`](../../tests/test_openair_parity.py)
  which runs on every PR.

## Regenerating reference data

Reference outputs live in `tests/fixtures/openair/` and are checked into
the repo. You don't need R installed to run the aeolus test suite — the
fixtures are read directly.

To regenerate (e.g. after pinning a new openair version):

```bash
# From the aeolus repo root
Rscript scripts/validation/generate_openair_fixtures.R
```

Pinned versions live in the script header. Treat version bumps as
intentional, reviewed changes — a fixture diff in a PR is a useful
signal that openair's behaviour shifted.

## Rendering the Quarto docs

Quarto is only needed for building the HTML validation reports — not for
running any tests. Install from <https://quarto.org>, then:

```bash
quarto render docs/validation/openair-parity.qmd
```

The rendered HTML is self-contained (`embed-resources: true`) and can be
viewed in any browser without a web server.
