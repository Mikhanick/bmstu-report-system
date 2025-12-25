#!/usr/bin/env python3
import sys
import re
from pathlib import Path
from lint_tex_submodules.lint_logging import warning, error, info
from lint_tex_submodules.list_puctuation import fix_lists
from lint_tex_submodules.links_linter import process_bibliography_order
from lint_tex_submodules.gde_formatting import format_variables_enumerate
from lint_tex_submodules.bibitem_formatting import BibliographyValidator, validate_single_entry


# ========================
# Правила
# ========================

def check_forbidden_words(text, filepath):
    """Проверяет текст на наличие запрещённых слов из массива FORBIDDEN_WORDS"""

    FORBIDDEN_WORDS = [
        'рассмотрим',
        'обозначим',
        'эксперим',
        'примем',
        ' мы ',
    ]

    errors_found = 0
    for i, line in enumerate(text.splitlines(), start=1):
        for word in FORBIDDEN_WORDS:
            if re.search(re.escape(word), line, re.IGNORECASE):
                error(f"{filepath}:{i}: запрещённое слово '{word}'")
                errors_found = 1
    return errors_found, text

def replace_typographic_symbols(text, filepath):
    replacements = {
        "«": "<<",
        "»": ">>",
        "“": "<<",
        "”": ">>",
        "„": "<<",
        "‟": ">>",
        "❝": "<<",
        "❞": ">>",
        "…": "...",
        "×": r" $\times$ ",
        " \leq ": " \leqslant ",
        " \geq ": " \geqslant ",
        "™": r"\texttrademark",
    }
    new_text = text
    for old, new in replacements.items():
        new_text = new_text.replace(old, new)
    if new_text != text:
        info(f"{filepath}: заменены типографские символы")
        return 0, new_text
    return 0, text

def replace_typographic_dashes(text, filepath):
    changed = False
    if '—' in text:
        text = text.replace('—', '---')
        changed = True
    if '–' in text:
        text = text.replace('–', '--')
        changed = True
    if changed:
        info(f"{filepath}: заменены типографские тире")
        return 0, text
    return 0, text

def replace_space_before_citations(text, filepath):
    pattern = r' (\\(?:ref|cite|eqref|vref|pageref|autoref|cref|Cref)\b)'
    new_text, count = re.subn(pattern, r'~\1', text)
    if count > 0:
        info(f"{filepath}: заменены пробелы на ~ перед ссылками ({count} шт.)")
        return 0, new_text
    return 0, text


def replace_words_with_yo(text, filepath):
    """Заменяет слова с неправильной буквой 'е' на слова с правильной буквой 'ё', сохраняя регистр."""
    # Словарь с неправильными и правильными словами (в нижнем регистре)
    replacements = {
        "ее": "её",
        "еще": "ещё",
        "ребер": "рёбер",
        "посещенную": "посещённую",
        "посещенных": "посещённых",
        "учет": "учёт",
        "путем": "путём",
        "дает": "даёт",
        "счет": "счёт",
        "усредненные": "усреднённые",
        "усредненное": "усреднённое",
        "растет": "растёт",
        "проведенный": "проведённый",
        "проведенных": "проведённых",
        "ведется": "ведётся",
        "определенной": "определённой",
        "трудоемкость": "трудоёмкость",
        "трудоемкости": "трудоёмкости",
        "остается": "остаётся",
        "проведен": "проведён",
        "коммивояжер": "коммивояжёр",
        "коммивояжера": "коммивояжёра",
        "учетом": "учётом",
        "ребрах": "рёбрах",
        "создает": "создаёт",
        "проведенное": "проведённое",
        "счетчик": "счётчик",
        "посещенн": "посещённ",
    }

    total_replacements = 0

    def apply_case(original, replacement):
        """Применяет регистр оригинального слова к заменяющему."""
        if original.isupper():
            return replacement.upper()
        elif original[0].isupper():
            return replacement.capitalize()
        else:
            return replacement

    for wrong_word, correct_word in replacements.items():
        pattern = r"\b" + re.escape(wrong_word) + r"\b"

        def make_replacer(correct_word):
            def replacer(match):
                nonlocal total_replacements
                total_replacements += 1
                return apply_case(match.group(), correct_word)

            return replacer

        text = re.sub(pattern, make_replacer(correct_word), text, flags=re.IGNORECASE)

    if total_replacements > 0:
        # Предполагается, что функция `info` определена где-то в коде (например, логирование)
        info(f"{filepath}: заменено {total_replacements} слов(а) с 'е' на 'ё'")

    return 0, text



