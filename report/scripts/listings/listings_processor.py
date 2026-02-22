#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Listings Processor for LaTeX Automation v5 (Final)
- Макс. строк в части: 36
- Нумерация: если >1 части, то ВСЕ части нумеруются (ч.1, ч.2...)
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import List, Tuple

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

DEFAULT_MAX_LINES_PER_PART = 36  # ИЗМЕНЕНО: было 50
DEFAULT_REMOVE_COMMENTS = True
DEFAULT_TRANSLIT = True

FILE_SEPARATOR = "@@"
LINE_SEPARATOR = "@@"
PATH_ESCAPE = "__"

COMMENT_SYMBOLS = {
    ".cpp": "//",
    ".c": "//",
    ".h": "//",
    ".hpp": "//",
    ".py": "#",
    ".js": "//",
    ".ts": "//",
    ".java": "//",
    ".cs": "//",
    ".php": "//",
    ".sh": "#",
    ".bash": "#",
    ".tex": "%",
    ".sql": "--",
    ".rs": "//",
    ".go": "//",
}

TRANSLIT_MAP = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "yo",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shh",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
    "А": "A",
    "Б": "B",
    "В": "V",
    "Г": "G",
    "Д": "D",
    "Е": "E",
    "Ё": "Yo",
    "Ж": "Zh",
    "З": "Z",
    "И": "I",
    "Й": "Y",
    "К": "K",
    "Л": "L",
    "М": "M",
    "Н": "N",
    "О": "O",
    "П": "P",
    "Р": "R",
    "С": "S",
    "Т": "T",
    "У": "U",
    "Ф": "F",
    "Х": "Kh",
    "Ц": "Ts",
    "Ч": "Ch",
    "Ш": "Sh",
    "Щ": "Shh",
    "Ъ": "",
    "Ы": "Y",
    "Ь": "",
    "Э": "E",
    "Ю": "Yu",
    "Я": "Ya",
}

# ============================================================================
# ФУНКЦИИ
# ============================================================================


def safe_encode_path(path_str: str) -> str:
    return path_str.replace("/", PATH_ESCAPE).replace("\\", PATH_ESCAPE)


def safe_decode_path(encoded_str: str) -> str:
    return encoded_str.replace(PATH_ESCAPE, "/")


def transliterate(text: str) -> str:
    result = []
    for char in text:
        result.append(TRANSLIT_MAP.get(char, char))
    return "".join(result)


def remove_comments(code: str, file_extension: str) -> str:
    comment_symbol = COMMENT_SYMBOLS.get(file_extension)
    if not comment_symbol:
        return code

    lines = code.split("\n")
    cleaned_lines = []

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith(comment_symbol):
            continue

        in_string = False
        string_char = None
        comment_pos = -1

        for i, char in enumerate(line):
            if char in "\"'":
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
            elif not in_string and line[i : i + len(comment_symbol)] == comment_symbol:
                comment_pos = i
                break

        if comment_pos >= 0:
            cleaned_lines.append(line[:comment_pos].rstrip())
        else:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def parse_first_line(line: str) -> Tuple[List[int], bool, bool, str]:
    parts = line.split(LINE_SEPARATOR, 1)
    config_part = parts[0].strip()
    name_part = parts[1].strip() if len(parts) > 1 else ""

    config_tokens = config_part.split()
    split_points = []
    keep_comments = not DEFAULT_REMOVE_COMMENTS
    no_translit = not DEFAULT_TRANSLIT

    for token in config_tokens:
        if token.isdigit():
            split_points.append(int(token))
        elif token == "--keep-comments":
            keep_comments = True
        elif token == "--no-translit":
            no_translit = True

    return split_points, not keep_comments, not no_translit, name_part


def format_first_line(
    split_points: List[int], keep_comments: bool, no_translit: bool, name: str
) -> str:
    parts = [str(p) for p in split_points]
    if keep_comments:
        parts.append("--keep-comments")
    if no_translit:
        parts.append("--no-translit")

    config_str = " ".join(parts)
    return f"{config_str} {LINE_SEPARATOR} {name}"


