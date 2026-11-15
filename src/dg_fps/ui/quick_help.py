"""A short, offline guide available even when the website cannot be reached."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from dg_fps.ui.i18n import localize


class QuickHelp(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(localize("Guia rápido"))
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        for title, text in (
            (
                "1. Abra o vídeo",
                "Use a captura original. A prévia pode ser reduzida sem alterar a análise.",
            ),
            (
                "2. Selecione os trechos",
                (
        "Arraste na timeline ou use I para o início e O para o fim. Delete apaga "
        "o trecho selecionado."
        ),
            ),
            (
                "3. Confira a meta",
                (
        "A meta serve de referência. Ela não pode superar a taxa que a captura "
        "permite observar."
        ),
            ),
            (
                "4. Analise ou exporte",
                (
        "Você pode analisar no Studio ou ir direto à exportação. Escolha vídeo, "
        "relatório para IA ou ambos."
        ),
            ),
            (
                "5. Salve seu projeto",
                (
        "O arquivo .aida guarda os trechos, resultados e opções. Mantenha o vídeo"
        " original disponível para reabrir o projeto."
        ),
            ),
        ):
            heading = QLabel(localize(title))
            heading.setStyleSheet("font-weight: 600; margin-top: 12px;")
            label = QLabel(localize(text))
            label.setWordWrap(True)
            layout.addWidget(heading)
            layout.addWidget(label)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
