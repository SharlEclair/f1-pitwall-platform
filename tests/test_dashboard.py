from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parent.parent / "dashboard" / "app.py")


def test_dashboard_renders_without_error_and_shows_all_tabs():
    app = AppTest.from_file(APP, default_timeout=60).run()
    assert not app.exception
    assert [t.label for t in app.tabs] == [
        "1. Tyre degradation", "2. Pit-stop cost", "3. Lap-time model", "4. Undercut",
        "Data quality", "Limits"]
    assert len(app.metric) >= 9  # slopes, pit loss, model difference, undercut


def test_compound_filter_changes_the_chart_without_error():
    app = AppTest.from_file(APP, default_timeout=60).run()
    app.multiselect[0].set_value(["SOFT"]).run()
    assert not app.exception


def test_season_filter_changes_the_views_without_error():
    app = AppTest.from_file(APP, default_timeout=60).run()
    app.radio[0].set_value("2025").run()
    assert not app.exception
