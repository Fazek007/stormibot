import sys
import keyboard
from PyQt6.QtWidgets import QApplication
from stormibot.GUI.main_window import BotWindow

def main():
    app = QApplication(sys.argv)
    window = BotWindow()
    keyboard.add_hotkey('q', lambda: window.stop_signal.emit())
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()