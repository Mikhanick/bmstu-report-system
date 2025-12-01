#!/usr/bin/env python3
import csv
import sys
import os
import matplotlib.pyplot as plt
import re
import numpy as np
from matplotlib.lines import Line2D

plt.rcParams["font.family"] = "STIXGeneral"
plt.rcParams["text.usetex"] = False
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42

# Стандартные маркеры для автоматического выбора
DEFAULT_MARKERS = ["o", "s", "^", "D", "v", "<", ">", "p", "h", "*", "X", "P"]


def parse_metadata_and_data(csv_path):
    metadata = {}
    data_lines = []
    fieldnames = None

    with open(csv_path, "r", encoding="utf-8") as f:
        # Сначала читаем заголовки для сохранения порядка
        header_line = None
        for line in f:
            stripped = line.strip()
            if stripped.startswith("#"):
                if ":" in stripped:
                    key, value = stripped[1:].split(":", 1)
                    metadata[key.strip()] = value.strip()
            elif stripped:
                header_line = stripped
                break

        if header_line is None:
            raise ValueError("Нет данных в CSV")

        fieldnames = next(csv.reader([header_line]))
        data_lines = [line for line in f if line.strip()]

    if not data_lines:
        raise ValueError("Нет данных в CSV")

    reader = csv.DictReader(data_lines, fieldnames=fieldnames)
    rows = list(reader)
    if not rows:
        raise ValueError("Пустые данные")

    return metadata, rows, fieldnames


def parse_series_labels(label_str, mode="list"):
    """Парсит метки в зависимости от режима"""
    if not label_str:
        return []

    if mode == "map":
        # Режим ключ:значение (для series_col)
        items = {}
        pairs = re.split(r"[;,]\s*", label_str)
        for pair in pairs:
            if ":" in pair:
                key, value = pair.split(":", 1)
                items[key.strip()] = value.strip()
        return items
    else:
        # Режим списка (для multi_column)
        return [
            part.strip() for part in re.split(r"[;,]\s*", label_str) if part.strip()
        ]


def parse_series_markers(marker_str, mode="list"):
    """Парсит маркеры в зависимости от режима"""
    if not marker_str:
        return []

    if mode == "map":
        # Режим ключ:значение (для series_col)
        items = {}
        pairs = re.split(r"[;,]\s*", marker_str)
        for pair in pairs:
            if ":" in pair:
                key, value = pair.split(":", 1)
                items[key.strip()] = value.strip()
        return items
    else:
        # Режим списка (для multi_column)
        return [
            part.strip() for part in re.split(r"[;,]\s*", marker_str) if part.strip()
        ]


def parse_approximation(approx_str):
    """Парсит параметры аппроксимации"""
    if not approx_str:
        return None

    approx_str = approx_str.strip().lower()

    if approx_str == "none" or approx_str == "linear":
        return {"type": "linear"}

    if approx_str.startswith("polynomial"):
        parts = approx_str.split(":")
        if len(parts) > 1:
            try:
                degree = int(parts[1].strip())
                return {"type": "polynomial", "degree": degree}
            except ValueError:
                return {"type": "polynomial", "degree": 2}
        return {"type": "polynomial", "degree": 2}

    if approx_str.startswith("spline"):
        parts = approx_str.split(":")
        if len(parts) > 1:
            try:
                smooth = float(parts[1].strip())
                return {"type": "spline", "smooth": smooth}
            except ValueError:
                return {"type": "spline", "smooth": 0.5}
        return {"type": "spline", "smooth": 0.5}

    return None


