import re
from .lint_logging import info

# Предварительно компилируем регулярные выражения для производительности
LATEX_CMD_REGEX = re.compile(r"\\[a-zA-Z]+(?:\{[^{}]*\})?")
LATEX_MATH_START_REGEX = re.compile(r"^(\$|\\[a-zA-Z]|\\[^a-zA-Z]|\\\(|\\\[|\\begin\{)")
ABBREV_EXCEPTIONS = re.compile(
    r"(т\.д|т\.п|и\.о|т\.о|рис|табл|eq|eqref|ref|cite|footnote|рис\.|табл\.)\.?$",
    re.IGNORECASE,
)
MATH_END_REGEX = re.compile(r"\$\s*$")
PUNCTUATION_REGEX = re.compile(r"[.!?;:]\s*$")  # Включаем двоеточие как знак препинания


def fix_lists(text, filepath):
    """
    Обработка списков itemize/enumerate с учетом LaTeX-команд и аббревиатур.
    Не изменяет первую букву если:
    - текст начинается с LaTeX-команды (\command), математического окружения ($...$, \[...\], \(...\))
    - в первом слове больше одной заглавной буквы (аббревиатуры)
    """
    lines = text.splitlines()
    i = 0
    count_fixed = 0
    changes = []  # Список для отслеживания изменений: (номер_строки, старый_текст, новый_текст)
    processed_positions = set()  # Защита от повторной обработки одних и тех же позиций

    while i < len(lines):
        if i in processed_positions:
            i += 1
            continue

        stripped_line = lines[i].strip()

        # Защита от бесконечного цикла (на случай очень длинных файлов)
        if i > len(lines) * 2:
            break

        # 1. Поиск окружений списка
        if stripped_line.startswith(r"\begin{itemize}") or stripped_line.startswith(
            r"\begin{enumerate}"
        ):
            env_type = "itemize" if "itemize" in stripped_line else "enumerate"
            start_idx = i

            # 2. Определение границ списка с ограничением поиска
            end_idx = -1
            search_limit = min(i + 200, len(lines))  # Ограничиваем поиск 200 строками

            for j in range(i + 1, search_limit):
                if lines[j].strip() == f"\\end{{{env_type}}}":
                    end_idx = j
                    break

            if end_idx == -1:
                # Попытка найти любой конец окружения, если не нашли точный
                for j in range(i + 1, search_limit):
                    if lines[j].strip().startswith("\\end{"):
                        end_idx = j
                        break

            if end_idx == -1:
                i += 1
                continue

            # 3. Анализ текста перед списком - расширенный контекст
            context_lines = []  # Храним пары (индекс_строки, содержимое_строки)
            pre_idx = start_idx - 1
            non_empty_count = 0

            # Собираем до 5 НЕПУСТЫХ строк перед списком
            while pre_idx >= 0 and non_empty_count < 5:
                stripped = lines[pre_idx].strip()
                if stripped:
                    # Сохраняем исходную строку со всеми отступами
                    context_lines.append((pre_idx, lines[pre_idx]))
                    non_empty_count += 1
                pre_idx -= 1

            if not context_lines:
                i = end_idx + 1
                processed_positions.update(range(start_idx, end_idx + 1))
                continue

            # Восстанавливаем хронологический порядок (от старых строк к новым)
            context_lines.reverse()
            nearest_context_idx, nearest_context_line = context_lines[
                -1
            ]  # Ближайшая строка
            stripped_nearest = nearest_context_line.strip()

            # Проверяем контекст на наличие двоеточия только в ближайшей строке
            ends_with_colon = stripped_nearest.endswith(":")
            is_after_gde = bool(
                re.search(r"\bгде\b\s*$", stripped_nearest, re.IGNORECASE)
            )
            has_lint_ignore_before = "% #lint-ignore" in nearest_context_line

            # 4. Сбор элементов списка
            items = []  # Хранит кортежи (индекс_строки, позиция_\item_в_строке, исходная_строка)
            for j in range(start_idx + 1, end_idx):
                line = lines[j]
                item_pos = line.find(r"\item")
                if item_pos != -1:
                    items.append((j, item_pos, line))

            if not items:
                i = end_idx + 1
                processed_positions.update(range(start_idx, end_idx + 1))
                continue

            # 5. Проверка на двоеточия в элементах (для определения режима) - оптимизированная версия
            has_colon_in_items = False
            for item_idx, item_pos, original_line in items:
                line = original_line

                # Пропускаем элементы с игнорированием
                if "% #lint-ignore" in line:
                    continue

                # Извлекаем текст после \item
                after_item = line[item_pos + 5 :]  # 5 = len('\item')

                # Оптимизированная проверка на двоеточия вне LaTeX-команд
                in_command = False
                in_math = False
                for pos, char in enumerate(after_item):
                    if char == "$":
                        in_math = not in_math
                    if (
                        char == "\\"
                        and pos + 1 < len(after_item)
                        and after_item[pos + 1].isalpha()
                    ):
                        in_command = True
                    elif in_command and char in ["{", "}", "[", "]", "(", ")", " "]:
                        in_command = False

                    if char == ":" and not in_command and not in_math:
                        # Проверяем, что двоеточие не часть сокращения или специального синтаксиса
                        if pos + 1 < len(after_item) and after_item[pos + 1] not in [
                            "$",
                            "\\",
                        ]:
                            has_colon_in_items = True
                            break
                if has_colon_in_items:
                    break

            # 6. Определение режима обработки
            mode_colon = (
                (not has_colon_in_items)
                and ends_with_colon
                and (not has_lint_ignore_before)
            )

            # Особый режим для списков после "где"
            if is_after_gde:
                mode_colon = False  # Не используем режим двоеточия после "где"

            changes_made = False

            # 7. Обработка текста перед списком - ИСПРАВЛЕННАЯ ЛОГИКА
            if not has_lint_ignore_before:
                stripped_ctx = nearest_context_line.rstrip()
                ends_with_punctuation = bool(PUNCTUATION_REGEX.search(stripped_ctx))

                # СЛУЧАЙ 1: Строка заканчивается двоеточием перед списком
                if stripped_ctx.endswith(":"):
                    if mode_colon:
                        # Двоеточие уместно в режиме двоеточия - оставляем как есть
                        pass
                    else:
                        # В стандартном режиме заменяем двоеточие на точку
                        if not re.search(
                            r"[.!?]\s*$", stripped_ctx[:-1]
                        ):  # Проверяем, что перед двоеточием нет другого знака
                            indent = nearest_context_line[
                                : len(nearest_context_line)
                                - len(nearest_context_line.lstrip())
                            ]
                            new_ctx_line = indent + stripped_ctx[:-1].rstrip() + "."

                            if new_ctx_line != nearest_context_line:
                                changes.append(
                                    (
                                        nearest_context_idx + 1,
                                        nearest_context_line,
                                        new_ctx_line,
                                    )
                                )
                                lines[nearest_context_idx] = new_ctx_line
                                changes_made = True

                # СЛУЧАЙ 2: Строка заканчивается словом "где" - не добавляем точку
                elif is_after_gde:
                    # Ничего не делаем, "где" не требует точки
                    pass

                # СЛУЧАЙ 3: Нет знака препинания в конце контекста
                elif not ends_with_punctuation:
                    # Исключения: не добавляем точку в LaTeX-командах, математике
                    if not (
                        re.match(r"^\s*(\\[a-zA-Z]+|\$)", stripped_ctx)
                        or re.search(r"^\s*\\label", stripped_ctx)
                    ):
                        indent = nearest_context_line[
                            : len(nearest_context_line)
                            - len(nearest_context_line.lstrip())
                        ]
                        new_ctx_line = indent + stripped_ctx + "."

                        if new_ctx_line != nearest_context_line:
                            changes.append(
                                (
                                    nearest_context_idx + 1,
                                    nearest_context_line,
                                    new_ctx_line,
                                )
                            )
                            lines[nearest_context_idx] = new_ctx_line
                            changes_made = True

            # 8. Обработка элементов списка
            for idx, (item_idx, item_pos, original_line) in enumerate(items):
                if "% #lint-ignore" in original_line:
                    continue

                # Извлечение текста после \item
                before_item = original_line[:item_pos]  # Отступы перед \item
                after_item = original_line[
                    item_pos + 5 :
                ].lstrip()  # Текст после \item (без начальных пробелов)

                # Пропускаем пустые элементы
                if not after_item.strip():
                    continue

                new_after_item = after_item

                # === Проверка перед обработкой первой буквы ===
                should_process_first_letter = True

                # 1. Проверка на LaTeX-конструкции в начале
                if LATEX_MATH_START_REGEX.match(new_after_item):
                    should_process_first_letter = False

                # 2. Проверка на аббревиатуры в первом слове (только если ещё не отключено)
                if should_process_first_letter and len(new_after_item) > 0:
                    # Быстрая проверка для очень длинных строк
                    sample_text = new_after_item[
                        :100
                    ]  # Анализируем только начало строки

                    # Ищем конец первого слова (до первого разделителя)
                    first_word_end = len(sample_text)
                    for pos, char in enumerate(sample_text):
                        if char in " ,.;:!?([{/\\\"'":
                            first_word_end = pos
                            break

                    first_word = sample_text[:first_word_end].strip()

                    # Считаем заглавные буквы в первом слове
                    uppercase_letters = [
                        c for c in first_word if c.isalpha() and c.isupper()
                    ]
                    uppercase_count = len(uppercase_letters)

                    # Если больше одной заглавной буквы - считаем это аббревиатурой
                    if uppercase_count > 1:
                        should_process_first_letter = False
                    # Если первое слово - одиночная заглавная буква (часто в математике)
                    elif len(first_word) == 1 and uppercase_count == 1:
                        should_process_first_letter = False

                # Обработка первой буквы (только если разрешено)
                if should_process_first_letter and len(new_after_item) > 0:
                    first_alpha_idx = -1
                    for k, char in enumerate(new_after_item):
                        if char.isalpha():
                            first_alpha_idx = k
                            break

                    if (
                        first_alpha_idx != -1
                        and first_alpha_idx < len(new_after_item) - 1
                    ):
                        if mode_colon and not is_after_gde:
                            # Строчная первая буква (режим двоеточия)
                            if new_after_item[first_alpha_idx].isupper():
                                new_after_item = (
                                    new_after_item[:first_alpha_idx]
                                    + new_after_item[first_alpha_idx].lower()
                                    + new_after_item[first_alpha_idx + 1 :]
                                )
                        else:
                            # Заглавная первая буква (стандартный режим или после "где")
                            if new_after_item[first_alpha_idx].islower():
                                new_after_item = (
                                    new_after_item[:first_alpha_idx]
                                    + new_after_item[first_alpha_idx].upper()
                                    + new_after_item[first_alpha_idx + 1 :]
                                )

                # Обработка концовки
                is_last = idx == len(items) - 1
                stripped_after = new_after_item.rstrip()

                # Ищем последний непробельный символ
                last_char_pos = len(stripped_after) - 1
                while last_char_pos >= 0 and stripped_after[last_char_pos].isspace():
                    last_char_pos -= 1

                # Обработка знаков препинания в конце
                new_ending = ""
                if last_char_pos >= 0:
                    last_char = stripped_after[last_char_pos]

                    # Быстрая проверка для сокращений
                    is_abbreviation = bool(
                        ABBREV_EXCEPTIONS.search(stripped_after.lower())
                    )
                    is_in_math = bool(MATH_END_REGEX.search(stripped_after))

                    # Убираем существующие точки/запятые/двоеточия/точки с запятой,
                    # если они не являются частью сокращения или специального синтаксиса
                    should_remove_last_punct = (
                        last_char in [".", ",", ":", ";"]
                        and not is_abbreviation
                        and not is_in_math
                    )

                    if should_remove_last_punct:
                        stripped_after = stripped_after[:last_char_pos].rstrip()

                    # Определяем нужный знак препинания для конца
                    if is_after_gde and not is_last:
                        # Для всех пунктов кроме последнего после "где" ставим точку с запятой
                        new_ending = ";"
                    elif mode_colon:
                        # Режим двоеточия: для последнего пункта - точка, для остальных - точка с запятой
                        new_ending = "." if is_last else ";"
                    else:
                        # Стандартный режим: всегда точка
                        new_ending = "."

                # Формируем новую строку
                new_line_content = f"{before_item}\\item {stripped_after}{new_ending}"

                # Проверяем, что строка действительно изменилась
                if new_line_content != original_line:
                    changes.append((item_idx + 1, original_line, new_line_content))
                    lines[item_idx] = new_line_content
                    changes_made = True

            if changes_made:
                count_fixed += 1

            i = end_idx + 1
            # Помечаем обработанные позиции для защиты от повторной обработки
            processed_positions.update(range(start_idx, end_idx + 2))
        else:
            i += 1
            processed_positions.add(i)

    # 9. Логирование только при наличии фактических изменений
    if changes:
        for line_num, old_line, new_line in changes:
            info(f"{filepath}:{line_num}:")
            info(f"- {old_line.rstrip()}")
            info(f"+ {new_line.rstrip()}")
        info(f"{filepath}: всего исправлено списков: {count_fixed}")

    return 0, "\n".join(lines)
