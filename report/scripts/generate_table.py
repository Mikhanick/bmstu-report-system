#!/usr/bin/env python3
import csv
import sys
import re
import os

def escape_latex(text):
    """Экранирует спецсимволы LaTeX в строке"""
    if text is None:
        return ""
    
    replacements = {
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\^{}',
        '\\': r'\textbackslash{}',
        '_': r'\_',
        '<': r'\textless{}',
        '>': r'\textgreater{}',
    }
    
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)
    
    return re.sub(r'\s+', ' ', text).strip()

def split_header(header, max_line_length=15):
    """
    Умное разделение заголовка на две строки:
    - Если заголовок короткий (<= max_line_length) - оставляем одной строкой
    - Если есть пробелы - разделяем по оптимальному месту (ближе к середине)
    - Если нет пробелов - оставляем как есть
    """
    # Если заголовок пустой или слишком короткий
    if not header or len(header) <= max_line_length:
        return (header, '')
    
    # Ищем оптимальное место для разбивки (ближе к середине)
    target_pos = len(header) // 2
    left_space = header.rfind(' ', 0, target_pos)
    right_space = header.find(' ', target_pos)
    
    # Если нет пробелов - не разбиваем
    if left_space == -1 and right_space == -1:
        return (header, '')
    
    # Выбираем ближайший пробел к середине
    if left_space == -1:
        split_pos = right_space
    elif right_space == -1:
        split_pos = left_space
    else:
        # Выбираем тот пробел, который ближе к середине
        if (target_pos - left_space) <= (right_space - target_pos):
            split_pos = left_space
        else:
            split_pos = right_space
    
    # Возвращаем две части, удаляя лишние пробелы
    part1 = header[:split_pos].strip()
    part2 = header[split_pos:].strip()
    
    # Если вторая часть слишком короткая, возможно, лучше не разбивать
    if len(part2) < 4 and len(part1) > max_line_length + 3:
        return (header, '')
    
    return (part1, part2)

def parse_metadata(csv_path):
    """Извлекает метаданные из комментариев в начале CSV"""
    caption = None
    label = None
    header_max_length = 15  # По умолчанию
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('#caption:'):
                caption = line.split(':', 1)[1].strip()
            elif line.startswith('#label:'):
                label = "tab:" + line.split(':', 1)[1].strip()
            elif line.startswith('#header_max_length:'):
                try:
                    header_max_length = int(line.split(':', 1)[1].strip())
                except ValueError:
                    pass
            elif not line.startswith('#') and line.strip():
                # Первые непустые данные - конец метаданных
                break
    
    if caption is None or label is None:
        raise ValueError(f"В CSV-файле {csv_path} отсутствуют обязательные метаданные #caption или #label")
    
    return caption, label, header_max_length

def generate_latex_table(csv_path, tex_path):
    try:
        caption, label, header_max_length = parse_metadata(csv_path)
    except Exception as e:
        print(f"Ошибка обработки метаданных в {csv_path}: {e}")
        sys.exit(1)
    
    # Собираем данные, пропуская комментарии
    data_lines = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.startswith('#') and line.strip():
                data_lines.append(line)
    
    if not data_lines:
        raise ValueError(f"В CSV-файле {csv_path} отсутствуют данные таблицы")
    
    try:
        reader = csv.reader(data_lines)
        headers = next(reader)
        rows = list(reader)
    except Exception as e:
        print(f"Ошибка чтения CSV {csv_path}: {e}")
        sys.exit(1)

    # Умное разделение заголовков
    split_headers = []
    for header in headers:
        escaped = escape_latex(header)
        part1, part2 = split_header(escaped, header_max_length)
        split_headers.append((part1, part2))

    num_cols = len(headers)
    col_format = '|'.join(['c'] * num_cols)
    
    # Создаем директорию для выходного файла, если её нет
    os.makedirs(os.path.dirname(tex_path), exist_ok=True)
    
    with open(tex_path, 'w', encoding='utf-8') as f:
        f.write(f"\\begin{{longtable}}{{|{col_format}|}}\n")
        f.write(f"\\caption{{{caption}}}\\label{{{label}}}\\\\\n")
        f.write("\\toprule\n")
        
        # Первая строка заголовков
        f.write(" & ".join(h[0] for h in split_headers) + " \\\\\n")
        
        # Вторая строка заголовков (только если есть вторая часть)
        second_row = [h[1] for h in split_headers]
        if any(second_row):
            f.write(" & ".join(second_row) + " \\\\\n")
        else:
            # Если все заголовки не требуют переноса, добавляем пустую строку
            f.write(" & ".join([''] * num_cols) + " \\\\\n")
        
        f.write("\\midrule\n")
        f.write("\\endfirsthead\n\n")
        
        # Продолжение таблицы
        f.write(f"\\multicolumn{{{num_cols}}}{{c}}{{Продолжение таблицы \\thetable}} \\\\\n")
        f.write("\\toprule\n")
        f.write(" & ".join(h[0] for h in split_headers) + " \\\\\n")
        
        if any(second_row):
            f.write(" & ".join(second_row) + " \\\\\n")
        else:
            f.write(" & ".join([''] * num_cols) + " \\\\\n")
            
        f.write("\\midrule\n")
        f.write("\\endhead\n\n")
        
        f.write("\\bottomrule\n")
        f.write("\\endfoot\n\n")
        
        # Данные таблицы
        for row in rows:
            processed_row = [escape_latex(cell) for cell in row]
            f.write(" & ".join(processed_row) + " \\\\\n")
        
        f.write("\\end{longtable}\n")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Использование: python generate_table.py <csv> <tex>")
        print("Пример: python generate_table.py data.csv table.tex")
        sys.exit(1)
    
    try:
        generate_latex_table(sys.argv[1], sys.argv[2])
        print(f"Таблица успешно сгенерирована: {sys.argv[2]}")
    except Exception as e:
        print(f"Ошибка генерации таблицы: {e}")
        sys.exit(1)