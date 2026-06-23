-- database/schema.sql
-- 词汇主表
CREATE TABLE IF NOT EXISTS words (
    word_id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT UNIQUE NOT NULL,
    level TEXT NOT NULL,
    part_of_speech TEXT,
    translation TEXT,
    phonetic TEXT,
    audio_path TEXT,           -- 本地缓存路径，如 audio_cache/Level3/beautiful.mp3
    frequency_level INTEGER    -- 柯林斯词频等级：5/4/3/2/1
);

-- 同义词表
CREATE TABLE IF NOT EXISTS synonyms (
    syn_id INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id INTEGER NOT NULL,
    synonym TEXT NOT NULL,
    translation TEXT,
    phonetic TEXT,
    audio_path TEXT,
    FOREIGN KEY (word_id) REFERENCES words(word_id) ON DELETE CASCADE
);

-- 笔记表
CREATE TABLE IF NOT EXISTS notes (
    note_id INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id INTEGER NOT NULL,
    content TEXT,               -- 富文本 HTML
    recording_path TEXT,        -- 用户录音文件路径（user_recordings/word_id_timestamp.mp3）
    github_sha TEXT,            -- 云端同步时的GitHub文件SHA（用于更新已存在的文件）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (word_id) REFERENCES words(word_id) ON DELETE CASCADE
);

-- 练习题表
CREATE TABLE IF NOT EXISTS exercises (
    exercise_id INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id INTEGER NOT NULL,
    question_json TEXT,         -- 5道题及答案的 JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (word_id) REFERENCES words(word_id) ON DELETE CASCADE
);

-- 变更日志表（用于增量备份）
CREATE TABLE IF NOT EXISTS change_log (
    change_id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    record_id INTEGER NOT NULL,
    change_type TEXT NOT NULL,      -- 'insert', 'update', 'delete'
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    backup_status TEXT DEFAULT 'pending'
);

-- 设置表（用于存储云端配置等）
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);