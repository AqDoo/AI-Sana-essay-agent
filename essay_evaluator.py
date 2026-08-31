"""
Оценщик качества эссе через Google Gemini API
Бесплатный план: 1500 запросов/день, 15 запросов/минуту
Ключ: https://aistudio.google.com/app/apikey
Поддерживает казахский и русский языки
"""

import json
import re
import requests
from typing import Dict


class EssayEvaluator:
    """
    Оценивает качество эссе с помощью Gemini 1.5 Flash.
    Полностью бесплатно в рамках лимитов Google AI Studio.
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"
    FALLBACK_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

    def __init__(self, api_key: str):
        """
        Args:
            api_key: Gemini API ключ с aistudio.google.com/app/apikey
        """
        self.api_key = api_key

    def evaluate(self, text: str, language: str = "auto") -> Dict:
        """
        Оценивает эссе по 4 критериям (по 25 баллов каждый).

        Args:
            text: Текст эссе
            language: 'kz' | 'ru' | 'auto'

        Returns:
            Dict с оценками и обратной связью
        """
        prompt = self._build_prompt(text, language)
        urls_to_try = [self.BASE_URL, self.FALLBACK_URL]

        for url in urls_to_try:
            try:
                response = requests.post(
                    f"{url}?key={self.api_key}",
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0.2,
                            "maxOutputTokens": 1500
                        }
                    },
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return self._parse_response(raw_text, text)

                elif response.status_code == 503:
                    if url == self.FALLBACK_URL:
                        return {"error": "Gemini перегружен, попробуйте через 30 секунд"}
                    continue

                elif response.status_code == 403:
                    return {"error": "Неверный Gemini API ключ"}

                elif response.status_code == 429:
                    return {"error": "Превышен лимит Gemini (15 запросов/мин) — подождите минуту"}

                else:
                    err_text = response.text[:300] if response.text else "нет текста"
                    return {"error": f"Ошибка Gemini API: {response.status_code} — {err_text}"}

            except requests.exceptions.Timeout:
                if url == self.FALLBACK_URL:
                    return {"error": "Таймаут запроса к Gemini (30 сек)"}
                continue
            except requests.exceptions.ConnectionError:
                return {"error": "Нет соединения с Gemini API — проверьте интернет или VPN"}
            except (KeyError, IndexError):
                return {"error": "Неожиданный формат ответа от Gemini"}
            except Exception as e:
                return {"error": f"Ошибка: {str(e)}"}

    def _build_prompt(self, text: str, language: str) -> str:

        if language == "kz":
            lang_note = "Текст написан на казахском языке. Оценивай с учётом норм казахского языка."
        elif language == "ru":
            lang_note = "Текст написан на русском языке."
        else:
            lang_note = "Определи язык текста (казахский или русский) и оценивай соответственно."

        return f"""Ты — опытный преподаватель, оценивающий письменные работы.
{lang_note}

Оцени эссе по 4 критериям от 0 до 25 баллов каждый.

КРИТЕРИИ:
1. Грамматика (0-25): правильность языка, пунктуация, орфография
2. Структура (0-25): логичность, введение/основная часть/заключение, связность
3. Содержание (0-25): раскрытие темы, аргументация, глубина мысли
4. Стиль (0-25): богатство лексики, разнообразие конструкций, читаемость

ТЕКСТ:
\"\"\"
{text[:3000]}
\"\"\"

Ответь ТОЛЬКО чистым JSON без markdown и без пояснений вне JSON:
{{
  "language_detected": "kz или ru или other",
  "grammar": <число 0-25>,
  "structure": <число 0-25>,
  "content": <число 0-25>,
  "style": <число 0-25>,
  "grammar_comment": "<комментарий 1-2 предложения на русском>",
  "structure_comment": "<комментарий 1-2 предложения на русском>",
  "content_comment": "<комментарий 1-2 предложения на русском>",
  "style_comment": "<комментарий 1-2 предложения на русском>",
  "strengths": ["<сильная сторона 1>", "<сильная сторона 2>"],
  "improvements": ["<что улучшить 1>", "<что улучшить 2>"],
  "general_feedback": "<общий вывод 2-3 предложения>"
}}"""

    def _parse_response(self, raw_text: str, original_text: str) -> Dict:
        """Парсит ответ Gemini."""

        # Убираем markdown-блоки если Gemini их добавил
        cleaned = re.sub(r'```json|```', '', raw_text).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Пробуем найти JSON внутри текста
            match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except Exception:
                    data = {}
            else:
                data = {}

        grammar = max(0, min(25, int(data.get("grammar", 15))))
        structure = max(0, min(25, int(data.get("structure", 15))))
        content = max(0, min(25, int(data.get("content", 15))))
        style = max(0, min(25, int(data.get("style", 15))))
        total = grammar + structure + content + style

        if total >= 90:
            grade, grade_letter = "Отлично", "A"
        elif total >= 75:
            grade, grade_letter = "Хорошо", "B"
        elif total >= 60:
            grade, grade_letter = "Удовлетворительно", "C"
        else:
            grade, grade_letter = "Требует доработки", "D"

        words = original_text.split()
        sentences = [s.strip() for s in re.split(r'[.!?]', original_text) if s.strip()]

        return {
            "grammar": grammar,
            "structure": structure,
            "content": content,
            "style": style,
            "total": total,
            "grade": grade,
            "grade_letter": grade_letter,
            "language_detected": data.get("language_detected", "unknown"),
            "grammar_comment": data.get("grammar_comment", ""),
            "structure_comment": data.get("structure_comment", ""),
            "content_comment": data.get("content_comment", ""),
            "style_comment": data.get("style_comment", ""),
            "strengths": data.get("strengths", []),
            "improvements": data.get("improvements", []),
            "general_feedback": data.get("general_feedback", ""),
            "word_count": len(words),
            "sentence_count": len(sentences),
            "avg_sentence_length": round(len(words) / max(len(sentences), 1), 1),
            "method": "gemini_api"
        }
