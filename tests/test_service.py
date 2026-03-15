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

    def test_ydl_opts_format_caps_at_1080p(self, service):
        """_build_ydl_opts deve produzir format com cap de 1080p."""
        item = DownloadItem(url="http://x.com", custom_name="Aula 01")
        opts = service._build_ydl_opts(item, output_dir=None, download_subtitles=False)
        assert "height<=1080" in opts['format']

    def test_filename_suffix_reflects_1080p_cap_not_source_resolution(self, service, tmp_path):
        """
        4K source scenario: ydl_opts_info must carry height<=1080 cap so that
        extract_info returns 1080 (not 2160), ensuring filename suffix is correct.
        """
        item = DownloadItem(url="http://x.com", custom_name="Aula 01")

        with patch('yt_dlp.YoutubeDL') as mock_ydl:
            mock_ctx = MagicMock()
            # With cap in ydl_opts_info, yt-dlp selects best-at-or-below-1080p → returns 1080
            # Without the cap, a 4K source would return height=2160 here
            mock_ctx.extract_info.return_value = {
                'id': 'abc123', 'height': 1080,
                'filesize': None, 'filesize_approx': None,
            }
            mock_ydl.return_value.__enter__ = lambda s: mock_ctx
            mock_ydl.return_value.__exit__ = MagicMock(return_value=False)
            service.download_items([item], output_dir=tmp_path)

        # ydl_opts_info (first YoutubeDL call) must carry the cap
        first_call_opts = mock_ydl.call_args_list[0][0][0]
        assert "height<=1080" in first_call_opts.get('format', ''), \
            "Without cap in ydl_opts_info, a 4K source returns height=2160 → wrong filename"

    def test_build_final_name_uses_height_from_info(self, service, tmp_path):
        """_build_final_name suffix reflects the height in info dict."""
        item = DownloadItem(url="http://x.com", custom_name="Aula 01")

        # Simulates what yt-dlp returns WITH cap applied (1080, not 2160)
        info_with_cap = {'height': 1080, 'title': 'Test'}
        result = service._build_final_name(item, info_with_cap, tmp_path)
        assert "_1080p.mp4" in result.name
        assert "_2160p.mp4" not in result.name

    def test_build_ydl_opts_without_bitrate_limit_has_no_format_sort(self, service):
        """Sem limite de bitrate, format_sort não deve estar presente nos opts."""
        item = DownloadItem(url="http://x.com", custom_name="Aula 01")
        opts = service._build_ydl_opts(item, output_dir=None, download_subtitles=False,
                                       max_bitrate_kbps=None)
        assert 'format_sort' not in opts

    def test_build_ydl_opts_with_bitrate_limit_adds_format_sort(self, service):
        """Com max_bitrate_kbps=2000, format_sort deve conter vbr:2000, tbr:2000 e res:1080."""
        item = DownloadItem(url="http://x.com", custom_name="Aula 01")
        opts = service._build_ydl_opts(item, output_dir=None, download_subtitles=False,
                                       max_bitrate_kbps=2000)
        assert 'format_sort' in opts
        assert 'vbr:2000' in opts['format_sort']
        assert 'tbr:2000' in opts['format_sort']
        assert 'res:1080' in opts['format_sort']

    def test_download_items_passes_bitrate_limit_to_both_ydl_calls(self, service, tmp_path):
        """
        max_bitrate_kbps=2000 deve chegar como format_sort tanto na chamada de info extraction
        (1ª call: call_args_list[0]) quanto na chamada de download (2ª call: call_args_list[1]).
        """
        item = DownloadItem(url="http://x.com", custom_name="Aula 01")
        with patch('yt_dlp.YoutubeDL') as mock_ydl:
            mock_ctx = MagicMock()
            mock_ctx.extract_info.return_value = {
                'id': 'abc123', 'height': 720,   # simula formato bitrate-reduzido em 720p
                'filesize': None, 'filesize_approx': None,
            }
            mock_ydl.return_value.__enter__ = lambda s: mock_ctx
            mock_ydl.return_value.__exit__ = MagicMock(return_value=False)
            service.download_items([item], output_dir=tmp_path, max_bitrate_kbps=2000)

        # 1ª call = ydl_opts_info (extract_info)
        info_call_opts = mock_ydl.call_args_list[0][0][0]
        assert 'format_sort' in info_call_opts, \
            "ydl_opts_info deve ter format_sort para garantir altura correta no filename"
        assert 'vbr:2000' in info_call_opts['format_sort']

        # 2ª call = opts de download real
        download_call_opts = mock_ydl.call_args_list[1][0][0]
        assert 'format_sort' in download_call_opts
        assert 'vbr:2000' in download_call_opts['format_sort']
