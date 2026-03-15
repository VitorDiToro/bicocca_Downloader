# Design: Post-Download Compression + GUI Resize

**Date:** 2026-03-15
**Status:** Approved

---

## Summary

Two coordinated changes:

1. **Remove bitrate-limit download preference** (format_sort) and replace it with **post-download FFmpeg compression**: if a downloaded file exceeds 1.5 GB, compress the video stream to ≤ 3 Mbps while copying audio unchanged. One pass only — no retry if the result is still large.
2. **Make the GUI window resizable**, with all controls at fixed size and only the log area growing with the window.

---

## Motivation

`yt-dlp` `format_sort` is a *soft preference* — it cannot enforce a bitrate ceiling, only reorder stream candidates. When only a high-bitrate stream exists, yt-dlp downloads it regardless. True size reduction requires re-encoding with FFmpeg after the fact. The GUI resize is a usability improvement — the log area is too small for long download sessions.

---

## Architecture

### New class: `app/compressor.py` — `VideoCompressor`

Single-responsibility: decide whether to compress and run FFmpeg.

**Interface:**
```python
class VideoCompressor:
    SIZE_LIMIT_BYTES: int = int(1.5 * 1024 ** 3)  # 1.5 GB
    VIDEO_BITRATE_KBPS: int = 3000

    def __init__(self, log_callback: Callable[[str], None]) -> None: ...
    def compress_if_large(self, file_path: Path) -> None: ...
```

**`compress_if_large` flow:**
1. If `file_path.stat().st_size < SIZE_LIMIT_BYTES`: log "dentro do limite, pulando" and return.
2. Log original size and start message.
3. Create temp path: `file_path.parent / f"{file_path.stem}_tmp_compress.mp4"`
4. Run FFmpeg via `subprocess.run` with `stderr=subprocess.PIPE` (captures FFmpeg output for logging on failure):
   ```
   ffmpeg -i <input> -c:v libx264 -b:v 3000k -maxrate 3000k -bufsize 6000k -c:a copy -y <temp>
   ```
5. On failure (returncode ≠ 0 or exception):
   - Log error message (include captured stderr if available)
   - Delete temp file if it exists (`temp.unlink(missing_ok=True)`)
   - **Leave original untouched**, return.
6. On success: `os.replace(temp, file_path)`, log before/after sizes.
7. **No second pass** — if compressed file is still > 1.5 GB, that is accepted.

**Dependencies:** `subprocess`, `os`, `pathlib.Path`, `typing.Callable` — no external packages.

---

### Modified: `app/service.py` — `VideoDownloader`

**Removals:**
- `_bitrate_sort_keys` static method
- `max_bitrate_kbps` parameter from `download_items`, `_process_item`, `_build_ydl_opts`
- All `format_sort` usage in `ydl_opts_info` and `_build_ydl_opts`

**Additions:**
- Constructor receives `compressor: VideoCompressor` as injected dependency, stored as `self._compressor`

**Compression call site — custom-name mode only:**

Compression is applied **only when `item.use_custom_name` is True** (i.e. YAML mode), because in that mode `final_name` is a deterministic, resolved `Path` that is guaranteed to exist after `_rename_temp_file` succeeds.

For non-custom-name mode (single URL, TXT), yt-dlp chooses the filename autonomously based on the video title with its own sanitization rules. The resulting path cannot be reliably predicted from `info['title']` alone, so compression is not applied in those modes.

Call site in `_process_item`:
```python
# inside the branch: if item.use_custom_name:
self._rename_temp_file(item, info, final_name, output_dir, download_subtitles, summary)
self._compressor.compress_if_large(final_name)
```

**Note:** `_FORMAT_WITH_CAP` (1080p hard filter) is unchanged — resolution cap is still enforced at download time.

---

### Modified: `app/gui/main_window.py` — `DownloaderGUI`