def perform_approximation(x_vals, y_vals, approx_params, num_points=200):
    """Выполняет аппроксимацию данных"""
    if not approx_params or len(x_vals) < 2:
        return None, None

    try:
        x = np.array(x_vals)
        y = np.array(y_vals)

        # Создаем плотную сетку для плавной кривой
        x_new = np.linspace(np.min(x), np.max(x), num_points)

        if approx_params["type"] == "linear":
            coeffs = np.polyfit(x, y, 1)
            y_new = np.polyval(coeffs, x_new)
            return x_new, y_new

        elif approx_params["type"] == "polynomial":
            degree = approx_params["degree"]
            # Проверяем, достаточно ли точек для аппроксимации
            if len(x) <= degree:
                print(
                    f"Предупреждение: недостаточно точек для полинома степени {degree}. Используется линейная аппроксимация.",
                    file=sys.stderr,
                )
                coeffs = np.polyfit(x, y, 1)
            else:
                coeffs = np.polyfit(x, y, degree)
            y_new = np.polyval(coeffs, x_new)
            return x_new, y_new

        elif approx_params["type"] == "spline":
            from scipy.interpolate import UnivariateSpline

            smooth = approx_params["smooth"]
            spline = UnivariateSpline(x, y, s=smooth)
            y_new = spline(x_new)
            return x_new, y_new

    except Exception as e:
        print(
            f"Предупреждение: ошибка аппроксимации ({e}). Используются исходные точки.",
            file=sys.stderr,
        )

    return None, None


