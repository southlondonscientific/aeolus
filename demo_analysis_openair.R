#!/usr/bin/env Rscript
# =============================================================================
# Aeolus v0.4.0 — openair comparison script
#
# Reads the same CSV data exported by demo_analysis.py and runs the
# corresponding openair functions, producing comparable outputs for
# side-by-side verification.
#
# Prerequisites:
#   install.packages(c("openair", "dplyr", "readr", "trend"))
#
# Usage:
#   python demo_analysis.py          # first: generates CSVs
#   Rscript demo_analysis_openair.R  # then: runs openair comparisons
# =============================================================================

library(openair)
library(dplyr)
library(readr)

OUTPUT_DIR <- "demo_analysis_output"

cat("=======================================================================\n")
cat("openair comparison for Aeolus v0.4.0 analysis functions\n")
cat("=======================================================================\n\n")

# =============================================================================
# Helper: load data exported by Python
# =============================================================================

load_data <- function(filename) {
    path <- file.path(OUTPUT_DIR, filename)
    if (!file.exists(path)) {
        cat(sprintf("  File not found: %s\n", path))
        cat("  Run 'python demo_analysis.py' first.\n")
        return(NULL)
    }
    df <- read_csv(path, show_col_types = FALSE)
    # openair expects a POSIXct column called 'date'
    df$date <- as.POSIXct(df$date, tz = "UTC")
    return(df)
}

# =============================================================================
# 1. timeAverage comparison
# =============================================================================

compare_time_average <- function(data, label) {
    cat(sprintf("\n--- timeAverage() on %s ---\n", label))

    # Daily mean (default)
    daily <- timeAverage(data, avg.time = "day", statistic = "mean",
                         data.thresh = 75)  # openair uses percentage
    cat(sprintf("  Daily mean: %d rows\n", nrow(daily)))

    # Print summary for NO2
    if ("NO2" %in% names(daily)) {
        cat(sprintf("  NO2 daily mean — mean: %.1f, sd: %.1f, min: %.1f, max: %.1f\n",
            mean(daily$NO2, na.rm = TRUE),
            sd(daily$NO2, na.rm = TRUE),
            min(daily$NO2, na.rm = TRUE),
            max(daily$NO2, na.rm = TRUE)))
    }

    # Monthly mean
    monthly <- timeAverage(data, avg.time = "month", statistic = "mean",
                           data.thresh = 75)
    cat(sprintf("  Monthly mean: %d rows\n", nrow(monthly)))

    if ("NO2" %in% names(monthly)) {
        cat(sprintf("  NO2 monthly mean — mean: %.1f, sd: %.1f\n",
            mean(monthly$NO2, na.rm = TRUE),
            sd(monthly$NO2, na.rm = TRUE)))
    }

    # Daily max
    daily_max <- timeAverage(data, avg.time = "day", statistic = "max",
                              data.thresh = 0)
    if ("NO2" %in% names(daily_max)) {
        cat(sprintf("  NO2 daily max — max of daily maxes: %.1f\n",
            max(daily_max$NO2, na.rm = TRUE)))
    }

    # Daily percentile
    daily_p95 <- timeAverage(data, avg.time = "day", statistic = "percentile",
                              percentile = 95, data.thresh = 0)
    if ("NO2" %in% names(daily_p95)) {
        cat(sprintf("  NO2 daily 95th percentile — mean: %.1f\n",
            mean(daily_p95$NO2, na.rm = TRUE)))
    }

    # Save for comparison
    write_csv(daily, file.path(OUTPUT_DIR, sprintf("daily_mean_%s_openair.csv", label)))
    write_csv(monthly, file.path(OUTPUT_DIR, sprintf("monthly_mean_%s_openair.csv", label)))
    cat(sprintf("  Saved: daily_mean_%s_openair.csv, monthly_mean_%s_openair.csv\n",
        label, label))
}


# =============================================================================
# 2. aq_stats comparison (manual, openair doesn't have a direct equivalent)
# =============================================================================

