"""Process-wide switches. Set as attributes: ``aeolus.options.legacy_columns = False``."""

import os

# Keep the pre-0.5.0 mirror columns (`source_network`, `ratification`) on every
# frame. Turn off to prove a consumer has migrated: anything still reading a
# mirror then fails loudly. Removed, with the mirrors, in v1.0.
legacy_columns: bool = os.environ.get("AEOLUS_LEGACY_COLUMNS", "1").strip() not in ("0", "false", "False")
