# stopwatch_widget.py
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import QElapsedTimer, QTime, QTimer

class StopwatchWidget(QLabel):
    DEFAULT_TEXT = "Elapsed: 00:00:00"

    def __init__(self, parent=None):
        super().__init__(parent)

        self.reset_display()
        self.start_time = None
        self.elapsed_timer = QElapsedTimer()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)

    def update_time(self):
        ms = self.elapsed_timer.elapsed()
        elapsed_secs = round(ms / 1000)
        seconds = elapsed_secs % 60 # using round is necessary, because elapsed timer is inconsistent: 997, 1999, 3001 ms and it would jump ahead by 2 seconds there
        hours = elapsed_secs // 3600
        minutes = (elapsed_secs % 3600) // 60

        # Debugging
        print(f"[DEBUG] ms elapsed = {ms}, elapsed_secs = {elapsed_secs}")

        self.setText(f"Elapsed: {hours:02}:{minutes:02}:{seconds:02}")

    def start_timer(self):
        if self.timer.isActive():
            return

        self.reset_display()
        self.elapsed_timer.start()
        self.timer.start(1000)

    def stop_timer(self):
        self.timer.stop()

    def reset_display(self):
        self.setText(self.DEFAULT_TEXT)