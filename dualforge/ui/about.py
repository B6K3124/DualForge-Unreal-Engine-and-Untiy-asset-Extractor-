from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
)

from dualforge.version import __version__

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_LICENSE_FILE = _PROJECT_ROOT / "docs" / "LICENSES.md"


def _license_text() -> str:
    try:
        return _LICENSE_FILE.read_text(encoding="utf-8")
    except OSError:
        return "License information unavailable."


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About DualForge")
        self.resize(560, 460)

        from PySide6.QtWidgets import QApplication

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        from dualforge.ui.branding import make_app_icon

        icon_label = QLabel()
        icon_label.setPixmap(make_app_icon(48).pixmap(48, 48))
        header.addWidget(icon_label)

        title_col = QVBoxLayout()
        title = QLabel("DualForge")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        subtitle = QLabel("Unity & Unreal game asset extractor")
        subtitle.setStyleSheet("color: #8b90a3;")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header.addLayout(title_col)
        header.addStretch(1)

        version = QLabel(f"v{__version__}")
        version.setStyleSheet("color: #8b90a3;")
        header.addWidget(version)
        layout.addLayout(header)

        app = QApplication.instance()
        info = QLabel(
            f"Python {__import__('sys').version.split()[0]}  ·  "
            f"PySide6 {getattr(__import__('PySide6'), '__version__', '?')}  ·  "
            f"Qt {app.style().objectName()} style"
        )
        info.setStyleSheet("color: #8b90a3;")
        layout.addWidget(info)

        licenses = QPlainTextEdit()
        licenses.setReadOnly(True)
        licenses.setPlainText(_license_text())
        layout.addWidget(licenses, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setProperty("role", "primary")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


__all__ = ["AboutDialog"]
