import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
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
