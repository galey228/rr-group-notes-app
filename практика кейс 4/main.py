import sqlite3
import json
import os
from datetime import datetime
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty, NumericProperty
from kivymd.app import MDApp
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import OneLineListItem
from kivymd.uix.label import MDLabel

# ---------- МОДЕЛИ ----------
class Note:
    def __init__(self, note_id, title, date, time, content):
        self.id = note_id
        self.title = title
        self.date = date
        self.time = time
        self.content = content

# ---------- ХРАНИЛИЩЕ: SQLite ----------
class SQLiteStorage:
    def __init__(self, db_path="notes.db"):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                date TEXT,
                time TEXT,
                content TEXT
            )
        ''')
        self.conn.commit()

    def add(self, title, date, time, content):
        self.cursor.execute(
            "INSERT INTO notes (title, date, time, content) VALUES (?, ?, ?, ?)",
            (title, date, time, content)
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def update(self, note_id, title, date, time, content):
        self.cursor.execute(
            "UPDATE notes SET title=?, date=?, time=?, content=? WHERE id=?",
            (title, date, time, content, note_id)
        )
        self.conn.commit()

    def delete(self, note_id):
        self.cursor.execute("DELETE FROM notes WHERE id=?", (note_id,))
        self.conn.commit()

    def get_all(self):
        self.cursor.execute("SELECT id, title, date, time, content FROM notes ORDER BY date DESC, time DESC")
        rows = self.cursor.fetchall()
        return [Note(*row) for row in rows]

    def search(self, query):
        self.cursor.execute(
            "SELECT id, title, date, time, content FROM notes WHERE title LIKE ? OR content LIKE ?",
            (f'%{query}%', f'%{query}%')
        )
        rows = self.cursor.fetchall()
        return [Note(*row) for row in rows]

# ---------- ХРАНИЛИЩЕ: Файловая система (JSON) ----------
class FileStorage:
    def __init__(self, folder="notes_files"):
        self.folder = folder
        if not os.path.exists(folder):
            os.makedirs(folder)

    def _path(self, note_id):
        return os.path.join(self.folder, f"note_{note_id}.json")

    def add(self, title, date, time, content):
        # Находим следующий ID
        existing = [int(f.split('_')[1].split('.')[0]) for f in os.listdir(self.folder) if f.startswith('note_')]
        new_id = max(existing) + 1 if existing else 1
        data = {"id": new_id, "title": title, "date": date, "time": time, "content": content}
        with open(self._path(new_id), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return new_id

    def update(self, note_id, title, date, time, content):
        data = {"id": note_id, "title": title, "date": date, "time": time, "content": content}
        with open(self._path(note_id), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def delete(self, note_id):
        path = self._path(note_id)
        if os.path.exists(path):
            os.remove(path)

    def get_all(self):
        notes = []
        for f in os.listdir(self.folder):
            if f.startswith('note_') and f.endswith('.json'):
                with open(os.path.join(self.folder, f), 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    notes.append(Note(data['id'], data['title'], data['date'], data['time'], data['content']))
        return sorted(notes, key=lambda n: (n.date, n.time), reverse=True)

    def search(self, query):
        all_notes = self.get_all()
        q = query.lower()
        return [n for n in all_notes if q in n.title.lower() or q in n.content.lower()]

# ---------- ЭЛЕМЕНТ СПИСКА ----------
class NoteItem(BoxLayout):
    title_text = StringProperty("")
    date_text = StringProperty("")
    note_id = NumericProperty(0)

# ---------- ЭКРАН ----------
class MainScreen(Screen):
    pass

class CreateDialogContent(BoxLayout):
    pass

# ---------- ПРИЛОЖЕНИЕ ----------
class NotesApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.theme_style = "Light"
        self.sqlite = SQLiteStorage()
        self.file_storage = FileStorage()
        self.current_storage = self.sqlite
        self.storage_name = "SQLite"
        self.dialog = None
        self.editing_id = None  # None = создание, иначе = редактирование
        return Builder.load_file("notes.kv")

    def on_start(self):
        self.refresh_list()

    def toggle_storage(self):
        if self.storage_name == "SQLite":
            self.current_storage = self.file_storage
            self.storage_name = "Файлы (JSON)"
        else:
            self.current_storage = self.sqlite
            self.storage_name = "SQLite"
        self.root.ids.storage_label.text = f"Хранилище: {self.storage_name}"
        self.refresh_list()

    def refresh_list(self, notes=None):
        container = self.root.ids.notes_container
        container.clear_widgets()
        if notes is None:
            notes = self.current_storage.get_all()
        for note in notes:
            item = NoteItem()
            item.title_text = note.title
            item.date_text = f"{note.date} {note.time}"
            item.note_id = note.id
            container.add_widget(item)

    def search_notes(self, query):
        if not query:
            self.refresh_list()
        else:
            results = self.current_storage.search(query)
            self.refresh_list(results)

    def open_create_dialog(self):
        self.editing_id = None
        self.show_dialog("Новая заметка", "", "", "", "")

    def edit_note(self, note_id):
        # Ищем заметку по ID
        all_notes = self.current_storage.get_all()
        note = next((n for n in all_notes if n.id == note_id), None)
        if note:
            self.editing_id = note_id
            self.show_dialog("Редактировать", note.title, note.date, note.time, note.content)

    def show_dialog(self, title, t, d, tm, c):
        content = CreateDialogContent()
        content.ids.title_field.text = t
        content.ids.date_field.text = d
        content.ids.time_field.text = tm
        content.ids.content_field.text = c
        self.dialog = MDDialog(
            title=title,
            type="custom",
            content_cls=content,
            buttons=[],
        )
        self.dialog.open()

    def save_note_from_dialog(self):
        content = self.dialog.content_cls
        title = content.ids.title_field.text.strip()
        date = content.ids.date_field.text.strip()
        time = content.ids.time_field.text.strip()
        body = content.ids.content_field.text.strip()

        if not title:
            return  # заголовок обязателен

        # Если дата/время пустые — ставим текущие
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        if not time:
            time = datetime.now().strftime("%H:%M")

        if self.editing_id is None:
            self.current_storage.add(title, date, time, body)
        else:
            self.current_storage.update(self.editing_id, title, date, time, body)

        self.dialog.dismiss()
        self.editing_id = None
        self.refresh_list()

    def delete_note(self, note_id):
        self.current_storage.delete(note_id)
        self.refresh_list()

if __name__ == "__main__":
    NotesApp().run()