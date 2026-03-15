# Compressor Pós-Download + GUI Resize — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace soft bitrate preference (format_sort) with real post-download FFmpeg compression for files > 1.5 GB, and enable GUI window resize with log area expanding.

**Architecture:** New `VideoCompressor` class in `app/compressor.py` handles all FFmpeg logic. `VideoDownloader` receives it as an injected dependency and calls `compress_if_large(final_name)` after successful rename in YAML/custom-name mode. GUI gets `resizable(True, True)` + `minsize` — resize infra was already wired.

**Tech Stack:** Python stdlib only (`subprocess`, `os`, `pathlib`); tkinter for GUI; pytest + unittest.mock for tests.

**Spec:** `docs/superpowers/specs/2026-03-15-compressor-and-gui-resize-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `app/compressor.py` | **Create** | `VideoCompressor` — size check + FFmpeg invocation |
| `app/service.py` | **Modify** | Remove `max_bitrate_kbps`/`format_sort`; inject `VideoCompressor`; call `compress_if_large` |
| `app/gui/main_window.py` | **Modify** | Remove bitrate checkbox; `resizable(True,True)`; instantiate `VideoCompressor` |
| `tests/test_compressor.py` | **Create** | 5 unit tests for `VideoCompressor` |
| `tests/test_service.py` | **Modify** | Remove 3 obsolete bitrate tests; inject `MagicMock()` compressor in fixture |

---

## Chunk 1: VideoCompressor

### Task 1: Write failing tests for VideoCompressor

**Files:**
- Create: `tests/test_compressor.py`

- [ ] **Step 1: Create `tests/test_compressor.py` with 5 failing tests**

```python
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.compressor import VideoCompressor  # will fail until app/compressor.py exists

_LARGE = VideoCompressor.SIZE_LIMIT_BYTES + 1
_SMALL = 1024


@pytest.fixture
def logs():
    return []


@pytest.fixture
def compressor(logs):
    return VideoCompressor(log_callback=logs.append)


class TestVideoCompressor:
    def test_skips_file_below_threshold(self, compressor, tmp_path):
        """Arquivos abaixo de 1.5 GB não devem acionar o ffmpeg."""
        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"x")

        with patch('app.compressor.os.path.getsize', return_value=_SMALL), \
             patch('app.compressor.subprocess.run') as mock_run:
            compressor.compress_if_large(video_file)

        mock_run.assert_not_called()

    def test_calls_ffmpeg_for_large_file(self, compressor, tmp_path):
        """Arquivo > 1.5 GB deve acionar ffmpeg com args corretos."""
        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"x")

        with patch('app.compressor.os.path.getsize', return_value=_LARGE), \
             patch('app.compressor.subprocess.run') as mock_run, \
             patch('app.compressor.os.replace'):
            mock_run.return_value = MagicMock(returncode=0)
            compressor.compress_if_large(video_file)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert 'libx264' in cmd
        assert '-b:v' in cmd
        assert '3000k' in cmd
        assert '-maxrate' in cmd
        assert '6000k' in cmd   # bufsize = VIDEO_BITRATE_KBPS * 2
        assert '-c:a' in cmd
        assert 'copy' in cmd

    def test_replaces_original_on_success(self, compressor, tmp_path):
        """Quando ffmpeg tem sucesso, os.replace é chamado com (temp, original)."""
        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"x")
        expected_temp = tmp_path / "video_tmp_compress.mp4"

        with patch('app.compressor.os.path.getsize', return_value=_LARGE), \
             patch('app.compressor.subprocess.run') as mock_run, \
             patch('app.compressor.os.replace') as mock_replace:
            mock_run.return_value = MagicMock(returncode=0)
            compressor.compress_if_large(video_file)

        mock_replace.assert_called_once_with(expected_temp, video_file)

    def test_keeps_original_on_ffmpeg_failure(self, compressor, tmp_path):
        """Quando ffmpeg falha, o original fica intacto e o arquivo temp é removido."""
        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"original_content")
        temp_file = tmp_path / "video_tmp_compress.mp4"
        temp_file.write_bytes(b"partial_output")  # simula saída parcial do ffmpeg

        with patch('app.compressor.os.path.getsize', return_value=_LARGE), \
             patch('app.compressor.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr=b"codec error")
            compressor.compress_if_large(video_file)

        assert video_file.exists()
        assert not temp_file.exists()

    def test_no_second_pass_if_still_large(self, compressor, tmp_path):
        """compress_if_large nunca faz mais de uma passagem, mesmo que o resultado ainda seja grande."""
        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"x")

        with patch('app.compressor.os.path.getsize', return_value=_LARGE), \
             patch('app.compressor.subprocess.run') as mock_run, \
             patch('app.compressor.os.replace'):
            mock_run.return_value = MagicMock(returncode=0)
            compressor.compress_if_large(video_file)

        mock_run.assert_called_once()
