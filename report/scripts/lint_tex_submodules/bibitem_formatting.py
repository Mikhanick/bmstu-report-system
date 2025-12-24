import re


class BibliographyValidator:
    def __init__(self):
        """Инициализация валидатора со всеми правилами и поддержкой русских букв"""
        self.patterns = self._compile_patterns()
        self.scientific_domains = [
            "arxiv.org",
            "cyberleninka.ru",
            "elibrary.ru",
            "springer.com",
            "ieee.org",
            "acm.org",
            "sciencedirect.com",
            "tandfonline.com",
            "researchgate.net",
            "academia.edu",
            "scholar.google.com",
            "sci-hub.se",
            "sci-hub.st",
            "sci-hub.ru",
            "link.springer.com",
            "ieeexplore.ieee.org",
        ]

    def _compile_patterns(self):
        """Компилирует все регулярные выражения с поддержкой русских букв"""
        return {
            # Авторы - поддержка кириллицы и латиницы
            "author_with_comma": re.compile(
                r"([А-ЯЁа-яёA-Z][а-яёa-z]+),\s*([А-ЯЁA-Z]\.)"
            ),
            "author_separator": re.compile(r"[;,]"),
            "etal_source": re.compile(r"et\s*\.?\s*al\.?|и\s*др\.?", re.IGNORECASE),
            "etal_marker": re.compile(r"\[и\s*др\.\]"),
            "author_slash_section": re.compile(r"^([^/]+)\s*/\s*([^/]+?(?://|$))"),
            # Электронные ресурсы
            "url_pattern": re.compile(r"URL:\s*\\url\{([^}]+)\}"),
            "electronic_marker": re.compile(r"\[Электронный ресурс\]", re.IGNORECASE),
            "access_date": re.compile(r"\(дата\s+обращения:\s*(\d{2}\.\d{2}\.\d{4})\)"),
            # Структура записи с поддержкой русских названий
            "dash_pattern": re.compile(r"\s---\s"),
            "journal_separator": re.compile(r"//"),
            "journal_after_separator": re.compile(r"//\s*([^–]+)"),
            "bibitem_pattern": re.compile(r"\\bibitem\{([^\}]+)\}\s*(.*)", re.DOTALL),
            # Числовые обозначения - ИСПРАВЛЕНО: только неправильные форматы в контексте страниц
            "volume_wrong": re.compile(r"\bVol\.?|vol\.?\b", re.IGNORECASE),
            "number_wrong": re.compile(r"\bNo\.?|no\.?\b", re.IGNORECASE),
            "pages_wrong": re.compile(
                r"\b(?:pp\.?|p\.?|с\.?|стр\.?)\s*\d", re.IGNORECASE
            ),  # ИЩЕМ ТОЛЬКО С ЦИФРАМИ
            "pages_correct": re.compile(r"\bС\.\s*\d"),
            # Чистота
            "extra_spaces": re.compile(r"\s{2,}"),
            "double_punctuation": re.compile(r"([.,;:])\1+"),
            "leading_spaces": re.compile(r"^\s+"),
            "trailing_spaces": re.compile(r"\s+$"),
        }

    def _is_scientific_repo(self, url):
        """Определяет, является ли URL научным репозиторием"""
        if not url:
            return False
        return any(domain in url.lower() for domain in self.scientific_domains)

    def _count_authors(self, authors_string):
        """Подсчитывает количество авторов в строке с поддержкой кириллицы"""
        if not authors_string:
            return 0
        authors = [
            a.strip()
            for a in re.split(self.patterns["author_separator"], authors_string)
            if a.strip()
        ]
        return len(authors)

    def _extract_start_authors(self, entry_content):
        """Извлекает авторов из начала записи до первого разделителя"""
        # Берем часть до первого // или -- (но не до /, так как / может быть частью структуры)
        first_part = re.split(r"//|--", entry_content, maxsplit=1)[0].strip()
        return [
            a.strip()
            for a in re.split(self.patterns["author_separator"], first_part)
            if a.strip()
        ]


    def _get_all_authors_count(self, entry_content):
        """Получает общее количество авторов в записи, учитывая обе части разделителя /"""
        slash_match = self.patterns["author_slash_section"].match(entry_content)

        if slash_match:
            # Есть разделитель /, считаем авторов после него
            authors_part = slash_match.group(2).split("//")[0].split("--")[0].strip()
            return self._count_authors(authors_part)
        else:
            # Нет разделителя /, считаем авторов в начале
            start_authors = self._extract_start_authors(entry_content)
            return len(start_authors)

    def _has_etal_indication(self, text):
        """Проверяет наличие указаний на других авторов (et al, и др.)"""
        return bool(self.patterns["etal_source"].search(text)) or bool(
            self.patterns["etal_marker"].search(text)
        )

    def _validate_publication_after_separator(self, entry_content, warnings):
        """Проверяет, что после разделителя // есть название издания"""
        separator_match = self.patterns["journal_separator"].search(entry_content)
        if separator_match:
            # Ищем текст после разделителя //
            after_separator = entry_content[separator_match.end() :].strip()

            # Берем текст до следующего разделителя -- или конца строки
            next_separator = re.search(r"--|\[|$", after_separator)
            publication_name = (
                after_separator[: next_separator.start()].strip()
                if next_separator
                else after_separator.strip()
            )

            if not publication_name:
                warnings.append(
                    "❌ После разделителя '//' отсутствует название издания (журнала, конференции, сборника)."
                )
            elif len(publication_name) < 5:  # Увеличиваем минимальную длину
                warnings.append(
                    f"❌ Название издания после '//' слишком короткое: '{publication_name}'. Укажите полное название."
                )
            elif not re.search(
                r"[а-яёА-ЯЁa-zA-Z]{3,}", publication_name
            ):  # Требуем минимум 3 буквы подряд
                warnings.append(
                    f"❌ Название издания после '//' не содержит достаточно букв: '{publication_name}'. Укажите корректное название."
                )
        else:
            # Проверяем, требуется ли разделитель // для этого типа источника
            if any(
                keyword in entry_content.lower()
                for keyword in [
                    "journal",
                    "proc.",
                    "conference",
                    "трансляции",
                    "сборник",
                    "конференция",
                    "журнал",
                    "доклады",
                    "труды",
                    "proceedings",
                ]
            ):
                warnings.append(
                    "❌ Для указания названия журнала/конференции/сборника требуется разделитель '//'."
                )

    def validate_author_rules(self, entry_content, warnings):
        """Проверяет все правила, связанные с авторами с поддержкой кириллицы"""
        # Правило 1: Запрещены запятые между фамилией и инициалом (поддержка кириллицы)
        comma_authors = self.patterns["author_with_comma"].findall(entry_content)
        for match in comma_authors:
            full_match = f"{match[0]}, {match[1]}"
            warnings.append(
                f"❌ Запрещены запятые между фамилией и инициалом: '{full_match}'. Используйте 'Фамилия И.'"
            )

        # Правило 2: Правила размещения авторов
        slash_match = self.patterns["author_slash_section"].match(entry_content)
        has_electronic_marker = bool(
            self.patterns["electronic_marker"].search(entry_content)
        )

        # Извлекаем авторов до первого разделителя
        start_authors = self._extract_start_authors(entry_content)
        author_count = len(start_authors)
        has_etal = self._has_etal_indication(entry_content)

        if author_count > 3 or has_etal:
            # Случай: >3 авторов или есть et al/[и др.]
            if not slash_match:
                warnings.append(
                    f"❌ При {author_count} авторах или наличии 'et al/[и др.]' требуется разделитель '/'. Формат: 'ПервыйАвтор А. Название... / Все авторы или ПервыйАвтор А. [и др.]'"
                )
            else:
                # Проверяем корректность оформления после разделителя
                authors_part = (
                    slash_match.group(2).split("//")[0].split("--")[0].strip()
                )
                authors_count = self._get_all_authors_count(authors_part)

                if (
                    not self._has_etal_indication(authors_part)
                    and authors_count < author_count
                ):
                    warnings.append(
                        f"❌ После разделителя '/' должно быть перечислено всех {author_count} авторов или использована пометка '[и др.]'. Найдено только {authors_count} авторов."
                    )
        else:
            # Случай: ≤3 авторов и нет et al
            if slash_match and not has_electronic_marker:
                warnings.append(
                    f"❌ При {author_count} авторах (≤3) и отсутствии 'et al/[и др.]' не требуется разделитель '/'. Все авторы должны быть в начале перед названием."
                )

    def validate_electronic_rules(self, entry_content, url, warnings):
        """Проверяет все правила для электронных ресурсов"""
        is_scientific = self._is_scientific_repo(url) if url else False
        has_electronic_marker = bool(
            self.patterns["electronic_marker"].search(entry_content)
        )
        has_access_date = bool(self.patterns["access_date"].search(entry_content))

        if is_scientific:
            # Правила для научных репозиториев
            if has_electronic_marker:
                warnings.append(
                    "❌ Для научных репозиториев (arXiv, Cyberleninka и др.) не используется пометка '[Электронный ресурс]'"
                )
            if has_access_date:
                warnings.append(
                    "❌ Для научных репозиториев не требуется указывать дату обращения"
                )
        else:
            # Правила для обычных электронных ресурсов
            if url and not is_scientific:
                if has_electronic_marker and not has_access_date:
                    warnings.append(
                        "❌ Для электронного ресурса с пометкой '[Электронный ресурс]' требуется дата обращения в формате '(дата обращения: ДД.ММ.ГГГГ)'"
                    )
                if not has_electronic_marker:
                    warnings.append(
                        "❌ Для обычного электронного ресурса (не научный репозиторий) требуется пометка '[Электронный ресурс]'"
                    )

            # Правило логической связности
            if has_access_date and not has_electronic_marker:
                warnings.append(
                    "❌ Дата обращения указывается только при наличии пометки '[Электронный ресурс]'"
                )
            if has_electronic_marker and not url:
                warnings.append("❌ Пометка '[Электронный ресурс]' требует наличия URL")

    def validate_structure_rules(self, entry_content, warnings):
        """Проверяет правила структуры записи с поддержкой русских названий"""
        # Правило 1: Длинные тире "---"
        if not self.patterns["dash_pattern"].search(entry_content):
            warnings.append(
                "❌ Используйте длинные тире '---' для разделения частей записи (год, том, страницы). Короткие дефисы '-' и двойные тире '--' недопустимы."
            )

        # Правило 2: Проверка наличия издания после разделителя //
        self._validate_publication_after_separator(entry_content, warnings)

        # Правило 3: Числовые обозначения - только неправильные форматы
        if self.patterns["volume_wrong"].search(entry_content):
            warnings.append(
                "❌ 'Vol.' должно быть заменено на 'Том' для русскоязычного оформления"
            )

        if self.patterns["number_wrong"].search(entry_content):
            warnings.append(
                "❌ 'No.' должно быть заменено на '№' для русскоязычного оформления"
            )

        # Проверяем только неправильные форматы страниц, но не срабатываем на правильное "С."
        if self.patterns["pages_wrong"].search(entry_content) and not self.patterns[
            "pages_correct"
        ].search(entry_content):
            warnings.append(
                "❌ 'pp.', 'p.', 'с.', 'стр.' должно быть заменено на 'С.' для русскоязычного оформления"
            )

    def validate_consistency_rules(self, entry_content, warnings):
        """Проверяет правила согласованности и чистоты оформления с поддержкой кириллицы"""
        # Правило 1: Лишние пробелы
        if self.patterns["extra_spaces"].search(entry_content):
            warnings.append(
                "❌ Обнаружены лишние пробелы в тексте. Используйте одинарные пробелы."
            )

        # Правило 2: Двойные знаки препинания
        if self.patterns["double_punctuation"].search(entry_content):
            match = self.patterns["double_punctuation"].search(entry_content)
            warnings.append(
                f"❌ Обнаружены двойные знаки препинания: '{match.group(0)}'. Используйте одинарные знаки."
            )

        # Правило 3: Проверка формата [и др.]
        etal_matches = self.patterns["etal_marker"].findall(entry_content)
        for etal in etal_matches:
            if etal != "[и др.]":
                warnings.append(
                    f"❌ Неправильный формат пометки для других авторов: '{etal}'. Используйте строго '[и др.]'"
                )

    def validate_entry(self, bibitem_text):
        """
        Полная валидация одной библиографической записи

        Args:
            bibitem_text (str): Текст записи с \bibitem

        Returns:
            dict: Словарь с результатами валидации
        """
        result = {
            "original": self.patterns["leading_spaces"].sub(
                "", self.patterns["trailing_spaces"].sub("", bibitem_text)
            ),
            "is_valid": True,
            "warnings": [],
            "errors": [],
            "source_type": "unknown",
        }

        # Извлекаем ключ и содержимое
        bibitem_match = self.patterns["bibitem_pattern"].match(bibitem_text)
        if not bibitem_match:
            result["errors"].append(
                "❌ Не удалось распознать структуру записи \\bibitem"
            )
            result["is_valid"] = False
            return result

        result["key"] = bibitem_match.group(1)
        entry_content = bibitem_match.group(2).strip()

        # Извлекаем URL
        url_match = self.patterns["url_pattern"].search(entry_content)
        url = url_match.group(1) if url_match else None
        result["source_type"] = (
            "scientific"
            if self._is_scientific_repo(url)
            else "electronic"
            if url
            else "print"
        )

        # Проводим валидацию по всем правилам
        self.validate_author_rules(entry_content, result["warnings"])
        self.validate_electronic_rules(entry_content, url, result["warnings"])
        self.validate_structure_rules(entry_content, result["warnings"])
        self.validate_consistency_rules(entry_content, result["warnings"])

        # Определяем валидность
        result["is_valid"] = len(result["warnings"]) == 0 and len(result["errors"]) == 0

        return result

    def validate_bibliography(self, bibitems):
        """
        Валидация всего списка библиографических записей

        Args:
            bibitems (list[str]): Список записей \bibitem

        Returns:
            dict: Сводный результат валидации
        """
        results = []
        for item in bibitems:
            results.append(self.validate_entry(item))

        # Формируем сводную статистику
        total = len(results)
        valid = sum(1 for r in results if r["is_valid"])
        invalid = total - valid

        summary = {
            "total_entries": total,
            "valid_entries": valid,
            "invalid_entries": invalid,
            "validation_rate": (valid / total * 100) if total > 0 else 0,
            "entries": results,
        }

        return summary


