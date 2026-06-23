# utils/ai_exercise.py
import json
import requests
import base64
import streamlit as st
from utils.database import get_connection

# 固定使用 GitHub Models（无需用户配置）
GITHUB_MODELS_BASE_URL = "https://models.inference.ai.azure.com"
GITHUB_MODELS_MODEL = "gpt-4o"  # GitHub Models 默认分配

def generate_exercises(word: str, translation: str, synonyms: list,
                       github_token: str) -> list:
    """
    使用 GitHub Token 调用 GitHub Models 生成5道练习题。
    """
    syn_text = "、".join(synonyms) if synonyms else "无"
    prompt = f"""你是一位英语词汇老师。请根据以下单词生成5道练习题（可以是填空或选择题），同时给出正确答案。题目和答案必须用中文说明。
单词：{word}
中文释义：{translation}
同义词：{syn_text}
要求：
- 题目类型可混合：选择题或填空题
- 每道题包含题干、选项（如果是选择）、正确答案
- 答案必须明确给出
- 以JSON数组格式返回，每个元素包含字段：question（题干）, type（"choice"或"fill"）, options（列表，选择题时提供）, answer（正确答案）"""

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GITHUB_MODELS_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 2000
    }

    try:
        resp = requests.post(f"{GITHUB_MODELS_BASE_URL}/v1/chat/completions",
                              headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        # 尝试解析JSON（模型可能会返回markdown代码块）
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        questions = json.loads(content)
        return questions
    except Exception as e:
        st.error(f"生成练习题失败：{str(e)}")
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