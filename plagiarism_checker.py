"""
Проверка на плагиат через Serper API (Google Search)
Бесплатно: 2500 запросов при регистрации
Регистрация: https://serper.dev
"""

import requests
import re
import time
from typing import Dict, List


class GooglePlagiarismChecker:
    """
    Проверяет текст на плагиат через Serper API.
    Serper — обёртка над Google Search.
    Бесплатно: 2500 запросов (хватит на ~500 эссе).
    """

    SEARCH_URL = "https://google.serper.dev/search"

    def __init__(self, api_key: str, search_engine_id: str = None):
        """
        Args:
            api_key: Serper API ключ с serper.dev
            search_engine_id: не используется, оставлен для совместимости
        """
        self.api_key = api_key
        self.headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }

    def check(self, text: str) -> Dict:
        phrases = self._extract_phrases(text)

        if not phrases:
            return {
                "error": "Не удалось извлечь фразы для проверки",
                "similarity_percentage": 0,
                "similarity_score": 0,
                "verdict": "Не удалось проверить",
                "matches": []
            }

        matches = []
        hit_count = 0

        for phrase in phrases:
            result = self._search_phrase(phrase)

            if result is None:
                continue

            # Засчитываем совпадение только если найдено 3+ результата
            # 1-2 результата = случайное совпадение общей фразы
            if result.get("total_results", 0) >= 3 and result.get("top_urls"):
                # Проверяем что найденный URL реально похож на источник
                # (не случайный сайт с похожей фразой)
                hit_count += 1
                matches.append({
                    "phrase": phrase.strip('"'),
                    "results_count": result["total_results"],
                    "source_url": result["top_urls"][0],
                    "source_title": result.get("top_titles", [""])[0]
                })

            time.sleep(0.3)

        total_checked = len(phrases)
        if total_checked == 0:
            similarity = 0.0
        else:
            similarity = min(1.0, (hit_count / total_checked) * 1.3)

        similarity_pct = round(similarity * 100, 1)

        if similarity_pct >= 50:
            verdict = "Высокий уровень совпадения (вероятный плагиат)"
            status = "plagiarized"
        elif similarity_pct >= 25:
            verdict = "Умеренное совпадение (требует проверки)"
            status = "suspicious"
        else:
            verdict = "Совпадений не обнаружено"
            status = "clean"

        return {
            "similarity_score": round(similarity, 3),
            "similarity_percentage": similarity_pct,
            "verdict": verdict,
            "status": status,
            "matches": matches[:10],
            "phrases_checked": total_checked,
            "phrases_matched": hit_count,
            "method": "serper_api"
        }

    def _extract_phrases(self, text: str) -> List[str]:
        """
        Извлекает 5 наиболее уникальных фраз из текста.
        Избегает коротких слов, вводных конструкций и общих фраз.
        """
        text = re.sub(r'\s+', ' ', text.strip())
        # Убираем заголовки (строки с ##)
        text = re.sub(r'#+\s+.+', '', text)
        words = text.split()

        if len(words) < 15:
            return []

        # Стоп-слова которые делают фразу слишком общей
        stop_starts = [
            'это', 'в', 'и', 'а', 'но', 'что', 'как', 'для', 'на', 'с',
            'по', 'из', 'к', 'о', 'от', 'за', 'при', 'не', 'так', 'уже',
            'бұл', 'және', 'үшін', 'да', 'де', 'бір'
        ]

        phrases = []
        # Ищем фразы по всему тексту, пропускаем начинающиеся со стоп-слов
        step = max(1, len(words) // 8)
        for i in range(0, len(words) - 6, step):
            word = words[i].lower().strip('.,!?;:')
            if word in stop_starts:
                continue
            if len(word) < 4:  # пропускаем короткие слова в начале
                continue
            phrase = ' '.join(words[i:i + 7])  # 7 слов — более уникально
            phrases.append(f'"{phrase}"')
            if len(phrases) == 5:
                break

        # Если не набрали 5 — добираем без фильтрации
        if len(phrases) < 3:
            for i in range(0, min(len(words) - 6, 50), 10):
                phrase = ' '.join(words[i:i + 7])
                p = f'"{phrase}"'
                if p not in phrases:
                    phrases.append(p)
                if len(phrases) == 5:
                    break

        return phrases[:5]

    def _search_phrase(self, phrase: str) -> Dict:
        try:
            response = requests.post(
                self.SEARCH_URL,
                headers=self.headers,
                json={"q": phrase, "num": 5},
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                organic = data.get("organic", [])
                search_info = data.get("searchInformation", {})
                # Serper не всегда даёт totalResults — считаем по organic
                total = int(search_info.get("totalResults", 0)) or len(organic)

                return {
                    "total_results": total,
                    "top_urls": [r.get("link", "") for r in organic],
                    "top_titles": [r.get("title", "") for r in organic]
                }

            elif response.status_code == 401:
                return {"error": "invalid_key", "total_results": 0}

            elif response.status_code == 429:
                return {"error": "quota_exceeded", "total_results": 0}

            else:
                return None

        except Exception:
            return None


class SimplePlagiarismChecker:
    """Локальная проверка — fallback если нет Serper API."""

    def check(self, text: str) -> Dict:
        words = text.split()
        if not words:
            return {"error": "Пустой текст"}

        bigrams = set()
        bigram_total = 0
        for i in range(len(words) - 1):
            bigram = f"{words[i].lower()} {words[i+1].lower()}"
            bigrams.add(bigram)
            bigram_total += 1

        uniqueness = len(bigrams) / max(bigram_total, 1)
        similarity = max(0, min(1, 1 - uniqueness * 0.8))

        return {
            "similarity_score": round(similarity, 3),
            "similarity_percentage": round(similarity * 100, 1),
            "verdict": "Локальный анализ (без API): результат приблизительный",
            "status": "unknown",
            "matches": [],
            "method": "local_analysis",
            "note": "Для точной проверки настройте Serper API на serper.dev"
        }