compare_aq_stats <- function(data, label) {
    cat(sprintf("\n--- aq_stats equivalent on %s ---\n", label))

    # openair does not have a single aq_stats() function, but we can
    # replicate the key statistics manually for comparison.

    data$year <- as.integer(format(data$date, "%Y"))
    years <- unique(data$year)

    results <- data.frame()

    for (pollutant in c("NO2", "PM2.5", "O3", "PM10")) {
        if (!(pollutant %in% names(data))) next

        for (yr in years) {
            yr_data <- data[data$year == yr, ]
            vals <- yr_data[[pollutant]]
            vals <- vals[!is.na(vals)]

            if (length(vals) == 0) next

            # Expected hours
            hours_in_year <- ifelse(
                as.integer(format(as.Date(paste0(yr, "-02-29")), "%m")) == 2,
                8784, 8760
            )
            data_capture <- length(vals) / hours_in_year

            # Basic stats
            annual_mean <- mean(vals)
            max_hourly <- max(vals)
            p95 <- quantile(vals, 0.95)
            p99 <- quantile(vals, 0.99)

            # Daily means (18/24 rule)
            daily <- timeAverage(yr_data[, c("date", pollutant)],
                                 avg.time = "day", statistic = "mean",
                                 data.thresh = 75)
            daily_vals <- daily[[pollutant]]
            daily_vals <- daily_vals[!is.na(daily_vals)]
            max_daily_mean <- if (length(daily_vals) > 0) max(daily_vals) else NA

            # 8-hour rolling mean
            # Use rollingMean from openair (this adds the column)
            rolled <- rollingMean(yr_data[, c("date", pollutant)],
                                   pollutant = pollutant,
                                   width = 8, new.name = "rolling8h",
                                   data.thresh = 75)
            max_8h_rolling <- max(rolled$rolling8h, na.rm = TRUE)
            if (is.infinite(max_8h_rolling)) max_8h_rolling <- NA

            # Exceedances
            exc_hours_200 <- if (pollutant == "NO2") sum(vals > 200) else NA
            exc_days_50 <- if (pollutant == "PM10") sum(daily_vals > 50) else NA
            exc_days_120 <- NA
            if (pollutant == "O3") {
                daily_max_8h <- timeAverage(
                    rolled[, c("date", "rolling8h")],
                    avg.time = "day", statistic = "max", data.thresh = 0
                )
                dm8h <- daily_max_8h$rolling8h
                dm8h <- dm8h[!is.na(dm8h)]
                exc_days_120 <- sum(dm8h > 120)
            }

            row <- data.frame(
                site = unique(data$site)[1],
                year = yr,
                pollutant = pollutant,
                data_capture = data_capture,
                annual_mean = annual_mean,
                max_hourly = max_hourly,
                max_daily_mean = max_daily_mean,
                max_8h_rolling_mean = max_8h_rolling,
                p95 = as.numeric(p95),
                p99 = as.numeric(p99),
                exceedance_hours_200 = exc_hours_200,
                exceedance_days_50 = exc_days_50,
                exceedance_days_120 = exc_days_120,
                stringsAsFactors = FALSE
            )
            results <- rbind(results, row)
        }
    }

    if (nrow(results) > 0) {
        for (i in seq_len(nrow(results))) {
            r <- results[i, ]
            cat(sprintf("\n  %s / %d / %s:\n", r$site, r$year, r$pollutant))
            cat(sprintf("    Data capture:       %.1f%%\n", r$data_capture * 100))
            cat(sprintf("    Annual mean:        %.1f\n", r$annual_mean))
            cat(sprintf("    Max hourly:         %.1f\n", r$max_hourly))
            cat(sprintf("    Max daily mean:     %.1f\n", r$max_daily_mean))
            cat(sprintf("    Max 8h rolling:     %.1f\n", r$max_8h_rolling_mean))
            cat(sprintf("    P95:                %.1f\n", r$p95))
            cat(sprintf("    P99:                %.1f\n", r$p99))
            if (!is.na(r$exceedance_hours_200))
                cat(sprintf("    Exceedance hrs>200:  %d\n", r$exceedance_hours_200))
            if (!is.na(r$exceedance_days_50))
                cat(sprintf("    Exceedance days>50:  %d\n", r$exceedance_days_50))
            if (!is.na(r$exceedance_days_120))
                cat(sprintf("    Exceedance days 8h>120: %d\n", r$exceedance_days_120))
        }
    }

    write_csv(results, file.path(OUTPUT_DIR, sprintf("aq_stats_%s_openair.csv", label)))
    cat(sprintf("  Saved: aq_stats_%s_openair.csv\n", label))
}


# =============================================================================
# 3. TheilSen trend comparison
# =============================================================================

