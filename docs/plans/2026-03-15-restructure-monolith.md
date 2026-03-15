# Restructure Monolith Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split the monolithic `downloader.py` into a proper package with separated concerns: models, utilities, parsers, download service, and a thin GUI layer.

**Architecture:** An `app/` package holds all business logic split into layers (models → utils → parsers → service), while the GUI becomes a thin orchestrator that delegates everything to the service via callbacks. The existing `downloader.py` becomes a one-line entry point.

**Tech Stack:** Python 3.6+, tkinter (GUI), yt-dlp (download engine), PyYAML (YAML parsing), pytest (tests), unittest.mock (mocking yt-dlp in tests)

---

## Target Structure

```
app/
├── __init__.py
├── models.py           # DownloadItem, DownloadResult, DownloadSummary dataclasses
├── utils.py            # sanitize_name, remove_ansi_codes
├── parsers.py          # parse_yaml_file, parse_txt_file
├── service.py          # VideoDownloader — all yt-dlp + filesystem logic
└── gui/
    ├── __init__.py
    └── main_window.py  # DownloaderGUI — thin UI, delegates to service
tests/
├── __init__.py
├── fixtures/
│   ├── valid.yaml
│   ├── missing_url.yaml
│   └── urls.txt
├── test_utils.py
├── test_parsers.py
└── test_service.py
downloader.py           # Updated: single-line entry point
```

---

### Task 1: Pytest setup + package skeleton

**Files:**
- Create: `app/__init__.py`
- Create: `app/gui/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/fixtures/valid.yaml`
- Create: `tests/fixtures/missing_url.yaml`
- Create: `tests/fixtures/urls.txt`
- Create: `pytest.ini`

**Step 1: Create all empty `__init__.py` files and pytest config**

```bash
mkdir -p app/gui tests/fixtures
touch app/__init__.py app/gui/__init__.py tests/__init__.py
```

`pytest.ini`:
```ini
[pytest]
testpaths = tests
```

**Step 2: Create test fixtures**

`tests/fixtures/valid.yaml`:
```yaml
disciplina: "Curso de Exemplo"
aulas:
  - url: "https://exemplo.com/video1"
    nome: "Aula 01 - Introdução"
  - url: "https://exemplo.com/video2"
    nome: "Aula 02 - Conceitos"
```

`tests/fixtures/missing_url.yaml`:
```yaml
disciplina: "Curso Inválido"
aulas:
  - nome: "Aula sem URL"
```

`tests/fixtures/urls.txt`:
```
https://exemplo.com/video1
https://exemplo.com/video2

https://exemplo.com/video3
```

**Step 3: Verify pytest can find the suite (0 tests is OK)**

Run: `python -m pytest --collect-only`
Expected: `no tests ran` — no errors, just no tests yet

**Step 4: Commit**

```bash
git add app/ tests/ pytest.ini
git commit -m "chore: scaffold package structure and pytest setup"
```

---

### Task 2: `app/utils.py` — pure utility functions

**Files:**
- Create: `app/utils.py`
- Create: `tests/test_utils.py`

**Step 1: Write the failing tests**

`tests/test_utils.py`:
```python
import pytest
from app.utils import sanitize_name, remove_ansi_codes


class TestSanitizeName:
    def test_colon_becomes_space_dash(self):
        assert sanitize_name("Aula 1: Intro") == "Aula 1 - Intro"

    def test_invalid_windows_chars_become_underscore(self):
        assert sanitize_name('file<>"/\\|?*name') == "file_______name"

    def test_trailing_dots_and_spaces_removed(self):
        assert sanitize_name("name. ") == "name"

    def test_empty_string_returns_sem_nome(self):
        assert sanitize_name("") == "sem_nome"

    def test_string_of_invalid_chars_returns_sem_nome(self):
        assert sanitize_name("...") == "sem_nome"

    def test_normal_name_unchanged(self):
        assert sanitize_name("Aula 01 - Democracia") == "Aula 01 - Democracia"


class TestRemoveAnsiCodes:
    def test_removes_color_codes(self):
        assert remove_ansi_codes("\x1b[32m100%\x1b[0m") == "100%"

    def test_string_without_codes_unchanged(self):
        assert remove_ansi_codes("plain text") == "plain text"

    def test_empty_string(self):
        assert remove_ansi_codes("") == ""

    def test_multiple_codes(self):
        assert remove_ansi_codes("\x1b[1m\x1b[32mBold Green\x1b[0m") == "Bold Green"
```

**Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_utils.py -v`
Expected: `ModuleNotFoundError: No module named 'app.utils'`

**Step 3: Implement `app/utils.py`**

```python
import re


def sanitize_name(name: str) -> str:
    name = name.replace(':', ' -')
    for char in '<>"/\\|?*':
        name = name.replace(char, '_')
    name = name.rstrip('. ')
    return name if name else "sem_nome"


def remove_ansi_codes(text: str) -> str:
    return re.compile(r'\x1b\[[0-9;]*m').sub('', text)
```

**Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_utils.py -v`
Expected: 10 passed

**Step 5: Commit**

```bash
git add app/utils.py tests/test_utils.py
git commit -m "feat: extract utility functions to app/utils.py"
```

---

### Task 3: `app/models.py` — data classes

**Files:**
- Create: `app/models.py`

No unit tests needed for pure data classes — they will be exercised by parser and service tests.

**Step 1: Create `app/models.py`**

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List


@dataclass
class DownloadItem:
    url: str
    custom_name: Optional[str] = None

    @property
    def use_custom_name(self) -> bool:
        return self.custom_name is not None


class DownloadStatus(Enum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class DownloadResult:
    item: DownloadItem
    status: DownloadStatus
    message: str = ""


@dataclass
class DownloadSummary:
    results: List[DownloadResult] = field(default_factory=list)
    subtitle_success: int = 0
    subtitle_skipped: int = 0

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.status == DownloadStatus.SUCCESS)

    @property
    def skipped_count(self) -> int:
        return sum(1 for r in self.results if r.status == DownloadStatus.SKIPPED)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.results if r.status == DownloadStatus.ERROR)
```

**Step 2: Quick smoke test via Python REPL**

Run:
```bash
python -c "
from app.models import DownloadItem, DownloadStatus, DownloadResult, DownloadSummary
item = DownloadItem(url='http://x.com', custom_name='Aula 01')
assert item.use_custom_name is True
r = DownloadResult(item=item, status=DownloadStatus.SUCCESS)
s = DownloadSummary(results=[r])
assert s.success_count == 1 and s.error_count == 0
print('OK')
"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add app/models.py
git commit -m "feat: add domain models (DownloadItem, DownloadResult, DownloadSummary)"
```

---

### Task 4: `app/parsers.py` — YAML and TXT file parsing

**Files:**
- Create: `app/parsers.py`
- Create: `tests/test_parsers.py`

**Step 1: Write the failing tests**

`tests/test_parsers.py`:
```python
import pytest
from pathlib import Path
from app.parsers import parse_yaml_file, parse_txt_file
from app.models import DownloadItem

FIXTURES = Path(__file__).parent / "fixtures"


class TestParseYamlFile:
    def test_returns_disciplina_and_items(self):
        disciplina, items = parse_yaml_file(FIXTURES / "valid.yaml")
        assert disciplina == "Curso de Exemplo"
        assert len(items) == 2

    def test_items_are_download_items(self):
        _, items = parse_yaml_file(FIXTURES / "valid.yaml")
        assert all(isinstance(i, DownloadItem) for i in items)

    def test_item_fields_are_mapped(self):
        _, items = parse_yaml_file(FIXTURES / "valid.yaml")
        assert items[0].url == "https://exemplo.com/video1"
        assert items[0].custom_name == "Aula 01 - Introdução"

    def test_raises_on_missing_url(self):
        with pytest.raises(ValueError, match="url"):
            parse_yaml_file(FIXTURES / "missing_url.yaml")

    def test_raises_if_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_yaml_file(FIXTURES / "nonexistent.yaml")

    def test_raises_if_pyyaml_missing(self, monkeypatch):
        import builtins
        real_import = builtins.__import__
        def mock_import(name, *args, **kwargs):
            if name == 'yaml':
                raise ImportError("No module named 'yaml'")
            return real_import(name, *args, **kwargs)
        monkeypatch.setattr(builtins, '__import__', mock_import)
        with pytest.raises(ImportError, match="pip install pyyaml"):
            parse_yaml_file(FIXTURES / "valid.yaml")