def find_listing_in_file(filepath: str) -> List[Tuple[str, str, str, int, int]]:
    listings = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Ошибка чтения файла {filepath}: {e}", file=sys.stderr)
        return listings

    begin_pattern = re.compile(r"^\s*(?://|#|--|%)?\s*#begin_listing\s+(\S+)\s+(.+)$")
    end_pattern = re.compile(r"^\s*(?://|#|--|%)?\s*#end_listing")

    i = 0
    while i < len(lines):
        match = begin_pattern.match(lines[i])
        if match:
            tag = match.group(1)
            name = match.group(2).strip()
            start_line = i + 1
            code_lines = []
            i += 1

            while i < len(lines):
                if end_pattern.match(lines[i]):
                    end_line = i + 1
                    code = "\n".join(
                        [line.rstrip("\n").rstrip("\r") for line in code_lines]
                    )
                    listings.append((tag, name, code, start_line, end_line))
                    break
                code_lines.append(lines[i].rstrip("\n").rstrip("\r"))
                i += 1
        else:
            i += 1

    return listings


def calculate_split_points(
    code_lines: List[str], existing_points: List[int], max_lines: int
) -> List[int]:
    total_lines = len(code_lines)
    new_points = []

    for point in existing_points:
        if point < total_lines:
            new_points.append(point)

    if new_points:
        last_point = new_points[-1]
        remaining = total_lines - last_point
    else:
        last_point = 0
        remaining = total_lines

    while remaining > max_lines:
        last_point += max_lines
        if last_point < total_lines:
            new_points.append(last_point)
            remaining = total_lines - last_point
        else:
            break

    return new_points


def split_code(code: str, split_points: List[int]) -> List[str]:
    lines = code.split("\n")
    parts = []
    start = 0
    for point in split_points:
        parts.append("\n".join(lines[start:point]))
        start = point
    parts.append("\n".join(lines[start:]))
    return parts


