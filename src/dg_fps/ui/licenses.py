"""Read-only access to the installed distribution documents."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
)

from dg_fps.ui import i18n
from dg_fps.ui.i18n import localize


def distribution_documents() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3] / "installer" / "public"


class LicensesDialog(QDialog):
    def __init__(self, parent=None, documents: Path | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(localize("Termos e licenças"))
        self.resize(900, 620)
        root = documents or distribution_documents()
        layout = QVBoxLayout(self)
        explanation = QLabel(localize(
            "Os componentes de terceiros seguem suas próprias licenças. "
            "Os termos do AIDA não limitam os direitos concedidos por elas."
        ))
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(localize("Buscar documento ou componente…"))
        self.search.setAccessibleName(localize("Buscar licença"))
        row.addWidget(self.search)
        layout.addLayout(row)
        self.files = QListWidget()
        self.files.setAccessibleName(localize("Documentos de distribuição"))
        self.text = QTextBrowser()
        self.text.setOpenExternalLinks(False)
        self.text.setAccessibleName(localize("Texto da licença"))
        split = QSplitter()
        split.addWidget(self.files)
        split.addWidget(self.text)
        split.setSizes([280, 620])
        layout.addWidget(split, 1)
        self.documents = {}
        translated = root / "third_party_licenses" / "aida" / f"Terms.{i18n.LANGUAGE}.txt"
        paths = [translated if translated.is_file() else root / "Terms.txt",
                 root / "LICENSE.txt", root / "THIRD_PARTY_NOTICES.md"]
        paths.extend(p for p in sorted((root / "third_party_licenses").rglob("*"))
                     if p.parent.name != "aida")
        for path in paths:
            if path.is_file() and path.suffix.lower() in {".txt", ".md", ".rst", ""}:
                if path == paths[0]:
                    name = localize("Termos do AIDA")
                elif path.name == "LICENSE.txt" and path.parent == root:
                    name = localize("Licença do AIDA")
                elif path.name == "THIRD_PARTY_NOTICES.md" and path.parent == root:
                    name = localize("Componentes de terceiros")
                else:
                    name = path.relative_to(root / "third_party_licenses").as_posix()
                self.documents[name] = path
                self.files.addItem(name)
        self.files.currentTextChanged.connect(self._show_document)
        self.search.textChanged.connect(self._filter)
        if self.documents:
            self.files.insertItem(0, localize("Visão geral"))
            self.files.setCurrentRow(0)
        if not self.documents:
            self.text.setPlainText(localize("Documentos de distribuição indisponíveis."))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _show_document(self, name: str) -> None:
        if name == localize("Visão geral"):
            self.text.setHtml(
                "<h2>AIDA FPS Studio</h2><p>" + localize(
                    "Código aberto sob Apache-2.0. Você pode usar o AIDA "
                    "para análises pessoais ou comerciais. Seus vídeos e projetos continuam seus."
                ) + "</p><h3>" + localize("Termos do AIDA") + "</h3><p>" + localize(
                    "Selecione um documento na lista para ler os termos completos. "
                    "A busca localiza documentos e componentes."
                ) + "</p><h3>" + localize("Componentes de terceiros") + "</h3><p>" + localize(
                    "O AIDA utiliza Qt/PySide/Shiboken e FFmpeg sob LGPL, além de outros "
                    "componentes com licenças próprias. Os textos completos, avisos, fontes "
                    "e instruções de substituição acompanham a instalação. "
                    "Os termos do AIDA não restringem esses direitos."
                ) + "</p>"
            )
            return
        path = self.documents.get(name)
        if path is None:
            self.text.clear()
            return
        try:
            self.text.setPlainText(path.read_text("utf-8-sig", errors="replace"))
        except OSError:
            self.text.setPlainText(localize("Não foi possível abrir este documento."))

    def _filter(self, text: str) -> None:
        first = None
        for i in range(self.files.count()):
            item = self.files.item(i)
            item.setHidden(text.casefold() not in item.text().casefold())
            if not item.isHidden() and first is None:
                first = item
        self.files.setCurrentItem(first)
        if first is None:
            self.text.setPlainText(localize("Nenhum documento encontrado."))
