import re
from .lint_logging import info


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

    while i < len(lines):
        stripped_line = lines[i].strip()

        # 1. Поиск окружений списка
        if stripped_line.startswith(r"\begin{itemize}") or stripped_line.startswith(
            r"\begin{enumerate}"
        ):
            env_type = "itemize" if "itemize" in stripped_line else "enumerate"
            start_idx = i

            # 2. Определение границ списка
            end_idx = -1
            for j in range(i + 1, len(lines)):
                if lines[j].strip() == f"\\end{{{env_type}}}":
                    end_idx = j
                    break

            if end_idx == -1:
                i += 1
                continue

            # 3. Анализ текста перед списком - расширенный контекст
            pre_line_idx = start_idx - 1
            context_lines = []

            # Собираем контекст до пустой строки или начала файла (максимум 5 строк)
            while pre_line_idx >= 0 and len(context_lines) < 5:
                stripped = lines[pre_line_idx].strip()
                if stripped == "":
                    break  # Останавливаемся на пустой строке
                context_lines.append(stripped)
                pre_line_idx -= 1

            if not context_lines:
                i = end_idx + 1
                continue

            # Восстанавливаем хронологический порядок (от старых строк к новым)
            context_lines.reverse()
            full_context = " ".join(context_lines)

            # Проверяем контекст на наличие двоеточия или слова "где" в конце
            ends_with_colon = False
            if ":" in full_context:
                ends_with_colon = True
            else:
                # Ищем слово "где" в конце контекста
                if re.search(r'\bгде\b\s*$', full_context, re.IGNORECASE):
                    ends_with_colon = True
                # Или если "где" находится в конце любой из строк контекста
                elif any(re.search(r'\bгде\b\s*$', line, re.IGNORECASE) for line in context_lines):
                    ends_with_colon = True

            # Для обратной совместимости, используем ближайшую строку для lint-ignore
            pre_line = context_lines[-1]  # Ближайшая строка к списку
            has_lint_ignore_before = "% #lint-ignore" in pre_line

            # 4. Сбор элементов списка
            items = []  # Хранит кортежи (индекс_строки, позиция_\item_в_строке)
            for j in range(start_idx + 1, end_idx):
                line = lines[j]
                item_pos = line.find(r"\item")
                if item_pos != -1:
                    items.append((j, item_pos))

            if not items:
                i = end_idx + 1
                continue

            # 5. Проверка на двоеточия в элементах
            has_colon_in_items = False
            for item_idx, item_pos in items:
                line = lines[item_idx]

                # Пропускаем элементы с игнорированием
                if "% #lint-ignore" in line:
                    continue

                # Извлекаем текст после \item
                after_item = line[item_pos + 5 :]  # 5 = len('\item')

                # Удаляем команды LaTeX для анализа
                clean_text = re.sub(r"\\[a-zA-Z]+(?:\{[^{}]*\})?", "", after_item)

                # Проверяем наличие двоеточий в тексте (не в командах)
                if ":" in clean_text:
                    # Дополнительная проверка: двоеточие не является частью команды
                    if not re.search(r"\\[a-zA-Z]+{[^{}]*:[^{}]*}", after_item):
                        has_colon_in_items = True
                        break

            # 6. Определение режима обработки
            mode_colon = (
                (not has_colon_in_items)
                and ends_with_colon
                and (not has_lint_ignore_before)
            )

            changes_made = False

            # 7. Обработка текста перед списком
            if not mode_colon and not has_lint_ignore_before and ends_with_colon:
                original_line = lines[pre_line_idx]  # Сохраняем исходную строку
                stripped_pre = pre_line.rstrip()
                # Проверяем, что перед двоеточием нет другого знака препинания
                if stripped_pre.endswith(":") and not re.search(
                    r"[.!?]\s*$", stripped_pre[:-1]
                ):
                    indent = pre_line[: len(pre_line) - len(pre_line.lstrip())]
                    new_line = indent + stripped_pre[:-1].rstrip() + "."

                    # Проверяем, что строка действительно изменилась
                    if new_line != original_line:
                        changes.append((pre_line_idx + 1, original_line, new_line))
                        lines[pre_line_idx] = new_line
                        changes_made = True

            # 8. Обработка элементов списка
            for idx, (item_idx, item_pos) in enumerate(items):
                original_line = lines[item_idx]  # Сохраняем исходную строку
                line = original_line

                # Пропускаем элементы с игнорированием
                if "% #lint-ignore" in line:
                    continue

                # Извлечение текста после \item
                before_item = line[:item_pos]  # Отступы перед \item
                after_item = line[
                    item_pos + 5 :
                ].lstrip()  # Текст после \item (без начальных пробелов)

                if not after_item:
                    continue

                new_after_item = after_item

                # === Проверка перед обработкой первой буквы ===
                should_process_first_letter = True

                # 1. Проверка на LaTeX-конструкции в начале (расширенная)
                # Ищем LaTeX-команды, математические окружения и специальные символы
                if re.match(r"^(\$|\\[a-zA-Z]|\\[^a-zA-Z]|\\\(|\\\[)", new_after_item):
                    should_process_first_letter = False
                
                if re.match(r'^[<>\s]*(?:\$|\\[a-zA-Z]+)', new_after_item):
                    should_process_first_letter = False

                # 2. Проверка на аббревиатуры в первом слове (только если ещё не отключено)
                if should_process_first_letter:
                    first_word_end = len(new_after_item)
                    for pos, char in enumerate(new_after_item):
                        if (
                            char in " ,.;:!?([{/\\"
                        ):  # Оптимизированный список разделителей
                            first_word_end = pos
                            break

                    first_word = new_after_item[:first_word_end]

                    # Считаем заглавные буквы в первом слове
                    uppercase_count = sum(
                        1 for c in first_word if c.isalpha() and c.isupper()
                    )

                    # Если больше одной заглавной буквы - считаем это аббревиатурой
                    if uppercase_count > 1:
                        should_process_first_letter = False

                # Обработка первой буквы (только если разрешено)
                if should_process_first_letter:
                    first_alpha_idx = -1
                    for k, char in enumerate(new_after_item):
                        if char.isalpha():
                            first_alpha_idx = k
                            break

                    if first_alpha_idx != -1:
                        if mode_colon:
                            # Строчная первая буква
                            if new_after_item[first_alpha_idx].isupper():
                                new_after_item = (
                                    new_after_item[:first_alpha_idx]
                                    + new_after_item[first_alpha_idx].lower()
                                    + new_after_item[first_alpha_idx + 1 :]
                                )
                        else:
                            # Заглавная первая буква
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

                if last_char_pos >= 0:
                    last_char = stripped_after[last_char_pos]
                    if last_char not in ["!", "?"]:
                        if last_char in [".", ",", ";", ":"]:
                            stripped_after = stripped_after[:-1]
                        if mode_colon:
                            if is_last:
                                new_after_item = stripped_after + "."
                            else:
                                new_after_item = stripped_after + ";"
                        else:
                            new_after_item = stripped_after + "."

                # Формируем новую строку
                new_line_content = f"{before_item}\\item {new_after_item}"

                # Проверяем, что строка действительно изменилась
                if new_line_content != original_line:
                    changes.append((item_idx + 1, original_line, new_line_content))
                    lines[item_idx] = new_line_content
                    changes_made = True

            if changes_made:
                count_fixed += 1

            i = end_idx + 1
        else:
            i += 1

    # 9. Логирование только при наличии фактических изменений
    if changes:
        for line_num, old_line, new_line in changes:
            info(f"{filepath}:{line_num}:")
            info(f"- {old_line.rstrip()}")
            info(f"+ {new_line.rstrip()}")
        info(f"{filepath}: всего исправлено списков: {count_fixed}")

    return 0, "\n".join(lines)