```

- [ ] **Step 2: Run tests to confirm ImportError (arquivo ainda não existe)**

```
cd C:/git/download_bicocca && .venv/Scripts/python -m pytest tests/test_compressor.py -v
```

Expected: `ImportError: cannot import name 'VideoCompressor' from 'app.compressor'` or `ModuleNotFoundError`.

---

### Task 2: Implement VideoCompressor

**Files:**
- Create: `app/compressor.py`

- [ ] **Step 3: Create `app/compressor.py`**

```python
import os
import subprocess
from pathlib import Path
from typing import Callable


class VideoCompressor:
    SIZE_LIMIT_BYTES: int = int(1.5 * 1024 ** 3)  # 1.5 GB
    VIDEO_BITRATE_KBPS: int = 3000

    def __init__(self, log_callback: Callable[[str], None]) -> None:
        self._log = log_callback

    def compress_if_large(self, file_path: Path) -> None:
        """Comprime o vídeo com ffmpeg se > 1.5 GB. Uma única passagem — sem iteração."""
        original_size = os.path.getsize(file_path)
        if original_size < self.SIZE_LIMIT_BYTES:
            self._log("  ⓘ Arquivo dentro do limite de tamanho, compressão não necessária.")
            return

        self._log(
            f"  ⚠ Arquivo grande ({original_size / 1024 ** 3:.2f} GB), "
            f"iniciando compressão com ffmpeg..."
        )
        temp_path = file_path.parent / f"{file_path.stem}_tmp_compress.mp4"

        try:
            result = subprocess.run(
                [
                    'ffmpeg', '-i', str(file_path),
                    '-c:v', 'libx264',
                    '-b:v', f'{self.VIDEO_BITRATE_KBPS}k',
                    '-maxrate', f'{self.VIDEO_BITRATE_KBPS}k',
                    '-bufsize', f'{self.VIDEO_BITRATE_KBPS * 2}k',
                    '-c:a', 'copy',
                    '-y', str(temp_path),
                ],
                stderr=subprocess.PIPE,
            )
        except Exception as e:
            self._log(f"  ✗ Erro ao executar ffmpeg: {e}")
            temp_path.unlink(missing_ok=True)
            return

        if result.returncode != 0:
            stderr_text = result.stderr.decode('utf-8', errors='replace') if result.stderr else ''
            self._log(f"  ✗ Erro na compressão ffmpeg: {stderr_text}")
            temp_path.unlink(missing_ok=True)
            return

        new_size = os.path.getsize(temp_path)
        os.replace(temp_path, file_path)
        self._log(
            f"  ✓ Compressão concluída: {original_size / 1024 ** 3:.2f} GB "
            f"→ {new_size / 1024 ** 3:.2f} GB"
        )
```

- [ ] **Step 4: Run tests to confirm all 5 pass**

```
cd C:/git/download_bicocca && .venv/Scripts/python -m pytest tests/test_compressor.py -v
```

Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add app/compressor.py tests/test_compressor.py
git commit -m "feat: adicionar VideoCompressor com compressão ffmpeg pós-download"
```

---

## Chunk 2: Service Refactor

### Task 3: Update test_service.py

**Files:**
- Modify: `tests/test_service.py`

- [ ] **Step 1: Remove 3 obsolete bitrate tests and update the `service` fixture**

In `tests/test_service.py`, apply the following changes:

