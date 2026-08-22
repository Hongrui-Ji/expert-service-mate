from streamlit.testing.v1 import AppTest


def test_streamlit_app_renders_without_exception(monkeypatch, tmp_path):
    monkeypatch.setenv("SCHEDULER_CONFIG_PATH", str(tmp_path / "config.json"))
    app = AppTest.from_file("auto_scheduler/app.py", default_timeout=20)

    app.run()

    assert not app.exception
    assert any(title.value == "智能排班生成器" for title in app.title) or any(
        "智能排班生成器" in markdown.value for markdown in app.markdown
    )
