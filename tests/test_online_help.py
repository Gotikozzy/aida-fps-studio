import pytest
from PySide6.QtGui import QDesktopServices

from dg_fps.ui.main_window import FPSWindow


@pytest.mark.parametrize("language", ["pt", "en", "system"])
def test_help_action_opens_official_wiki_in_user_language(qtbot, tmp_path, monkeypatch, language):
    urls = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: urls.append(url.toString()))
    monkeypatch.setattr("dg_fps.ui.studio_actions.system_language", lambda: "en")
    window = FPSWindow(tmp_path / "data", tmp_path / "cache", language=language)
    qtbot.addWidget(window)
    action = next(a for a in window._menu_actions if a.shortcut().toString() == "F1")
    action.trigger()
    expected = "en" if language == "system" else language
    assert urls == [f"https://detonandogueek.com.br/aida/ajuda?lang={expected}"]
    window.close()
