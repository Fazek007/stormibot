from PyQt6.QtWidgets import QLabel


class DeathCounter(QLabel):
    death_string = "Deaths: 0"
    def __init__(self, parent=None):
        super().__init__(parent)

        self.reset_death_counter()

    def update_death_counter(self, nofdeaths):
        self.setText(f"Death: {nofdeaths}")
    def reset_death_counter(self):
        self.setText(self.death_string)