def parse_equation_descriptions_simple(text: str) -> list:
    """
    Парсит описания переменных после формул.
    Ищет строки, начинающиеся с 'где' и заканчивающиеся \n
    """
    descriptions = []

    # Шаблон для поиска: формула + строка начинающаяся с "где"
    pattern = r"\\begin{equation}([\s\S]+?)\\end{equation}\s*\n\s*([Гг]де\b[^\n]+)\n"

    for match in re.finditer(pattern, text):
        eq_content = match.group(1).strip()
        where_line = match.group(2).strip()

        # Извлекаем текст после "где"
        where_text = re.sub(r"^[Гг]де\s*", "", where_line, count=1)

        # Парсим переменные из строки
        variables = parse_variables_simple(where_text)

        descriptions.append(
            {
                "equation_content": eq_content,
                "where_text": where_text,
                "variables": variables,
                "position": match.start(),
            }
        )

    return descriptions


def parse_variables_simple(where_text: str) -> list:
    """
    Парсит переменные из строки после 'где'.
    Разделяет по точкам с запятой и обрабатывает каждую часть.
    """
    variables = []

    # Разделяем строку по точкам с запятой
    parts = [part.strip() for part in where_text.split(";") if part.strip()]

    for part in parts:
        # Ищем разделитель между переменной и описанием
        # Поддерживаем форматы: "--- ", "- ", ": ", "— "
        separator_patterns = [
            r"^(.*?)\s*---\s*(.*?)$",
            r"^(.*?)\s*-\s*(.*?)$",
            r"^(.*?)\s*:\s*(.*?)$",
            r"^(.*?)\s*—\s*(.*?)$",
        ]

        parsed = False
        for pattern in separator_patterns:
            match = re.match(pattern, part)
            if match:
                var_part = match.group(1).strip()
                desc_part = match.group(2).strip()

                # Удаляем точку в конце описания, если есть
                desc_part = re.sub(r"[.]$", "", desc_part).strip()

                variables.append(
                    {"variable": var_part, "description": desc_part, "raw_text": part}
                )
                parsed = True
                break

        # Если не удалось разделить, сохраняем как есть
        if not parsed:
            variables.append({"variable": part, "description": "", "raw_text": part})

    return variables

