from validate.report import format_summary


def summary(balanced=True, quarantined=2):
    return {
        "year": 2024, "sessions": 30, "elapsed_seconds": 3.5, "balanced": balanced,
        "rows": {"laps": {"raw": 10, "silver": 10 - quarantined, "quarantined": quarantined}},
        "rule_counts": {"DQ-LAP-005": 2}, "unbalanced_sessions": [],
    }


def test_ok_subject_and_rule_lines():
    subject, body = format_summary(summary())
    assert "OK" in subject and "30 sessions" in subject and "2 rows quarantined" in subject
    assert "DQ-LAP-005: 2" in body


def test_stale_sessions_or_imbalance_raise_attention():
    assert "ATTENTION" in format_summary(summary(), [9001])[0]
    assert "ATTENTION" in format_summary(summary(balanced=False))[0]
