from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)


class KeyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add AES Key")
        self.setMinimumWidth(380)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("e.g. Fortnite")
        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("64 hex characters (AES-256)")
        self.engine_edit = QLineEdit("unreal")
        form = QFormLayout()
        form.addRow("Game title", self.title_edit)
        form.addRow("AES key", self.key_edit)
        form.addRow("Engine", self.engine_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setProperty("role", "primary")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self):
        return (
            self.title_edit.text().strip(),
            self.key_edit.text().strip(),
            self.engine_edit.text().strip(),
        )


__all__ = ["KeyDialog"]
