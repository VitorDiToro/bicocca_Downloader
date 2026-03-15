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
4. Run FFmpeg via `subprocess.run`:
   ```
   ffmpeg -i <input> -c:v libx264 -b:v 3000k -maxrate 3000k -bufsize 6000k -c:a copy -y <temp>
   ```
5. On failure (returncode ≠ 0 or exception): log error, delete temp if it exists, **leave original untouched**, return.
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
- In `_process_item`, after a successful download and file rename, call:
  ```python
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
- `main_frame` `rowconfigure` for the log row gets `weight=1` to propagate vertical growth
- `log_frame` inner `rowconfigure(0, weight=1)` and `columnconfigure(0, weight=1)` confirmed present
- All other frames/widgets remain at fixed size (no `sticky` changes except log area)

**`VideoCompressor` instantiation:**
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

### New: `tests/test_compressor.py` (5 tests)

| Test | Scenario | Assert |
|------|----------|--------|
| `test_skips_file_below_threshold` | file < 1.5 GB | `subprocess.run` not called |
| `test_calls_ffmpeg_for_large_file` | file > 1.5 GB | `subprocess.run` called; args contain `libx264`, `3000k`, `-c:a`, `copy` |
| `test_replaces_original_on_success` | ffmpeg returncode=0 | original path replaced by temp output |
| `test_keeps_original_on_ffmpeg_failure` | ffmpeg returncode=1 | original untouched, temp removed |
| `test_no_second_pass_if_still_large` | file still > 1.5 GB post-compress | `subprocess.run` called exactly once |

### `tests/test_service.py`: update fixture to inject `VideoCompressor` mock

All existing service tests pass a `MagicMock()` compressor to avoid ffmpeg side-effects.

**Expected total: 38 − 3 + 5 = 40 tests**

---

## File Checklist

| File | Action |
|------|--------|
| `app/compressor.py` | **Create** |
| `app/service.py` | **Modify** (remove bitrate params, inject compressor, call compress_if_large) |
| `app/gui/main_window.py` | **Modify** (remove checkbox, add resizable, instantiate compressor) |
| `tests/test_compressor.py` | **Create** |
| `tests/test_service.py` | **Modify** (remove 3 tests, update fixture) |
