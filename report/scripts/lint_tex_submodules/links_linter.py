import re
from collections import OrderedDict
from pathlib import Path
from .lint_logging import warning, info

# Глобальное состояние
ALL_CITATIONS = set()  # Все ключи цитат из текстовых файлов
FIRST_OCCURRENCE = (
    OrderedDict()
)  # Порядок первого упоминания: ключ -> (file_index, pos_in_file)
FILE_ORDER = [
    "abstract.pdf",
    "intro.pdf",
    "analytic_part.pdf",
    "design_part.pdf",
    "tech_part.pdf",
    "experimental_part.pdf",
    "conclusion.pdf",
    "additions.pdf",
]


def process_bibliography_order(text, filepath):
    """
    Обрабатывает файл для контроля порядка источников.
    Для текстовых файлов: собирает информацию о цитатах.
    Для links.tex: проверяет соответствие и переупорядочивает \bibitem.

    Аргументы:
    text: str - содержимое файла
    filepath: str или Path - путь к файлу
    """
    # Получаем имя файла без расширения
    if isinstance(filepath, Path):
        filename = filepath.stem
    else:
        filename = Path(filepath).stem

    # Обработка текстовых файлов (сбор цитат)
    if filename != "links":
        return _process_text_file(text, filename)

    # Обработка links.tex (финальная проверка и сортировка)
    return _process_links_file(text, filepath)


def _process_text_file(text, filename):
    """Собирает информацию о цитатах в текстовых файлах"""
    global ALL_CITATIONS, FIRST_OCCURRENCE

    # Определяем приоритет файла
    file_index = (
        FILE_ORDER.index(filename) if filename in FILE_ORDER else len(FILE_ORDER)
    )

    # Ищем все цитаты вида \cite{key1,key2}
    citations = []
    for match in re.finditer(r"\\cite\{([^}]*)\}", text):
        keys = [k.strip() for k in match.group(1).split(",") if k.strip()]
        citations.extend(keys)

    # Запоминаем первые вхождения
    for pos, key in enumerate(citations):
        ALL_CITATIONS.add(key)
        if key not in FIRST_OCCURRENCE:
            FIRST_OCCURRENCE[key] = (file_index, pos)

    return 0, text  # В текстовых файлах замен нет


def _process_links_file(text, filepath):
    """Проверяет и переупорядочивает источники в links.tex"""
    global ALL_CITATIONS, FIRST_OCCURRENCE

    # Извлекаем все \bibitem
    bib_items = {}
    bib_order = []
    current_key = None
    buffer = []

    # Ищем начало и конец окружения thebibliography
    env_start = text.find(r"\begin{thebibliography}")
    env_end = text.find(r"\end{thebibliography}")
    if env_start == -1 or env_end == -1:
        warning(f"{filepath}: не найдено окружение thebibliography")
        return 0, text

    # Обрабатываем содержимое окружения
    env_content = text[env_start:env_end]
    lines = env_content.splitlines()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(r"\bibitem{"):
            # Сохраняем предыдущий элемент
            if current_key is not None and buffer:
                bib_items[current_key] = "\n".join(buffer)
                bib_order.append(current_key)
                buffer = []

            # Начинаем новый элемент
            match = re.match(r"\\bibitem\{([^}]*)\}(.*)", stripped)
            if match:
                current_key = match.group(1).strip()
                # Сохраняем полную строку с отступами
                buffer.append(line)
            else:
                current_key = None
                buffer = []
        elif current_key is not None:
            buffer.append(line)

    # Сохраняем последний элемент
    if current_key is not None and buffer:
        bib_items[current_key] = "\n".join(buffer)
        bib_order.append(current_key)

    # Проверка 1: Источники в тексте, но нет в links.tex
    missing_in_links = [key for key in ALL_CITATIONS if key not in bib_items]
    for key in missing_in_links:
        warning(
            f"{filepath}: источник '{key}' упомянут в тексте, но отсутствует в списке литературы"
        )

    # Проверка 2: Источники в links.tex, но нет в тексте
    missing_in_text = [key for key in bib_items if key not in ALL_CITATIONS]
    for key in missing_in_text:
        warning(
            f"{filepath}: источник '{key}' есть в списке литературы, но не упомянут в тексте"
        )

    # Формируем правильный порядок
    ordered_keys = [
        k for k in FIRST_OCCURRENCE if k in bib_items
    ]  # В порядке первого упоминания
    remaining_keys = [
        k for k in bib_order if k not in ordered_keys
    ]  # Остальные в исходном порядке
    new_order = ordered_keys + remaining_keys

    # Если порядок не изменился - выходим
    if new_order == bib_order:
        return 0, text

    # Собираем новое содержимое окружения
    new_env_lines = []
    for key in new_order:
        new_env_lines.append(bib_items[key])

    # Формируем новое окружение
    new_env_content = "\n".join(new_env_lines)
    full_env_content = (
        r"\begin{thebibliography}{}"
        + "\n\t\\vspace{-1\\baselineskip}\n\n"
        + new_env_content
        + "\n\n\\end{thebibliography}"
    )

    # Собираем финальный текст
    new_text = (
        text[:env_start]
        + full_env_content
        + text[env_end + len(r"\end{thebibliography}") :]
    )
    count_reordered = len(ordered_keys)
    info(
        f"{filepath}: переупорядочено {count_reordered} источников (всего: {len(new_order)})"
    )

    # Очищаем состояние после обработки
    ALL_CITATIONS.clear()
    FIRST_OCCURRENCE.clear()

    return 0, new_text
