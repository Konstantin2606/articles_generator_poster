import sys
import json
import os
import traceback
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout, QWidget,
    QFileDialog, QLineEdit, QComboBox, QTextEdit
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from article_generator import ArticleGenerator  # Импортируем генератор статей ArticleGenerator.


SETTINGS_FILE_PATH = os.path.join('settings', 'app_settings.json')


class WorkerThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self, data_folder, api_key_file, output_folder, prompt_file, min_chars, model_name, language):
        super().__init__()
        self.data_folder = data_folder
        self.api_key_file = api_key_file
        self.output_folder = output_folder
        self.prompt_file = prompt_file
        self.min_chars = min_chars
        self.model_name = model_name
        self.language = language

    def run(self):
        try:
            generator = ArticleGenerator(
                self.data_folder,
                self.api_key_file,
                self.output_folder,
                self.prompt_file,
                self.min_chars,
                model_name=self.model_name,
                language=self.language,
                log_output=self.log_signal.emit
            )

            # Генерация статей
            generator.generate_articles()

            self.finished_signal.emit(True)
        except Exception as e:
            error_message = f'Ошибка в процессе генерации: {str(e)}\n{traceback.format_exc()}'
            self.log_signal.emit(error_message)
            self.finished_signal.emit(False)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('Генератор SEO статей')
        self.setGeometry(100, 100, 400, 600)
        icon_path = os.path.join('icons', 'main_icon.ico')
        self.setWindowIcon(QIcon(icon_path))

        self.api_key_file = ''
        self.output_folder = ''
        self.prompt_file = ''
        self.keyword_file = ''
        self.min_chars = None

        self.layout = QVBoxLayout()
        self.init_ui()

        container = QWidget()
        container.setLayout(self.layout)
        self.setCentralWidget(container)

        self.load_settings()
        self.thread = None

    def init_ui(self):
        grid_layout = QGridLayout()

        self.api_key_label = QLabel('Путь к файлу с API ключом:')
        self.api_key_path = QLineEdit()
        self.api_key_button = QPushButton('Обзор...')
        self.api_key_button.clicked.connect(self.select_api_key_file)

        self.prompt_label = QLabel('Путь к файлу с промптом:')
        self.prompt_path = QLineEdit()
        self.prompt_button = QPushButton('Обзор...')
        self.prompt_button.clicked.connect(self.select_prompt_file)

        self.output_folder_label = QLabel('Папка для сохранения статей:')
        self.output_folder_path = QLineEdit()
        self.output_folder_button = QPushButton('Обзор...')
        self.output_folder_button.clicked.connect(self.select_output_folder)

        self.keyword_file_label = QLabel('Файл с ключевыми словами:')
        self.keyword_file_path = QLineEdit()
        self.keyword_file_button = QPushButton('Обзор...')
        self.keyword_file_button.clicked.connect(self.select_keyword_file)

        self.min_chars_label = QLabel('Минимальное количество символов для статьи:')
        self.min_chars_input = QLineEdit()
        self.min_chars_input.setPlaceholderText('Введите минимум символов')

        self.model_label = QLabel('Выберите модель:')
        self.model_combo = QComboBox()
        self.model_combo.addItems(['gpt-4o-mini', 'deepseek-chat'])
        self.model_combo.setCurrentText('gpt-4o-mini')

        self.language_label = QLabel('Выберите язык генерации:')
        self.language_combo = QComboBox()
        self.language_combo.addItems(['English', 'German', 'French', 'Custom'])
        self.language_input = QLineEdit()
        self.language_input.setPlaceholderText('Введите свой язык на английском (с заглавной буквы)')
        self.language_input.setEnabled(False)
        self.language_combo.currentIndexChanged.connect(self.toggle_custom_language)

        self.start_button = QPushButton('Запустить генерацию')
        self.start_button.clicked.connect(self.start_process)

        self.save_button = QPushButton('Сохранить настройки')
        self.save_button.clicked.connect(self.save_settings)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)

        grid_layout.addWidget(self.api_key_label, 0, 0)
        grid_layout.addWidget(self.api_key_path, 0, 1)
        grid_layout.addWidget(self.api_key_button, 0, 2)

        grid_layout.addWidget(self.prompt_label, 1, 0)
        grid_layout.addWidget(self.prompt_path, 1, 1)
        grid_layout.addWidget(self.prompt_button, 1, 2)

        grid_layout.addWidget(self.output_folder_label, 2, 0)
        grid_layout.addWidget(self.output_folder_path, 2, 1)
        grid_layout.addWidget(self.output_folder_button, 2, 2)

        grid_layout.addWidget(self.keyword_file_label, 3, 0)
        grid_layout.addWidget(self.keyword_file_path, 3, 1)
        grid_layout.addWidget(self.keyword_file_button, 3, 2)

        grid_layout.addWidget(self.min_chars_label, 4, 0)
        grid_layout.addWidget(self.min_chars_input, 4, 1)

        grid_layout.addWidget(self.model_label, 5, 0)
        grid_layout.addWidget(self.model_combo, 5, 1)

        grid_layout.addWidget(self.language_label, 6, 0)
        grid_layout.addWidget(self.language_combo, 6, 1)
        grid_layout.addWidget(self.language_input, 7, 0, 1, 2)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.save_button)

        self.layout.addLayout(grid_layout)
        self.layout.addLayout(button_layout)
        self.layout.addWidget(QLabel('Логи:', self), alignment=Qt.AlignmentFlag.AlignLeft)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.addWidget(self.log_output)

    def toggle_custom_language(self):
        is_custom = self.language_combo.currentText() == 'Custom'
        self.language_input.setEnabled(is_custom)

    def select_api_key_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Выберите файл с API ключом", "", "Текстовые файлы (*.txt)")
        if file:
            self.api_key_file = os.path.relpath(file)
            self.api_key_path.setText(self.api_key_file)
            self.log_output.append(f'Выбран файл с API ключом: {self.api_key_file}')
            QApplication.processEvents()

    def select_prompt_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Выберите файл с промптом", "", "Текстовые файлы (*.txt)")
        if file:
            self.prompt_file = os.path.relpath(file)
            self.prompt_path.setText(self.prompt_file)
            self.log_output.append(f'Выбран файл с промптом: {self.prompt_file}')
            QApplication.processEvents()

    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку для сохранения")
        if folder:
            self.output_folder = os.path.relpath(folder)
            self.output_folder_path.setText(self.output_folder)
            self.log_output.append(f'Выбрана папка для сохранения: {self.output_folder}')
            QApplication.processEvents()

    def select_keyword_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Выберите файл с ключевыми словами", "", "Текстовые файлы (*.txt)")
        if file:
            self.keyword_file = os.path.relpath(file)
            self.keyword_file_path.setText(self.keyword_file)
            self.log_output.append(f'Выбран файл с ключевыми словами: {self.keyword_file}')
            QApplication.processEvents()

    def save_settings(self):
        settings = {
            'api_key_file': self.api_key_file,
            'output_folder': self.output_folder,
            'prompt_file': self.prompt_file,
            'keyword_file': self.keyword_file,
            'min_chars': self.min_chars_input.text(),
            'model_name': self.model_combo.currentText(),
            'language': self.language_combo.currentText() if self.language_combo.currentText() != 'Custom' else self.language_input.text(),
        }
        os.makedirs(os.path.dirname(SETTINGS_FILE_PATH), exist_ok=True)
        with open(SETTINGS_FILE_PATH, 'w') as file:
            json.dump(settings, file, indent=4)
        self.log_output.append('Настройки сохранены')
        self.log_output.append(f'Сохранённые настройки: {settings}')
        QApplication.processEvents()

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE_PATH):
            self.log_output.append('Загрузка настроек...')
            try:
                with open(SETTINGS_FILE_PATH, 'r') as file:
                    settings = json.load(file)
                    self.api_key_file = settings.get('api_key_file', '')
                    self.output_folder = settings.get('output_folder', '')
                    self.prompt_file = settings.get('prompt_file', '')
                    self.keyword_file = settings.get('keyword_file', '')
                    self.min_chars = settings.get('min_chars', '')

                    self.api_key_path.setText(self.api_key_file)
                    self.output_folder_path.setText(self.output_folder)
                    self.prompt_path.setText(self.prompt_file)
                    self.keyword_file_path.setText(self.keyword_file)
                    self.min_chars_input.setText(self.min_chars)

                    self.model_combo.setCurrentText(settings.get('model_name', 'gpt-4o-mini'))
                    language = settings.get('language', 'English')

                    if language in ['English', 'German', 'French']:
                        self.language_combo.setCurrentText(language)
                    else:
                        self.language_combo.setCurrentText('Custom')
                        self.language_input.setText(language)

                    self.log_output.append(f'Загруженные настройки: {settings}')
            except Exception as e:
                error_message = f'Ошибка загрузки настроек: {str(e)}\n{traceback.format_exc()}'
                self.log_output.append(error_message)
                QApplication.processEvents()
        else:
            self.log_output.append('Файл настроек не найден. Используются настройки по умолчанию.')
            QApplication.processEvents()

    def start_process(self):
        if not self.api_key_file or not self.output_folder or not self.prompt_file or not self.keyword_file or not self.min_chars_input.text():
            self.log_output.append('Пожалуйста, выберите необходимые файлы, папки и введите минимальное количество символов')
            return

        try:
            min_chars = int(self.min_chars_input.text()) if self.min_chars_input.text() else None
            model_name = self.model_combo.currentText()
            language = self.language_combo.currentText() if self.language_combo.currentText() != 'Custom' else self.language_input.text()

            self.thread = WorkerThread(self.keyword_file, self.api_key_file, self.output_folder, self.prompt_file, min_chars, model_name, language)
            self.thread.log_signal.connect(self.log_output.append)
            self.thread.finished_signal.connect(self.on_process_finished)
            self.thread.start()

            self.start_button.setEnabled(False)
        except Exception as e:
            error_message = f'Ошибка при запуске процесса: {str(e)}\n{traceback.format_exc()}'
            self.log_output.append(error_message)
            QApplication.processEvents()

    def on_process_finished(self, success):
        if success:
            self.log_output.append('Процесс завершен успешно')
        else:
            self.log_output.append('Процесс завершился с ошибкой')
        self.start_button.setEnabled(True)
        QApplication.processEvents()

    def closeEvent(self, event):
        if self.thread is not None and self.thread.isRunning():
            self.thread.wait()
        event.accept()

def load_styles(app):
    style_path = os.path.join(os.getcwd(), 'style.qss')
    if os.path.exists(style_path):
        with open(style_path, "r") as style_file:
            app.setStyleSheet(style_file.read())

if __name__ == '__main__':
    app = QApplication(sys.argv)
    load_styles(app)
    base_path = os.path.dirname(os.path.abspath(__file__))
    style_path = os.path.join(base_path, 'style.qss')
    if os.path.exists(style_path):
        with open(style_path, "r") as style_file:
            app.setStyleSheet(style_file.read())

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
