#!/usr/bin/env python3
import sys
import re
from pathlib import Path
from lint_tex_submodules.lint_logging import warning, error, info
from lint_tex_submodules.list_puctuation import fix_lists
from lint_tex_submodules.links_linter import process_bibliography_order


# ========================
# Правила
# ========================

def check_forbidden_words(text, filepath):
    """Проверяет текст на наличие запрещённых слов из массива FORBIDDEN_WORDS"""

    FORBIDDEN_WORDS = [
        'рассмотрим',
        'обозначим',
        'эксперим',
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
        '«': '<<',
        '»': '>>',
        '“': '<<',
        '”': '>>',
        '„': '<<',
        '‟': '>>',
        '❝': '<<',
        '❞': '>>',
        '…': '...',
        '×': r' $\times$ '
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


def fix_equations_before_text(text, filepath):
    count_commas = 0  # Счётчик замен на запятые (перед "где")
    count_dots = 0  # Счётчик замен на точки (перед заглавными буквами)

    # 1. Обработка случаев с "где"
    pattern_where = r"(\\begin{equation}[\s\S]+?\\end{equation})\s+(?=[Гг]де\b)"

    def replace_where(match):
        nonlocal count_commas
        count_commas += 1
        return _add_punctuation_before_end(match.group(1), ",", filepath) + "\n"

    text = re.sub(pattern_where, replace_where, text, flags=re.DOTALL)

    # 2. Обработка случаев с заглавной буквы
    pattern_upper = r"(\\begin{equation}[\s\S]+?\\end{equation})\s+(?=[А-ЯA-Z])"

    def replace_upper(match):
        nonlocal count_dots
        count_dots += 1
        return _add_punctuation_before_end(match.group(1), ".", filepath) + "\n"

    text = re.sub(pattern_upper, replace_upper, text, flags=re.DOTALL)
    text = re.sub(
        r',(\s*\n\s*\\label\{[^}]*\},\s*\n\s*\\end\{equation\})',
        r'\1',
        text,
        flags=re.MULTILINE
    )
    text = re.sub(
        r'\.(\s*\n\s*\\label\{[^}]*\}\.\s*\n\s*\\end\{equation\})',
        r'\1',
        text,
        flags=re.MULTILINE
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
        fix_lists,
        process_bibliography_order,
        replace_typographic_symbols,
        replace_typographic_dashes,
        replace_space_before_citations,
        replace_words_with_yo,
        check_todo_comments,
        fix_equations_before_text,
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