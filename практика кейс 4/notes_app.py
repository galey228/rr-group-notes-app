import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
import json
import os
from datetime import datetime

# ---------- ХРАНИЛИЩЕ SQLite ----------
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
            (title, date, time, content))
        self.conn.commit()
        return self.cursor.lastrowid

    def update(self, nid, title, date, time, content):
        self.cursor.execute(
            "UPDATE notes SET title=?, date=?, time=?, content=? WHERE id=?",
            (title, date, time, content, nid))
        self.conn.commit()

    def delete(self, nid):
        self.cursor.execute("DELETE FROM notes WHERE id=?", (nid,))
        self.conn.commit()

    def get_all(self):
        self.cursor.execute("SELECT id, title, date, time, content FROM notes ORDER BY date DESC, time DESC")
        return self.cursor.fetchall()

    def search(self, q):
        self.cursor.execute(
            "SELECT id, title, date, time, content FROM notes WHERE title LIKE ? OR content LIKE ?",
            (f'%{q}%', f'%{q}%'))
        return self.cursor.fetchall()

# ---------- ХРАНИЛИЩЕ: файловая система (JSON) ----------
class FileStorage:
    def __init__(self, folder="notes_files"):
        self.folder = folder
        if not os.path.exists(folder):
            os.makedirs(folder)

    def _path(self, nid):
        return os.path.join(self.folder, f"note_{nid}.json")

    def _next_id(self):
        existing = [int(f.split('_')[1].split('.')[0])
                    for f in os.listdir(self.folder) if f.startswith('note_')]
        return max(existing) + 1 if existing else 1

    def add(self, title, date, time, content):
        nid = self._next_id()
        with open(self._path(nid), 'w', encoding='utf-8') as f:
            json.dump({"id": nid, "title": title, "date": date,
                       "time": time, "content": content},
                      f, ensure_ascii=False, indent=2)
        return nid

    def update(self, nid, title, date, time, content):
        with open(self._path(nid), 'w', encoding='utf-8') as f:
            json.dump({"id": nid, "title": title, "date": date,
                       "time": time, "content": content},
                      f, ensure_ascii=False, indent=2)

    def delete(self, nid):
        p = self._path(nid)
        if os.path.exists(p):
            os.remove(p)

    def get_all(self):
        result = []
        for f in os.listdir(self.folder):
            if f.startswith('note_') and f.endswith('.json'):
                with open(os.path.join(self.folder, f), 'r', encoding='utf-8') as file:
                    d = json.load(file)
                    result.append((d['id'], d['title'], d['date'], d['time'], d['content']))
        return sorted(result, key=lambda x: (x[2], x[3]), reverse=True)

    def search(self, q):
        q = q.lower()
        return [n for n in self.get_all() if q in n[1].lower() or q in n[4].lower()]

# ---------- ГЛАВНОЕ ПРИЛОЖЕНИЕ ----------
class NotesApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Заметки РР-Групп")
        self.root.geometry("800x600")

        self.sqlite = SQLiteStorage()
        self.file_storage = FileStorage()
        self.storage = self.sqlite
        self.storage_name = "SQLite"

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Верхняя панель
        top = tk.Frame(self.root, bg="#1976D2", height=50)
        top.pack(fill=tk.X)
        tk.Label(top, text="Заметки РР-Групп", font=("Arial", 16, "bold"),
                 fg="white", bg="#1976D2").pack(side=tk.LEFT, padx=10, pady=10)

        self.storage_btn = tk.Button(top, text="Хранилище: SQLite",
                                     command=self.toggle_storage)
        self.storage_btn.pack(side=tk.RIGHT, padx=10)
        tk.Button(top, text="+ Новая", command=self.add_note).pack(side=tk.RIGHT, padx=5)

        # Поиск
        search_frame = tk.Frame(self.root, pady=10)
        search_frame.pack(fill=tk.X, padx=10)
        tk.Label(search_frame, text="Поиск:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh())
        tk.Entry(search_frame, textvariable=self.search_var, width=40).pack(side=tk.LEFT, padx=5)
        tk.Button(search_frame, text="Сброс", command=lambda: self.search_var.set("")).pack(side=tk.LEFT)

        # Таблица заметок
        self.tree = ttk.Treeview(self.root, columns=("id", "title", "date", "time", "content"),
                                 show="headings", height=18)
        for c, h, w in [("id", "ID", 40), ("title", "Заголовок", 200),
                        ("date", "Дата", 100), ("time", "Время", 80),
                        ("content", "Содержание", 300)]:
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Кнопки управления
        btn_frame = tk.Frame(self.root, pady=10)
        btn_frame.pack(fill=tk.X, padx=10)
        tk.Button(btn_frame, text="Редактировать", command=self.edit_note,
                  bg="#FFA726", width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Удалить", command=self.delete_note,
                  bg="#EF5350", fg="white", width=15).pack(side=tk.LEFT, padx=5)

    def toggle_storage(self):
        if self.storage_name == "SQLite":
            self.storage = self.file_storage
            self.storage_name = "Файлы (JSON)"
        else:
            self.storage = self.sqlite
            self.storage_name = "SQLite"
        self.storage_btn.config(text=f"Хранилище: {self.storage_name}")
        self.refresh()

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        q = self.search_var.get().strip()
        notes = self.storage.search(q) if q else self.storage.get_all()
        for n in notes:
            self.tree.insert("", tk.END, values=n)

    def add_note(self):
        self._open_edit_dialog(None)

    def edit_note(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Внимание", "Выберите заметку")
            return
        nid = int(self.tree.item(sel[0])['values'][0])
        note = next((n for n in self.storage.get_all() if n[0] == nid), None)
        if note:
            self._open_edit_dialog(note)

    def delete_note(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Внимание", "Выберите заметку")
            return
        nid = int(self.tree.item(sel[0])['values'][0])
        if messagebox.askyesno("Удаление", "Удалить заметку?"):
            self.storage.delete(nid)
            self.refresh()

    def _open_edit_dialog(self, note):
        win = tk.Toplevel(self.root)
        win.title("Редактирование" if note else "Новая заметка")
        win.geometry("500x400")

        labels = ["Заголовок:", "Дата (ГГГГ-ММ-ДД):", "Время (ЧЧ:ММ):", "Содержание:"]
        entries = []
        for i, lbl in enumerate(labels):
            tk.Label(win, text=lbl).pack(anchor="w", padx=10, pady=(10 if i == 0 else 5, 0))
            if lbl == "Содержание:":
                e = tk.Text(win, height=8, width=55)
            else:
                e = tk.Entry(win, width=55)
            e.pack(padx=10)
            entries.append(e)

        if note:
            entries[0].insert(0, note[1])
            entries[1].insert(0, note[2])
            entries[2].insert(0, note[3])
            entries[3].insert("1.0", note[4])

        def save():
            title = entries[0].get().strip()
            date = entries[1].get().strip() or datetime.now().strftime("%Y-%m-%d")
            tm = entries[2].get().strip() or datetime.now().strftime("%H:%M")
            content = entries[3].get("1.0", tk.END).strip()
            if not title:
                messagebox.showerror("Ошибка", "Заголовок обязателен")
                return
            if note:
                self.storage.update(note[0], title, date, tm, content)
            else:
                self.storage.add(title, date, tm, content)
            win.destroy()
            self.refresh()

        tk.Button(win, text="Сохранить", command=save,
                  bg="#4CAF50", fg="white", width=20).pack(pady=15)

if __name__ == "__main__":
    root = tk.Tk()
    app = NotesApp(root)
    root.mainloop()