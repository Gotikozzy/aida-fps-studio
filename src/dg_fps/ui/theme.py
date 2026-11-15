"""Native desktop visual tokens. No analysis behavior lives here."""

ANALYST_STYLE = """
QMainWindow,
QDialog,
QWidget { background: #151515;
color: #ececec;
font-family: 'Segoe UI';
font-size: 12px;
}
QMainWindow::separator { background: #383838;
width: 5px;
height: 5px;
}
QMainWindow::separator:hover { background: #20cfe3;
}
QMenuBar { background: #181818;
padding: 4px 10px;
border-bottom: 1px solid #383838;
}
QMenuBar::item { padding: 6px 12px;
background: transparent;
}
QMenuBar::item:selected,
QMenu::item:selected { background: #24434a;
color: #f4f4f4;
}
QMenu { background: #242424;
border: 1px solid #484848;
padding: 6px;
}
QMenu::item { padding: 8px 30px 8px 14px;
}
QMenu::separator { height: 1px;
background: #334155;
margin: 5px 10px;
}
QToolBar { background: #1e1e1e;
border: 0;
border-bottom: 1px solid #383838;
spacing: 8px;
padding: 8px;
}
QDockWidget { font-weight: 600;
}
QDockWidget::title { background: #242424;
padding: 8px 12px;
border-bottom: 1px solid #383838;
}
QDockWidget::close-button,
QDockWidget::float-button { padding: 3px;
}
QStatusBar { background: #181818;
border-top: 1px solid #383838;
color: #aaaaaa;
}
QLabel { background: transparent;
}
QLabel#processTitle { font-size: 19px;
font-weight: 600;
color: #ececec;
}
QLabel#processGuide { color: #bdbdbd;
padding: 10px;
background: #222222;
border: 1px solid #383838;
border-radius: 6px;
}
QLabel#sourceLabel { color: #aaaaaa;
padding: 0 12px;
}
QLabel#timelineHeading { color: #aaaaaa;
font-size: 11px;
font-weight: 600;
}
QLabel#timecodeReadout { font-family: 'Consolas';
font-size: 14px;
color: #ececec;
}
QPushButton,
QToolButton { background: #282828;
border: 1px solid #484848;
border-radius: 5px;
padding: 7px 10px;
color: #ececec;
}
QPushButton:hover,
QToolButton:hover { background: #333333;
border-color: #666666;
}
QPushButton:pressed,
QToolButton:pressed { background: #333333;
}
QPushButton:checked,
QToolButton:checked { background: #20383d;
border-color: #20cfe3;
color: #78e3ed;
}
QPushButton[role="primary"] { background: #f49a39;
border-color: #20cfe3;
color: #f4f4f4;
font-weight: 600;
}
QPushButton[role="primary"]:hover { background: #ffb15c;
}
QPushButton:disabled,
QToolButton:disabled { color: #929292;
background: #202020;
border-color: #383838;
}
QPushButton:focus,
QToolButton:focus,
QComboBox:focus,
QLineEdit:focus,
QSpinBox:focus,
QTextEdit:focus,
QPlainTextEdit:focus { border: 1px solid #78e3ed;
}
QLineEdit,
QSpinBox,
QDoubleSpinBox,
QComboBox { background: #181818;
border: 1px solid #484848;
border-radius: 4px;
padding: 6px;
selection-background-color: #24434a;
min-height: 20px;
}
QComboBox { padding-right: 25px;
}
QComboBox QAbstractItemView { background: #242424;
selection-background-color: #24434a;
color: #ececec;
outline: none;
}
QPlainTextEdit,
QTextEdit,
QTextBrowser,
QListWidget { background: #181818;
border: 1px solid #383838;
border-radius: 5px;
padding: 7px;
selection-background-color: #24434a;
}
QPlainTextEdit { font-family: 'Consolas';
font-size: 11px;
}
QListWidget::item { padding: 7px 5px;
border-bottom: 1px solid #303030;
}
QListWidget::item:selected { background: #24434a;
}
QTabWidget::pane { border: 1px solid #383838;
border-radius: 4px;
}
QTabBar::tab { background: #1e1e1e;
color: #aaaaaa;
padding: 7px 10px;
border-bottom: 2px solid transparent;
}
QTabBar::tab:selected { background: #24434a;
color: #ececec;
border-bottom: 2px solid #20cfe3;
}
QScrollArea { border: 0;
background: transparent;
}
QScrollBar:vertical { background: #181818;
width: 10px;
margin: 0;
}
QScrollBar:horizontal { background: #181818;
height: 10px;
margin: 0;
}
QScrollBar::handle { background: #555555;
border-radius: 4px;
min-height: 24px;
min-width: 24px;
}
QScrollBar::handle:hover { background: #777777;
}
QScrollBar::add-line,
QScrollBar::sub-line { width: 0;
height: 0;
}
QScrollBar::add-page,
QScrollBar::sub-page { background: transparent;
}
QSlider::groove:horizontal { height: 5px;
background: #383838;
border-radius: 2px;
}
QSlider::sub-page:horizontal { background: #20cfe3;
}
QSlider::handle:horizontal { width: 10px;
margin: -5px 0;
border-radius: 5px;
background: #ececec;
border: 1px solid #20cfe3;
}
QProgressBar { background: #181818;
border: 1px solid #484848;
border-radius: 4px;
text-align: center;
}
QProgressBar::chunk { background: #20cfe3;
border-radius: 3px;
}
QToolTip { background: #282828;
color: #ececec;
border: 1px solid #666666;
padding: 7px;
}
QWidget#videoCanvas { background: #101010;
border: 1px solid #383838;
}
"""


