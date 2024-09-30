import os
import sys
import json
import asyncio
import logging
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox, QCheckBox, QPlainTextEdit)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from WordPressPoster import WordPressPoster  # Импортируем класс WordPressPoster

class WordPressPosterThread(QThread):
    finished = pyqtSignal()

    def __init__(self, wp_poster):
        super().__init__()
        self.wp_poster = wp_poster

    def run(self):
        asyncio.run(self.wp_poster.process_sites_with_batches())
        self.finished.emit()

class WordPressGUI(QWidget):
    def __init__(self):
        super().__init__()

        # Путь к файлу настроек
        self.settings_folder = os.path.join(os.getcwd(), "settings")
        self.settings_file = os.path.join(self.settings_folder, "settings.json")

        # Логи приложения
        self.logger = self.setup_logger()

        # Элементы интерфейса
        self.initUI()

        # Загрузка настроек
        self.load_settings()

        # Инициализация переменных для WordPressPoster и потока
        self.wp_poster = None
        self.thread = None

        # Флаг для отслеживания ошибок
        self.has_errors = False

    def setup_logger(self):
        """Настройка логирования"""
        logger = logging.getLogger('WordPressPosterLogger')
        logger.setLevel(logging.DEBUG)

        # Логгер в файл
        file_handler = logging.FileHandler('wordpress_poster.log')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)

        # Логгер для командной строки
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(file_formatter)

        # Добавляем обработчики
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        return logger

    def initUI(self):
        self.setWindowTitle('WordPress Poster')
        self.setGeometry(100, 100, 600, 400)

        self.base_folder_label = QLabel('Sites Folder Path:')
        self.base_folder_input = QLineEdit()
        self.base_folder_button = QPushButton('Browse')
        self.base_folder_button.clicked.connect(self.browse_base_folder)

        self.credentials_file_label = QLabel('Credentials File Path:')
        self.credentials_file_input = QLineEdit()
        self.credentials_file_button = QPushButton('Browse')
        self.credentials_file_button.clicked.connect(self.browse_credentials_file)

        self.db_file_label = QLabel('Database File Path (optional):')
        self.db_file_input = QLineEdit()
        self.db_file_button = QPushButton('Browse')
        self.db_file_button.clicked.connect(self.browse_db_file)

        self.advanced_settings_checkbox = QCheckBox('Show Advanced Settings')
        self.advanced_settings_checkbox.stateChanged.connect(self.toggle_advanced_settings)

        self.batch_size_label = QLabel('Batch Size:')
        self.batch_size_input = QLineEdit()
        self.pause_label = QLabel('Pause Between Batches (s):')
        self.pause_input = QLineEdit()

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)

        self.start_button = QPushButton('Start')
        self.stop_button = QPushButton('Stop')
        self.save_button = QPushButton('Save Settings')

        layout = QVBoxLayout()

        base_folder_layout = QHBoxLayout()
        base_folder_layout.addWidget(self.base_folder_label)
        base_folder_layout.addWidget(self.base_folder_input)
        base_folder_layout.addWidget(self.base_folder_button)
        layout.addLayout(base_folder_layout)

        credentials_layout = QHBoxLayout()
        credentials_layout.addWidget(self.credentials_file_label)
        credentials_layout.addWidget(self.credentials_file_input)
        credentials_layout.addWidget(self.credentials_file_button)
        layout.addLayout(credentials_layout)

        db_file_layout = QHBoxLayout()
        db_file_layout.addWidget(self.db_file_label)
        db_file_layout.addWidget(self.db_file_input)
        db_file_layout.addWidget(self.db_file_button)
        layout.addLayout(db_file_layout)

        layout.addWidget(self.advanced_settings_checkbox)

        self.advanced_settings_layout = QVBoxLayout()
        self.advanced_settings_layout.addWidget(self.batch_size_label)
        self.advanced_settings_layout.addWidget(self.batch_size_input)
        self.advanced_settings_layout.addWidget(self.pause_label)
        self.advanced_settings_layout.addWidget(self.pause_input)
        self.advanced_settings_layout.setContentsMargins(20, 0, 20, 0)

        self.batch_size_label.hide()
        self.batch_size_input.hide()
        self.pause_label.hide()
        self.pause_input.hide()

        layout.addLayout(self.advanced_settings_layout)
        layout.addWidget(self.log_output)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.start_button)
        buttons_layout.addWidget(self.stop_button)
        layout.addLayout(buttons_layout)

        layout.addWidget(self.save_button)

        self.setLayout(layout)

        self.start_button.clicked.connect(self.start_poster)
        self.stop_button.clicked.connect(self.stop_poster)
        self.save_button.clicked.connect(self.save_settings)

    def toggle_advanced_settings(self):
        if self.advanced_settings_checkbox.isChecked():
            self.batch_size_label.show()
            self.batch_size_input.show()
            self.pause_label.show()
            self.pause_input.show()
        else:
            self.batch_size_label.hide()
            self.batch_size_input.hide()
            self.pause_label.hide()
            self.pause_input.hide()

    def browse_base_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, 'Select Base Folder')
        if folder_path:
            self.base_folder_input.setText(folder_path)

    def browse_credentials_file(self):
        file_path = QFileDialog.getOpenFileName(self, 'Select Credentials File', '', 'Text Files (*.txt)')[0]
        if file_path:
            self.credentials_file_input.setText(file_path)

    def browse_db_file(self):
        file_path = QFileDialog.getOpenFileName(self, 'Select Database File', '', 'Database Files (*.db)')[0]
        if file_path:
            self.db_file_input.setText(file_path)

    def load_settings(self):
        if not os.path.exists(self.settings_folder):
            os.makedirs(self.settings_folder)

        if os.path.exists(self.settings_file):
            with open(self.settings_file, 'r') as f:
                settings = json.load(f)
                self.batch_size_input.setText(str(settings.get('batch_size', '5')))
                self.pause_input.setText(str(settings.get('pause_between_batches', '10')))
                self.base_folder_input.setText(settings.get('base_folder', ''))
                self.credentials_file_input.setText(settings.get('credentials_file', ''))
                self.db_file_input.setText(settings.get('db_file', ''))
        else:
            self.batch_size_input.setText('5')
            self.pause_input.setText('10')

    def save_settings(self):
        settings = {
            'batch_size': int(self.batch_size_input.text()),
            'pause_between_batches': int(self.pause_input.text()),
            'base_folder': self.base_folder_input.text(),
            'credentials_file': self.credentials_file_input.text(),
            'db_file': self.db_file_input.text()
        }

        with open(self.settings_file, 'w') as f:
            json.dump(settings, f)

        QMessageBox.information(self, 'Settings Saved', 'Settings have been saved successfully!')

    def log_message(self, message, level="INFO"):
        color = "black"
        if level == "ERROR":
            color = "red"
            self.has_errors = True
        elif level == "WARNING":
            color = "orange"

        self.log_output.appendHtml(f'<span style="color:{color}">{message}</span>')
        self.log_output.repaint()

        if level == "ERROR":
            self.logger.error(message)
        elif level == "WARNING":
            self.logger.warning(message)
        else:
            self.logger.info(message)

    def start_poster(self):
        try:
            self.has_errors = False
            batch_size = int(self.batch_size_input.text())
            pause_between_batches = int(self.pause_input.text())
            base_folder = self.base_folder_input.text()
            credentials_file = self.credentials_file_input.text()
            db_file = self.db_file_input.text()

            if not db_file:
                db_file = os.path.join(os.getcwd(), "post_tracking.db")
                self.db_file_input.setText(db_file)

            if not os.path.exists(base_folder) or not os.path.isfile(credentials_file):
                self.log_message("One or more paths are invalid.", "ERROR")
                QMessageBox.critical(self, 'Error', 'One or more paths are invalid.')
                return

            self.wp_poster = WordPressPoster(base_folder, credentials_file, db_file, batch_size=batch_size, pause_between_batches=pause_between_batches, logger=self.logger)

            self.thread = WordPressPosterThread(self.wp_poster)
            self.thread.start()
            self.thread.finished.connect(self.on_poster_finished)
            self.log_message('WordPress Poster started successfully!', "INFO")

        except ValueError:
            self.log_message('Invalid input for batch size or pause.', "ERROR")
            QMessageBox.critical(self, 'Error', 'Invalid input for batch size or pause.')

    def stop_poster(self):
        if self.thread:
            self.wp_poster.stop()
            self.log_message('WordPress Poster stopped successfully!', "INFO")
            QMessageBox.information(self, 'Stopped', 'WordPress Poster stopped successfully!')

    def on_poster_finished(self):
        if self.has_errors:
            self.log_message('WordPress Poster finished with errors.', "ERROR")
            QMessageBox.warning(self, 'Finished', 'WordPress Poster finished with errors.')
        else:
            self.log_message('WordPress Poster finished successfully!', "INFO")
            QMessageBox.information(self, 'Finished', 'WordPress Poster finished successfully!')
        self.thread = None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = WordPressGUI()
    gui.show()
    sys.exit(app.exec())