def main():
    if len(sys.argv) != 3:
        print("Использование: python generate_plot.py <входной.csv> <выходной.pdf>")
        sys.exit(1)

    input_csv = sys.argv[1]
    output_pdf = sys.argv[2]

    if not os.path.isfile(input_csv):
        print(f"Ошибка: входной файл не найден: {input_csv}", file=sys.stderr)
        sys.exit(1)

    try:
        metadata, rows, fieldnames = parse_metadata_and_data(input_csv)
    except Exception as e:
        print(f"Ошибка чтения CSV: {e}", file=sys.stderr)
        sys.exit(1)

    # Получаем режим работы
    mode = metadata.get("mode", "").lower().strip()
    xcol = metadata.get("xcol")
    ycol = metadata.get("ycol")
    series_col = metadata.get("series")
    series_labels_str = metadata.get("series_labels", "")
    series_markers_str = metadata.get("series_markers", "")
    approximation_str = metadata.get("approximation", "")

    # Парсим параметры
    approx_params = parse_approximation(approximation_str)

    # Проверка конфликтов режимов
    if mode == "multi_column" and series_col:
        print(
            "Ошибка: нельзя одновременно использовать #mode: multi_column и #series",
            file=sys.stderr,
        )
        sys.exit(1)

    # Режим multi_column: каждая колонка - отдельная серия
    if mode == "multi_column":
        if not xcol:
            print(
                "Ошибка: в режиме multi_column обязательно указать #xcol",
                file=sys.stderr,
            )
            sys.exit(1)

        if xcol not in fieldnames:
            print(f"Ошибка: колонка '{xcol}' отсутствует в данных", file=sys.stderr)
            sys.exit(1)

        # Сохраняем порядок колонок как в CSV (кроме xcol)
        y_columns = [col for col in fieldnames if col != xcol]

        if not y_columns:
            print(
                "Ошибка: в режиме multi_column не найдены колонки для отображения",
                file=sys.stderr,
            )
            sys.exit(1)

        # Определяем режим парсинга меток
        label_mode = (
            "map"
            if any(":" in part for part in re.split(r"[;,]", series_labels_str))
            else "list"
        )
        marker_mode = (
            "map"
            if any(":" in part for part in re.split(r"[;,]", series_markers_str))
            else "list"
        )

        custom_labels = parse_series_labels(series_labels_str, mode=label_mode)
        custom_markers = parse_series_markers(series_markers_str, mode=marker_mode)

        # Проверяем соответствие количества меток
        if (
            label_mode == "list"
            and isinstance(custom_labels, list)
            and len(custom_labels) != len(y_columns)
        ):
            print(
                f"Предупреждение: количество меток ({len(custom_labels)}) не совпадает с числом серий ({len(y_columns)}). "
                "Будут использованы названия колонок для недостающих меток.",
                file=sys.stderr,
            )

    # Стандартный режим (с series или без)
    else:
        if not xcol or not ycol:
            print("Ошибка: в CSV должны быть указаны #xcol и #ycol", file=sys.stderr)
            sys.exit(1)

        if xcol not in fieldnames or ycol not in fieldnames:
            print(
                f"Ошибка: колонки '{xcol}' или '{ycol}' отсутствуют в данных",
                file=sys.stderr,
            )
            sys.exit(1)

        if series_col and series_col not in fieldnames:
            print(f"Ошибка: колонка серии '{series_col}' отсутствует", file=sys.stderr)
            sys.exit(1)

        # Парсим метки и маркеры для series_col режима
        custom_labels = (
            parse_series_labels(series_labels_str, mode="map")
            if series_labels_str
            else {}
        )
        custom_markers = (
            parse_series_markers(series_markers_str, mode="map")
            if series_markers_str
            else {}
        )

    # Опциональные метаданные
    title = metadata.get("title", "")
    xlabel = metadata.get("xlabel", xcol)
    ylabel = metadata.get("ylabel", ycol if mode != "multi_column" else "Значение")

    plt.figure(figsize=(10, 6))

    # Режим multi_column: каждая колонка - отдельная серия
    if mode == "multi_column":
        series_data = {col: {"x": [], "y": []} for col in y_columns}

        # Собираем данные
        for row in rows:
            try:
                x_val = float(row[xcol])
            except (ValueError, KeyError):
                continue

            for col in y_columns:
                try:
                    y_val = float(row[col])
                    series_data[col]["x"].append(x_val)
                    series_data[col]["y"].append(y_val)
                except (ValueError, KeyError):
                    continue

        # Строим серии
        marker_legend_handles = []
        for i, col in enumerate(y_columns):
            # Выбираем метку
            label = col
            if isinstance(custom_labels, dict) and col in custom_labels:
                label = custom_labels[col]
            elif isinstance(custom_labels, list) and i < len(custom_labels):
                label = custom_labels[i]

            # Выбираем маркер
            marker = DEFAULT_MARKERS[i % len(DEFAULT_MARKERS)]
            if isinstance(custom_markers, dict) and col in custom_markers:
                marker = custom_markers[col]
            elif isinstance(custom_markers, list) and i < len(custom_markers):
                marker = custom_markers[i]

            # Строим точки
            x_vals = series_data[col]["x"]
            y_vals = series_data[col]["y"]

            if not x_vals or not y_vals:
                continue

            # Сначала строим точки с маркерами
            points = plt.scatter(
                x_vals, y_vals, s=60, marker=marker, zorder=3, label=f"{label} (точки)"
            )

            # Затем строим линию (аппроксимацию или обычную)
            if approx_params and approx_params["type"] != "none":
                x_approx, y_approx = perform_approximation(
                    x_vals, y_vals, approx_params
                )
                if x_approx is not None and y_approx is not None:
                    (line,) = plt.plot(
                        x_approx,
                        y_approx,
                        linestyle="-",
                        linewidth=2.5,
                        alpha=0.8,
                        label=f"{label} (аппроксимация)",
                    )
                    # Создаем составной маркер для легенды
                    marker_legend_handles.append(
                        Line2D(
                            [0],
                            [0],
                            marker=marker,
                            color=line.get_color(),
                            linestyle="-",
                            markersize=10,
                            label=label,
                        )
                    )
                else:
                    # Если аппроксимация не удалась, строим обычную линию
                    (line,) = plt.plot(
                        x_vals,
                        y_vals,
                        marker=marker,
                        linestyle="-",
                        linewidth=2,
                        markersize=8,
                        alpha=0.8,
                        label=label,
                    )
                    marker_legend_handles.append(line)
            else:
                # Обычная кусочно-линейная функция
                (line,) = plt.plot(
                    x_vals,
                    y_vals,
                    marker=marker,
                    linestyle="-",
                    linewidth=2,
                    markersize=8,
                    alpha=0.8,
                    label=label,
                )
                marker_legend_handles.append(line)

        # Создаем кастомную легенду с составными маркерами
        if marker_legend_handles:
            plt.legend(handles=marker_legend_handles)

    # Стандартный режим с группировкой по колонке series
    elif series_col:
        series_groups = {}
        for row in rows:
            key = row[series_col]
            if key not in series_groups:
                series_groups[key] = {"x": [], "y": []}
            try:
                series_groups[key]["x"].append(float(row[xcol]))
                series_groups[key]["y"].append(float(row[ycol]))
            except ValueError:
                continue  # пропускаем некорректные строки

        # Строим серии
        marker_legend_handles = []
        for i, (key, data) in enumerate(series_groups.items()):
            x_vals = data["x"]
            y_vals = data["y"]

            if not x_vals or not y_vals:
                continue

            # Выбираем метку
            label = (
                custom_labels.get(key, key) if isinstance(custom_labels, dict) else key
            )

            # Выбираем маркер
            marker = DEFAULT_MARKERS[i % len(DEFAULT_MARKERS)]
            if isinstance(custom_markers, dict) and key in custom_markers:
                marker = custom_markers[key]

            # Строим точки
            points = plt.scatter(
                x_vals, y_vals, s=60, marker=marker, zorder=3, label=f"{label} (точки)"
            )

            # Затем строим линию (аппроксимацию или обычную)
            if approx_params and approx_params["type"] != "none":
                x_approx, y_approx = perform_approximation(
                    x_vals, y_vals, approx_params
                )
                if x_approx is not None and y_approx is not None:
                    (line,) = plt.plot(
                        x_approx,
                        y_approx,
                        linestyle="-",
                        linewidth=2.5,
                        alpha=0.8,
                        label=f"{label} (аппроксимация)",
                    )
                    # Создаем составной маркер для легенды
                    marker_legend_handles.append(
                        Line2D(
                            [0],
                            [0],
                            marker=marker,
                            color=line.get_color(),
                            linestyle="-",
                            markersize=10,
                            label=label,
                        )
                    )
                else:
                    # Если аппроксимация не удалась, строим обычную линию
                    (line,) = plt.plot(
                        x_vals,
                        y_vals,
                        marker=marker,
                        linestyle="-",
                        linewidth=2,
                        markersize=8,
                        alpha=0.8,
                        label=label,
                    )
                    marker_legend_handles.append(line)
            else:
                # Обычная кусочно-линейная функция
                (line,) = plt.plot(
                    x_vals,
                    y_vals,
                    marker=marker,
                    linestyle="-",
                    linewidth=2,
                    markersize=8,
                    alpha=0.8,
                    label=label,
                )
                marker_legend_handles.append(line)

        # Создаем кастомную легенду с составными маркерами
        if marker_legend_handles:
            plt.legend(handles=marker_legend_handles)

    # Простой режим без серий
    else:
        x_vals, y_vals = [], []
        for row in rows:
            try:
                x_vals.append(float(row[xcol]))
                y_vals.append(float(row[ycol]))
            except ValueError:
                continue

        if x_vals and y_vals:
            # Строим точки
            plt.scatter(x_vals, y_vals, s=60, marker="o", zorder=3, color="blue")

            # Строим линию (аппроксимацию или обычную)
            if approx_params and approx_params["type"] != "none":
                x_approx, y_approx = perform_approximation(
                    x_vals, y_vals, approx_params
                )
                if x_approx is not None and y_approx is not None:
                    plt.plot(x_approx, y_approx, "b-", linewidth=2.5, alpha=0.8)
                else:
                    plt.plot(
                        x_vals, y_vals, "bo-", linewidth=2, markersize=8, alpha=0.8
                    )
            else:
                plt.plot(x_vals, y_vals, "bo-", linewidth=2, markersize=8, alpha=0.8)

    plt.title(title, fontsize=14, pad=20)
    plt.xlabel(xlabel, fontsize=12)
    plt.ylabel(ylabel, fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.7)
    plt.tight_layout()

    # Сохранение
    output_dir = os.path.dirname(output_pdf)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    try:
        plt.savefig(output_pdf, bbox_inches="tight")
        print(f"График успешно сохранён: {output_pdf}")
    except Exception as e:
        print(f"Ошибка сохранения PDF: {e}", file=sys.stderr)
        sys.exit(1)

    plt.close()


if __name__ == "__main__":
    main()
