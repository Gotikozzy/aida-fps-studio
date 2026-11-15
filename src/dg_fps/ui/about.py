from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QPushButton, QVBoxLayout, QWidget

from dg_fps import __version__
from dg_fps.ui.i18n import localize
from dg_fps.updates import AIDA_URL, SITE_URL, UpdateCheck, UpdateRelease, version_key


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(localize("Sobre AIDA FPS Studio"))
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        title = localize("Análise de FPS e cadência visual • versão {version}").format(
            version=__version__
        )
        layout.addWidget(QLabel(title))
        for label in (
            f'{localize("Autor")}: <a href="{SITE_URL}">detonandogueek.com.br</a>',
            f'<a href="{AIDA_URL}">{localize("Ajuda e downloads do AIDA")}</a>',
        ):
            link = QLabel(label)
            link.setTextFormat(Qt.TextFormat.RichText)
            link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            link.setOpenExternalLinks(True)
            layout.addWidget(link)

        self._status = QLabel()
        self._status.setTextFormat(Qt.TextFormat.PlainText)
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        self._available_release = None
        self._install_button = QPushButton(localize("Baixar e atualizar"))
        self._install_button.hide()
        self._install_button.clicked.connect(self._install)
        layout.addWidget(self._install_button)
        license_button = QPushButton(localize("Termos e licenças"))
        license_button.clicked.connect(self._licenses)
        layout.addWidget(license_button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._check_button = QPushButton(localize("Verificar atualizações"))
        buttons.addButton(self._check_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._checker = UpdateCheck(self)
        self._check_button.clicked.connect(self._check)
        self._checker.succeeded.connect(self._checked)
        self._checker.failed.connect(self._check_failed)

    def _licenses(self):
        from dg_fps.ui.licenses import LicensesDialog

        LicensesDialog(self).open()

    def _check(self) -> None:
        self._check_button.setEnabled(False)
        self._status.setText(localize("Consultando o servidor de atualizações…"))
        self._checker.start()

    def _checked(self, latest: str) -> None:
        if version_key(latest) > version_key(__version__):
            self._available_release = self._checker.release or UpdateRelease(latest)
            self._install_button.show()
            status = localize("Versão {version} disponível na página do AIDA.").format(
                version=latest
            )
        else:
            self._install_button.hide()
            status = localize("Nenhuma atualização disponível.")
        self._show_result(status)

    def _install(self) -> None:
        parent = self.parentWidget()
        if self._available_release is not None and hasattr(parent, "_offer_update"):
            parent._offer_update(self._available_release)
            self.close()

    def _check_failed(self, reason: str) -> None:
        messages = {
            "unpublished": "A consulta de atualizações ainda não está disponível no servidor.",
            "invalid": "O servidor retornou uma informação de versão inválida.",
            "unreachable": "Não foi possível consultar atualizações. Tente novamente mais tarde.",
        }
        self._show_result(localize(messages[reason]))

    def _show_result(self, message: str) -> None:
        self._status.setText(message)
        self._check_button.setEnabled(True)
