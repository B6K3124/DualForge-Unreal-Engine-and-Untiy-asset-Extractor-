from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class LoadingOverlay(QWidget):
    """Semi-transparent spinner panel placed on top of the preview area."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "background: rgba(20, 21, 26, 0.72); border-radius: 10px;"
        )
        self.setHidden(True)
        self._cancel_clicked = False

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)

        self.message = QLabel("Loading preview...")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setStyleSheet("color: #d7dae3; font-size: 14px; background: transparent;")

        bar = QProgressBar()
        bar.setFixedWidth(220)
        bar.setRange(0, 0)
        bar.setTextVisible(False)
        bar.setStyleSheet(
            "QProgressBar { background: transparent; border: none; }"
            "QProgressBar::chunk { background: #e88b3a; border-radius: 3px; }"
        )

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet(
            "QPushButton { color: #e05252; background: rgba(255,255,255,0.06);"
            " border: 1px solid rgba(224, 82, 82, 0.6); border-radius: 5px; padding: 4px 16px; }"
            "QPushButton:hover { background: #e05252; color: #16171c; }"
        )
        self.cancel_button.clicked.connect(self._on_cancel)

        layout.addWidget(self.message)
        layout.addWidget(bar)
        layout.addWidget(self.cancel_button)

    def _on_cancel(self) -> None:
        self._cancel_clicked = True
        self.set_message("Cancelling...")

    def cancelled(self) -> bool:
        return self._cancel_clicked

    def reset(self) -> None:
        self._cancel_clicked = False

    def set_message(self, text: str) -> None:
        self.message.setText(text)

    def show_overlay(self, message: str = "Loading preview...") -> None:
        self.reset()
        self.set_message(message)
        self.raise_()
        self.show()

    def hide_overlay(self) -> None:
        self.hide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.parentWidget():
            self.setGeometry(self.parentWidget().rect())

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.ParentChange and self.parentWidget():
            self.setGeometry(self.parentWidget().rect())
        return super().event(event)