class TestParseTxtFile:
    def test_returns_list_of_download_items(self):
        items = parse_txt_file(FIXTURES / "urls.txt")
        assert len(items) == 3  # blank lines skipped

    def test_items_have_no_custom_name(self):
        items = parse_txt_file(FIXTURES / "urls.txt")
        assert all(i.custom_name is None for i in items)

    def test_urls_are_stripped(self):
        items = parse_txt_file(FIXTURES / "urls.txt")
        assert items[0].url == "https://exemplo.com/video1"

    def test_raises_if_file_empty(self, tmp_path):
        empty = tmp_path / "empty.txt"
        empty.write_text("")
        with pytest.raises(ValueError, match="vazio"):
            parse_txt_file(empty)

    def test_raises_if_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_txt_file(Path("nonexistent.txt"))
```

**Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_parsers.py -v`
Expected: `ModuleNotFoundError: No module named 'app.parsers'`

**Step 3: Implement `app/parsers.py`**

```python
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
```

**Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_parsers.py -v`
Expected: all passed

**Step 5: Commit**

```bash
git add app/parsers.py tests/test_parsers.py
git commit -m "feat: extract file parsers to app/parsers.py"
```

---

### Task 5: `app/service.py` — VideoDownloader business logic

This is the largest extraction. All yt-dlp, filesystem, and skip-detection logic moves here. The GUI will inject `log_callback` and `progress_callback` so the service never imports tkinter.

**Files:**
- Create: `app/service.py`
- Create: `tests/test_service.py`

**Step 1: Write the failing tests**

`tests/test_service.py`:
```python
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from app.service import VideoDownloader
from app.models import DownloadItem, DownloadStatus


@pytest.fixture
def cookies(tmp_path):
    p = tmp_path / "cookies.txt"
    p.write_text("# Netscape HTTP Cookie File")
    return p


@pytest.fixture
def logs():
    return []


@pytest.fixture
def service(cookies, logs):
    return VideoDownloader(
        cookies_path=cookies,
        log_callback=logs.append,
        progress_callback=lambda p, s, e: None,
    )


class TestVideoDownloaderInit:
    def test_raises_if_cookies_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="cookies.txt"):
            VideoDownloader(
                cookies_path=tmp_path / "missing.txt",
                log_callback=lambda m: None,
                progress_callback=lambda p, s, e: None,
            )


class TestDownloadItems:
    def test_logs_start_message(self, service, logs):
        item = DownloadItem(url="http://x.com")
        with patch('yt_dlp.YoutubeDL') as mock_ydl:
            mock_ctx = MagicMock()
            mock_ctx.extract_info.return_value = {
                'id': 'abc123', 'title': 'Test Video',
                'height': 1080, 'filesize': None, 'filesize_approx': None,
            }
            mock_ydl.return_value.__enter__ = lambda s: mock_ctx
            mock_ydl.return_value.__exit__ = MagicMock(return_value=False)
            service.download_items([item], output_dir=None)

        assert any("1 vídeo" in m for m in logs)

    def test_skips_existing_complete_file(self, service, logs, tmp_path):
        item = DownloadItem(url="http://x.com", custom_name="Aula 01")
        expected_file = tmp_path / "Aula 01_1080p.mp4"
        expected_file.write_bytes(b"x" * 1000)

        with patch('yt_dlp.YoutubeDL') as mock_ydl:
            mock_ctx = MagicMock()
            mock_ctx.extract_info.return_value = {
                'id': 'abc123', 'height': 1080,
                'filesize': 1000, 'filesize_approx': None,
            }
            mock_ydl.return_value.__enter__ = lambda s: mock_ctx
            mock_ydl.return_value.__exit__ = MagicMock(return_value=False)

            summary = service.download_items([item], output_dir=tmp_path)

        assert summary.skipped_count == 1
        assert summary.success_count == 0
        assert any("já existe" in m for m in logs)

    def test_summary_counts_errors(self, service, logs):
        item = DownloadItem(url="http://bad.url")
        with patch('yt_dlp.YoutubeDL') as mock_ydl:
            mock_ctx = MagicMock()
            mock_ctx.extract_info.side_effect = Exception("Connection refused")
            mock_ydl.return_value.__enter__ = lambda s: mock_ctx
            mock_ydl.return_value.__exit__ = MagicMock(return_value=False)

            summary = service.download_items([item], output_dir=None)

        assert summary.error_count == 1
        assert any("Erro" in m for m in logs)
