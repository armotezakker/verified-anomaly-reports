"""A deliberately simple anomaly detector.

This project is about generating trustworthy incident reports and verifying
them against data, not about state of the art anomaly detection. The
detector here is a rolling, time-based IQR (interquartile range) fence.

Why IQR over a rolling z-score: streamflow is heavily right-skewed (floods
push values far above baseline, rarely far below it) and a flood inside the
trailing window inflates the window's own mean and standard deviation,
which can mask the flood it is supposed to flag (the window "learns" the
flood as normal while it is still happening). The median and IQR are far
less sensitive to a handful of extreme points, so the baseline stays
representative of ordinary conditions even while an event is in progress.

Why a time-based window rather than a fixed row count: several of the
pulled series mix 5-minute and 15-minute sampling within the same year.
A row-count window would cover less real time during 5-minute stretches
and more during 15-minute stretches, so the same number of rows would mean
different amounts of history depending on which sampling rate happened to
be active. A time-based window (a trailing N-day span) always covers the
same wall-clock history regardless of local sampling density, so it does
not manufacture anomalies purely from a change in sampling rate.

Streamflow lower bound is floored at zero. A pure IQR fence has no
physical floor and, during a low-variance calm stretch, can compute a
lower bound below zero for a quantity that cannot physically be negative
in the ordinary case. This is applied only to streamflow (parameter
00060), not temperature, since water temperature near freezing can
legitimately read a hair below zero on some sensors. The floor can only
raise a lower bound that would otherwise be negative, so it can only add
flags, never remove one: it is a fix, not a retuning of the detector's
sensitivity.
"""

from dataclasses import dataclass

import pandas as pd

WINDOW = "14D"
MIN_PERIODS = 200
K = 3.0


@dataclass
class DetectorConfig:
    window: str = WINDOW
    min_periods: int = MIN_PERIODS
    k: float = K


def detect(series: pd.Series, config: DetectorConfig = DetectorConfig(), floor: float | None = None) -> pd.DataFrame:
    """series: a pandas Series of values indexed by UTC datetime, sorted, one
    station-parameter series with any duplicate-sensor issue already
    resolved and no other preprocessing.

    floor: if given, the lower bound is clipped to never go below this
    value (see module docstring). Pass 0.0 for streamflow, None for
    temperature.

    Returns a DataFrame indexed like `series` with the rolling baseline and
    a `is_anomaly` boolean column. The baseline for a given timestamp is
    computed only from points strictly before it, so a point never
    influences its own threshold.
    """
    s = series.sort_index()

    shifted = s.shift(1)
    roll = shifted.rolling(config.window, min_periods=config.min_periods)
    median = roll.median()
    q1 = roll.quantile(0.25)
    q3 = roll.quantile(0.75)
    iqr = q3 - q1

    lower = median - config.k * iqr
    if floor is not None:
        lower = lower.clip(lower=floor)
    upper = median + config.k * iqr

    out = pd.DataFrame(
        {
            "value": s,
            "baseline_median": median,
            "baseline_low": lower,
            "baseline_high": upper,
        }
    )
    out["has_baseline"] = median.notna()
    out["is_anomaly"] = out["has_baseline"] & ((s < lower) | (s > upper))
    return out
