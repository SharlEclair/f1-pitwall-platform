import polars as pl

from undercut.report import bootstrap_rate, primary_attempts


def events():
    rows = [
        # session, gap, response, same/prev lap, neutralised, outcome
        (1, 1.0, 1, False, False, "success"),
        (1, 2.0, 2, False, False, "failure"),
        (2, 3.5, 1, False, False, "success"),  # gap too large for a 3 s threshold
        (2, 1.0, 5, False, False, "success"),  # response too late for a 3-lap window
        (3, 1.0, 1, True, False, "success"),  # B stopped on the same or previous lap
        (3, 1.0, 2, False, True, "failure"),  # neutralised
        (3, None, 1, False, False, "success"),  # unknown gap
    ]
    return pl.DataFrame(rows, schema=["session_key", "gap_s", "response_laps",
                                      "b_stopped_same_or_previous_lap", "neutralised_in_window",
                                      "outcome"], orient="row")


def test_primary_attempts_apply_every_filter_and_never_impute_a_gap():
    kept = primary_attempts(events(), 3.0, 3, True)
    assert kept["session_key"].to_list() == [1, 1]
    assert primary_attempts(events(), 3.0, 3, False).height == 3


def test_bootstrap_is_deterministic_and_resamples_races():
    attempts = primary_attempts(events(), 3.0, 3, True)
    first = bootstrap_rate(attempts)
    assert first == bootstrap_rate(attempts)
    rate, low, high, races = first
    assert rate == 0.5 and races == 1 and low <= rate <= high
