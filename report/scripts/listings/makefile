# ==============================================================================
# Makefile для автоматизации листингов 
# ==============================================================================

SOURCE_DIR ?= ../code
LISTINGS_DIR ?= src/listings
BUILD_DIR ?= build/listings
SCRIPT_DIR ?= scripts/listings

PROCESSOR := python3 $(SCRIPT_DIR)/listings_processor.py
MAX_LINES := 36

.PHONY: all clean init listings update-all check-deps help

all: listings

# ==============================================================================
# Инициализация
# ==============================================================================

init:
	@mkdir -p $(LISTINGS_DIR)
	@$(PROCESSOR) init --source-dir $(SOURCE_DIR) --listings-dir $(LISTINGS_DIR) --max-lines $(MAX_LINES)

# ==============================================================================
# Проверка зависимостей (промежуточные файлы)
# Вывод только при обновлении
# ==============================================================================

check-deps:
	@for f in $(LISTINGS_DIR)/*.txt; do \
		if [ -f "$$f" ]; then \
			BASENAME=$$(basename "$$f" .txt); \
			ENCODED_PATH=$$(echo "$$BASENAME" | cut -d'@' -f3-); \
			SOURCE_PATH=$$(echo "$$ENCODED_PATH" | sed 's/__/\//g'); \
			FULL_SOURCE="$(SOURCE_DIR)/$$SOURCE_PATH"; \
			if [ -f "$$FULL_SOURCE" ]; then \
				if [ "$$FULL_SOURCE" -nt "$$f" ]; then \
					echo "🔄 $$f"; \
					$(PROCESSOR) update --intermediate "$$f" --source-dir "$(SOURCE_DIR)" --max-lines $(MAX_LINES); \
				fi; \
			fi; \
		fi \
	done

# ==============================================================================
# Генерация .tex файлов (только если промежуточный новее)
# Вывод только при генерации
# ==============================================================================

generate-tex:
	@mkdir -p $(BUILD_DIR)
	@for f in $(LISTINGS_DIR)/*.txt; do \
		if [ -f "$$f" ]; then \
			BASENAME=$$(basename "$$f" .txt); \
			TAG=$$(echo "$$BASENAME" | cut -d'@' -f1); \
			TEX_FILE="$(BUILD_DIR)/$$TAG.tex"; \
			if [ ! -f "$$TEX_FILE" ] || [ "$$f" -nt "$$TEX_FILE" ]; then \
				echo "📝 $$TAG.tex"; \
				$(PROCESSOR) generate --intermediate "$$f" --output "$$TEX_FILE"; \
			fi; \
		fi \
	done

# ==============================================================================
# Основная цель: проверить зависимости + сгенерировать
# ==============================================================================

listings: check-deps generate-tex
	@echo "Листинги актуальны"

# ==============================================================================
# Принудительное обновление всех (игнорируя timestamps)
# ==============================================================================

update-all:
	@for f in $(LISTINGS_DIR)/*.txt; do \
		if [ -f "$$f" ]; then \
			$(PROCESSOR) update --intermediate "$$f" --source-dir "$(SOURCE_DIR)" --max-lines $(MAX_LINES) || true; \
		fi \
	done
	@for f in $(LISTINGS_DIR)/*.txt; do \
		if [ -f "$$f" ]; then \
			BASENAME=$$(basename "$$f" .txt); \
			TAG=$$(echo "$$BASENAME" | cut -d'@' -f1); \
			$(PROCESSOR) generate --intermediate "$$f" --output "$(BUILD_DIR)/$$TAG.tex"; \
		fi \
	done
	@echo "✅ Обновлено"

# ==============================================================================
# Очистка
# ==============================================================================

clean:
	@rm -rf $(BUILD_DIR)/*.tex
	@echo "🧹 .tex файлы удалены"

distclean: clean
	@rm -rf $(LISTINGS_DIR)/*.txt
	@echo "🧹 Промежуточные файлы удалены"

help:
	@echo "Команды:"
	@echo "  make init       - Создать промежуточные файлы"
	@echo "  make listings   - Проверить изменения и сгенерировать .tex"
	@echo "  make update-all - Принудительно обновить всё"
	@echo "  make clean      - Удалить .tex файлы"
	@echo "  make distclean  - Удалить всё"
	@echo ""
	@echo "Параметры:"
	@echo "  make SOURCE_DIR=../code listings"