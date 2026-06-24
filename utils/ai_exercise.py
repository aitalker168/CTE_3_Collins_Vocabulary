# utils/ai_exercise.py
import json
import requests
import base64
import streamlit as st
from utils.database import get_connection

GITHUB_MODELS_BASE_URL = "https://models.inference.ai.azure.com"
CHAT_COMPLETIONS_URL = f"{GITHUB_MODELS_BASE_URL}/chat/completions"
CHAT_MODEL = "gpt-4o"

def generate_exercises(word: str, translation: str, synonyms: list,
                       github_token: str) -> list:
    """生成5道练习题，难度从易到难递增"""
    syn_text = "、".join(synonyms) if synonyms else "无"
    prompt = f"""你是一位英语词汇老师。请根据以下单词生成5道练习题，难度必须从易到难逐渐递增（第一题最容易，第五题最难）。
单词：{word}
中文释义：{translation}
同义词：{syn_text}

要求：
- 总共5道题，每题难度逐级上升
- 题目类型可混合：选择题或填空题
- 每道题必须包含中文翻译
- 每道题包含题干、选项（如果是选择题）、正确答案、中文翻译
- 答案必须明确给出
- 以JSON数组格式返回，每个元素包含字段：question（题干）, type（"choice"或"fill"）, options（列表，选择题时提供）, answer（正确答案）, chinese_translation（中文翻译）
- 确保严格按难度顺序排列，第一题最简单，第五题最难。"""

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": CHAT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 3000
    }

    try:
        resp = requests.post(CHAT_COMPLETIONS_URL,
                              headers=headers, json=payload, timeout=30)
        if resp.status_code == 401:
            st.error("GitHub Models 认证失败。请确保Token是Classic Token并已勾选'read:user'权限。")
            return []
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        questions = json.loads(content)
        return questions
    except Exception as e:
        st.error(f"生成练习题失败：{str(e)}")
        return []

def generate_synonyms(word: str, translation: str, github_token: str) -> list:
    """
    调用 AI 为指定单词生成最多2个同义词，返回列表。
    每个同义词包含：synonym（单词）、phonetic（音标）、part_of_speech（词性）、translation（中文释义）。
    """
    prompt = f"""请为英语单词 "{word}"（中文释义：{translation}）提供最多2个常见的同义词（synonyms）。
每个同义词必须提供以下信息：
- synonym：同义词单词
- phonetic：音标（用方括号括起，例如 [ˈbjuːtɪfl]）
- part_of_speech：词性（如 adj., v., n. 等）
- translation：中文释义

要求：
- 最多返回2个同义词，如果该单词没有合适的同义词则返回空数组。
- 必须返回有效的 JSON 数组格式，每个元素包含上述四个字段。
- 仅返回 JSON，不要额外解释。"""

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": CHAT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 500
    }

    try:
        resp = requests.post(CHAT_COMPLETIONS_URL,
                              headers=headers, json=payload, timeout=15)
        if resp.status_code != 200:
            return []
        content = resp.json()["choices"][0]["message"]["content"]
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        syns = json.loads(content)
        if not isinstance(syns, list):
            return []
        # 确保每个元素包含必要字段
        valid_syns = []
        for s in syns[:2]:
            if isinstance(s, dict) and "synonym" in s:
                valid_syns.append({
                    "synonym": s.get("synonym", ""),
                    "phonetic": s.get("phonetic", ""),
                    "part_of_speech": s.get("part_of_speech", ""),
                    "translation": s.get("translation", "")
                })
        return valid_syns
    except Exception:
        return []

def save_exercises_to_github(word_id: int, questions: list,
                               github_token: str, repo: str, branch: str = "main"):
    """将练习题以JSON文件提交到GitHub仓库"""
    file_path = f"exercises/word_{word_id}.json"
    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = {"Authorization": f"token {github_token}"}
    content = json.dumps(questions, ensure_ascii=False, indent=2)
    data = {
        "message": f"Add exercises for word {word_id}",
        "content": base64.b64encode(content.encode()).decode(),
        "branch": branch
    }
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        data["sha"] = r.json()["sha"]
    r = requests.put(url, headers=headers, json=data)
    return r.status_code in (200, 201)