def validate_single_entry(bibitem_text):
    """Удобная функция для валидации одной записи с выводом результатов"""
    validator = BibliographyValidator()
    result = validator.validate_entry(bibitem_text)

    print("=== РЕЗУЛЬТАТЫ ВАЛИДАЦИИ ===")
    print(f"Ключ записи: {result['key']}")
    print(f"Тип источника: {result['source_type']}")
    print(
        f"Статус: {'✅ КОРРЕКТНО' if result['is_valid'] else '❌ ТРЕБУЕТ ИСПРАВЛЕНИЙ'}"
    )

    if result["warnings"]:
        print(f"\n⚠️ НАЙДЕНО {len(result['warnings'])} ПРЕДУПРЕЖДЕНИЙ:")
        for i, warning in enumerate(result["warnings"], 1):
            print(f"{i}. {warning}")

    if result["errors"]:
        print(f"\n❌ НАЙДЕНО {len(result['errors'])} ОШИБОК:")
        for i, error in enumerate(result["errors"], 1):
            print(f"{i}. {error}")

    print("\nИСХОДНЫЙ ТЕКСТ:")
    print(result["original"])
    print("=" * 60)

    return result


# Исправленные примеры для тестирования
if __name__ == "__main__":
    # Пример 5: Корректная запись arXiv с русским описанием
    test5 = r"""\bibitem{arxiv_russian}
Чжан Л. Простые базовые методы для восстановления изображений (NAFNet) / Чжан Л., Чу С., Чжан С., Сунь Ц. // Труды Европейской конференции по компьютерному зрению. -- 2022. -- URL: \url{https://arxiv.org/abs/2204.04676}"""

    # Пример 6: Корректная запись с электронным ресурсом на русском
    test6 = r"""\bibitem{russian_electronic}
Петров А.Б., Иванов В.Г. Веб-страница с материалами [Электронный ресурс] // Сайт университета. -- 2023. -- URL: \url{https://example.ru} (дата обращения: 16.12.2025)"""

    print("ТЕСТ 5: Исправленная запись arXiv с русским описанием")
    validate_single_entry(test5)

    print("\nТЕСТ 6: Исправленная запись с электронным ресурсом на русском")
    validate_single_entry(test6)
