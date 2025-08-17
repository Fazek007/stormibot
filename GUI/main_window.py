import sys
import threading

from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow, QHBoxLayout, QPushButton, QListWidget, \
    QAbstractItemView, QVBoxLayout, QCheckBox, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QSettings
from Core.ship_bot import ShipBot
from stop_watch import StopwatchWidget
from death_counter import DeathCounter
import keyboard

class BotWindow(QMainWindow):
    stop_signal = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.settings = QSettings("SomeOrg","Stormibot")
        self.stop_signal.connect(self.stop_bot)
        self.setWindowTitle("Stormibot")
        self.resize(400,200)
        self.bot = ShipBot()
        self.bot_thread = None  # placeholder for the bot thread

        self._setup_ui()
        self.load_settings()
    def _setup_ui(self):
        #QMainWindow must use a central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        #Layouts
        parent_layout = QHBoxLayout()
        left_box_layout = QHBoxLayout()
        right_box_layout = QVBoxLayout()
        central_widget.setLayout(parent_layout)

        #Start button
        self.start_button = QPushButton("Start")
        self.start_button.setFixedSize(100,100)

        #Stop button
        self.stop_button = QPushButton("Stop")
        self.stop_button.setFixedSize(100,100)

        #Stopwatch
        self.stopwatch = StopwatchWidget()

        #Attack all Checkbox
        attack_all_layout = QHBoxLayout()  # Horizontal layout for label + checkbox
        self.attack_all_checkbox = QCheckBox()
        attack_all_label = QLabel("Attack all levels")
        attack_all_layout.addWidget(attack_all_label)
        attack_all_layout.addWidget(self.attack_all_checkbox)
        attack_all_widget = QWidget()
        attack_all_widget.setLayout(attack_all_layout)

        #Target level selector
        self.target_level_list = QListWidget()
        self.target_level_list.setFixedSize(200,100)
        self.target_level_list.addItems(["10-19", "20-29", "30-39"])
        self.target_level_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)

        #Death Counter
        self.death_counter = DeathCounter()

        #Signal connections
        self.stop_button.clicked.connect(self.stop_bot)
        self.start_button.clicked.connect(self.start_bot)
        self.attack_all_checkbox.stateChanged.connect(self.toggle_list)
        self.bot.bot_died.connect(self.handle_bot_died)

        #Left block
        left_box_layout.addWidget(self.start_button)
        left_box_layout.addWidget(self.stop_button)

        #Right block
        right_box_layout.addWidget(self.stopwatch, alignment=Qt.AlignmentFlag.AlignTop)
        right_box_layout.addWidget(self.death_counter, alignment=Qt.AlignmentFlag.AlignTop)
        right_box_layout.addWidget(attack_all_widget, alignment=Qt.AlignmentFlag.AlignBottom) # needs fixing still
        right_box_layout.addWidget(self.target_level_list, alignment=Qt.AlignmentFlag.AlignTop) # needs fixing still


        parent_layout.addLayout(left_box_layout)
        parent_layout.addLayout(right_box_layout)

    def toggle_list(self):
        # If checkbox is checked, disable the list; otherwise enable it
        if self.attack_all_checkbox.isChecked():
            self.target_level_list.setDisabled(True)
        else:
            self.target_level_list.setDisabled(False)

    def get_selected_levels(self):
        return [item.text() for item in self.target_level_list.selectedItems()]

    def start_bot(self):
        if self.attack_all_checkbox.isChecked():
            self.bot.set_attack_levels(["all"])
        else:
            self.bot.set_attack_levels(self.get_selected_levels())

        if self.bot_thread is None or not self.bot_thread.is_alive():
            # Run the bot in a separate thread
            self.bot_thread = threading.Thread(target=self.bot.run)
            self.bot_thread.start()
            print("Bot thread started")

        self.bot.statistics.reset()
        self.update_statistics()
        self.stopwatch.start_timer()

    def update_statistics(self):
        self.death_counter.update_death_counter(self.bot.statistics.deaths)

    def stop_bot(self):
        self.bot.stop_program()
        self.stopwatch.stop_timer()

    def handle_bot_died(self):
        self.update_statistics()

    def load_settings(self):
        saved_levels = self.settings.value("attack_levels", [])
        saved_attack_all = self.settings.value("attack_all", False, bool)

        self.attack_all_checkbox.setChecked(saved_attack_all)

        if not saved_attack_all:
            for i in range(self.target_level_list.count()):
                item = self.target_level_list.item(i)
                item.setSelected(item.text() in saved_levels)

    def save_settings(self):
        current_levels = [item.text() for item in self.target_level_list.selectedItems()]

        attack_all_checked = self.attack_all_checkbox.isChecked()

        self.settings.setValue("attack_levels", current_levels)
        self.settings.setValue("attack_all", attack_all_checked)

    def closeEvent(self, event):
        self.save_settings()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BotWindow()
    keyboard.add_hotkey('q', lambda: window.stop_signal.emit())
    window.show()
    sys.exit(app.exec())