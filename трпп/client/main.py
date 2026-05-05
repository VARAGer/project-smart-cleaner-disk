import sys
from PyQt6.QtWidgets import QApplication

from database.local_db import init_database
from gui.main_window import MainWindow
from theme import build_stylesheet


def main():
    init_database()

    app = QApplication(sys.argv)
    app.setStyleSheet(build_stylesheet("dark"))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()