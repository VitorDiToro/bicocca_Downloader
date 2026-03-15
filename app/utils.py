import re
from pathlib import Path
from typing import Optional


def sanitize_name(name: str) -> str:
    name = name.replace(':', ' -')
    for char in '<>"/\\|?*':
        name = name.replace(char, '_')
    name = name.rstrip('. ')
    return name if name else "sem_nome"


def remove_ansi_codes(text: str) -> str:
    return re.compile(r'\x1b\[[0-9;]*m').sub('', text)


def resolve_output_dir(
    base_dir: Optional[str],
    mode: str,
    disciplina: Optional[str],
) -> Optional[Path]:
    """
    Resolve o diretório de saída final.

    - base_dir vazio/None → None (salva no diretório atual, comportamento legado)
    - modo yaml + disciplina → base_dir / sanitize_name(disciplina)
    - outros modos → Path(base_dir)
    """
    if not base_dir or not base_dir.strip():
        return None
    base = Path(base_dir)
    if mode == "yaml" and disciplina:
        return base / sanitize_name(disciplina)
    return base
