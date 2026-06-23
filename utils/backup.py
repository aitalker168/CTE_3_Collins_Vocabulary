# utils/backup.py
import os
import zipfile
import json
import datetime
from pathlib import Path
import streamlit as st
from utils.database import get_connection

_PROJECT_DIR = Path(__file__).resolve().parent.parent
_DB_PATH = _PROJECT_DIR / "database" / "vocab_notes.db"
_AUDIO_CACHE_DIR = _PROJECT_DIR / "audio_cache"
_USER_RECORDINGS_DIR = _PROJECT_DIR / "user_recordings"
_BACKUP_DIR = _PROJECT_DIR / "backup"

def perform_full_backup() -> Path:
    """全局完整备份：打包数据库+音频缓存+录音为zip"""
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = _BACKUP_DIR / f"full_backup_{timestamp}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 添加数据库
        if _DB_PATH.exists():
            zf.write(_DB_PATH, "database/vocab_notes.db")
        # 添加音频缓存
        if _AUDIO_CACHE_DIR.exists():
            for fpath in _AUDIO_CACHE_DIR.rglob("*"):
                if fpath.is_file():
                    zf.write(fpath, fpath.relative_to(_PROJECT_DIR))
        # 添加录音
        if _USER_RECORDINGS_DIR.exists():
            for fpath in _USER_RECORDINGS_DIR.rglob("*"):
                if fpath.is_file():
                    zf.write(fpath, fpath.relative_to(_PROJECT_DIR))
    return zip_path

def perform_incremental_backup() -> Path:
    """增量备份：导出变更记录JSON + 新增音频文件"""
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = _BACKUP_DIR / f"incremental_{timestamp}.zip"

    conn = get_connection()
    pending = conn.execute(
        "SELECT * FROM change_log WHERE backup_status='pending' ORDER BY change_id"
    ).fetchall()

    # 收集需要备份的变更记录
    changes = []
    audio_files = set()
    for row in pending:
        row = dict(row)
        changes.append(row)
        # 如果是insert/update的notes且有录音文件，需打包录音
        if row["table_name"] == "notes" and row["change_type"] in ("insert", "update"):
            note = conn.execute("SELECT recording_path FROM notes WHERE note_id=?", (row["record_id"],)).fetchone()
            if note and note["recording_path"]:
                audio_files.add(note["recording_path"])
        # 如果是words或synonyms有新的音频缓存？但音频缓存不在变更日志中，我们额外扫描audio_cache中修改时间晚于上次备份的文件
        # 这里简化：仅处理notes录音；音频缓存可加入全局备份

    conn.close()

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 写入变更JSON
        changes_json = json.dumps(changes, ensure_ascii=False, indent=2, default=str)
        zf.writestr("changes.json", changes_json)
        # 写入涉及的录音文件
        for audio_path in audio_files:
            full_path = _PROJECT_DIR / audio_path
            if full_path.exists():
                zf.write(full_path, audio_path)

    # 标记已备份
    conn = get_connection()
    conn.execute("UPDATE change_log SET backup_status='backed_up' WHERE backup_status='pending'")
    conn.commit()
    conn.close()

    return zip_path

def restore_from_backup(zip_path: Path, restore_type: str = "full"):
    """
    从备份恢复。
    restore_type: "full" 完整恢复（覆盖数据库、音频、录音）
                   "incremental" 增量恢复（仅应用changes.json）
    """
    if not zip_path.exists():
        raise FileNotFoundError("备份文件不存在")
    with zipfile.ZipFile(zip_path, 'r') as zf:
        if restore_type == "full":
            # 解压所有文件到项目根目录（覆盖已存在文件）
            zf.extractall(_PROJECT_DIR)
            # 注意：数据库被覆盖后需要重新连接
        else:
            # 增量恢复：读取changes.json
            if "changes.json" in zf.namelist():
                data = json.loads(zf.read("changes.json"))
                # 这里简化处理：直接执行INSERT/UPDATE（需根据记录重建）
                # 实际需解析每个change，重新应用数据（此处占位）
                pass
            # 解压音频文件
            for name in zf.namelist():
                if name.startswith("user_recordings/") or name.startswith("audio_cache/"):
                    zf.extract(name, _PROJECT_DIR)
    return True