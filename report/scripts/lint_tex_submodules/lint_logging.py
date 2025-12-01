import sys

# ANSI цвета
BLUE = "\033[34m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"

USE_COLOR = sys.stdout.isatty()


def info(msg):
    prefix = "[INFO]" if not USE_COLOR else f"{BLUE}[INFO]{RESET}"
    print(f"{prefix} {msg}")


def warning(msg):
    prefix = "[WARNING]" if not USE_COLOR else f"{YELLOW}[WARNING]{RESET}"
    print(f"{prefix} {msg}")


def error(msg):
    prefix = "[ERROR]" if not USE_COLOR else f"{RED}[ERROR]{RESET}"
    print(f"{prefix} {msg}", file=sys.stderr)
