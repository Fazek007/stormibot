# stopwatch_widget.py
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import QTimer, QTime

class StopwatchWidget(QLabel):
    DEFAULT_TEXT = "Elapsed: 00:00:00"

    def __init__(self, parent=None):
        super().__init__(parent)

        self.reset_display()
        self.start_time = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)

    def update_time(self):
        elapsed_secs = self.start_time.secsTo(QTime.currentTime())
        hours = elapsed_secs // 3600
        minutes = (elapsed_secs % 3600) // 60
        seconds = elapsed_secs % 60
        self.setText(f"Elapsed: {hours:02}:{minutes:02}:{seconds:02}")

    def start_timer(self):
        if self.timer.isActive():
            return

        self.reset_display()
        self.start_time = QTime.currentTime()
        self.timer.start(1000)

    def stop_timer(self):
        self.timer.stop()

    def reset_display(self):
        self.setText(self.DEFAULT_TEXT)