# AIDA FPS Studio workspace tokens, layered over the shared native control styling.
ANALYST_STYLE += """
QMainWindow, QDialog, QWidget { background: #151515; color: #ececec; font-size: 13px; }
QLabel { background: transparent; }
QMenuBar, QStatusBar { background: #181818; border-color: #383838; }
QMenu { background: #242424; }
QMenu::item:selected { background: #24434a; }
QLabel#brandName { font-size: 17px; font-weight: 600; color: #ececec; }
QLabel#projectTitle { color: #aaaaaa; font-size: 13px; }
QFrame#studioPanel { border: 1px solid #383838; background: #1e1e1e; }
QLabel#panelHeading { background: #242424; padding: 9px 12px; font-weight: 600;
 border-bottom: 1px solid #383838; }
QTabWidget::pane { border: 1px solid #383838; background: #1e1e1e; }
QTabWidget#workspaceTabs::pane { border: 0; }
QTabBar::tab { background: transparent; color: #aaaaaa; padding: 10px 17px;
 border: 0; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: #ececec; border-bottom: 2px solid #20cfe3; }
QTabBar::tab:hover { background: #2d2d2d; }
QSplitter::handle { background: #151515; width: 6px; height: 6px; }
QSplitter::handle:hover { background: #20cfe3; }
QLabel#fpsValue { font-size: 42px; font-weight: 600; color: #ececec; }
QLabel#muted { color: #aaaaaa; }
QPushButton, QToolButton { border-radius: 3px; background: #282828; border: 1px solid #484848;
 padding: 6px 10px; }
QPushButton:hover, QToolButton:hover { background: #333333; border-color: #666666; }
QPushButton[role="primary"] { background: #f49a39; border-color: #ffc17c; color: #181818;
 font-weight: 600; padding: 9px 12px; min-height: 22px; }
QPushButton[role="primary"]:hover { background: #ffb15c; }
QPushButton[role="primary"]:pressed { background: #d9822b; }
QPushButton[role="primary"]:focus { border: 1px solid #20cfe3; }
QPushButton[role="primary"]:disabled { background: #202020; color: #929292;
 border-color: #383838; }
QPushButton:disabled, QToolButton:disabled { background: #202020; color: #929292;
 border-color: #383838; }
QListWidget { background: #181818; border: 0; outline: none; }
QListWidget::item { padding: 10px 5px; border-bottom: 1px solid #383838; }
QListWidget::item:selected { background: #20383d; color: #ececec; border-left: 3px solid #20cfe3; }
QPlainTextEdit#technicalSummary { background: #181818; color: #aaaaaa; border: 0; font-size: 11px; }
QLabel#exportPreview { background: #101010; border: 1px solid #383838; }
QFrame#welcomePanel { background: #1e1e1e; border: 1px solid #383838; }
QLabel#welcomeTitle { color: #ececec; font-size: 26px; font-weight: 600;
 padding-bottom: 12px; }
QFrame#captureTips { background: #1e1e1e; border: 1px solid #383838; border-radius: 4px; }
QLabel#captureTipsTitle { color: #ececec; font-size: 17px; font-weight: 600; }
QWidget#captureTipsItems, QWidget#captureTipBody { background: #1e1e1e; }
QPushButton#captureTipHeader { text-align: left; padding: 5px 8px; }
QPushButton#captureTipHeader:checked { background: #20383d; border-color: #20cfe3; }
QPushButton#captureTipsChannel { color: #bdbdbd; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: #181818; border: 1px solid #484848;
 padding: 6px; border-radius: 3px; }
QProgressBar { background: #181818; border: 1px solid #484848; text-align: center; min-height: 18px;
 }
QProgressBar::chunk { background: #20cfe3; }
QScrollBar:horizontal { background: #181818; height: 10px; }
QScrollBar::handle:horizontal { background: #555555; min-width: 24px; }
QLabel#welcomeCaption { color: #bdbdbd; font-size: 14px; padding-bottom: 12px; }
QPushButton#homeNewAnalysis { background: #f49a39; color: #181818;
 border: 1px solid #ffc17c; padding: 11px 16px; font-weight: 600; min-height: 22px; }
QPushButton#homeNewAnalysis:hover { background: #ffb15c; }
QPushButton#homeNewAnalysis:pressed { background: #d9822b; }
QPushButton#homeNewAnalysis:focus { border: 1px solid #20cfe3; }
QPushButton#homeNewAnalysis:disabled { background: #202020; color: #929292;
 border-color: #383838; }
QLabel#homeWorkflow { color: #bdbdbd; background: #242424; border: 1px solid #383838;
 border-radius: 6px; padding: 12px; margin-top: 8px; margin-bottom: 12px; }
QFrame#captureFeature { background: #242424; border: 1px solid #484848; border-radius: 6px; }
QFrame#captureFeature QLabel { background: transparent; }
QLabel#captureFeatureKicker { color: #ffc17c; font-size: 10px; font-weight: 600; }
QLabel#captureFeatureTitle { color: #ececec; font-size: 19px; font-weight: 600; }
QLabel#captureTipCategory { color: #aaaaaa; font-size: 10px; }
QLabel#captureTipTitle { color: #ececec; font-size: 13px; font-weight: 600; }
QPushButton#captureTipHeader QWidget { background: transparent; }
QPushButton#captureTipHeader:focus { border: 2px solid #78e3ed; }
QWidget#captureTipBody QLabel { color: #bdbdbd; }
"""