def generate_latex(tag: str, name: str, parts: List[str], output_path: str):
    """
    ИЗМЕНЕНО: Логика нумерации частей
    - 1 часть: без номера
    - 2+ части: все части с номером (ч.1, ч.2...)
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    total_parts = len(parts)

    with open(output_path, "w", encoding="utf-8") as f:
        for i, part in enumerate(parts):
            part_num = i + 1

            # Логика заголовка и лейбла
            if total_parts == 1:
                # Если часть всего одна, не пишем номер
                title = name
                label = f"lst:{tag}"
            else:
                # Если частей много, нумеруем ВСЕ (включая первую)
                title = f"{name} ч.{part_num}"
                label = f"lst:{tag}-{part_num}"

            f.write(f"\\begin{{mylisting}}{{{title}}}{{{label}}}\n")
            f.write(part)
            if part and not part.endswith("\n"):
                f.write("\n")
            f.write("\\end{mylisting}\n")

            if i < len(parts) - 1:
                f.write("\n")


# ============================================================================
# РЕЖИМЫ
# ============================================================================


def mode_init(source_dir: str, listings_dir: str, max_lines: int):
    source_path = Path(source_dir).resolve()
    listings_path = Path(listings_dir)
    listings_path.mkdir(parents=True, exist_ok=True)

    created_count = 0

    for ext in COMMENT_SYMBOLS.keys():
        for filepath in source_path.rglob(f"*{ext}"):
            listings = find_listing_in_file(str(filepath))

            for tag, name, code, start, end in listings:
                try:
                    rel_path = filepath.relative_to(source_path)
                except ValueError:
                    rel_path = filepath.name

                encoded_path = safe_encode_path(str(rel_path))
                intermediate_name = f"{tag}{FILE_SEPARATOR}{encoded_path}.txt"
                intermediate_path = listings_path / intermediate_name

                if intermediate_path.exists():
                    print(f"⚠️  Файл {intermediate_name} уже существует, пропускаем")
                    continue

                ext = filepath.suffix
                if DEFAULT_REMOVE_COMMENTS:
                    code = remove_comments(code, ext)
                if DEFAULT_TRANSLIT:
                    code = transliterate(code)

                code_lines = code.split("\n")
                split_points = calculate_split_points(code_lines, [], max_lines)

                first_line = format_first_line(
                    split_points,
                    not DEFAULT_REMOVE_COMMENTS,
                    not DEFAULT_TRANSLIT,
                    name,
                )

                with open(intermediate_path, "w", encoding="utf-8") as f:
                    f.write(first_line + "\n")
                    f.write(code)

                print(f"✅ Создан: {intermediate_name}")
                created_count += 1

    print(f"\nВсего создано файлов: {created_count}")


def mode_update(intermediate_path: str, source_dir: str, max_lines: int):
    intermediate_file = Path(intermediate_path)

    if not intermediate_file.exists():
        print(f"❌ Файл не найден: {intermediate_path}", file=sys.stderr)
        sys.exit(1)

    name = intermediate_file.stem
    parts = name.split(FILE_SEPARATOR, 1)

    if len(parts) < 2:
        print(f"❌ Неверный формат имени: {name}", file=sys.stderr)
        sys.exit(1)

    tag = parts[0]
    encoded_source_path = parts[1]

    rel_source_path = safe_decode_path(encoded_source_path)
    source_path = Path(source_dir) / rel_source_path

    if not source_path.exists():
        found_files = list(Path(source_dir).rglob(Path(rel_source_path).name))
        if found_files:
            source_path = found_files[0]

    if not source_path.exists():
        print(f"❌ Исходный файл не найден: {rel_source_path}", file=sys.stderr)
        sys.exit(1)

    with open(intermediate_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if not lines:
        print(f"❌ Пустой файл: {intermediate_path}", file=sys.stderr)
        sys.exit(1)

    split_points, remove_comments_flag, translit_flag, saved_name = parse_first_line(
        lines[0].rstrip("\n").rstrip("\r")
    )

    listings = find_listing_in_file(str(source_path))

    target_listing = None
    for tag_found, name_found, code, start, end in listings:
        if tag_found == tag:
            target_listing = (tag_found, name_found, code, start, end)
            break

    if not target_listing:
        print(f"❌ Листинг с тегом {tag} не найден в исходнике", file=sys.stderr)
        sys.exit(1)

    _, name, code, _, _ = target_listing

    ext = source_path.suffix
    if remove_comments_flag:
        code = remove_comments(code, ext)
    if translit_flag:
        code = transliterate(code)

    code_lines = code.split("\n")
    new_split_points = calculate_split_points(code_lines, split_points, max_lines)

    final_name = saved_name if saved_name else name

    first_line = format_first_line(
        new_split_points, not remove_comments_flag, not translit_flag, final_name
    )

    with open(intermediate_file, "w", encoding="utf-8") as f:
        f.write(first_line + "\n")
        f.write(code)

    print(f"✅ Обновлен: {intermediate_file.name}")


def mode_generate(intermediate_path: str, output_path: str):
    intermediate_file = Path(intermediate_path)

    if not intermediate_file.exists():
        print(f"❌ Файл не найден: {intermediate_path}", file=sys.stderr)
        sys.exit(1)

    with open(intermediate_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if not lines:
        print(f"❌ Пустой файл: {intermediate_path}", file=sys.stderr)
        sys.exit(1)

    split_points, _, _, listing_name = parse_first_line(
        lines[0].rstrip("\n").rstrip("\r")
    )

    name = intermediate_file.stem
    parts = name.split(FILE_SEPARATOR, 1)
    tag = parts[0]

    code_lines = [line.rstrip("\n").rstrip("\r") for line in lines[1:]]
    code = "\n".join(code_lines)

    code_parts = split_code(code.strip(), split_points)

    generate_latex(tag, listing_name, code_parts, output_path)
    print(f"✅ Сгенерирован: {output_path}")


# ============================================================================
# MAIN
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Process code listings for LaTeX reports"
    )
    subparsers = parser.add_subparsers(dest="mode", help="Режим работы")

    init_parser = subparsers.add_parser("init", help="Инициализация листингов")
    init_parser.add_argument("--source-dir", "-s", required=True)
    init_parser.add_argument("--listings-dir", "-l", default="src/listings")
    init_parser.add_argument(
        "--max-lines", "-m", type=int, default=DEFAULT_MAX_LINES_PER_PART
    )

    update_parser = subparsers.add_parser("update", help="Обновление листинга")
    update_parser.add_argument("--intermediate", "-i", required=True)
    update_parser.add_argument("--source-dir", "-s", required=True)
    update_parser.add_argument(
        "--max-lines", "-m", type=int, default=DEFAULT_MAX_LINES_PER_PART
    )

    generate_parser = subparsers.add_parser("generate", help="Генерация LaTeX")
    generate_parser.add_argument("--intermediate", "-i", required=True)
    generate_parser.add_argument("--output", "-o", required=True)

    args = parser.parse_args()

    if args.mode == "init":
        mode_init(args.source_dir, args.listings_dir, args.max_lines)
    elif args.mode == "update":
        mode_update(args.intermediate, args.source_dir, args.max_lines)
    elif args.mode == "generate":
        mode_generate(args.intermediate, args.output)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
