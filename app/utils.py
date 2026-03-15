import re


def sanitize_name(name: str) -> str:
    name = name.replace(':', ' -')
    for char in '<>"/\\|?*':
        name = name.replace(char, '_')
    name = name.rstrip('. ')
    return name if name else "sem_nome"


def remove_ansi_codes(text: str) -> str:
    return re.compile(r'\x1b\[[0-9;]*m').sub('', text)
