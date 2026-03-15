from pathlib import Path
from typing import List, Tuple

from app.models import DownloadItem


def parse_yaml_file(file_path: Path) -> Tuple[str, List[DownloadItem]]:
    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML não está instalado. Instale com: pip install pyyaml")

    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Erro ao ler arquivo YAML: {e}")

    if not isinstance(data, dict):
        raise ValueError("Formato YAML inválido. Arquivo deve conter um objeto YAML.")

    disciplina = data.get('disciplina', 'Disciplina não especificada')
    aulas = data.get('aulas', [])

    if not aulas:
        raise ValueError("Nenhuma aula encontrada no arquivo YAML.")

    items = []
    for idx, aula in enumerate(aulas, 1):
        if not isinstance(aula, dict):
            raise ValueError(f"Aula {idx}: formato inválido.")
        url = aula.get('url', '').strip()
        nome = aula.get('nome', '').strip()
        if not url:
            raise ValueError(f"Aula {idx}: campo 'url' está vazio ou ausente.")
        if not nome:
            raise ValueError(f"Aula {idx}: campo 'nome' está vazio ou ausente.")
        items.append(DownloadItem(url=url, custom_name=nome))

    return disciplina, items


def parse_txt_file(file_path: Path) -> List[DownloadItem]:
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]

    if not urls:
        raise ValueError("O arquivo está vazio ou não contém URLs válidas.")

    return [DownloadItem(url=url) for url in urls]