**Remove these three test methods entirely** (they test `format_sort` behavior that no longer exists):
- `test_build_ydl_opts_without_bitrate_limit_has_no_format_sort`
- `test_build_ydl_opts_with_bitrate_limit_adds_format_sort`
- `test_download_items_passes_bitrate_limit_to_both_ydl_calls`

**Update the `service` fixture** to inject a mock compressor:

```python
# Replace the existing service fixture with this:
@pytest.fixture
def service(cookies, logs):
    return VideoDownloader(
        cookies_path=cookies,
        log_callback=logs.append,
        progress_callback=lambda p, s, e: None,
        compressor=MagicMock(),
    )
```

**Confirm `MagicMock` is already in the import** — no change needed:
```python
from unittest.mock import MagicMock, patch  # MagicMock already present
```

- [ ] **Step 2: Run tests to confirm fixture failure**

```
cd C:/git/download_bicocca && .venv/Scripts/python -m pytest tests/test_service.py -v
```

Expected: `TypeError: __init__() got an unexpected keyword argument 'compressor'` — confirms service change is still needed.

---

### Task 4: Update VideoDownloader in service.py

**Files:**
- Modify: `app/service.py`

- [ ] **Step 3: Apply all changes to `app/service.py`**

**1. Add import at the top** (after existing imports):
```python
from app.compressor import VideoCompressor
```

**2. Remove `_bitrate_sort_keys` static method entirely:**
```python
# DELETE this entire method:
@staticmethod
def _bitrate_sort_keys(bitrate_kbps: int) -> list:
    return [f'vbr:{bitrate_kbps}', f'tbr:{bitrate_kbps}', 'res:1080']
```

**3. Update `__init__` to accept and store `compressor`:**
```python
def __init__(
    self,
    cookies_path: Path,
    log_callback: Callable[[str], None],
    progress_callback: Callable[[str, str, str], None],
    compressor: VideoCompressor,
):
    cookies_path = Path(cookies_path)
    if not cookies_path.exists():
        raise FileNotFoundError(
            f"Arquivo cookies.txt não encontrado: {cookies_path}"
        )
    self._cookies = cookies_path
    self._log_cb = log_callback
    self._progress_cb = progress_callback
    self._compressor = compressor
```

**4. Remove `max_bitrate_kbps` parameter from `download_items`:**
```python
def download_items(
    self,
    items: List[DownloadItem],
    output_dir: Optional[Path] = None,
    download_subtitles: bool = True,
    disciplina: Optional[str] = None,
) -> DownloadSummary:
```

**5. Update the call to `_process_item` inside `download_items`** (remove `max_bitrate_kbps`):
```python
result = self._process_item(
    item, output_dir, download_subtitles, downloaded_ids, yt_dlp, summary
)
```

**6. Update `_process_item` signature** (remove `max_bitrate_kbps=None`):
```python
def _process_item(self, item, output_dir, download_subtitles, downloaded_ids, yt_dlp, summary):
```

**7. Remove `format_sort` from `ydl_opts_info`** inside `_process_item`:
```python
ydl_opts_info = {
    'cookiefile': str(self._cookies),
    'quiet': True,
    'no_warnings': True,
    'format': _FORMAT_WITH_CAP,
}
# DELETE: if max_bitrate_kbps is not None: ydl_opts_info['format_sort'] = ...
```

**8. Add `compress_if_large` call after `_rename_temp_file`** inside `_process_item`:
```python
if item.use_custom_name:
    self._rename_temp_file(item, info, final_name, output_dir, download_subtitles, summary)
    self._compressor.compress_if_large(final_name)
else:
    self._log_cb("✓ Download concluído!\n")
```

**9. Update `_build_ydl_opts` call** (remove `max_bitrate_kbps`):
```python
ydl_opts = self._build_ydl_opts(item, output_dir, download_subtitles)
```

