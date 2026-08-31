"""
AI детектор через Google Gemini API
Поддерживает казахский и русский языки
Бесплатно: 1500 запросов/день
"""

import requests
import json
import re
from typing import Dict


class GeminiAIDetector:
    """
    Определяет написан ли текст AI с помощью Gemini.
    Работает с казахским и русским языками.
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"
    FALLBACK_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _call_api(self, url: str, prompt: str) -> dict:
        """Делает запрос к Gemini API."""
        return requests.post(
            f"{url}?key={self.api_key}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 800
                }
            },
            timeout=30
        )

    def detect(self, text: str) -> Dict:
        prompt = f"""Ты эксперт по определению AI-сгенерированных текстов.
Проанализируй текст ниже и определи — написан ли он человеком или сгенерирован AI (ChatGPT, Claude, Gemini и т.д.).

Признаки AI-текста:
- Слишком правильная и однообразная структура предложений
- Типичные AI-фразы: "следует отметить", "таким образом", "в заключение", "қорытындылай келе", "атап өтсек"
- Отсутствие личного голоса, эмоций, ошибок
- Идеальные переходы между абзацами
- Сухой академический стиль без индивидуальности

ТЕКСТ ДЛЯ АНАЛИЗА:
\"\"\"
{text[:3000]}
\"\"\"

Ответь ТОЛЬКО чистым JSON без markdown:
{{
  "ai_percentage": <число от 0 до 100, где 0=точно человек, 100=точно AI>,
  "verdict": "<вердикт на русском>",
  "status": "<одно из: human | mixed | ai>",
  "reasons": ["<причина 1>", "<причина 2>", "<причина 3>"],
  "ai_phrases_found": ["<найденная AI-фраза если есть>"],
  "confidence": "<low | medium | high>"
}}"""

        urls_to_try = [self.BASE_URL, self.FALLBACK_URL]

        for url in urls_to_try:
            try:
                response = self._call_api(url, prompt)

                if response.status_code == 200:
                    data = response.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return self._parse(raw_text)

                elif response.status_code == 503:
                    # Перегрузка — пробуем следующую модель
                    if url == self.FALLBACK_URL:
                        return {"error": "Gemini перегружен, попробуйте через 30 секунд"}
                    continue

                elif response.status_code == 429:
                    return {"error": "Превышен лимит Gemini API — подождите минуту"}

                elif response.status_code == 403:
                    return {"error": "Неверный Gemini API ключ"}

                else:
                    err = response.text[:300] if response.text else ""
                    return {"error": f"Ошибка Gemini API: {response.status_code} — {err}"}

            except requests.exceptions.Timeout:
                if url == self.FALLBACK_URL:
                    return {"error": "Таймаут запроса к Gemini (30 сек)"}
                continue
            except requests.exceptions.ConnectionError:
                return {"error": "Нет соединения с Gemini API"}
            except (KeyError, IndexError) as e:
                return {"error": f"Неожиданный формат ответа: {str(e)}"}
            except Exception as e:
                return {"error": f"Ошибка: {str(e)}"}

    def _parse(self, raw: str) -> Dict:
        cleaned = re.sub(r'```json|```', '', raw).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except Exception:
                    data = {}
            else:
                data = {}

        ai_pct = float(data.get("ai_percentage", 0))
        ai_pct = max(0, min(100, ai_pct))

        return {
            "ai_percentage": round(ai_pct, 1),
            "ai_probability": ai_pct / 100,
            "verdict": data.get("verdict", "Не удалось определить"),
            "status": data.get("status", "unknown"),
            "reasons": data.get("reasons", []),
            "ai_phrases_found": data.get("ai_phrases_found", []),
            "confidence": data.get("confidence", "medium"),
            "method": "gemini_ai_detector"
        }

    def detect_long_text(self, text: str) -> Dict:
        """Для длинных текстов — берём начало, середину и конец."""
        if len(text) <= 3000:
            return self.detect(text)

        # Берём три части текста
        chunk_size = 1000
        start = text[:chunk_size]
        mid_pos = len(text) // 2
        middle = text[mid_pos:mid_pos + chunk_size]
        end = text[-chunk_size:]

        combined = f"{start}\n...\n{middle}\n...\n{end}"
        return self.detect(combined)


# Оставляем для совместимости со старым кодом
ZeroGPTDetector = GeminiAIDetector
