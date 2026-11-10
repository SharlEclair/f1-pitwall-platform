from ml.run import verdict


def test_verdict_reads_the_interval_not_the_mean():
    assert "beats" in verdict((-0.1, -0.2, -0.05), "A", "B")
    assert verdict((-0.1, -0.2, -0.05), "A", "B").startswith("A beats B")
    assert verdict((0.1, 0.05, 0.2), "A", "B").startswith("B beats A")
    assert verdict((-0.05, -0.2, 0.1), "A", "B").startswith("No detectable difference")