**Removals:**
- `self.limit_bitrate = tk.BooleanVar(value=True)`
- `Checkbutton` "Limitar qualidade de vídeo (~2 Mbps)"
- `max_bitrate_kbps=...` argument in `service.download_items()` call

**GUI resize:**
- `self.root.resizable(False, False)` → `self.root.resizable(True, True)`
- Window minimum size set: `self.root.minsize(600, 500)`
- `main_frame` is already gridded with `sticky=(tk.W, tk.E, tk.N, tk.S)` — this must be preserved
- `self.root.rowconfigure(0, weight=1)` and `self.root.columnconfigure(0, weight=1)` already exist — preserve them
- Add `main_frame.rowconfigure(<log_row_index>, weight=1)` to make the log row expand vertically
- `log_frame` already has `rowconfigure(0, weight=1)` and `columnconfigure(0, weight=1)` — preserve them
- `log_frame` must be gridded with `sticky=(tk.W, tk.E, tk.N, tk.S)` — already present, preserve it
- All other frames/widgets remain at fixed size

**`VideoCompressor` instantiation** (inside `_start_download`, intentionally recreated per download — stateless design):
```python
compressor = VideoCompressor(
    log_callback=lambda m: self.root.after(0, lambda msg=m: self._log(msg))
)
service = VideoDownloader(..., compressor=compressor)
```

---

## Testing

### Remove (obsolete bitrate tests) from `tests/test_service.py`:
- `test_build_ydl_opts_without_bitrate_limit_has_no_format_sort`
- `test_build_ydl_opts_with_bitrate_limit_adds_format_sort`
- `test_download_items_passes_bitrate_limit_to_both_ydl_calls`

### Update `tests/test_service.py` fixture:

All existing service tests must inject a `MagicMock()` compressor to avoid FFmpeg side-effects:
```python
@pytest.fixture
def service(cookies, logs):
    return VideoDownloader(
        cookies_path=cookies,
        log_callback=logs.append,
        progress_callback=lambda p, s, e: None,
        compressor=MagicMock(),
    )
```

### New: `tests/test_compressor.py` (5 tests)

All tests use `tmp_path` for real files and `unittest.mock.patch('subprocess.run')` to control FFmpeg behavior.

| Test | Scenario | Arrange | Assert |
|------|----------|---------|--------|
| `test_skips_file_below_threshold` | file < 1.5 GB | create file with 1 byte | `subprocess.run` not called |
| `test_calls_ffmpeg_for_large_file` | file > 1.5 GB | create file > SIZE_LIMIT_BYTES | `subprocess.run` called once; cmd contains `libx264`, `3000k`, `-c:a`, `copy` |
| `test_replaces_original_on_success` | ffmpeg returncode=0 | file > threshold; mock `subprocess.run` returncode=0; mock `os.replace` | `os.replace` called with `(temp_path, original_path)`; temp path follows naming convention `{stem}_tmp_compress.mp4` |
| `test_keeps_original_on_ffmpeg_failure` | ffmpeg returncode=1 | file > threshold; mock returncode=1; temp file created on disk | original file still exists and is unmodified; temp file deleted |
| `test_no_second_pass_if_still_large` | file still > 1.5 GB post-compress | file > threshold; mock `subprocess.run` returncode=0; mock `os.replace` to keep size unchanged; mock `Path.stat` to always return large size | `subprocess.run` called exactly once |

**Expected total: 38 − 3 + 5 = 40 tests**

---

## File Checklist

| File | Action |
|------|--------|
| `app/compressor.py` | **Create** |
| `app/service.py` | **Modify** (remove bitrate params, inject compressor, call compress_if_large after rename in custom-name branch only) |
| `app/gui/main_window.py` | **Modify** (remove checkbox, enable resize, instantiate compressor) |
| `tests/test_compressor.py` | **Create** |
| `tests/test_service.py` | **Modify** (remove 3 tests, update fixture with MagicMock compressor) |
