from validate.catalogue import render
from validate.rules import REGISTRY


def test_catalogue_lists_every_rule_with_counts_from_the_run():
    summary = {
        "year": 2024, "sessions": 2, "elapsed_seconds": 1.5, "balanced": True,
        "rows": {e: {"raw": 10, "silver": 9, "quarantined": 1}
                 for e in ("laps", "stints", "pit", "drivers", "race_control", "weather")},
        "rule_counts": {"DQ-PIT-001": 3},
        "rule_counts_by_session": {"7": {"DQ-PIT-001": 3}},
    }
    text = render(summary, {7: "Monza (Race)"})
    assert all(code in text for code in REGISTRY)
    assert "| DQ-PIT-001 | flag |" in text
    assert "| 3 | 10 pit stops | Monza (Race) 3 |" in text
    assert "All sessions balanced: True." in text
