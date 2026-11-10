from validate.catalogue import render
from validate.rules import REGISTRY


def test_catalogue_lists_every_rule_with_counts_from_the_run():
    summary = {
        "year": 2024, "sessions": 2, "elapsed_seconds": 1.5, "balanced": True,
        "rows": {e: {"raw": 10, "silver": 9, "quarantined": 1}
                 for e in ("laps", "stints", "pit", "drivers", "race_control", "weather",
                           "position", "intervals")},
        "rule_counts": {"DQ-PIT-001": 3},
        "rule_counts_by_session": {"7": {"DQ-PIT-001": 3}},
    }
    text = render(summary, {7: "Monza (Race)"})
    assert all(code in text for code in REGISTRY)
    assert "| DQ-PIT-001 | flag |" in text
    assert "| 3 | 10 pit stops | Monza (Race) 3 |" in text
    assert "All sessions balanced: True." in text


def test_combine_sums_seasons_and_keeps_every_session():
    from validate.catalogue import combine

    def season(year, fired):
        return {"year": year, "sessions": 1, "elapsed_seconds": 1.0, "balanced": True,
                "rows": {"laps": {"raw": 10, "silver": 9, "quarantined": 1}},
                "rule_counts": {"DQ-PIT-001": fired},
                "rule_counts_by_session": {str(year): {"DQ-PIT-001": fired}}}

    total = combine([season(2023, 2), season(2024, 3)])
    assert total["year"] == "2023 to 2024" and total["sessions"] == 2
    assert total["rows"]["laps"]["raw"] == 20
    assert total["rule_counts"] == {"DQ-PIT-001": 5}
    assert set(total["rule_counts_by_session"]) == {"2023", "2024"}
