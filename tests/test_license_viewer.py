from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QPushButton

from dg_fps.ui.i18n import localize, set_language
from dg_fps.ui.licenses import LicensesDialog


def test_license_search_empty_and_keyboard_close(qtbot, tmp_path):
    set_language("en")
    (tmp_path / "Terms.txt").write_text("AIDA terms", encoding="utf-8")
    folder = tmp_path / "third_party_licenses"
    folder.mkdir()
    (folder / "LGPL.txt").write_text("full license text", encoding="utf-8")
    dialog = LicensesDialog(documents=tmp_path)
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.search.y() < 100
    assert dialog.files.currentItem().text() == "Overview"
    assert "Open source under Apache-2.0" in dialog.text.toPlainText()
    dialog.files.setCurrentRow(1)
    assert dialog.text.toPlainText() == "AIDA terms"
    qtbot.keyClicks(dialog.search, "LGPL")
    assert dialog.text.toPlainText() == "full license text"
    dialog.search.setText("unavailable-component")
    assert dialog.text.toPlainText() == "No documents found."
    dialog.search.clear()
    assert not dialog.findChild(QListWidget).item(0).isHidden()
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert not dialog.isVisible()
    set_language("pt")


def test_aida_terms_follow_interface_language_and_preserve_complete_license(qtbot, tmp_path):
    folder = tmp_path / "third_party_licenses" / "aida"
    folder.mkdir(parents=True)
    (folder / "Terms.en.txt").write_text("English AIDA terms", encoding="utf-8")
    (folder / "Terms.pt.txt").write_text("Termos do AIDA em português", encoding="utf-8")
    (folder.parent / "LGPL.txt").write_text("COMPLETE LGPL NOTICE", encoding="utf-8")
    for language, expected in (("pt", "Termos do AIDA em português"),
                               ("en", "English AIDA terms")):
        set_language(language)
        dialog = LicensesDialog(documents=tmp_path)
        qtbot.addWidget(dialog)
        dialog.files.setCurrentRow(1)
        assert dialog.text.toPlainText() == expected
        dialog.search.setText("LGPL")
        assert dialog.text.toPlainText() == "COMPLETE LGPL NOTICE"
    set_language("pt")


def test_missing_distribution_documents_are_explained(qtbot, tmp_path):
    dialog = LicensesDialog(documents=tmp_path)
    qtbot.addWidget(dialog)
    assert dialog.text.toPlainText() == localize("Documentos de distribuição indisponíveis.")
    assert any(button.text() for button in dialog.findChildren(QPushButton))
