# utils/database.py
import sqlite3
import os
import json
import re
import base64
from pathlib import Path
import streamlit as st
import requests

_PROJECT_DIR = Path(__file__).resolve().parent.parent
_DB_DIR = _PROJECT_DIR / "database"
_DB_PATH = _DB_DIR / "vocab_notes.db"
_SCHEMA_PATH = _DB_DIR / "schema.sql"
_DATA_DIR = _PROJECT_DIR / "data"

LEVEL_FREQ_MAP = {
    "Level5.txt": (5, 5),
    "Level4.txt": (4, 2),
    "Level3.txt": (3, 3),
    "Level2.txt": (2, 4),
}

def get_connection() -> sqlite3.Connection:
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_database():
    conn = get_connection()
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()
    conn.executescript(schema)
    conn.commit()
    conn.close()

def log_change(table_name: str, record_id: int, change_type: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO change_log (table_name, record_id, change_type) VALUES (?, ?, ?)",
        (table_name, record_id, change_type)
    )
    conn.commit()
    conn.close()

def get_all_words(level: str = None, frequency: int = None):
    conn = get_connection()
    query = "SELECT * FROM words WHERE 1=1"
    params = []
    if level:
        query += " AND level = ?"
        params.append(level)
    if frequency:
        query += " AND frequency_level = ?"
        params.append(frequency)
    query += " ORDER BY word"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_synonyms(word_id: int):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM synonyms WHERE word_id = ?", (word_id,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_note(word_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM notes WHERE word_id = ?", (word_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def save_note(word_id: int, content: str, recording_path: str = None):
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT note_id, github_sha FROM notes WHERE word_id = ?", (word_id,)
        ).fetchone()
        if existing:
            note_id = existing["note_id"]
            if recording_path:
                conn.execute(
                    "UPDATE notes SET content = ?, recording_path = ?, updated_at = CURRENT_TIMESTAMP WHERE word_id = ?",
                    (content, recording_path, word_id)
                )
            else:
                conn.execute(
                    "UPDATE notes SET content = ?, updated_at = CURRENT_TIMESTAMP WHERE word_id = ?",
                    (content, word_id)
                )
            change_type = "update"
        else:
            conn.execute(
                "INSERT INTO notes (word_id, content, recording_path) VALUES (?, ?, ?)",
                (word_id, content, recording_path)
            )
            note_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            change_type = "insert"
        conn.execute(
            "INSERT INTO change_log (table_name, record_id, change_type) VALUES (?, ?, ?)",
            ("notes", note_id, change_type)
        )
        conn.commit()
    finally:
        conn.close()

def get_settings():
    """
    获取设置，优先级：Streamlit Secrets > 本地数据库 > 默认值
    """
    defaults = {
        "github_token": "",
        "github_repo": "",
        "audio_raw_base": "",
        "dict_url": "https://dict.youdao.com/result?word={word}&lang=en",
        "listen_interval": "3",
        "audio_scan_dir": str(_PROJECT_DIR / "audio_cache"),
    }
    settings = defaults.copy()
    # 从本地数据库读取
    try:
        conn = get_connection()
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        for row in rows:
            settings[row["key"]] = row["value"]
        conn.close()
    except Exception:
        pass
    # 从Streamlit Secrets读取（覆盖数据库和默认值）
    try:
        for key in defaults.keys():
            if key in st.secrets:
                settings[key] = st.secrets[key]
    except Exception:
        pass
    return settings

def set_setting(key: str, value: str):
    conn = get_connection()
    conn.execute("REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def sync_note_to_github(word_id: int, content: str, github_token: str, repo: str, word: str = None, branch: str = "main"):
    """
    将笔记内容通过GitHub API提交到仓库。
    文件名改为 notes/{word}.html，而不是 word_{id}.html。
    """
    if not word:
        conn = get_connection()
        row = conn.execute("SELECT word FROM words WHERE word_id = ?", (word_id,)).fetchone()
        conn.close()
        if not row:
            return False, "Word not found"
        word = row["word"]
    # 清理文件名中的非法字符
    safe_word = re.sub(r'[<>:"/\\|?*]', '_', word)
    safe_word = safe_word.replace(' ', '_')
    file_path = f"notes/{safe_word}.html"
    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = {"Authorization": f"token {github_token}"}
    sha = None
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        sha = r.json().get("sha")
    data = {
        "message": f"Update note for {word}",
        "content": base64.b64encode(content.encode()).decode(),
        "branch": branch
    }
    if sha:
        data["sha"] = sha
    r = requests.put(url, headers=headers, json=data)
    if r.status_code in (200, 201):
        new_sha = r.json()["content"]["sha"]
        conn = get_connection()
        conn.execute("UPDATE notes SET github_sha = ? WHERE word_id = ?", (new_sha, word_id))
        conn.commit()
        conn.close()
        return True, ""
    else:
        return False, r.json().get("message", "Unknown error")

def parse_vocab_line(line: str):
    pattern = r"^\d+\.\s*([a-zA-Z\-'\.]+)\[([^\]]*)\]([a-z]+)\.(.+)"
    m = re.match(pattern, line.strip())
    if m:
        word = m.group(1).strip()
        phonetic = m.group(2).strip()
        pos = m.group(3).strip()
        translation = m.group(4).strip()
        return word, phonetic, pos, translation
    return None

def import_vocab_files():
    conn = get_connection()
    inserted = 0
    skipped = 0
    for filepath in sorted(_DATA_DIR.glob("Level*.txt")):
        fname = filepath.name
        if fname not in LEVEL_FREQ_MAP:
            continue
        level_num, freq_level = LEVEL_FREQ_MAP[fname]
        level_name = f"Level{level_num}"
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                parsed = parse_vocab_line(line)
                if parsed is None:
                    continue
                word, phonetic, pos, translation = parsed
                existing = conn.execute("SELECT word_id FROM words WHERE word = ?", (word,)).fetchone()
                if existing:
                    skipped += 1
                    continue
                conn.execute(
                    "INSERT INTO words (word, level, part_of_speech, translation, phonetic, frequency_level) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (word, level_name, pos, translation, phonetic, freq_level)
                )
                inserted += 1
    conn.commit()
    conn.close()
    return inserted, skipped
