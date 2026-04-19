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
# Single year for time-average comparisons (fast, representative coverage).
YEAR <- 2023
# Multi-year range for trend analyses — TheilSen needs several years to be
# meaningful. Kept separate so single-year comparisons stay fast.
TREND_YEARS <- 2020:2023
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

cat("\nComputing weekly mean (data.thresh=75) ...\n")
weekly <- timeAverage(raw, avg.time = "week", data.thresh = 75)
cat("  Rows:", nrow(weekly), "\n")
write_iso_csv(weekly, file.path(OUT_DIR, "aurn_my1_2023_weekly_mean_thresh75.csv"))

cat("\nComputing monthly mean (data.thresh=75) ...\n")
monthly <- timeAverage(raw, avg.time = "month", data.thresh = 75)
cat("  Rows:", nrow(monthly), "\n")
write_iso_csv(monthly, file.path(OUT_DIR, "aurn_my1_2023_monthly_mean_thresh75.csv"))

cat("\nComputing monthly p95 (data.thresh=75) ...\n")
# openair's timeAverage supports statistic="percentile" with `percentile=`.
# Catches quantile-interpolation-method divergences (R default type=7 vs
# numpy/pandas 'linear' — they should match but worth pinning).
monthly_p95 <- timeAverage(raw, avg.time = "month", data.thresh = 75,
                           statistic = "percentile", percentile = 95)
cat("  Rows:", nrow(monthly_p95), "\n")
write_iso_csv(monthly_p95, file.path(OUT_DIR, "aurn_my1_2023_monthly_p95_thresh75.csv"))

# ---------------------------------------------------------------------------
# Multi-year dataset for trend analyses
# ---------------------------------------------------------------------------

cat("\nDownloading multi-year AURN data (", min(TREND_YEARS), "-", max(TREND_YEARS), ") ...\n", sep = "")
trend_raw <- importAURN(site = SITE, year = TREND_YEARS)
trend_raw <- trend_raw[, intersect(keep_cols, colnames(trend_raw))]
cat("  Rows:", nrow(trend_raw), "\n")
write_iso_csv(trend_raw, file.path(OUT_DIR, "aurn_my1_2020_2023_raw.csv"))

# ---------------------------------------------------------------------------
# Reference output 4: Theil-Sen trend per pollutant
# ---------------------------------------------------------------------------
#
# openair::TheilSen computes the Theil-Sen slope with Mann-Kendall p-value
# and bootstrap confidence intervals. aeolus uses scipy.stats.theilslopes
# which returns analytical (not bootstrap) CIs, so:
#   - slope and p-value should match exactly
#   - CI bounds will differ by the CI estimation method
# We record both and let the Python side assert parity only on slope + p.

cat("\nComputing Theil-Sen trends (deseason=FALSE, avg.time='month') ...\n")
pdf(NULL)  # suppress the plot device

trend_rows <- list()
for (poll in c("no2", "pm2.5", "pm10", "o3")) {
  if (!(poll %in% colnames(trend_raw))) next
  # openair's TheilSen needs a deterministic seed for reproducible bootstrap CIs.
  # data.thresh=75 matches aeolus's default (and LAQM guidance); without it,
  # openair defaults to 0 which admits under-covered months into the regression.
  set.seed(42)
  ts <- TheilSen(
    trend_raw, pollutant = poll, deseason = FALSE,
    avg.time = "month", data.thresh = 75
  )
  # res2 can have a trailing NaN row for some pollutants (an openair internal
  # artefact). Take the first row which holds the real values.
  res <- ts$data$res2[1, ]
  trend_rows[[length(trend_rows) + 1]] <- data.frame(
    pollutant = poll,  # canonicalised below
    slope = res$slope,
    slope_lower = res$lower,
    slope_upper = res$upper,
    intercept = res$intercept,
    p_value = res$p,
    slope_percent = res$slope.percent,
    stringsAsFactors = FALSE
  )
  cat("  ", poll, ": slope=", sprintf("%.6g", res$slope),
      " p=", sprintf("%.4g", res$p), "\n", sep = "")
}
dev.off()

trend_df <- do.call(rbind, trend_rows)
# Canonicalise pollutant names to match aeolus
trend_df$pollutant <- c("no2" = "NO2", "pm2.5" = "PM2.5", "pm10" = "PM10", "o3" = "O3")[
  tolower(trend_df$pollutant)
]
write.csv(trend_df, file.path(OUT_DIR, "aurn_my1_2020_2023_trend_theilsen.csv"), row.names = FALSE)

# ---------------------------------------------------------------------------
# Reference output 5: timeVariation decomposition
# ---------------------------------------------------------------------------
#
# openair::timeVariation returns four aggregation tables: hour (0-23),
# day (wkday Mon=1..Sun=7 by default in openair's numeric coding),
# month (1-12), and day.hour (24 × 7 heatmap).
#
# Each table carries Mean, Lower, Upper, CI level. aeolus computes the same
# means internally in plot_diurnal / plot_weekly / plot_monthly (see
# viz/plots.py) — we extract the means here and assert parity.

cat("\nComputing timeVariation (NO2) ...\n")
pdf(NULL)
tv <- timeVariation(raw, pollutant = "no2")
dev.off()

# Extract the four panels, keeping only the aggregation columns
hour_df <- as.data.frame(tv$data$hour[, c("hour", "Mean", "Lower", "Upper")])
day_df  <- as.data.frame(tv$data$day[, c("wkday", "Mean", "Lower", "Upper")])
month_df <- as.data.frame(tv$data$month[, c("mnth", "Mean", "Lower", "Upper")])
cat("  hour rows:", nrow(hour_df), "  day rows:", nrow(day_df),
    "  month rows:", nrow(month_df), "\n")

write.csv(hour_df, file.path(OUT_DIR, "aurn_my1_2023_timevariation_hour.csv"), row.names = FALSE)
write.csv(day_df, file.path(OUT_DIR, "aurn_my1_2023_timevariation_day.csv"), row.names = FALSE)
write.csv(month_df, file.path(OUT_DIR, "aurn_my1_2023_timevariation_month.csv"), row.names = FALSE)

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
