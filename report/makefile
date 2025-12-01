# === Настройки отчёта ===
PDF_BUILD_DIR_NAME := build
OUTPUT_TEXSTUDIO_NAME ?= report
PDF_MAIN_FILE := report
PDF_IMAGES_DIR := images

# Цвета
GREEN = \033[32m
RED = \033[31m
YELLOW = \033[33m
BLUE = \033[34m
RESET = \033[0m


.PHONY: pdf pdf-clean pdf-synctex lint-tex open-pdf generate-plantuml check-tools

# ===== PDF REPORT BUILD CONFIGURATION =====
PDF_BUILD_DIR := $(PDF_BUILD_DIR_NAME)
PDF_SRC_DIR := src
PDF_TABLES_SRC_DIR := $(PDF_SRC_DIR)/tables
PDF_IMAGES_SRC_DIR := $(PDF_SRC_DIR)/$(PDF_IMAGES_DIR)
PDF_SCRIPTS_DIR := scripts
PDF_TABLES_BUILD_DIR := $(PDF_BUILD_DIR)/tables

PDF_SRC_TEX_FILES := $(wildcard $(PDF_SRC_DIR)/*.tex)
PDF_BUILD_TEX_FILES := $(patsubst $(PDF_SRC_DIR)/%.tex,$(PDF_BUILD_DIR)/%.tex,$(PDF_SRC_TEX_FILES))

PDF_CSV_FILES := $(shell python3 $(PDF_SCRIPTS_DIR)/extract_table_names.py $(PDF_SRC_TEX_FILES))
PDF_GENERATED_TABLES := $(patsubst %,$(PDF_TABLES_BUILD_DIR)/%.tex,$(PDF_CSV_FILES))

# === Автоматическое копирование ВСЕХ изображений ===
# Все PNG/PDF файлы в src/images (включая сгенерированные PlantUML и таблицами)
SRC_IMAGE_FILES := $(wildcard $(PDF_IMAGES_SRC_DIR)/*.png) $(wildcard $(PDF_IMAGES_SRC_DIR)/*.pdf)
# Целевые пути в build/images
BUILD_IMAGE_FILES := $(addprefix $(PDF_BUILD_DIR)/$(PDF_IMAGES_DIR)/,$(notdir $(SRC_IMAGE_FILES)))
PDF_IMAGES_TARGET_DIR := $(PDF_BUILD_DIR)/$(PDF_IMAGES_DIR)

# === Автогенерация графиков === 
PDF_GRAPHIC_BASENAMES := $(sort $(shell \
	grep -h '\\includegraphics' $(PDF_SRC_TEX_FILES) 2>/dev/null | \
	sed -E 's/.*\\includegraphics(\[[^]]*\])?\{([^}]*)\}.*/\2/g' | \
	sed -E 's/\.[^.]*$$//' | \
	sort -u \
))
PDF_GRAPHIC_NAMES_TO_GENERATE := $(shell python3 $(PDF_SCRIPTS_DIR)/filter_graphic_names.py $(PDF_IMAGES_SRC_DIR) $(PDF_GRAPHIC_BASENAMES))
PDF_REQUIRED_IMAGES := $(addprefix $(PDF_IMAGES_SRC_DIR)/,$(addsuffix .pdf,$(PDF_GRAPHIC_NAMES_TO_GENERATE)))

# === PlantUML Settings ===
PLANTUML := plantuml
INKSCAPE := inkscape
PLANTUML_SOURCE_DIR := $(PDF_IMAGES_SRC_DIR)/plantuml
PLANTUML_BUILD_DIR := $(PDF_BUILD_DIR)/images/plantuml
PLANTUML_SVG_FILES := $(patsubst $(PLANTUML_SOURCE_DIR)/%.plantuml,$(PLANTUML_BUILD_DIR)/%.svg,$(wildcard $(PLANTUML_SOURCE_DIR)/*.plantuml))
PLANTUML_PDF_FILES := $(patsubst $(PLANTUML_SOURCE_DIR)/%.plantuml,$(PDF_IMAGES_SRC_DIR)/%.pdf,$(wildcard $(PLANTUML_SOURCE_DIR)/*.plantuml))

# Целевые файлы
PDF_TARGET := $(PDF_BUILD_DIR)/$(PDF_MAIN_FILE).pdf
LINT_MARKER := $(PDF_BUILD_DIR)/.linted

# ===== PDF REPORT BUILD RULES =====
pdf: check-tools generate-plantuml $(PDF_GENERATED_TABLES) $(PDF_TARGET)

pdf-synctex: pdf-clean $(LINT_MARKER) $(PDF_GENERATED_TABLES) $(BUILD_IMAGE_FILES)
	@echo "=== Сборка PDF отчёта с synctex ==="
	pdflatex -synctex=1 \
		-output-directory=$(PDF_BUILD_DIR) \
		-interaction=batchmode \
		-include-directory=$(PDF_SRC_DIR) \
		-jobname=$$(basename $(OUTPUT_TEXSTUDIO_NAME) .tex) \
		$(PDF_SRC_DIR)/$(PDF_MAIN_FILE).tex
		
	pdflatex -synctex=1 \
		-output-directory=$(PDF_BUILD_DIR) \
		-interaction=batchmode \
		-include-directory=$(PDF_SRC_DIR) \
		-jobname=$$(basename $(OUTPUT_TEXSTUDIO_NAME) .tex) \
		$(PDF_SRC_DIR)/$(PDF_MAIN_FILE).tex
		
	@echo "Готово: $(PDF_TARGET)"

$(PDF_TARGET): $(LINT_MARKER) $(PDF_BUILD_TEX_FILES) $(BUILD_IMAGE_FILES)
	@echo "=== Сборка PDF отчёта ==="
	@cd $(PDF_BUILD_DIR) && pdflatex -interaction=batchmode -halt-on-error $(PDF_MAIN_FILE).tex
	@cd $(PDF_BUILD_DIR) && pdflatex -interaction=batchmode -halt-on-error $(PDF_MAIN_FILE).tex
	@echo "Готово: $(PDF_TARGET)"

$(PDF_BUILD_DIR)/%.tex: $(PDF_SRC_DIR)/%.tex
	@mkdir -p $(dir $@)
	@cp $< $@
	@echo "Скопировано в build: $@"

$(LINT_MARKER): $(PDF_SRC_TEX_FILES) $(PDF_SCRIPTS_DIR)/lint_tex.py
	@python3 $(PDF_SCRIPTS_DIR)/lint_tex.py $(PDF_SRC_TEX_FILES)
	@mkdir -p $(PDF_BUILD_DIR)
	@touch $@

# === Генерация изображений из таблиц ===
$(PDF_IMAGES_SRC_DIR)/%.pdf: $(PDF_TABLES_SRC_DIR)/%.csv $(PDF_SCRIPTS_DIR)/generate_plot.py
	@echo -e "$(BLUE)Генерация изображения из таблицы: $< → $@$(RESET)"
	@mkdir -p $(dir $@)
	@python3 $(PDF_SCRIPTS_DIR)/generate_plot.py $< $@

$(PDF_TABLES_BUILD_DIR)/%.tex: $(PDF_TABLES_SRC_DIR)/%.csv $(PDF_SCRIPTS_DIR)/generate_table.py
	@echo "Генерация таблицы" $@
	@mkdir -p $(dir $@)
	@python3 $(PDF_SCRIPTS_DIR)/generate_table.py $< $@

# === PlantUML Rules (только Inkscape) ===
check-tools:
	@which $(PLANTUML) >/dev/null || (echo -e "$(RED)PlantUML не найден!$(RESET)"; exit 1)
	@which $(INKSCAPE) >/dev/null || (echo -e "$(RED)Inkscape не установлен!$(RESET)"; exit 1)

generate-plantuml: $(PLANTUML_PDF_FILES)

# Генерация SVG из PlantUML
$(PLANTUML_BUILD_DIR)/%.svg: $(PLANTUML_SOURCE_DIR)/%.plantuml | $(PLANTUML_BUILD_DIR)
	@echo -e "$(GREEN)Генерация PlantUML → SVG: $<$(RESET)"
	@$(PLANTUML) -tsvg -o $(abspath $(PLANTUML_BUILD_DIR)) $<

# Конвертация SVG в PDF через Inkscape
$(PDF_IMAGES_SRC_DIR)/%.pdf: $(PLANTUML_BUILD_DIR)/%.svg
	@echo -e "$(BLUE)Конвертация SVG → PDF (Inkscape): $<$(RESET)"
	@mkdir -p $(dir $@)
	@$(INKSCAPE) --export-type=pdf --export-area-drawing $< -o $@

$(PLANTUML_BUILD_DIR):
	@mkdir -p $@

# === Копирование ВСЕХ изображений в build ===
$(PDF_IMAGES_TARGET_DIR): $(PDF_REQUIRED_IMAGES)
	@mkdir -p $@

# Правило копирования для каждого файла (отслеживает изменения)
$(PDF_IMAGES_TARGET_DIR)/%.png: $(PDF_IMAGES_SRC_DIR)/%.png | $(PDF_IMAGES_TARGET_DIR)
	@cp $< $@
#	@echo -e "$(YELLOW)Скопировано: $< → $@$(RESET)"

$(PDF_IMAGES_TARGET_DIR)/%.pdf: $(PDF_IMAGES_SRC_DIR)/%.pdf | $(PDF_IMAGES_TARGET_DIR)
	@cp $< $@
#	@echo -e "$(YELLOW)Скопировано: $< → $@$(RESET)"

# Гарантируем, что все изображения скопированы перед сборкой PDF
$(BUILD_IMAGE_FILES): generate-plantuml $(PDF_GENERATED_TABLES)

open-pdf: pdf
	@echo -e "$(BLUE)Открытие PDF-файла...$(RESET)"
	@if [ -f "$(PDF_TARGET)" ]; then \
		if command -v xdg-open > /dev/null; then \
			xdg-open "$(PDF_TARGET)"; \
		elif command -v open > /dev/null; then \
			open "$(PDF_TARGET)"; \
		else \
			echo -e "$(RED)Не найдена команда для открытия PDF-файла$(RESET)"; \
			exit 1; \
		fi; \
	else \
		echo -e "$(RED)PDF-файл не найден: $(PDF_TARGET)$(RESET)"; \
	fi

pdf-clean:
	@echo "Очистка PDF build-директории и сгенерированных файлов..."
	@rm -rf $(PDF_BUILD_DIR)