**10. Update `_build_ydl_opts` signature and remove `format_sort` logic:**
```python
def _build_ydl_opts(self, item, output_dir, download_subtitles):
    if item.use_custom_name:
        base = output_dir if output_dir else Path('.')
        outtmpl = str(base / 'temp_%(id)s.%(ext)s')
    else:
        outtmpl = '%(title)s.%(ext)s'

    opts = {
        'format': _FORMAT_WITH_CAP,
        'merge_output_format': 'mp4',
        'outtmpl': outtmpl,
        'cookiefile': str(self._cookies),
        'progress_hooks': [self._progress_hook],
        'encoding': 'utf-8',
        'restrictfilenames': False,
    }
    # DELETE: if max_bitrate_kbps is not None: opts['format_sort'] = ...
    if download_subtitles:
        opts.update({
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': 'pt-BR,pt',
            'subtitlesformat': 'srt',
        })
    return opts
```

- [ ] **Step 4: Run service tests to confirm all pass**

```
cd C:/git/download_bicocca && .venv/Scripts/python -m pytest tests/test_service.py -v
```

Expected: `7 passed` (10 original − 3 removed).

- [ ] **Step 5: Run full suite to confirm no regressions**

```
cd C:/git/download_bicocca && .venv/Scripts/python -m pytest -v
```

Expected: all pass. The spec baseline is 38 tests; after this chunk the count is still 38 (compressor tests already added in Chunk 1, service tests net −3+0 = −3, so intermediate count = 38 − 3 + 5 = 40 only after Chunk 3). At this point expect 38 − 3 = 35 service-related tests, plus the 5 compressor tests already committed = verify count matches baseline minus 3.

- [ ] **Step 6: Commit**

```bash
git add app/service.py tests/test_service.py app/compressor.py
git commit -m "refactor: remover max_bitrate_kbps e injetar VideoCompressor no serviço"
```

---

## Chunk 3: GUI Changes + Final Verification

### Task 5: Update main_window.py

**Files:**
- Modify: `app/gui/main_window.py`

- [ ] **Step 1: Apply all changes to `app/gui/main_window.py`**

**1. Add import** (after existing imports):
```python
from app.compressor import VideoCompressor
```

**2. In `__init__`, remove:**
```python
self.limit_bitrate = tk.BooleanVar(value=True)
```

**3. In `__init__`, change `resizable` and add `minsize`:**
```python
# Change:
self.root.resizable(False, False)
# To:
self.root.resizable(True, True)
self.root.minsize(600, 500)
```

**4. In `_create_widgets`, remove the bitrate Checkbutton block:**
```python
# DELETE these lines:
ttk.Checkbutton(mode_frame, text="Limitar qualidade de vídeo (~2 Mbps)",
                variable=self.limit_bitrate).grid(
    row=2, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
```

**5. In `_start_download`, in the outer scope (before `run()` is defined), replace the `VideoDownloader` instantiation to add `VideoCompressor` and remove `max_bitrate_kbps`:**

Replace:
```python
# OLD — in _start_download outer scope, before `def run()`:
service = VideoDownloader(
    cookies_path=cookies_path,
    log_callback=lambda m: self.root.after(0, lambda msg=m: self._log(msg)),
    progress_callback=lambda p, s, e: self.root.after(
        0, lambda pp=p, ss=s, ee=e: self._update_progress(pp, ss, ee)
    ),
)
```

With:
```python
compressor = VideoCompressor(
    log_callback=lambda m: self.root.after(0, lambda msg=m: self._log(msg))
)
service = VideoDownloader(
    cookies_path=cookies_path,
    log_callback=lambda m: self.root.after(0, lambda msg=m: self._log(msg)),
    progress_callback=lambda p, s, e: self.root.after(
        0, lambda pp=p, ss=s, ee=e: self._update_progress(pp, ss, ee)
    ),
    compressor=compressor,
)
```

Replace the `service.download_items(...)` call (remove `max_bitrate_kbps`):
```python
service.download_items(
    items=items,
    output_dir=output_dir,
    download_subtitles=self.download_subtitles.get(),
    disciplina=disciplina,
)
```

- [ ] **Step 2: Run full test suite**

```
cd C:/git/download_bicocca && .venv/Scripts/python -m pytest -v
```

Expected: **40 passed**.

- [ ] **Step 3: Commit**

```bash
git add app/gui/main_window.py
git commit -m "feat: remover checkbox de bitrate e habilitar redimensionamento da GUI"
```

- [ ] **Step 4: Final commit — push**

```bash
git push
```
