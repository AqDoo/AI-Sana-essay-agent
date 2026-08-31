"""
AI Агент «Оценивание письменных работ»
Версия: 2.0 — Реальные API (без демо и рандома)

Используемые API:
- Gemini API       → AI детекция + оценка качества
- Google Search API → Проверка плагиата (100 запросов/день бесплатно)
- Claude API (Haiku)→ Оценка качества эссе

Запуск:
    streamlit run app.py
"""

import streamlit as st
import time
import os
from datetime import datetime

# Загружаем наши модули
from ai_detector import GeminiAIDetector
from plagiarism_checker import GooglePlagiarismChecker, SimplePlagiarismChecker
from essay_evaluator import EssayEvaluator
from word_report import generate_report, read_docx
from dotenv import load_dotenv
load_dotenv()

# ──────────────────────────────────────────
# КОНФИГУРАЦИЯ
# ──────────────────────────────────────────

st.set_page_config(
    page_title="Оценка письменных работ",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ──────────────────────────────────────────
# ПРОСТАЯ ЗАЩИТА ПАРОЛЕМ (опционально)
# Включается, если в .env / переменных окружения задан APP_PASSWORD.
# Если APP_PASSWORD не задан — приложение работает без пароля (как раньше).
# ──────────────────────────────────────────

_app_password = os.environ.get("APP_PASSWORD", "")

if _app_password:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔒 Вход")
        entered = st.text_input("Пароль доступа:", type="password")
        col_a, col_b = st.columns([1, 5])
        with col_a:
            login_clicked = st.button("Войти", type="primary")
        if login_clicked:
            if entered == _app_password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Неверный пароль")
        st.stop()

# Стили
st.markdown("""
<style>
    .metric-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
        border: 1px solid #e9ecef;
    }
    .score-big {
        font-size: 2rem;
        font-weight: 700;
        margin: 0;
    }
    .score-label {
        font-size: 0.8rem;
        color: #6c757d;
        margin: 0;
    }
    .result-section {
        background: #ffffff;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        border: 1px solid #e9ecef;
    }
    .status-ai { color: #dc3545; }
    .status-human { color: #198754; }
    .status-mixed { color: #fd7e14; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────
# БОКОВАЯ ПАНЕЛЬ — НАСТРОЙКА КЛЮЧЕЙ
# ──────────────────────────────────────────

with st.sidebar:
    st.title("⚙️ Настройки API")

    st.markdown("### 🔑 API Ключи")
    st.caption("Все ключи хранятся только в сессии браузера")

    # Gemini — один ключ для всего (детекция + оценка качества)
    with st.expander("🧠 Gemini API (детекция + оценка)", expanded=True):
        gemini_key = st.text_input(
            "Gemini API Key",
            type="password",
            value=os.environ.get("GEMINI_API_KEY", ""),
            placeholder="AIzaSy...",
            help="aistudio.google.com/app/apikey — бесплатно"
        )
        st.caption("Бесплатно: 1500 запросов/день · Казахский ✅ Русский ✅")
        st.markdown("[Получить ключ →](https://aistudio.google.com/app/apikey)", unsafe_allow_html=False)

    # Serper
    with st.expander("🔍 Serper API (плагиат)"):
        google_key = st.text_input(
            "Serper API Key",
            type="password",
            value=os.environ.get("SERPER_API_KEY", ""),
            placeholder="Вставьте ваш Serper API ключ",
            help="serper.dev → Register → 2500 запросов бесплатно"
        )
        google_cx = ""
        st.caption("Бесплатно: 2500 запросов (~500 эссе)")
        st.markdown("[Получить ключ →](https://serper.dev)", unsafe_allow_html=False)

    st.divider()

    # Статус API
    st.markdown("### 📊 Статус")
    col1, col2, col3 = st.columns(3)
    col1.metric("AI детекция", "✅" if gemini_key else "❌")
    col2.metric("Плагиат", "✅" if google_key else "⚠️")
    col3.metric("Качество", "✅" if gemini_key else "❌")

    if not google_key:
        st.caption("⚠️ Без Serper API используется упрощённая проверка плагиата")

    st.divider()

    # Инструкция
    with st.expander("📖 Как получить ключи"):
        st.markdown("""
**ZeroGPT (бесплатно):**
1. zerogpt.com/api
2. Зарегистрируйтесь
3. API Keys → Create

**Google Search (бесплатно):**
1. console.cloud.google.com
2. Включите "Custom Search JSON API"
3. Создайте ключ
4. cse.google.com/cse → новый поиск
5. Скопируйте Search Engine ID

**Gemini (бесплатно):**
1. aistudio.google.com/app/apikey
2. Войдите через Google аккаунт
3. "Create API key" → готово
""")


# ──────────────────────────────────────────
# ГЛАВНАЯ ОБЛАСТЬ
# ──────────────────────────────────────────

st.title("📝 AI Агент — Оценка письменных работ")
st.caption("Казахский и русский языки · Реальный AI анализ без случайных данных")

st.divider()

# Ввод текста
col_left, col_right = st.columns([3, 1])

with col_left:
    # Имя студента (опционально)
    student_name = st.text_input(
        "Имя студента (необязательно):",
        placeholder="Например: Айгерим Сейткали",
        help="Будет указано в отчёте"
    )

    tab1, tab2 = st.tabs(["✍️ Ввести текст", "📄 Загрузить файл (.txt или .docx)"])

    with tab1:
        essay_text = st.text_area(
            "Текст эссе:",
            height=250,
            placeholder="Вставьте эссе на казахском или русском языке...\n\nМинимум 100 слов для корректного анализа.",
            label_visibility="collapsed"
        )

    with tab2:
        uploaded = st.file_uploader(
            "Файл .txt или .docx",
            type=["txt", "docx"],
            help="Поддерживаются текстовые и Word файлы"
        )
        if uploaded:
            try:
                if uploaded.name.endswith(".docx"):
                    essay_text = read_docx(uploaded.read())
                    st.success(f"Загружено из Word: {len(essay_text)} символов")
                else:
                    try:
                        essay_text = uploaded.read().decode("utf-8")
                    except UnicodeDecodeError:
                        uploaded.seek(0)
                        essay_text = uploaded.read().decode("cp1251")
                    st.success(f"Загружено: {len(essay_text)} символов")

                with st.expander("Просмотр текста"):
                    st.text(essay_text[:1000] + ("..." if len(essay_text) > 1000 else ""))
            except Exception as e:
                st.error(f"Не удалось прочитать файл: {e}")
                essay_text = ""

with col_right:
    st.markdown("**Статистика**")
    if essay_text:
        words = essay_text.split()
        sentences = [s for s in essay_text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
        st.metric("Слов", len(words))
        st.metric("Предложений", len(sentences))
        st.metric("Символов", len(essay_text))

        if len(words) < 50:
            st.warning("Мало слов для анализа")
        elif len(words) < 100:
            st.info("Короткий текст")
        else:
            st.success("Достаточный объём")
    else:
        st.info("Введите текст")

st.divider()

# Кнопка запуска
if not essay_text or len(essay_text.strip()) < 50:
    st.button("🔍 Анализировать", type="primary", disabled=True, use_container_width=False)
    if essay_text:
        st.error("Текст слишком короткий. Минимум 50 символов.")
else:
    run_btn = st.button("🔍 Анализировать эссе", type="primary")

    if run_btn:
        if not gemini_key:
            st.error("❌ Укажите Gemini API ключ в боковой панели")
            st.stop()
        if not gemini_key:
            st.error("❌ Укажите Gemini API ключ в боковой панели")
            st.stop()

        # ──────────────────────────────
        # АНАЛИЗ
        # ──────────────────────────────
        st.divider()
        st.markdown("## 🔄 Анализ...")

        results = {}
        errors = []

        progress = st.progress(0)
        status = st.empty()

        # 1. Оценка качества (Gemini)
        status.markdown("**1/3** — Оценка качества текста через Gemini...")
        try:
            evaluator = EssayEvaluator(api_key=gemini_key)
            quality = evaluator.evaluate(essay_text)
            if "error" in quality:
                errors.append(f"Оценка качества: {quality['error']}")
                results["quality"] = None
            else:
                results["quality"] = quality
        except Exception as e:
            errors.append(f"Оценка качества: {str(e)}")
            results["quality"] = None
        progress.progress(33)

        # 2. AI детекция (ZeroGPT)
        status.markdown("**2/3** — Проверка на AI-генерацию (Gemini)...")
        try:
            detector = GeminiAIDetector(api_key=gemini_key)
            ai_result = detector.detect_long_text(essay_text)
            if "error" in ai_result:
                errors.append(f"AI детекция: {ai_result['error']}")
                results["ai"] = None
            else:
                results["ai"] = ai_result
        except Exception as e:
            errors.append(f"AI детекция: {str(e)}")
            results["ai"] = None
        progress.progress(66)

        # 3. Плагиат
        status.markdown("**3/3** — Проверка на плагиат...")
        try:
            if google_key:
                plagiarism_checker = GooglePlagiarismChecker(
                    api_key=google_key,
                    search_engine_id=""
                )
                plagiarism = plagiarism_checker.check(essay_text)
            else:
                simple_checker = SimplePlagiarismChecker()
                plagiarism = simple_checker.check(essay_text)

            results["plagiarism"] = plagiarism
        except Exception as e:
            errors.append(f"Проверка плагиата: {str(e)}")
            results["plagiarism"] = None
        progress.progress(100)

        status.empty()
        progress.empty()

        # ──────────────────────────────
        # ВЫВОД РЕЗУЛЬТАТОВ
        # ──────────────────────────────

        if errors:
            with st.expander(f"⚠️ {len(errors)} ошибок при анализе"):
                for err in errors:
                    st.warning(err)

        st.markdown("## 📊 Результаты анализа")
        st.caption(f"Проверено: {datetime.now().strftime('%d.%m.%Y %H:%M')}")

        # ── БЛОК: Общая оценка ──
        if results.get("quality"):
            q = results["quality"]
            st.markdown("### 🎯 Оценка качества текста")

            col1, col2, col3, col4, col5 = st.columns(5)

            def score_color(score, max_score=25):
                pct = score / max_score
                if pct >= 0.8:
                    return "#198754"
                elif pct >= 0.6:
                    return "#fd7e14"
                else:
                    return "#dc3545"

            for col, label, score in [
                (col1, "Грамматика", q["grammar"]),
                (col2, "Структура", q["structure"]),
                (col3, "Содержание", q["content"]),
                (col4, "Стиль", q["style"]),
            ]:
                color = score_color(score)
                col.markdown(
                    f"""<div class="metric-card">
                        <p class="score-label">{label}</p>
                        <p class="score-big" style="color:{color}">{score}</p>
                        <p class="score-label">из 25</p>
                    </div>""",
                    unsafe_allow_html=True
                )

            total_color = score_color(q["total"], 100)
            col5.markdown(
                f"""<div class="metric-card" style="background:#fff3cd">
                    <p class="score-label">ИТОГО ({q['grade_letter']})</p>
                    <p class="score-big" style="color:{total_color}">{q['total']}</p>
                    <p class="score-label">из 100 · {q['grade']}</p>
                </div>""",
                unsafe_allow_html=True
            )

            st.markdown("")

            # Комментарии по критериям
            with st.expander("📋 Подробные комментарии по критериям"):
                for criterion, label, comment_key in [
                    ("grammar", "Грамматика", "grammar_comment"),
                    ("structure", "Структура", "structure_comment"),
                    ("content", "Содержание", "content_comment"),
                    ("style", "Стиль", "style_comment"),
                ]:
                    score = q[criterion]
                    comment = q.get(comment_key, "")
                    color = score_color(score)
                    st.markdown(
                        f"**{label}: {score}/25** <span style='color:{color}'>{'●' * min(score // 5, 5)}</span>",
                        unsafe_allow_html=True
                    )
                    if comment:
                        st.caption(comment)
                    st.markdown("")

            # Обратная связь
            col_fb1, col_fb2 = st.columns(2)
            with col_fb1:
                if q.get("strengths"):
                    st.markdown("**✅ Сильные стороны:**")
                    for s in q["strengths"]:
                        st.markdown(f"- {s}")
            with col_fb2:
                if q.get("improvements"):
                    st.markdown("**📌 Что улучшить:**")
                    for imp in q["improvements"]:
                        st.markdown(f"- {imp}")

            if q.get("general_feedback"):
                st.info(f"💬 {q['general_feedback']}")

            # Статистика
            st.caption(
                f"Язык: {q.get('language_detected', '?').upper()} · "
                f"Слов: {q['word_count']} · "
                f"Предложений: {q['sentence_count']} · "
                f"Ср. длина предложения: {q['avg_sentence_length']} слов"
            )

        st.divider()

        # ── БЛОК: AI Детекция ──
        if results.get("ai"):
            ai = results["ai"]
            st.markdown("### 🤖 AI-детекция (Gemini)")

            ai_pct = ai["ai_percentage"]
            status_class = ai.get("status", "human")

            col_ai1, col_ai2 = st.columns([1, 2])
            with col_ai1:
                if status_class == "ai":
                    st.error(f"**{ai['verdict']}**")
                elif status_class == "mixed":
                    st.warning(f"**{ai['verdict']}**")
                else:
                    st.success(f"**{ai['verdict']}**")

                st.metric("Вероятность AI", f"{ai_pct:.1f}%")

            with col_ai2:
                st.progress(ai_pct / 100)
                st.caption("0% = написано человеком · 100% = написано AI")

                if ai.get("ai_sentences_count", 0) > 0:
                    st.caption(f"Предложений с признаками AI: {ai['ai_sentences_count']}")

            if ai.get("ai_sentences") and len(ai["ai_sentences"]) > 0:
                with st.expander("📍 Фрагменты с признаками AI-генерации"):
                    for sent in ai["ai_sentences"]:
                        st.markdown(f"> {sent}")

            st.caption(f"Метод: {ai.get('method', 'gemini')}")
        elif results.get("ai") is None and "AI детекция" not in " ".join(errors):
            st.warning("🤖 AI-детекция: результат недоступен")

        st.divider()

        # ── БЛОК: Плагиат ──
        if results.get("plagiarism"):
            plag = results["plagiarism"]
            st.markdown("### 🔎 Проверка на плагиат")

            plag_pct = plag.get("similarity_percentage", 0)
            plag_status = plag.get("status", "unknown")

            col_p1, col_p2 = st.columns([1, 2])
            with col_p1:
                if plag_status == "plagiarized":
                    st.error(f"**{plag['verdict']}**")
                elif plag_status == "suspicious":
                    st.warning(f"**{plag['verdict']}**")
                elif plag_status == "clean":
                    st.success(f"**{plag['verdict']}**")
                else:
                    st.info(f"**{plag['verdict']}**")

                st.metric("Совпадение", f"{plag_pct:.1f}%")

            with col_p2:
                st.progress(min(plag_pct / 100, 1.0))
                st.caption("0% = оригинальный текст · 100% = полное совпадение")

                if plag.get("phrases_checked"):
                    st.caption(
                        f"Проверено фраз: {plag['phrases_checked']} · "
                        f"Совпадений: {plag.get('phrases_matched', 0)}"
                    )

            if plag.get("matches"):
                with st.expander(f"🔗 Найденные совпадения ({len(plag['matches'])})"):
                    for match in plag["matches"]:
                        phrase = match.get("phrase", "").strip('"')
                        url = match.get("source_url", "")
                        title = match.get("source_title", url)
                        count = match.get("results_count", 0)

                        st.markdown(f"**Фраза:** `{phrase}`")
                        if url:
                            st.markdown(f"[{title}]({url})")
                        if count:
                            st.caption(f"Результатов в Google: {count:,}")
                        st.markdown("---")

            if plag.get("note"):
                st.info(plag["note"])

            st.caption(f"Метод: {plag.get('method', 'unknown')}")

        st.divider()

        # ── СКАЧАТЬ ОТЧЁТ ──
        st.markdown("### 📥 Скачать отчёт")

        report_lines = [
            "=" * 60,
            "ОТЧЁТ ОЦЕНКИ ПИСЬМЕННОЙ РАБОТЫ",
            f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            "=" * 60,
            "",
        ]

        if results.get("quality"):
            q = results["quality"]
            report_lines += [
                "ОЦЕНКА КАЧЕСТВА:",
                f"  Грамматика : {q['grammar']}/25",
                f"  Структура  : {q['structure']}/25",
                f"  Содержание : {q['content']}/25",
                f"  Стиль      : {q['style']}/25",
                f"  ИТОГО      : {q['total']}/100 ({q['grade']})",
                f"  Язык       : {q.get('language_detected', '?').upper()}",
                "",
            ]
            if q.get("general_feedback"):
                report_lines += [
                    "ОБЩИЙ ВЫВОД:",
                    f"  {q['general_feedback']}",
                    "",
                ]

        if results.get("ai"):
            ai = results["ai"]
            report_lines += [
                "AI ДЕТЕКЦИЯ (Gemini):",
                f"  Вероятность AI : {ai['ai_percentage']:.1f}%",
                f"  Вердикт        : {ai['verdict']}",
                "",
            ]

        if results.get("plagiarism"):
            plag = results["plagiarism"]
            report_lines += [
                "ПРОВЕРКА НА ПЛАГИАТ:",
                f"  Совпадение : {plag.get('similarity_percentage', 0):.1f}%",
                f"  Вердикт    : {plag.get('verdict', '')}",
                "",
            ]

        report_lines += [
            "=" * 60,
            "ИСХОДНЫЙ ТЕКСТ:",
            essay_text,
        ]

        report_text = "\n".join(report_lines)

        col_dl1, col_dl2 = st.columns(2)

        with col_dl1:
            st.download_button(
                "💾 Скачать отчёт (.txt)",
                data=report_text.encode("utf-8"),
                file_name=f"essay_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain",
                use_container_width=True
            )

        with col_dl2:
            try:
                word_bytes = generate_report(
                    essay_text=essay_text,
                    quality=results.get("quality"),
                    ai_result=results.get("ai"),
                    plagiarism=results.get("plagiarism"),
                    student_name=student_name
                )
                st.download_button(
                    "📄 Скачать отчёт (.docx)",
                    data=word_bytes,
                    file_name=f"essay_report_{datetime.now().strftime('%Y%m%d_%H%M')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Ошибка генерации Word: {e}")
