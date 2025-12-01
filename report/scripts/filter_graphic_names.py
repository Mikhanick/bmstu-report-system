#!/usr/bin/env python3
import sys
import os


def main():
    if len(sys.argv) < 3:
        print("Usage: filter_graphic_names.py <images_dir> <name1> [name2 ...]")
        sys.exit(1)

    images_dir = sys.argv[1]
    names = sys.argv[2:]

    # Расширения, которые блокируют генерацию PDF
    blocked_exts = ["png", "jpg", "jpeg", "gif", "svg"]

    names_to_generate = []
    for name in names:
        # Проверяем, есть ли файл с другим расширением
        exists_as_other = any(
            os.path.exists(os.path.join(images_dir, f"{name}.{ext}"))
            for ext in blocked_exts
        )

        if not exists_as_other:
            names_to_generate.append(name)

    print(" ".join(names_to_generate))


if __name__ == "__main__":
    main()
