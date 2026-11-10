from datetime import UTC, datetime

import pytest
from conftest import baseline_session, expand_case, load_golden, row

from validate.checks import freshness_warnings, validate_session
from validate.rules import REGISTRY
from validate.track_status import lap_statuses

GOLDEN = load_golden()
CASES = [(code, kind, i, case) for code, g in GOLDEN.items()
         for kind in ("bad", "good") for i, case in enumerate(g[kind])]


def test_baseline_session_fires_no_rules_and_reconciles():
    result = validate_session(1, baseline_session())
    assert result.rule_counts == {}
    assert result.quarantine.height == 0
    assert result.balanced


def test_every_rule_has_golden_cases_except_freshness():
    assert set(REGISTRY) - set(GOLDEN) == {"DQ-FRESH-001"}
    assert set(GOLDEN) <= set(REGISTRY)


@pytest.mark.parametrize(("code", "kind", "i", "case"), CASES,
                         ids=[f"{c}-{k}{i}" for c, k, i, _ in CASES])
def test_golden_case(code, kind, i, case):
    result = validate_session(1, expand_case(case))
    if kind == "bad":
        assert code in result.rule_counts
    else:
        assert code not in result.rule_counts
    assert result.balanced


def test_rejected_row_is_quarantined_with_code_and_pointer_not_in_silver():
    session = expand_case({"stints": [{"compound": "MEDIUMM"}]})
    result = validate_session(1, session, {"stints": "raw/season=2024/session_key=1/stints.json"})
    q = result.quarantine
    assert q.height == 1
    assert q["rule_code"][0] == "DQ-STINT-003"
    assert q["source_key"][0].endswith("stints.json")
    assert result.silver["stints"].height == 0


def test_flagged_row_stays_in_silver_with_its_code():
    session = expand_case({"pit": [{"pit_duration": 2390.0}]})
    result = validate_session(1, session)
    assert result.silver["pit"].height == 1
    assert result.silver["pit"]["dq_flags"][0].to_list() == ["DQ-PIT-001"]
    assert result.quarantine.height == 0


def test_lap_silver_gets_track_status_and_in_lap():
    session = expand_case({
        "laps": [{"lap_number": 1}, {"lap_number": 2}, {"lap_number": 3}],
        "race_control": [{"category": "SafetyCar", "flag": None,
                          "date": "2024-01-01T10:03:10+00:00", "message": "SAFETY CAR DEPLOYED"}],
    })
    laps = validate_session(1, session).silver["laps"].sort("lap_number")
    assert laps["track_status"].to_list() == ["GREEN", "GREEN", "SC"]
    assert laps["is_in_lap"].to_list() == [False, True, False]


def rc(at, message, category="SafetyCar", flag=None):
    return row("race_control", date=at, message=message, category=category, flag=flag)


def six_laps():
    return [row("laps", lap_number=n) for n in range(1, 7)]  # lap n starts 10:00:00 + 90 s * (n-1)


def test_vsc_window_covers_laps_overlapping_deploy_to_ending():
    rows = [rc("2024-01-01T10:00:10+00:00", "VIRTUAL SAFETY CAR DEPLOYED"),
            rc("2024-01-01T10:02:00+00:00", "VIRTUAL SAFETY CAR ENDING")]
    assert lap_statuses(rows, six_laps()) == {(1, 1): "VSC", (1, 2): "VSC"}


def test_window_is_matched_by_time_so_lapped_cars_are_judged_correctly():
    rows = [rc("2024-01-01T10:03:10+00:00", "VIRTUAL SAFETY CAR DEPLOYED"),
            rc("2024-01-01T10:03:50+00:00", "VIRTUAL SAFETY CAR ENDING")]
    lapped = row("laps", driver_number=2, lap_number=2, date_start="2024-01-01T10:03:05+00:00")
    status = lap_statuses(rows, six_laps() + [lapped])
    assert status == {(1, 3): "VSC", (2, 2): "VSC"}


def test_sc_beats_vsc_when_they_overlap():
    rows = [rc("2024-01-01T10:00:10+00:00", "VIRTUAL SAFETY CAR DEPLOYED"),
            rc("2024-01-01T10:00:20+00:00", "SAFETY CAR DEPLOYED"),
            rc("2024-01-01T10:01:00+00:00", "VIRTUAL SAFETY CAR ENDING"),
            rc("2024-01-01T10:02:00+00:00", "SAFETY CAR IN THIS LAP")]
    # SC ends one typical lap (90 s) after its IN THIS LAP message, so lap 3 is still SC
    assert lap_statuses(rows, six_laps()) == {(1, 1): "SC", (1, 2): "SC", (1, 3): "SC"}


def test_red_flag_closes_open_sc_and_second_sc_is_not_lost():
    rows = [rc("2024-01-01T10:01:40+00:00", "SAFETY CAR DEPLOYED"),
            rc("2024-01-01T10:03:10+00:00", "RED FLAG", category="Flag", flag="RED"),
            rc("2024-01-01T10:05:50+00:00", "SESSION STARTED", category="SessionStatus"),
            rc("2024-01-01T10:07:40+00:00", "SAFETY CAR DEPLOYED")]
    assert lap_statuses(rows, six_laps()) == {
        (1, 2): "SC", (1, 3): "RED", (1, 4): "RED", (1, 5): "RED", (1, 6): "SC"}


def test_race_start_session_started_does_not_open_or_close_anything():
    rows = [rc("2024-01-01T10:00:00+00:00", "SESSION STARTED", category="SessionStatus")]
    assert lap_statuses(rows, six_laps()) == {}


def test_freshness_flags_only_old_unfinished_ingests():
    now = datetime(2026, 11, 10, tzinfo=UTC)

    def s(key, end, name="Race"):
        return {"session_key": key, "session_name": name, "date_end": end, "is_cancelled": False}

    sessions = [s(1, "2026-11-01T15:00:00+00:00"), s(2, "2026-11-01T15:00:00+00:00"),
                s(3, "2026-11-09T15:00:00+00:00"), s(4, "2026-11-01T15:00:00+00:00", "Qualifying")]
    assert freshness_warnings(sessions, {2}, now, hours=48) == [1]
