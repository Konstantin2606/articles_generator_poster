import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel, QMessageBox
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt
import subprocess

class MainAppWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Setup the main window
        self.setWindowTitle("Application Launcher")
        self.setGeometry(300, 300, 400, 200)

        # Load the icon
        icon_path = os.path.join('icons', 'main_icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Create buttons
        self.generator_button = QPushButton("Article Generator")
        self.wordpress_button = QPushButton("WordPress Poster")

        # Connect buttons to the respective functions
        self.generator_button.clicked.connect(self.run_generator_window)
        self.wordpress_button.clicked.connect(self.run_wordpress_poster_window)

        # Layout for buttons
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Select an application to launch:", alignment=Qt.AlignmentFlag.AlignCenter))
        layout.addWidget(self.generator_button)
        layout.addWidget(self.wordpress_button)

        # Set the central widget
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Load styles
        self.load_styles()

    def load_styles(self):
        # Load styles from style.qss
        style_path = os.path.join(os.getcwd(), 'style.qss')
        if os.path.exists(style_path):
            with open(style_path, "r") as style_file:
                self.setStyleSheet(style_file.read())

    def run_generator_window(self):
        # Run GeneratorWindow.py
        try:
            subprocess.Popen([sys.executable, os.path.join('ArticleGenerator', 'GeneratorWindow.py')])
        except Exception as e:
            self.show_error(f"Failed to launch GeneratorWindow.py: {e}")

    def run_wordpress_poster_window(self):
        # Run WordPressPosterWindow.py
        try:
            subprocess.Popen([sys.executable, os.path.join('WordPressPoster', 'WordPressPosterWindow.py')])
        except Exception as e:
            self.show_error(f"Failed to launch WordPressPosterWindow.py: {e}")

    def show_error(self, message):
        # Display error message
        error_dialog = QMessageBox()
        error_dialog.setIcon(QMessageBox.Icon.Critical)
        error_dialog.setWindowTitle("Error")
        error_dialog.setText(message)
        error_dialog.exec()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Create and display the main window
    main_window = MainAppWindow()
    main_window.show()

    sys.exit(app.exec())