```

**Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_service.py -v`
Expected: `ModuleNotFoundError: No module named 'app.service'`

**Step 3: Implement `app/service.py`**

Extract the entire body of `_download_videos` from `downloader.py` into this class, replacing all `self._log(...)` calls with `self._log_cb(...)` and removing all `self.root.after(...)` calls (the GUI bridge is now via callbacks injected at construction time).

```python
import os
from pathlib import Path
from typing import Callable, List, Optional

from app.models import DownloadItem, DownloadResult, DownloadStatus, DownloadSummary
from app.utils import sanitize_name, remove_ansi_codes


class VideoDownloader:
    def __init__(
        self,
        cookies_path: Path,
        log_callback: Callable[[str], None],
        progress_callback: Callable[[str, str, str], None],
    ):
        cookies_path = Path(cookies_path)
        if not cookies_path.exists():
            raise FileNotFoundError(
                f"Arquivo cookies.txt não encontrado: {cookies_path}"
            )
        self._cookies = cookies_path
        self._log_cb = log_callback
        self._progress_cb = progress_callback

    def download_items(
        self,
        items: List[DownloadItem],
        output_dir: Optional[Path] = None,
        download_subtitles: bool = True,
        disciplina: Optional[str] = None,
    ) -> DownloadSummary:
        try:
            import yt_dlp
        except ImportError:
            raise ImportError("yt-dlp não está instalado. Instale com: pip install yt-dlp")

        total = len(items)
        summary = DownloadSummary()
        downloaded_ids: set = set()

        if disciplina:
            self._log_cb(f"Disciplina: {disciplina}")
            self._log_cb("=" * 60)
        self._log_cb(f"Iniciando download de {total} vídeo(s)...\n")

        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(exist_ok=True)
            self._log_cb(f"Pasta de saída: {output_dir}\n")

        for idx, item in enumerate(items, 1):
            self._log_cb(f"[{idx}/{total}] Processando: {item.url}")
            if item.use_custom_name:
                self._log_cb(f"  Nome: {item.custom_name}")

            result = self._process_item(
                item, output_dir, download_subtitles, downloaded_ids, yt_dlp, summary
            )
            summary.results.append(result)

        self._log_cb("=" * 60)
        self._log_cb("Download finalizado!")
        self._log_cb(f"Sucessos: {summary.success_count}")
        self._log_cb(f"Pulados (já existentes): {summary.skipped_count}")
        self._log_cb(f"Erros: {summary.error_count}")
        if download_subtitles:
            self._log_cb(f"Legendas baixadas: {summary.subtitle_success}")
            self._log_cb(f"Legendas puladas (já existentes): {summary.subtitle_skipped}")
        self._log_cb("=" * 60)

        return summary

    def _process_item(self, item, output_dir, download_subtitles, downloaded_ids, yt_dlp, summary):
        try:
            self._log_cb("  Verificando informações do vídeo...")
            ydl_opts_info = {
                'cookiefile': str(self._cookies),
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                info = ydl.extract_info(item.url, download=False)

            video_id = info.get('id', '')
            if video_id in downloaded_ids:
                self._log_cb(f"  ⊘ Vídeo duplicado (ID: {video_id}), pulando")
                return DownloadResult(item=item, status=DownloadStatus.SKIPPED, message="duplicado")

            final_name = self._build_final_name(item, info, output_dir)
            skip_result = self._check_existing_file(item, final_name, info)
            if skip_result:
                return skip_result

            self._log_cb("  Arquivo não existe, iniciando download...")
            self._check_existing_subtitle(item, final_name, download_subtitles, summary)

        except Exception as e:
            self._log_cb(f"✗ Erro ao verificar vídeo: {e}\n")
            return DownloadResult(item=item, status=DownloadStatus.ERROR, message=str(e))

        try:
            ydl_opts = self._build_ydl_opts(item, output_dir, download_subtitles)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([item.url])

                if item.use_custom_name:
                    self._rename_temp_file(item, info, final_name, output_dir, download_subtitles, summary)
                else:
                    self._log_cb("✓ Download concluído!\n")

            downloaded_ids.add(video_id)
            return DownloadResult(item=item, status=DownloadStatus.SUCCESS)
        except Exception as e:
            self._log_cb(f"✗ Erro: {e}\n")
            return DownloadResult(item=item, status=DownloadStatus.ERROR, message=str(e))

    def _build_final_name(self, item, info, output_dir):
        if item.use_custom_name:
            height = info.get('height', 'unknown')
            resolution = f"{height}p" if height != 'unknown' else "unknown"
            safe_name = sanitize_name(item.custom_name)
            base = output_dir if output_dir else Path('.')
            return base / f"{safe_name}_{resolution}.mp4"
        else:
            title = info.get('title', 'video')
            return Path(f"{title}.mp4")

    def _check_existing_file(self, item, final_name, info):
        if not final_name.exists():
            return None
        existing_size = final_name.stat().st_size
        expected_size = info.get('filesize') or info.get('filesize_approx') or 0
        if expected_size > 0:
            diff_pct = abs(existing_size - expected_size) / expected_size * 100
            if diff_pct > 5:
                self._log_cb(f"  ⚠ Arquivo incompleto ({diff_pct:.1f}% diferença), re-baixando...")
                final_name.unlink()
                return None
        self._log_cb(f"  ✓ Arquivo já existe e está completo, pulando: {final_name}")
        return DownloadResult(item=item, status=DownloadStatus.SKIPPED, message="já existe")

    def _check_existing_subtitle(self, item, final_name, download_subtitles, summary):
        if not download_subtitles:
            return
        for lang in ['pt-BR', 'pt']:
            sub = final_name.with_suffix(f'.{lang}.srt')
            if sub.exists() and sub.stat().st_size >= 100:
                self._log_cb(f"  ✓ Legenda já existe: {sub}")
                summary.subtitle_skipped += 1
                break
            elif sub.exists():
                self._log_cb(f"  ⚠ Legenda inválida, será re-baixada")
                sub.unlink()

    def _build_ydl_opts(self, item, output_dir, download_subtitles):
        if item.use_custom_name:
            base = output_dir if output_dir else Path('.')
            outtmpl = str(base / 'temp_%(id)s.%(ext)s')
        else:
            outtmpl = '%(title)s.%(ext)s'

        opts = {
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'outtmpl': outtmpl,
            'cookiefile': str(self._cookies),
            'progress_hooks': [self._progress_hook],
            'encoding': 'utf-8',
            'restrictfilenames': False,
        }
        if download_subtitles:
            opts.update({
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': 'pt-BR,pt',
                'subtitlesformat': 'srt',
            })
        return opts

    def _rename_temp_file(self, item, info, final_name, output_dir, download_subtitles, summary):
        video_id = info['id']
        base = output_dir if output_dir else Path('.')
        temp_file = base / f"temp_{video_id}.mp4"

        if not temp_file.exists():
            self._log_cb(f"✗ Arquivo temporário não encontrado: {temp_file}\n")
            return

        os.rename(temp_file, final_name)
        self._log_cb(f"✓ Salvo como: {final_name}\n")

        if download_subtitles:
            self._move_subtitle(temp_file, final_name, summary)

    def _move_subtitle(self, temp_file, final_name, summary):
        for lang in ['pt-BR', 'pt']:
            subtitle_temp = temp_file.with_suffix(f'.{lang}.srt')
            if subtitle_temp.exists():
                if subtitle_temp.stat().st_size < 100:
                    self._log_cb(f"  ⚠ Legenda muito pequena, pulando\n")
                    subtitle_temp.unlink()
                    continue
                subtitle_final = final_name.with_suffix(f'.{lang}.srt')
                os.rename(subtitle_temp, subtitle_final)
                self._log_cb(f"✓ Legenda salva como: {subtitle_final}\n")
                summary.subtitle_success += 1
                return
        self._log_cb("  ⓘ Nenhuma legenda em português encontrada\n")

    def _progress_hook(self, d):
        if d['status'] == 'downloading':
            percent = remove_ansi_codes(str(d.get('_percent_str', 'N/A')))
            speed = remove_ansi_codes(str(d.get('_speed_str', 'N/A')))
            eta = remove_ansi_codes(str(d.get('_eta_str', 'N/A')))
            self._progress_cb(percent, speed, eta)
```

**Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_service.py -v`
Expected: all passed

**Step 5: Run full suite**

Run: `python -m pytest -v`
Expected: all tests passed across all files

**Step 6: Commit**

```bash
git add app/service.py tests/test_service.py
git commit -m "feat: extract download logic to VideoDownloader service"
```

---

### Task 6: `app/gui/main_window.py` — thin GUI layer

The GUI only handles UI state, delegates all work to `VideoDownloader`.

**Files:**
- Create: `app/gui/main_window.py`

No unit tests (tkinter requires a display; covered manually).

**Step 1: Create `app/gui/main_window.py`**

```python
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
from pathlib import Path

from app.models import DownloadItem
from app.parsers import parse_yaml_file, parse_txt_file
from app.service import VideoDownloader
from app.utils import sanitize_name


class DownloaderGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Moodle video downloader")
        self.root.geometry("600x500")
        self.root.resizable(False, False)

        self.mode = tk.StringVar(value="single")
        self.file_path = tk.StringVar()
        self.yaml_path = tk.StringVar()
        self.download_subtitles = tk.BooleanVar(value=True)
        self.downloading = False

        self._create_widgets()
        self._center_window()

    def _center_window(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f'{w}x{h}+{x}+{y}')

    def _create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        ttk.Label(main_frame, text="Moodle video downloader",
                  font=("Arial", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 15))

        mode_frame = ttk.LabelFrame(main_frame, text="Modo de Download", padding="10")
        mode_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        for col, (text, value) in enumerate([("URL única", "single"),
                                              ("Arquivo TXT", "file"),
                                              ("Arquivo YAML", "yaml")]):
            ttk.Radiobutton(mode_frame, text=text, variable=self.mode,
                            value=value, command=self._update_mode).grid(
                row=0, column=col, sticky=tk.W, padx=(0, 20))

        ttk.Checkbutton(mode_frame, text="Baixar legendas em português",
                        variable=self.download_subtitles).grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(10, 0))

        # URL single frame
        self.single_frame = ttk.LabelFrame(main_frame, text="URL única", padding="10")
        self.single_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        ttk.Label(self.single_frame, text="Cole a URL da aula:").grid(row=0, column=0, sticky=tk.W)
        self.url_entry = ttk.Entry(self.single_frame, width=70)
        self.url_entry.grid(row=1, column=0, sticky=(tk.W, tk.E))

        # TXT file frame
        self.file_frame = ttk.LabelFrame(main_frame, text="Arquivo TXT", padding="10")
        self.file_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        self.file_frame.grid_remove()
        ttk.Label(self.file_frame, text="Selecione um arquivo .txt com URLs (uma por linha):").grid(
            row=0, column=0, columnspan=2, sticky=tk.W)
        f_inner = ttk.Frame(self.file_frame)
        f_inner.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E))
        ttk.Entry(f_inner, textvariable=self.file_path, width=55, state="readonly").grid(
            row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(f_inner, text="Procurar...", command=self._browse_file).grid(row=0, column=1)

        # YAML file frame
        self.yaml_frame = ttk.LabelFrame(main_frame, text="Arquivo YAML", padding="10")
        self.yaml_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        self.yaml_frame.grid_remove()
        ttk.Label(self.yaml_frame, text="Selecione um arquivo .yaml com disciplina e aulas:").grid(
            row=0, column=0, columnspan=2, sticky=tk.W)
        y_inner = ttk.Frame(self.yaml_frame)
        y_inner.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E))
        ttk.Entry(y_inner, textvariable=self.yaml_path, width=55, state="readonly").grid(
            row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(y_inner, text="Procurar...", command=self._browse_yaml).grid(row=0, column=1)

        # Log
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        log_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, width=70,
                                                   state="disabled", wrap=tk.WORD,
                                                   font=("Consolas", 9))
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.download_btn = ttk.Button(main_frame, text="Baixar", command=self._start_download)
        self.download_btn.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E))

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(5, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

    def _update_mode(self):
        self.single_frame.grid_remove()
        self.file_frame.grid_remove()
        self.yaml_frame.grid_remove()
        {'single': self.single_frame, 'file': self.file_frame,
         'yaml': self.yaml_frame}[self.mode.get()].grid()

    def _browse_file(self):
        f = filedialog.askopenfilename(title="Selecione o arquivo de URLs",
                                       filetypes=[("Arquivos de texto", "*.txt"), ("Todos", "*.*")])
        if f:
            self.file_path.set(f)

    def _browse_yaml(self):
        f = filedialog.askopenfilename(title="Selecione o arquivo YAML",
                                       filetypes=[("Arquivos YAML", "*.yaml *.yml"), ("Todos", "*.*")])
        if f:
            self.yaml_path.set(f)

    def _log(self, message: str):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        self.root.update_idletasks()

    def _update_progress(self, percent: str, speed: str, eta: str):
        self.log_text.config(state="normal")
        try:
            last_start = self.log_text.index("end-2l linestart")
            last_end = self.log_text.index("end-1l linestart")
            if self.log_text.get(last_start, last_end).strip().startswith('Progresso:'):
                self.log_text.delete(last_start, last_end)
        except tk.TclError:
            pass
        self.log_text.insert(tk.END, f"  Progresso: {percent} | Velocidade: {speed} | ETA: {eta}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        self.root.update_idletasks()

    def _start_download(self):
        if self.downloading:
            messagebox.showwarning("Aviso", "Um download já está em andamento.")
            return

        mode = self.mode.get()
        items = []
        disciplina = None
        output_dir = None

        try:
            if mode == "single":
                url = self.url_entry.get().strip()
                if not url:
                    messagebox.showwarning("Aviso", "Por favor, cole uma URL válida.")
                    return
                items = [DownloadItem(url=url)]

            elif mode == "file":
                path = self.file_path.get()
                if not path:
                    messagebox.showwarning("Aviso", "Por favor, selecione um arquivo TXT.")
                    return
                items = parse_txt_file(path)

            else:  # yaml
                path = self.yaml_path.get()
                if not path:
                    messagebox.showwarning("Aviso", "Por favor, selecione um arquivo YAML.")
                    return
                disciplina, items = parse_yaml_file(path)
                output_dir = Path(sanitize_name(disciplina))

        except Exception as e:
            messagebox.showerror("Erro", str(e))
            return

        cookies_path = Path(__file__).parent.parent.parent / "cookies.txt"
        if not cookies_path.exists():
            messagebox.showerror("Erro", "Arquivo cookies.txt não encontrado.")
            return

        try:
            service = VideoDownloader(
                cookies_path=cookies_path,
                log_callback=lambda m: self.root.after(0, lambda msg=m: self._log(msg)),
                progress_callback=lambda p, s, e: self.root.after(
                    0, lambda pp=p, ss=s, ee=e: self._update_progress(pp, ss, ee)
                ),
            )
        except FileNotFoundError as e:
            messagebox.showerror("Erro", str(e))
            return

        self.downloading = True
        self.download_btn.config(state="disabled")
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state="disabled")

        def run():
            try:
                service.download_items(
                    items=items,
                    output_dir=output_dir,
                    download_subtitles=self.download_subtitles.get(),
                    disciplina=disciplina,
                )
            finally:
                self.downloading = False
                self.root.after(0, lambda: self.download_btn.config(state="normal"))
                if mode == "single":
                    self.root.after(0, lambda: self.url_entry.delete(0, tk.END))

        threading.Thread(target=run, daemon=True).start()


def main():
    root = tk.Tk()
    DownloaderGUI(root)
    root.mainloop()
```

**Step 2: Smoke-test manually**

Run: `python -c "import app.gui.main_window; print('OK')"`
Expected: `OK` (no import errors)

**Step 3: Commit**

```bash
git add app/gui/main_window.py
git commit -m "feat: thin GUI layer delegates to VideoDownloader service"
```

---

### Task 7: Update entry point and final cleanup

**Files:**
- Modify: `downloader.py` (replace contents)

**Step 1: Replace `downloader.py` with a thin entry point**

```python
#!/usr/bin/env python3
from app.gui.main_window import main

if __name__ == "__main__":
    main()
```

**Step 2: Run the full test suite one final time**

Run: `python -m pytest -v`
Expected: all tests passed

**Step 3: Smoke-test the entry point imports cleanly**

Run: `python -c "import downloader; print('OK')"`
Expected: `OK`

**Step 4: Final commit**

```bash
git add downloader.py
git commit -m "refactor: downloader.py becomes thin entry point, logic lives in app/"
```

---

## What Was NOT Moved

- `downloader.ps1` — deprecated PowerShell script, left as-is
- `convert_to_480p.py` in module subdirectory — separate tool, out of scope
- `cookies.txt` — runtime artifact, not code