compare_trend <- function(data, label) {
    cat(sprintf("\n--- TheilSen() on %s ---\n", label))

    for (pollutant in c("NO2", "O3")) {
        if (!(pollutant %in% names(data))) next

        tryCatch({
            # openair TheilSen — deseasonalised monthly trend
            # Note: TheilSen returns a plot object, stats are in $data$res2
            result <- TheilSen(data, pollutant = pollutant,
                               deseason = TRUE, avg.time = "month",
                               plot = FALSE, silent = TRUE)

            # Extract the trend statistics
            stats <- result$data$res2
            if (!is.null(stats) && nrow(stats) > 0) {
                s <- stats[1, ]
                cat(sprintf("  %s (deseason, monthly):\n", pollutant))
                cat(sprintf("    slope:    %+.3f/yr\n", s$slope))
                cat(sprintf("    CI:       [%.3f, %.3f]\n", s$lower, s$upper))
                cat(sprintf("    p-value:  %.4f\n", s$p))
            }

            # Without deseasonalisation
            result2 <- TheilSen(data, pollutant = pollutant,
                                deseason = FALSE, avg.time = "month",
                                plot = FALSE, silent = TRUE)
            stats2 <- result2$data$res2
            if (!is.null(stats2) && nrow(stats2) > 0) {
                s2 <- stats2[1, ]
                cat(sprintf("  %s (raw, monthly):\n", pollutant))
                cat(sprintf("    slope:    %+.3f/yr\n", s2$slope))
                cat(sprintf("    CI:       [%.3f, %.3f]\n", s2$lower, s2$upper))
                cat(sprintf("    p-value:  %.4f\n", s2$p))
            }

            # Yearly
            result3 <- TheilSen(data, pollutant = pollutant,
                                deseason = FALSE, avg.time = "year",
                                plot = FALSE, silent = TRUE)
            stats3 <- result3$data$res2
            if (!is.null(stats3) && nrow(stats3) > 0) {
                s3 <- stats3[1, ]
                cat(sprintf("  %s (raw, yearly):\n", pollutant))
                cat(sprintf("    slope:    %+.3f/yr\n", s3$slope))
                cat(sprintf("    p-value:  %.4f\n", s3$p))
            }
        }, error = function(e) {
            cat(sprintf("  %s trend failed: %s\n", pollutant, e$message))
        })
    }
}


# =============================================================================
# 4. timeVariation comparison (save plot)
# =============================================================================

compare_time_variation <- function(data, label) {
    cat(sprintf("\n--- timeVariation() on %s ---\n", label))

    for (pollutant in c("NO2", "O3")) {
        if (!(pollutant %in% names(data))) next

        tryCatch({
            fname <- file.path(OUTPUT_DIR,
                               sprintf("time_variation_%s_%s_openair.png", pollutant, label))
            png(fname, width = 10, height = 8, units = "in", res = 150)
            timeVariation(data, pollutant = pollutant, ci = TRUE,
                          main = sprintf("%s Time Variation (%s, openair)", pollutant, label))
            dev.off()
            cat(sprintf("  Saved: time_variation_%s_%s_openair.png\n", pollutant, label))
        }, error = function(e) {
            cat(sprintf("  %s timeVariation failed: %s\n", pollutant, e$message))
            try(dev.off(), silent = TRUE)
        })
    }
}


# =============================================================================
# 5. TheilSen plot comparison
# =============================================================================

compare_trend_plot <- function(data, label) {
    cat(sprintf("\n--- TheilSen plot on %s ---\n", label))

    for (pollutant in c("NO2", "O3")) {
        if (!(pollutant %in% names(data))) next

        tryCatch({
            fname <- file.path(OUTPUT_DIR,
                               sprintf("trend_%s_%s_openair.png", pollutant, label))
            png(fname, width = 10, height = 4, units = "in", res = 150)
            TheilSen(data, pollutant = pollutant,
                     deseason = FALSE, avg.time = "month",
                     main = sprintf("%s Trend (%s, openair)", pollutant, label))
            dev.off()
            cat(sprintf("  Saved: trend_%s_%s_openair.png\n", pollutant, label))
        }, error = function(e) {
            cat(sprintf("  %s TheilSen plot failed: %s\n", pollutant, e$message))
            try(dev.off(), silent = TRUE)
        })
    }
}


# =============================================================================
# Main
# =============================================================================

# --- Synthetic data ---
cat("\n[1/2] Loading synthetic data...\n")
synth <- load_data("synth_data_wide.csv")

if (!is.null(synth)) {
    cat(sprintf("  %d rows, columns: %s\n", nrow(synth), paste(names(synth), collapse=", ")))

    compare_time_average(synth, "synth")
    compare_aq_stats(synth, "synth")
    compare_trend(synth, "synth")
    compare_time_variation(synth, "synth")
    compare_trend_plot(synth, "synth")
}

# --- Real AURN data ---
cat("\n[2/2] Loading AURN data...\n")
aurn <- load_data("aurn_data_wide.csv")

if (!is.null(aurn)) {
    cat(sprintf("  %d rows, columns: %s\n", nrow(aurn), paste(names(aurn), collapse=", ")))

    compare_time_average(aurn, "aurn")
    compare_aq_stats(aurn, "aurn")
    compare_trend(aurn, "aurn")
    compare_time_variation(aurn, "aurn")
    compare_trend_plot(aurn, "aurn")
}

# --- Summary ---
cat("\n=======================================================================\n")
cat("Comparison complete. Output files in", OUTPUT_DIR, "\n")
cat("\nCompare side-by-side:\n")
cat("  - daily_mean_*_openair.csv vs daily_mean_*.csv\n")
cat("  - aq_stats_*_openair.csv  vs aq_stats_*.csv\n")
cat("  - time_variation_*_openair.png vs time_variation_*.png\n")
cat("  - trend_*_openair.png vs trend_*.png\n")
cat("=======================================================================\n")
