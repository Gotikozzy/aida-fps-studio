from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from dg_fps.ui.i18n import localize
from dg_fps.ui.icons import action_icon

_ASSETS = Path(__file__).resolve().parents[1] / "assets"
CHANNEL_URL = "https://www.youtube.com/@DetonandoGueek"


@dataclass(frozen=True, slots=True)
class _Tip:
    title: str
    hint: str
    detail: str
    image: str
    caption: str


_TIPS = (
    _Tip(
        "Qualidade além da resolução",
        "Gravar · Preserve os detalhes",
        "Uma gravação 1080p bem codificada pode preservar mais detalhes em movimento "
        "que uma 4K muito comprimida. O bitrate, o codec e a cena influenciam o resultado.",
        "tip-quality.jpg",
        "Mesmo recorte · 1080p a 12 Mb/s à esquerda · 4K a 2 Mb/s à direita",
    ),
    _Tip(
        "Grave direto do console",
        "Gravar · Use o arquivo original",
        "Use a gravação original do Xbox Series S, Series X, PS5 ou PS5 Pro. Para organizar "
        "a sessão, prefira clipes de até 15 a 20 minutos, conforme as opções do seu console.",
        "tip-console.jpg",
        "Exemplo de gameplay usada em uma análise do AIDA",
    ),
    _Tip(
        "Um minuto bem escolhido",
        "Analisar · Foque nas cenas importantes",
        "Um minuto de uma cena importante pode valer mais que uma hora de gameplay. "
        "Separe combate, travessia e movimentos de câmera em trechos para analisar cada situação.",
        "tip-segments.png",
        "Trechos nomeados na timeline do AIDA",
    ),
    _Tip(
        "Escolha a taxa pela meta",
        "Gravar · Escolha a captura certa",
        "Uma captura a 60 FPS pode registrar um jogo a 30 FPS, com quadros repetidos "
        "esperados. A meta de 120 FPS fica disponível em capturas acima de 118 FPS, "
        "incluindo as gravações a 119.88 FPS. Para a meta de 40 FPS, use captura acima de 58 FPS.",
        "tip-capture-rate.png",
        "Exemplo testado · medição limitada à captura original",
    ),
    _Tip(
        "Aprenda a ler o pontilhado",
        "Entender · Leia o resultado",
        "No gráfico exportado, a linha sólida acompanha a medição. O pontilhado mantém "
        "a continuidade visual quando a medição é inconclusiva.",
        "tip-dotted.jpg",
        "Recorte do gráfico com medição e projeção pontilhada",
    ),
)


class CaptureTips(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("captureTips")
        self.setMinimumWidth(300)
        self.setMaximumWidth(460)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)

        title = QLabel(localize("Tire mais de cada captura"))
        title.setObjectName("captureTipsTitle")
        title.setWordWrap(True)
        layout.addWidget(title)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        items = QWidget()
        items.setObjectName("captureTipsItems")
        cards = QVBoxLayout(items)
        cards.setContentsMargins(0, 0, 5, 0)
        cards.setSpacing(4)
        feature = QFrame()
        feature.setObjectName("captureFeature")
        featured = QVBoxLayout(feature)
        featured.setContentsMargins(14, 12, 14, 14)
        for content, style in (
            ("SEU PRÓXIMO PASSO", "captureFeatureKicker"),
            ("Marque o trecho. Encontre a queda.", "captureFeatureTitle"),
        ):
            label = QLabel(localize(content))
            label.setObjectName(style)
            label.setWordWrap(True)
            featured.addWidget(label)
        image = QLabel()
        image.setAccessibleName(localize("Trechos selecionados na linha do tempo do AIDA"))
        image.setPixmap(QPixmap(str(_ASSETS / "studio-example.png")).scaledToWidth(
            220, Qt.TransformationMode.SmoothTransformation
        ))
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        featured.addWidget(image)
        benefit = QLabel(localize(
            "Analise só o que importa. Salve o projeto e retome quando quiser."
        ))
        benefit.setWordWrap(True)
        featured.addWidget(benefit)
        cards.addWidget(feature)
        self._cards: list[tuple[QPushButton, QWidget]] = []
        for index, tip in enumerate(_TIPS):
            preview = QPixmap(str(_ASSETS / tip.image))
            button = QPushButton()
            button.setObjectName("captureTipHeader")
            button.setAccessibleName(localize(tip.title))
            button.setCheckable(True)
            button.setAccessibleDescription(localize(
                "Dica recolhida. Pressione Espaço para abrir."
            ))
            button.setToolTip(localize("Abra a dica para ver o exemplo e as orientações."))
            header_layout = QHBoxLayout(button)
            header_layout.setContentsMargins(9, 10, 9, 10)
            thumbnail = QLabel()
            thumbnail.setPixmap(preview.scaled(
                56, 34, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
            thumbnail.setFixedSize(56, 34)
            thumbnail.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            header_layout.addWidget(thumbnail)
            heading = QWidget()
            heading.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            heading_layout = QVBoxLayout(heading)
            heading_layout.setContentsMargins(0, 0, 0, 0)
            heading_layout.setSpacing(3)
            headings = ((tip.hint, "captureTipCategory"), (tip.title, "captureTipTitle"))
            for content, style in headings:
                label = QLabel(localize(content))
                label.setObjectName(style)
                label.setWordWrap(True)
                heading_layout.addWidget(label)
            header_layout.addWidget(heading, 1)
            chevron = QLabel()
            chevron.setPixmap(action_icon("expand").pixmap(14, 14))
            chevron.setObjectName("captureTipChevron")
            chevron.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            header_layout.addWidget(chevron)
            button.setMinimumHeight(68)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            button.clicked.connect(
                lambda checked, row=index: self._expand(row if checked else None)
            )
            cards.addWidget(button)

            body = QWidget()
            body.setObjectName("captureTipBody")
            body_layout = QVBoxLayout(body)
            body_layout.setContentsMargins(9, 7, 9, 9)
            body_layout.setSpacing(6)
            image = QLabel()
            image.setAccessibleName(localize(tip.caption))
            image.setAlignment(Qt.AlignmentFlag.AlignCenter)
            image.setPixmap(
                preview.scaled(
                    245,
                    113,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            body_layout.addWidget(image)
            for content, style in ((tip.caption, "muted"), (tip.detail, "captureTipDetail")):
                label = QLabel(localize(content))
                label.setObjectName(style)
                label.setWordWrap(True)
                body_layout.addWidget(label)
            body.hide()
            cards.addWidget(body)
            self._cards.append((button, body))
        cards.addStretch()
        scroll.setWidget(items)
        layout.addWidget(scroll, 1)

        channel = QPushButton(localize("Assistir ao canal Detonando Gueek"))
        channel.setObjectName("captureTipsChannel")
        channel.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(CHANNEL_URL)))
        layout.addWidget(channel)

    def _expand(self, selected: int | None) -> None:
        for index, (header, body) in enumerate(self._cards):
            expanded = index == selected
            header.setChecked(expanded)
            body.setVisible(expanded)
            header.findChild(QLabel, "captureTipChevron").setPixmap(
                action_icon("collapse" if expanded else "expand").pixmap(14, 14)
            )
            header.setAccessibleDescription(localize(
                "Dica aberta. Pressione Espaço para fechar."
                if expanded else "Dica recolhida. Pressione Espaço para abrir."
            ))
