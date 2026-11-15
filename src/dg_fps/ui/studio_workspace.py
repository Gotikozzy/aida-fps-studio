"""AIDA FPS Studio workspace composition. No analysis algorithms in this module."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from dg_fps.ui.capture_tips import CaptureTips
from dg_fps.ui.i18n import localize
from dg_fps.ui.icons import icon_button

ASSETS = Path(__file__).resolve().parents[1] / "assets"


class PreviewView(QLabel):
    def __init__(self, text: str):
        super().__init__(text)
        self.image = QImage()

    def set_image(self, image: QImage) -> None:
        self.image = image
        self.update()

    def clear_image(self) -> None:
        self.image = QImage()
        self.update()

    def paintEvent(self, event) -> None:
        if self.image.isNull():
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#101010"))
        size = self.image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(
            QRectF(
                (self.width() - size.width()) / 2,
                (self.height() - size.height()) / 2,
                size.width(),
                size.height(),
            ),
            self.image,
        )
        painter.end()


def section(title: str, body: QWidget) -> QWidget:
    panel = QFrame()
    panel.setObjectName("studioPanel")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    label = QLabel(localize(title))
    label.setObjectName("panelHeading")
    layout.addWidget(label)
    layout.addWidget(body, 1)
    return panel


class MiniPlot(QWidget):
    frame_requested = Signal(int)

    def __init__(self):
        super().__init__()
        self.points = ()
        self.setMinimumHeight(90)

    def paintEvent(self, event):
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#1e1e1e"))
        for n in range(4):
            y = 12 + n * (self.height() - 22) / 3
            p.setPen(QPen(QColor("#383838"), 1))
            p.drawLine(QPointF(8, y), QPointF(self.width() - 8, y))
        if self.points:
            start = min(v.seconds for v in self.points)
            end = max(v.seconds for v in self.points)
            maximum = max(30, max((v.graph_fps or 0 for v in self.points), default=60))
            stride = max(1, len(self.points) // max(1, self.width() * 2))
            points = self.points[::stride]
            for a, b in zip(points, points[1:], strict=False):
                if (
                    a.segment != b.segment
                    or b.frame_index - a.frame_index != stride
                    or a.graph_fps is None
                    or b.graph_fps is None
                ):
                    continue
                p.setPen(
                    QPen(
                        QColor("#20cfe3"),
                        1.5,
                        Qt.PenStyle.DotLine
                        if a.graph_origin == "projected" or b.graph_origin == "projected"
                        else Qt.PenStyle.SolidLine,
                    )
                )
                p.drawLine(
                    QPointF(
                        8 + (a.seconds - start) / max(0.001, end - start) * (self.width() - 16),
                        self.height() - 10 - a.graph_fps / maximum * (self.height() - 24),
                    ),
                    QPointF(
                        8 + (b.seconds - start) / max(0.001, end - start) * (self.width() - 16),
                        self.height() - 10 - b.graph_fps / maximum * (self.height() - 24),
                    ),
                )
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.points:
            start = min(p.seconds for p in self.points)
            end = max(p.seconds for p in self.points)
            value = start + (event.position().x() - 8) / max(1, self.width() - 16) * (end - start)
            self.frame_requested.emit(
                min(self.points, key=lambda p: abs(p.seconds - value)).frame_index
            )


class ProcessDialog(QDialog):
    def __init__(self, parent, cancel):
        super().__init__(parent)
        self.setWindowTitle("AIDA FPS Studio")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumWidth(450)
        self.heading = QLabel()
        self.heading.setStyleSheet("font-size: 16px; font-weight: 600;")
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.bar = QProgressBar()
        self.cancel = QPushButton(localize("Cancelar"))
        self.cancel.clicked.connect(cancel)
        layout = QVBoxLayout(self)
        layout.addWidget(self.heading)
        layout.addWidget(self.message)
        layout.addWidget(self.bar)
        layout.addWidget(self.cancel)

    def reject(self):
        self.cancel.click()


def build_workspace(w) -> None:
    w.setWindowIcon(QIcon(str(ASSETS / "aida.ico")))
    w.setAcceptDrops(True)
    root = QWidget()
    layout = QVBoxLayout(root)
    layout.setContentsMargins(8, 4, 8, 4)
    layout.setSpacing(6)
    brandrow = QHBoxLayout()
    logo = QLabel()
    logo.setPixmap(
        QPixmap(str(ASSETS / "aida.png")).scaled(
            30, 30, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
    )
    brandrow.addWidget(logo)
    brand = QLabel("AIDA FPS Studio")
    brand.setObjectName("brandName")
    brandrow.addWidget(brand)
    w.project_title = QLabel(localize("Nova análise"))
    w.project_title.setObjectName("projectTitle")
    w.project_title.setProperty("i18n_skip", True)
    brandrow.addSpacing(20)
    brandrow.addWidget(w.project_title)
    w.save_state = QLabel()
    w.save_state.setObjectName("projectTitle")
    brandrow.addWidget(w.save_state)
    brandrow.addStretch()
    w.update_notice = QLabel()
    w.update_notice.setOpenExternalLinks(True)
    w.update_notice.setProperty("i18n_skip", True)
    w.update_notice.hide()
    brandrow.addWidget(w.update_notice)
    layout.addLayout(brandrow)
    w.workspaces = QTabWidget()
    w.workspaces.setObjectName("workspaceTabs")
    analysis = QWidget()
    al = QVBoxLayout(analysis)
    al.setContentsMargins(0, 4, 0, 0)
    w.main_splitter = QSplitter(Qt.Orientation.Horizontal)
    project = QWidget()
    pl = QVBoxLayout(project)
    pl.setContentsMargins(10, 10, 10, 10)
    w.source_thumbnail = QLabel()
    w.source_thumbnail.setMinimumHeight(85)
    w.source_thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
    pl.addWidget(w.source_thumbnail)
    pl.addWidget(w.file_label)
    w.source_details = QLabel()
    w.source_details.setObjectName("muted")
    w.source_details.setWordWrap(True)
    pl.addWidget(w.source_details)
    w.open_button.setMaximumHeight(30)
    pl.addWidget(w.open_button)
    pl.addWidget(w.panel, 1)
    for name in ("cadenceMarkStartButton", "cadenceMarkEndButton"):
        w.panel.findChild(QPushButton, name).hide()
    w.panel._range_list.setMaximumHeight(16777215)
    w.panel._range_list.setWordWrap(True)
    w.panel._points_label.hide()
    w.panel._status.hide()
    for button in w.panel.findChildren(QPushButton):
        if button.text() == localize("Adicionar trecho"):
            button.setText("+")
            button.setToolTip(localize("Adicionar trecho"))
            button.setMaximumWidth(36)
        if button.text() == localize("Remover trecho"):
            button.setText("−")
            button.setToolTip(localize("Remover trecho"))
            button.setMaximumWidth(36)
        if button.text() == localize("Limpar trechos"):
            button.clicked.disconnect()
            button.clicked.connect(lambda checked=False, b=button: w._range_menu(b))
            button.setText("…")
            button.setToolTip(localize("Mais opções de trechos"))
            button.setMaximumWidth(36)
    project_scroll = QScrollArea()
    project_scroll.setWidgetResizable(True)
    project_scroll.setFrameShape(QFrame.Shape.NoFrame)
    project_scroll.setWidget(project)
    left = section("Projeto", project_scroll)
    left.setMinimumWidth(240)
    monitor = QWidget()
    ml = QVBoxLayout(monitor)
    ml.setContentsMargins(4, 4, 4, 4)
    ml.addWidget(w.view, 1)
    ml.addWidget(w.timeline.transport)
    for widget in (w.timeline._total_label, w.timeline._playback_label):
        widget.hide()
    w.timeline._frame_entry.setMaximumWidth(92)
    icon_button(w.timeline._mark_in, "in", localize(
        "Marcar início do trecho (I). Depois, marque o fim para adicioná-lo à análise."
    ))
    icon_button(w.timeline._mark_out, "out", localize(
        "Marcar fim do trecho (O). O intervalo marcado será incluído na análise."
    ))
    w.inspector_tabs = QTabWidget()
    w.inspector_tabs.setMinimumWidth(275)
    results = QWidget()
    rl = QVBoxLayout(results)
    rl.setContentsMargins(12, 14, 12, 12)
    w.fps_value = QLabel("—")
    w.fps_value.setObjectName("fpsValue")
    w.fps_value.setProperty("i18n_skip", True)
    w.fps_value.setToolTip(localize(
        "FPS médio medido no trecho selecionado. Sem seleção, mostra a média da análise."
    ))
    rl.addWidget(w.fps_value)
    rl.addWidget(QLabel(localize("Média medida • FPS")))
    w.result_capture = QLabel(localize("Captura: —"))
    w.result_capture.setProperty("i18n_skip", True)
    w.result_capture.setToolTip(localize(
        "Taxa de quadros do arquivo gravado. Ela define quais metas a captura permite avaliar."
    ))
    rl.addWidget(w.result_capture)
    w.result_target = QLabel(localize("Meta: —"))
    w.result_target.setProperty("i18n_skip", True)
    w.result_target.setToolTip(localize(
        "FPS de referência para comparar o resultado. Escolher uma meta preserva a medição."
    ))
    rl.addWidget(w.result_target)
    w.analysis_state = QLabel(localize("Aguardando análise"))
    w.analysis_state.setWordWrap(True)
    rl.addWidget(w.analysis_state)
    rl.addWidget(QLabel(localize("FPS ao longo do tempo")))
    w.result_plot = MiniPlot()
    w.result_plot.frame_requested.connect(w.seek)
    rl.addWidget(w.result_plot)
    rl.addWidget(QLabel(localize("Trecho selecionado")))
    w.selected_range_name = QLabel("—")
    w.selected_range_time = QLabel("—")
    w.selected_range_time.setWordWrap(True)
    for field in (w.selected_range_name, w.selected_range_time):
        field.setProperty("i18n_skip", True)
        rl.addWidget(field)
    rl.addStretch(1)
    w.panel._summary.setMaximumHeight(170)
    w.panel._summary.setObjectName("technicalSummary")
    w.panel._analyze.setText(localize("Analisar trechos"))
    w.panel._analyze.setProperty("role", "primary")
    rl.addWidget(w.panel._analyze)
    props = QWidget()
    pf = QFormLayout(props)
    pf.addRow(localize("Meta de FPS"), w.content_target)
    w.content_target.setToolTip(localize(
        "Use Automático ou escolha o FPS esperado do jogo. "
        "A meta precisa ser compatível com a captura."
    ))
    w.target_validation = QLabel()
    w.target_validation.setWordWrap(True)
    pf.addRow(w.target_validation)
    pf.addRow(w.segment_targets_button)
    info = QLabel(localize("Selecione e ajuste os trechos na timeline. I e O marcam início e fim."))
    info.setWordWrap(True)
    pf.addRow(info)
    pf.addRow(w.panel._summary)
    w.inspector_tabs.addTab(results, localize("Resultados"))
    w.inspector_tabs.addTab(props, localize("Propriedades"))
    w.main_splitter.addWidget(left)
    w.main_splitter.addWidget(section("Monitor de vídeo", monitor))
    inspector_scroll = QScrollArea()
    inspector_scroll.setWidgetResizable(True)
    inspector_scroll.setFrameShape(QFrame.Shape.NoFrame)
    inspector_scroll.setWidget(w.inspector_tabs)
    inspector_scroll.setMinimumWidth(285)
    w.main_splitter.addWidget(inspector_scroll)
    w.main_splitter.setStretchFactor(1, 1)
    w.main_splitter.setSizes([240, 850, 300])
    w.vertical_splitter = QSplitter(Qt.Orientation.Vertical)
    w.vertical_splitter.addWidget(w.main_splitter)
    w.vertical_splitter.addWidget(w.timeline)
    w.vertical_splitter.setStretchFactor(0, 1)
    w.vertical_splitter.setSizes([600, 235])
    al.addWidget(w.vertical_splitter)
    w.workspaces.addTab(analysis, localize("Análise"))
    export = QWidget()
    el = QHBoxLayout(export)
    el.setContentsMargins(24, 20, 24, 20)
    w.export_preview = PreviewView(
        localize("Escolha a entrega. A análise será feita automaticamente ao exportar.")
    )
    w.export_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
    w.export_preview.setMinimumSize(320, 180)
    w.export_preview.setObjectName("exportPreview")
    el.addWidget(section("Prévia da apresentação", w.export_preview), 2)
    options = QWidget()
    ol = QVBoxLayout(options)
    ol.setSpacing(14)
    ol.addWidget(QLabel(localize("O que deseja exportar?")))
    w.delivery_kind = QComboBox()
    for text, value in (
        ("Vídeo e relatório para IA", "both"),
        ("Somente vídeo", "video"),
        ("Apenas relatório para IA", "report"),
    ):
        w.delivery_kind.addItem(localize(text), value)
    ol.addWidget(w.delivery_kind)
    w.delivery_kind.setToolTip(localize(
        "Escolha o que salvar. O relatório reúne medições e contexto em JSON para usar com uma IA."
    ))
    preview_button = QPushButton(localize("Atualizar prévia"))
    preview_button.clicked.connect(w._preview_export)
    ol.addWidget(preview_button)
    ol.addWidget(QLabel(localize("Nome dos arquivos")))
    w.delivery_name = QLineEdit("minha_analise")
    ol.addWidget(w.delivery_name)
    ol.addWidget(QLabel(localize("Salvar em")))
    w.delivery_directory = QLineEdit(str(w.data_directory / "entregas"))
    w.delivery_directory.setReadOnly(True)
    ol.addWidget(w.delivery_directory)
    destination = QPushButton(localize("Escolher pasta…"))
    destination.clicked.connect(w._choose_delivery_folder)
    ol.addWidget(destination)
    form = QFormLayout()
    form.addRow(localize("Processamento do vídeo"), w.encoding_mode)
    w.encoding_mode.setToolTip(localize(
        "Define como gerar o vídeo exportado. Automático usa a opção disponível no computador."
    ))
    ol.addLayout(form)
    encoding_label = form.labelForField(w.encoding_mode)

    def delivery_controls():
        video = w.delivery_kind.currentData() != "report"
        w.encoding_mode.setVisible(video)
        encoding_label.setVisible(video)
        preview_button.setVisible(video)

    w.delivery_kind.currentIndexChanged.connect(delivery_controls)
    hint = QLabel(
        localize("Arquivos técnicos ficam no projeto. Entrega somente dos itens escolhidos.")
    )
    hint.setWordWrap(True)
    ol.addWidget(hint)
    ol.addStretch()
    ol.addWidget(w.export_button)
    ol.addWidget(w.export_folder_button)
    w.export_button.setText(localize("Exportar arquivos"))
    w.export_button.setProperty("role", "primary")
    el.addWidget(section("Exportação", options), 1)
    w.workspaces.addTab(export, localize("Exportação"))
    layout.addWidget(w.workspaces)
    w.welcome = QFrame(root)
    w.welcome.setObjectName("welcomePanel")
    home = QHBoxLayout(w.welcome)
    home.setContentsMargins(32, 30, 32, 30)
    home.setSpacing(24)
    welcome_actions = QWidget()
    wel = QVBoxLayout(welcome_actions)
    wel.setContentsMargins(0, 0, 0, 0)
    home.addWidget(welcome_actions, 2)
    home.addWidget(CaptureTips(w.welcome), 1)
    title = QLabel(localize("Sua próxima análise começa aqui."))
    title.setObjectName("welcomeTitle")
    title.setWordWrap(True)
    wel.addWidget(title)
    caption = QLabel(localize(
        "Abra uma captura, marque os trechos e confira o FPS. "
        "Salve o projeto para continuar depois."
    ))
    caption.setObjectName("welcomeCaption")
    caption.setWordWrap(True)
    wel.addWidget(caption)
    row = QHBoxLayout()
    for text, callback in (
        ("Nova análise", w._choose_source),
        ("Abrir projeto…", w._choose_project),
        ("Preferências", w._show_preferences),
    ):
        button = QPushButton(localize(text))
        button.clicked.connect(callback)
        button.setMaximumWidth(210)
        icon_button(
            button,
            {"Nova análise": "add", "Abrir projeto…": "folder", "Preferências": "settings"}[text],
            localize(text),
            show_text=text != "Preferências",
        )
        if text == "Nova análise":
            button.setObjectName("homeNewAnalysis")
            button.setProperty("role", "primary")
            button.setToolTip(localize("Abra um vídeo para começar um novo projeto de análise."))
        elif text == "Abrir projeto…":
            button.setObjectName("homeOpenProject")
            button.setToolTip(localize("Retome os trechos e resultados de um projeto .aida salvo."))
        row.addWidget(button)
    row.addStretch()
    wel.addLayout(row)
    guidance = QLabel(localize(
        "1  Abra o vídeo    →    2  Selecione os trechos    →    3  Analise e salve"
    ))
    guidance.setObjectName("homeWorkflow")
    guidance.setWordWrap(True)
    wel.addWidget(guidance)
    wel.addWidget(QLabel(localize("Projetos recentes")))
    w.recent_empty = QLabel(localize(
        "Seus projetos salvos aparecem aqui. Comece em Nova análise ou abra um arquivo .aida."
    ))
    w.recent_empty.setWordWrap(True)
    w.recent_empty.setObjectName("muted")
    wel.addWidget(w.recent_empty)
    w.recent_list = QListWidget()
    w.recent_list.setMaximumHeight(280)
    w.recent_list.setAccessibleName(localize("Projetos recentes"))
    w.recent_list.itemActivated.connect(
        lambda item: w._open_project(Path(item.data(Qt.ItemDataRole.UserRole)))
    )
    wel.addWidget(w.recent_list, 1)
    w.recovery_button = QPushButton(localize("Recuperar última análise"))
    w.recovery_button.clicked.connect(w._recover)
    wel.addWidget(w.recovery_button)
    wel.addStretch()
    w.progress.hide()
    w.cancel_button.hide()
    w.folder_button.hide()
    w.show_folder.hide()
    w.home_index = w.workspaces.addTab(w.welcome, localize("Início"))
    for button, kind, label in (
        (w.open_button, "folder", "Abrir vídeo"),
        (w.panel._analyze, "analyze", "Analisar trechos"),
        (w.export_button, "export", "Exportar arquivos"),
        (w.export_folder_button, "folder", "Abrir pasta da entrega"),
        (preview_button, "preview", "Atualizar prévia"),
        (destination, "folder", "Escolher pasta…"),
        (w.recovery_button, "restore", "Recuperar última análise"),
        (w.segment_targets_button, "settings", "Metas por trecho…"),
        (w.timeline.select_tool, "range", "Selecionar intervalo • arraste na timeline"),
    ):
        icon_button(
            button, kind, localize(label),
            show_text=button in (
                w.panel._analyze, w.export_button, w.recovery_button, preview_button, destination
            ),
        )
    w.panel._analyze.setToolTip(localize(
        "Meça os trechos selecionados e veja o resultado no Studio. Você pode exportar depois."
    ))
    w.export_button.setToolTip(localize(
        "Salve os itens escolhidos. Se necessário, o Studio faz a análise antes de exportar."
    ))
    w.timeline.select_tool.setToolTip(localize(
        "Arraste na linha do tempo para criar um trecho. Ajuste as bordas ou use I e O."
    ))
    w.analysis_mode.setToolTip(localize(
        "Escolha como analisar. Automático verifica a aceleração disponível. "
        "A CPU funciona sem NVIDIA."
    ))
    for button in w.panel.findChildren(QPushButton):
        kind = {"+": "add", "−": "delete", "…": "more"}.get(button.text())
        if kind:
            icon_button(button, kind, button.toolTip())
    w.setCentralWidget(root)
    w.process_dialog = ProcessDialog(w, w._cancel_operation)
    w.preferences = QDialog(w)
    w.preferences.setWindowTitle(localize("Preferências"))
    w.preferences.setMinimumWidth(520)
    w.hardware_dialog = ProcessDialog(w.preferences, w._cancel)
    w.hardware_dialog.setWindowTitle(localize("Teste NVIDIA"))
    pref = QVBoxLayout(w.preferences)
    form = QFormLayout()
    form.addRow(localize("Idioma"), w.language_box)
    form.addRow(localize("Processar análise"), w.analysis_mode)
    form.addRow(localize("Preparar vídeo"), w.index_mode)
    pref.addLayout(form)
    pref.addWidget(w.hardware_button)
    pref.addWidget(w.hardware_status)
    pref.addWidget(w.folder_button)
    pref.addWidget(w.show_folder)
    w.folder_button.show()
    w.show_folder.show()
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(w.preferences.close)
    pref.addWidget(buttons)
