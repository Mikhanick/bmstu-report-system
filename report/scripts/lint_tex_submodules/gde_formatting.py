import re
from .lint_logging import info


def format_variables_enumerate(text, filepath):
    """
    Форматирует описания переменных после формул.
    Корректно обрабатывает:
    - Разделители только вне формул
    - Составные переменные (оставляет в одной строке при отсутствии разделителя)
    - Защита от повторной обработки уже отформатированных блоков
    """
    # Паттерн для поиска блоков с формулами и описаниями
    # Исключаем блоки, где после "где" уже есть itemize/enumerate
    pattern = (
        r"(\\begin{equation}[\s\S]+?\\end{equation})"  # Блок уравнения
        r"(\s*\n\s*)"  # Пробелы после уравнения
        r"([Гг]де\b(?!"  # "где" но не за которым следует
        r"\s*(?:\\begin{itemize}|\\begin{enumerate}))"  # itemize/enumerate
        r"[\s\S]*?)"  # Описание
        r"(?=\n\s*(?:\n|\\begin{))"  # До пустой строки или начала нового блока
    )

    replacements = []
    detailed_logs = []
    total_replacements = 0
    total_vars_processed = 0

    for match in re.finditer(pattern, text, re.DOTALL):
        eq_block = match.group(1)
        where_block = match.group(3).strip()
        full_match = match.group(0)
        start_pos = match.start()
        end_pos = match.end()

        # Извлекаем текст после "где"
        where_text = re.sub(r"^[Гг]де\s*", "", where_block, count=1).strip()

        # Если в тексте уже есть LaTeX окружения или сложные конструкции - пропускаем
        if re.search(
            r"\\begin{(?:equation|align|cases|itemize|enumerate)}", where_text
        ):
            continue

        # Парсим переменные с умным разделением
        variables = parse_variables_with_context(where_text)

        # Форматируем только если переменных больше 2
        if len(variables) > 2:
            total_replacements += 1
            total_vars_processed += len(variables)

            # Создаём itemize
            enum_items = []
            for var in variables:
                if var["description"]:
                    enum_items.append(
                        f"\\item {var['variable']} --- {var['description']}"
                    )
                else:
                    enum_items.append(f"\\item {var['variable']}")

            enum_text = (
                "\\begin{itemize}\n" + "\n".join(enum_items) + "\n\\end{itemize}"
            )
            new_block = f"{eq_block}\nгде\n{enum_text}\n"

            # Логирование
            log_message = (
                f"\n{'=' * 60}\n"
                f"ФАЙЛ: {filepath}\n"
                f"НАЙДЕН БЛОК ДЛЯ ФОРМАТИРОВАНИЯ:\n"
                f"Оригинальный текст после 'где':\n"
                f"  {where_block}\n\n"
                f"Распарсенные переменные ({len(variables)} шт.):\n"
                + "\n".join([f"  - {var['raw_text']}" for var in variables])
                + f"\n\n"
                f"СФОРМИРОВАНО СЛЕДУЮЩЕЕ ОКРУЖЕНИЕ itemize:\n"
                f"{enum_text}\n\n"
                f"ЗАМЕНА:\n"
                f"БЫЛО:\n{full_match.strip()}\n\n"
                f"СТАЛО:\n{new_block.strip()}\n"
                f"{'=' * 60}"
            )
            detailed_logs.append(log_message)
            replacements.append((start_pos, end_pos, new_block))

    # Применяем замены
    new_text = text
    for start, end, replacement in reversed(replacements):
        new_text = new_text[:start] + replacement + new_text[end:]

    # Вывод статистики
    if total_replacements > 0:
        for log in detailed_logs:
            info(log)

        summary_message = (
            f"\n{'*' * 80}\n"
            f"ИТОГОВАЯ СТАТИСТИКА ПО ФАЙЛУ {filepath}:\n"
            f"- Найдено блоков с описаниями переменных для форматирования: {total_replacements}\n"
            f"- Всего переменных обработано: {total_vars_processed}\n"
            f"{'*' * 80}"
        )
        info(summary_message)
        info(
            f"{filepath}: отформатировано {total_replacements} описаний переменных в itemize окружения"
        )
        return 0, new_text

    return 0, text


def parse_variables_with_context(text):
    """
    Умный парсер переменных, который:
    1. Делит только по последнему разделителю (запятой/точке с запятой) перед формулой
    2. Оставляет в одной строке элементы без разделителей между ними
    3. Останавливается при переходе на новую строку
    """
    variables = []
    current_segment = ""
    in_formula = False
    formula_depth = 0
    last_separator_pos = -1

    # Обрабатываем текст посимвольно для корректного отслеживания формул
    for i, char in enumerate(text):
        # Отслеживаем вход/выход из формул
        if char == "$":
            if i > 0 and text[i - 1] == "\\":
                # Экранированный доллар
                pass
            else:
                in_formula = not in_formula
        elif char == "{" and in_formula:
            formula_depth += 1
        elif char == "}" and in_formula and formula_depth > 0:
            formula_depth -= 1

        # Ищем разделители вне формул
        if not in_formula and formula_depth == 0:
            if char in [",", ";"] and (
                i == len(text) - 1 or text[i + 1] in [" ", "\n"]
            ):
                last_separator_pos = i

        current_segment += char

        # Проверяем необходимость разделения:
        # 1. Если встретили разделитель И
        # 2. После него начинается формула И
        # 3. Между разделителем и формулой нет другого разделителя
        if i < len(text) - 1:
            next_char = text[i + 1]
            if (
                next_char == "$"
                and not in_formula
                and last_separator_pos != -1
                and "," not in current_segment[last_separator_pos + 1 :]
                and ";" not in current_segment[last_separator_pos + 1 :]
            ):
                # Добавляем текущий сегмент как переменную
                segment = current_segment[:last_separator_pos].strip()
                if segment:
                    variables.append(parse_single_variable(segment))

                # Начинаем новый сегмент после разделителя
                current_segment = current_segment[last_separator_pos + 1 :].strip()
                last_separator_pos = -1

    # Добавляем оставшийся текст как последнюю переменную
    if current_segment.strip():
        variables.append(parse_single_variable(current_segment.strip()))

    return variables


def parse_single_variable(segment):
    """
    Парсит отдельный сегмент на переменную и описание
    """
    # Ищем разделитель "--" вне формул
    parts = re.split(r"\s*--\s*(?=(?:[^$]*\$[^$]*\$)*[^$]*$)", segment, maxsplit=1)

    if len(parts) == 2:
        var_part = parts[0].strip()
        desc_part = parts[1].strip()

        # Особый случай: объединяем переменные с союзом "и" перед описанием
        if re.search(r"\$\w+\$\s+и\s+\$\w+\$", var_part):
            return {"variable": var_part, "description": desc_part, "raw_text": segment}

        return {"variable": var_part, "description": desc_part, "raw_text": segment}
    else:
        return {"variable": segment, "description": "", "raw_text": segment}
