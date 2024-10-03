import sys
from pathlib import Path
import logging
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel, QMessageBox
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt

# Импортируем окна
from ArticleGenerator.GeneratorWindow import MainWindow
from WordPressPoster.WordPressPosterWindow import WordPressGUI

# Настройка логирования
logging.basicConfig(filename='app.log', level=logging.ERROR,
                    format='%(asctime)s:%(levelname)s:%(message)s')

def resource_path(relative_path):
    """Возвращает правильный путь к ресурсу, поддерживая как исполняемые файлы, так и обычные скрипты"""
    if getattr(sys, 'frozen', False):  # Если приложение скомпилировано
        base_path = Path(sys._MEIPASS)
    else:  # Если это обычный скрипт
        base_path = Path(__file__).parent
    return base_path / relative_path

class MainAppWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Setup the main window
        self.setWindowTitle("Application Launcher")
        self.setGeometry(300, 300, 400, 200)

        # Load the icon using pathlib
        icon_path = resource_path('icons/main_icon.ico')
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Create buttons
        self.generator_button = QPushButton("Article Generator")
        self.wordpress_button = QPushButton("WordPress Poster")

        # Connect buttons to the respective functions
        self.generator_button.clicked.connect(self.show_generator_window)
        self.wordpress_button.clicked.connect(self.show_wordpress_window)

        # Layout for buttons
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Select an application to launch:", alignment=Qt.AlignmentFlag.AlignCenter))
        layout.addWidget(self.generator_button)
        layout.addWidget(self.wordpress_button)

        # Set the central widget
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def show_generator_window(self):
        try:
            # Открываем окно генератора статей
            self.generator_window = MainWindow()
            self.generator_window.show()
        except Exception as e:
            self.show_error(f"Failed to open Article Generator window: {e}")

    def show_wordpress_window(self):
        try:
            # Открываем окно публикации WordPress
            self.wordpress_window = WordPressGUI()
            self.wordpress_window.show()
        except Exception as e:
            self.show_error(f"Failed to open WordPress Poster window: {e}")

    def show_error(self, message):
        # Log the error and display error message
        logging.error(message)
        error_dialog = QMessageBox()
        error_dialog.setIcon(QMessageBox.Icon.Critical)
        error_dialog.setWindowTitle("Error")
        error_dialog.setText(message)
        error_dialog.exec()

def load_styles(app):
    """Загружает стили и применяет их ко всему приложению"""
    style_path = resource_path('style.qss')
    if style_path.exists():
        with open(style_path, "r") as style_file:
            app.setStyleSheet(style_file.read())

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Загружаем стили на уровне всего приложения
    load_styles(app)

    # Create and display the main window
    main_window = MainAppWindow()
    main_window.show()

    sys.exit(app.exec())