def fix_equations_before_text(text, filepath):
    count_commas = 0  # Счётчик замен на запятые (перед "где")
    count_dots = 0  # Счётчик замен на точки (перед заглавными буквами)

    # 1. Обработка случаев с "где"
    pattern_where = r"(\\begin{equation}[\s\S]+?\\end{equation})\s+(?=[Гг]де\b)"

    def replace_where(match):
        nonlocal count_commas
        count_commas += 1
        # Добавляем ДВЕ новой строки для создания пустой строки
        return _add_punctuation_before_end(match.group(1), ",", filepath) + "\n"

    text = re.sub(pattern_where, replace_where, text, flags=re.DOTALL)

    # 2. Обработка случаев с заглавной буквы (сохраняем оригинальное поведение)
    pattern_upper = r"(\\begin{equation}[\s\S]+?\\end{equation})\s+(?=[А-ЯA-Z])"

    def replace_upper(match):
        nonlocal count_dots
        count_dots += 1
        # Сохраняем одну новую строку (без пустой строки)
        return _add_punctuation_before_end(match.group(1), ".", filepath) + "\n"

    text = re.sub(pattern_upper, replace_upper, text, flags=re.DOTALL)

    # 3. Исправление артефактов с \label (обновлены шаблоны для учёта пустых строк)
    text = re.sub(
        r",(\s*\n\s*\\label\{[^}]*\},\s*\n\s*\\end\{equation\})",
        r"\1",
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(
        r"\.(\s*\n\s*\\label\{[^}]*\}\.\s*\n\s*\\end\{equation\})",
        r"\1",
        text,
        flags=re.MULTILINE,
    )
    return 0, text

def _add_punctuation_before_end(eq_block, punctuation, filepath):
    """Добавляет знак препинания (',' или '.') перед \\end{equation}"""
    lines = eq_block.splitlines()
    if len(lines) < 2:
        return eq_block

    # Ищем строку с \end{equation}
    end_idx = next(
        (
            i
            for i in range(len(lines) - 1, -1, -1)
            if lines[i].strip().startswith(r"\end{equation}")
        ),
        None,
    )

    if end_idx is None or end_idx == 0:
        return eq_block

    # Находим последнюю непустую строку перед \end
    prev_idx = end_idx - 1
    while prev_idx >= 0 and not lines[prev_idx].strip():
        prev_idx -= 1

    if prev_idx < 0:
        return eq_block

    # Проверяем, нет ли уже знака препинания
    last_line = lines[prev_idx].rstrip()
    if last_line.endswith((".", ",", ";", ":", "!", "?")):
        return eq_block

    # Добавляем знак препинания
    lines[prev_idx] = last_line + punctuation

    info(f"Добавлен знак препинания в {filepath}: {last_line}")
    result = "\n".join(lines)

    return result
    

def check_todo_comments(text, filepath):
    """Проверяет текст на наличие #TODO комментариев и выводит предупреждение с содержимым после #TODO"""
    # Регулярное выражение для поиска #TODO и всего, что за ним следует (в пределах строки)
    pattern = r'#TODO(.*)'

    for i, line in enumerate(text.splitlines(), start=1):
        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            todo_content = match.group(1).strip()
            warning(f"{filepath}:{i}: найден #TODO: {todo_content}")
    return 0, text


def check_parentheses_comments(text, filepath):
    r"""
    Проверяет текст на наличие слов в скобках вне математических контекстов LaTeX.

    Игнорируются:
    - Строки с флагом % #lint-ignore в конце
    - Скобки внутри $...$, $$...$$
    - Скобки внутри \\begin{equation}...\end{equation}

    Допускается наличие запятых внутри скобок (например: "(а, б, в)").
    """

    if (
        "preambula.tex" in str(filepath)
        or "title.tex" in str(filepath)
        or "links.tex" in str(filepath)
    ):
        return 0, text
    in_equation = False  # Флаг нахождения внутри окружения equation
    ignore_pattern = re.compile(r"%\s*#lint-ignore\s*$")
    equation_begin_pattern = re.compile(r"\\begin\{equation\*?\}")
    equation_end_pattern = re.compile(r"\\end\{equation\*?\}")
    math_pattern = re.compile(
        r"\$\$.*?\$\$|\$.*?\$"
    )  # Нежадный поиск математических выражений
    parentheses_pattern = re.compile(r"(?<!\\)\([^)]*[a-zA-Zа-яА-ЯёЁ][^)]*\)")

    lines = text.splitlines()
    for i, line in enumerate(lines, start=1):
        # 1. Проверка на явное игнорирование строки
        if ignore_pattern.search(line):
            continue

        # 2. Обработка состояния окружения equation
        if in_equation:
            if equation_end_pattern.search(line):
                in_equation = False
            continue  # Все строки внутри equation пропускаются

        # Проверка на начало equation в текущей строке
        if equation_begin_pattern.search(line):
            in_equation = True
            # Особый случай: начало и конец equation в одной строке
            if equation_end_pattern.search(line):
                in_equation = False
            continue

        # 3. Удаление математических выражений из строки
        cleaned_line = math_pattern.sub("", line)

        # 4. Поиск скобок с буквами в оставшемся тексте
        for match in parentheses_pattern.finditer(cleaned_line):
            content = match.group()[1:-1].strip()
            if re.search(r"[a-zA-Zа-яА-ЯёЁ]", content):
                warning(
                    f"{filepath}:{i}: обнаружены слова в скобках вне математического контекста: "
                    f"{match.group()}"
                    "Если используем в скобках, значит неважно, тогда либо убираем скобки, либо удаляем. Чтобы игнорировать варнинг: поставить '% #lint-ignore' в конце"
                )

    return 0, text

def validate_bibliography_entries(text, filepath):
    """Проверяет библиографические записи на соответствие формату ГОСТ с помощью bibitem_formatting.BibliographyValidator"""

    # Проверяем, является ли файл файлом библиографии
    if "links.tex" not in str(filepath) and "bibliography" not in str(filepath).lower():
        return 0, text

    # Находим все записи \bibitem
    bibitem_pattern = re.compile(r'\\bibitem\{[^\}]+\}.*?(?=\\bibitem\{|\\end\{|$)', re.DOTALL)
    matches = bibitem_pattern.findall(text)

    total_warnings = 0
    total_errors = 0

    validator = BibliographyValidator()

    for match in matches:
        # Валидируем каждую запись
        result = validator.validate_entry(match)

        # Находим точную позицию вхождения в тексте для правильного определения строки
        match_pos = text.find(match.strip())
        if match_pos != -1:
            # Подсчитываем номер строки до позиции вхождения
            line_number = text.count('\n', 0, match_pos) + 1
        else:
            # Если точное совпадение не найдено, ищем частичное совпадение
            line_number = 1
            for i, line in enumerate(text.splitlines(), start=1):
                if match.strip()[:50] in line:  # Ищем первые 50 символов
                    line_number = i
                    break

        # Выводим предупреждения для каждого варнинга из результата
        for warn_msg in result.get("warnings", []):
            warning(f"{filepath}:{line_number}: {warn_msg}")
            total_warnings += 1

        for error_msg in result.get("errors", []):
            error(f"{filepath}:{line_number}: {error_msg}")
            total_errors += 1

    # Если есть хотя бы одно предупреждение или ошибка, выводим примеры правильного форматирования
    if total_warnings > 0 or total_errors > 0:
        info(f"\n{filepath}: Ниже приведены примеры правильного форматирования библиографических записей:")
        info("\\bibitem{kuznetsov2022}")
        info("Кузнецов А.В. Алгоритмы машинного обучения / Кузнецов А.В., Смирнов Б.И., Попов В.Г., Васильев Г.Д. // Труды Международной конференции по искусственному интеллекту. -- 2022. -- С. 145--158.")
        info("\\bibitem{zamir2021mprnet}")
        info("Zamir S. W. Multi-Stage Progressive Image Restoration (MPRNet) / Zamir S. W. [и др.] // Proc. CVPR. -- 2021. -- С. 14821--14831.")
        info("\\bibitem{levin_blind}")
        info("Levin A., Durand F., Freeman W. T. Understanding and Evaluating Blind Deconvolution Algorithms // Proc. CVPR. -- 2009. -- С. 1964--1971.")
        info("\\bibitem{github_nafnet}")
        info("MEGVII Research. NAFNet: Results and Pre-trained Models (GoPro) [Электронный ресурс] // GitHub repository. -- 2022. -- URL: \\url{https://github.com/megvii-research/NAFNet} (дата обращения: 16.12.2025)")

    return 0, text

# ========================
# Основная логика
# ========================

def apply_rules_to_file(filepath, rules):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception as e:
        error(f"не удалось прочитать {filepath}: {e}")
        return 1

    original_text = text
    file_error = 0

    for rule in rules:
        code, text = rule(text, filepath)
        if code != 0:
            file_error = 1

    if text != original_text:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(text)
        except Exception as e:
            error(f"не удалось записать {filepath}: {e}")
            return 1

    return file_error

def resolve_tex_paths(input_paths):
    """Преобразует список входных путей в список .tex файлов."""
    tex_files = []
    for path_str in input_paths:
        p = Path(path_str)
        if not p.exists():
            error(f"путь не существует: {p}")
            continue
        if p.is_file():
            if p.suffix == '.tex':
                tex_files.append(p)
            else:
                warning(f"пропущен не-.tex файл: {p}")
        elif p.is_dir():
            tex_files.extend(p.rglob("*.tex"))
        else:
            error(f"некорректный путь: {p}")
    return tex_files

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Проверка и исправление LaTeX-файлов",
        epilog="Можно указать каталоги или отдельные .tex файлы."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["../src"],
        help="пути к .tex файлам или каталогам (по умолчанию: текущая директория)"
    )
    args = parser.parse_args()

    tex_files = resolve_tex_paths(args.paths)
    if not tex_files:
        info("нет .tex файлов для обработки")
        sys.exit(0)

    tex_files = sorted(set(tex_files), key=lambda x: (x.name == 'links.tex', x))

    rules = [
        check_forbidden_words,
        process_bibliography_order,
        replace_typographic_symbols,
        replace_typographic_dashes,
        replace_space_before_citations,
        replace_words_with_yo,
        check_todo_comments,
        fix_equations_before_text,
        format_variables_enumerate,
        fix_lists,
        check_parentheses_comments,
        validate_bibliography_entries,
    ]

    global_error = 0
    for filepath in tex_files:
        err = apply_rules_to_file(filepath, rules)
        global_error = max(global_error, err)

    if global_error:
        error("Проверка .tex файлов завершена с ошибками")
        sys.exit(1)
    else:
        info("Проверка .tex файлов завершена успешно")
        sys.exit(0)

if __name__ == "__main__":
    main()