# Generate reference fixtures from R openair for aeolus validation.
#
# This script downloads a canonical AURN dataset, runs openair's time-average
# and annual-statistics functions, and saves the outputs as Parquet files in
# tests/fixtures/openair/. The Python test suite and validation Quarto doc
# read those fixtures to verify aeolus produces numerically identical output.
#
# You do NOT need to run this script to work on aeolus. The fixtures are
# checked into the repo. Regenerate only when:
#   - Pinning a new openair version
#   - Extending the comparison to more sites/metrics
#   - Investigating a numerical divergence
#
# Pinned versions (update intentionally, treat as a reviewed change):
#   openair  : 2.19.0
#   R        : 4.3+ (any recent)
#
# No extra R packages beyond openair. Fixtures are written as CSV, which
# preserves full double precision via stringification and ISO-8601 timestamps.
#
# Usage:
#   Rscript scripts/validation/generate_openair_fixtures.R

suppressPackageStartupMessages({
  library(openair)
})

# ---------------------------------------------------------------------------
# Configuration — the canonical comparison dataset
# ---------------------------------------------------------------------------
#
# We use Marylebone Road (MY1), a well-known AURN site with continuous data
# across all the standard regulatory pollutants. 2023 is recent, complete,
# and contains DST transitions in both directions.

SITE <- "my1"
YEAR <- 2023
# Run from repo root (getwd() should be the aeolus repo when launched via
# `Rscript scripts/validation/generate_openair_fixtures.R`)
OUT_DIR <- file.path(getwd(), "tests", "fixtures", "openair")
if (!dir.exists(dirname(OUT_DIR))) {
  stop(
    "Expected to be run from the aeolus repo root; getwd()=", getwd(),
    " does not contain tests/fixtures/"
  )
}
dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)

cat("Writing fixtures to:", OUT_DIR, "\n")
cat("Site:", SITE, " Year:", YEAR, "\n")
cat("openair version:", as.character(packageVersion("openair")), "\n\n")

# ---------------------------------------------------------------------------
# Raw input — shared between R and Python comparisons
# ---------------------------------------------------------------------------

cat("Downloading raw AURN data for", SITE, YEAR, "...\n")
raw <- importAURN(site = SITE, year = YEAR)

# openair returns a tibble with columns: date, site, code, <pollutants>
# Keep only pollutants aeolus supports canonically for the comparison
keep_cols <- c("date", "site", "code", "no2", "pm2.5", "pm10", "o3")
raw <- raw[, intersect(keep_cols, colnames(raw))]

cat("  Rows:", nrow(raw), "  Cols:", ncol(raw), "\n")

# Write raw input as CSV with ISO-8601 timestamps (pandas reads these natively)
write_iso_csv <- function(df, path) {
  df_out <- df
  if ("date" %in% colnames(df_out)) {
    # Force UTC string so timezone round-trips cleanly to Python
    df_out$date <- format(df_out$date, "%Y-%m-%dT%H:%M:%S+00:00", tz = "UTC")
  }
  write.csv(df_out, path, row.names = FALSE, na = "")
}

write_iso_csv(raw, file.path(OUT_DIR, "aurn_my1_2023_raw.csv"))

# ---------------------------------------------------------------------------
# Reference output 1: daily mean with 75% data capture
# ---------------------------------------------------------------------------

cat("\nComputing daily mean (data.thresh=75) ...\n")
daily <- timeAverage(raw, avg.time = "day", data.thresh = 75)
cat("  Rows:", nrow(daily), "\n")
write_iso_csv(daily, file.path(OUT_DIR, "aurn_my1_2023_daily_mean_thresh75.csv"))

# ---------------------------------------------------------------------------
# Provenance — pin what produced these outputs
# ---------------------------------------------------------------------------

provenance <- data.frame(
  site = SITE,
  year = YEAR,
  openair_version = as.character(packageVersion("openair")),
  r_version = R.version.string,
  generated_at = format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"),
  stringsAsFactors = FALSE
)
write.csv(provenance, file.path(OUT_DIR, "provenance.csv"), row.names = FALSE)

cat("\nDone. Fixtures:\n")
for (f in list.files(OUT_DIR, full.names = FALSE)) {
  cat("  ", f, "\n")
}
