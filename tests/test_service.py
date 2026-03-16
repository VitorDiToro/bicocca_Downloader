import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from app.service import VideoDownloader
from app.models import DownloadItem, DownloadStatus, DownloadSummary


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
        compressor=MagicMock(),
    )


class TestVideoDownloaderInit:
    def test_raises_if_cookies_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="cookies.txt"):
            VideoDownloader(
                cookies_path=tmp_path / "missing.txt",
                log_callback=lambda m: None,
                progress_callback=lambda p, s, e: None,
                compressor=MagicMock(),
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


_VTT_CONTENT = (
    b"WEBVTT\n\n"
    b"1\n00:00:00.600 --> 00:00:03.520\nBom dia!\n\n"
    b"2\n00:00:03.520 --> 00:00:06.120\nSejam bem-vindos!\n\n"
) * 10  # >100 bytes


class TestSubtitleHandling:
    """Testa _move_subtitle e _convert_vtt_to_srt."""

    # ------------------------------------------------------------------
    # _convert_vtt_to_srt
    # ------------------------------------------------------------------

    def test_convert_vtt_to_srt_calls_ffmpeg_with_utf8_flag(self, service, tmp_path):
        vtt = tmp_path / "sub.pt.vtt"
        vtt.write_bytes(_VTT_CONTENT)
        srt = tmp_path / "sub.srt"

        with patch("app.service.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = service._convert_vtt_to_srt(vtt, srt)

        assert result is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "ffmpeg"
        assert str(vtt) in cmd
        assert str(srt) in cmd
        assert "-metadata:s:0" in cmd
        assert "charset=UTF-8" in cmd

    def test_convert_vtt_to_srt_returns_false_on_ffmpeg_error(self, service, tmp_path):
        vtt = tmp_path / "sub.pt.vtt"
        vtt.write_bytes(_VTT_CONTENT)
        srt = tmp_path / "sub.srt"

        with patch("app.service.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr=b"erro simulado")
            result = service._convert_vtt_to_srt(vtt, srt)

        assert result is False

    def test_convert_vtt_to_srt_returns_false_on_exception(self, service, tmp_path):
        vtt = tmp_path / "sub.pt.vtt"
        vtt.write_bytes(_VTT_CONTENT)
        srt = tmp_path / "sub.srt"

        with patch("app.service.subprocess.run", side_effect=FileNotFoundError("ffmpeg")):
            result = service._convert_vtt_to_srt(vtt, srt)

        assert result is False

    # ------------------------------------------------------------------
    # _move_subtitle — VTT encontrado
    # ------------------------------------------------------------------

    def test_move_subtitle_converts_vtt_and_removes_original(self, service, tmp_path):
        vtt = tmp_path / "temp_abc.pt.vtt"
        vtt.write_bytes(_VTT_CONTENT)
        temp_file = tmp_path / "temp_abc.mp4"
        final_name = tmp_path / "Aula_01_1080p.mp4"
        summary = DownloadSummary()

        with patch("app.service.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            service._move_subtitle(temp_file, final_name, summary)

        # ffmpeg foi chamado
        assert mock_run.called
        cmd = mock_run.call_args[0][0]
        assert str(vtt) in cmd
        assert str(tmp_path / "Aula_01_1080p.srt") in cmd

        # VTT original removido; contador incrementado
        assert not vtt.exists()
        assert summary.subtitle_success == 1

    def test_move_subtitle_uses_pt_br_when_pt_absent(self, service, tmp_path):
        """Deve tentar 'pt' primeiro, depois 'pt-BR'."""
        vtt = tmp_path / "temp_xyz.pt-BR.vtt"
        vtt.write_bytes(_VTT_CONTENT)
        temp_file = tmp_path / "temp_xyz.mp4"
        final_name = tmp_path / "Aula_02_1080p.mp4"
        summary = DownloadSummary()

        with patch("app.service.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            service._move_subtitle(temp_file, final_name, summary)

        assert mock_run.called
        assert summary.subtitle_success == 1

    def test_move_subtitle_skips_vtt_smaller_than_100_bytes(self, service, tmp_path):
        vtt = tmp_path / "temp_abc.pt.vtt"
        vtt.write_bytes(b"WEBVTT\n\ntiny")
        temp_file = tmp_path / "temp_abc.mp4"
        final_name = tmp_path / "Aula_01_1080p.mp4"
        summary = DownloadSummary()

        with patch("app.service.subprocess.run") as mock_run:
            service._move_subtitle(temp_file, final_name, summary)

        assert not mock_run.called
        assert not vtt.exists()
        assert summary.subtitle_success == 0

    def test_move_subtitle_logs_none_found_when_no_files(self, service, tmp_path, logs):
        temp_file = tmp_path / "temp_abc.mp4"
        final_name = tmp_path / "Aula_01_1080p.mp4"
        summary = DownloadSummary()

        service._move_subtitle(temp_file, final_name, summary)

        assert summary.subtitle_success == 0
        assert any("Nenhuma legenda" in m for m in logs)

    def test_move_subtitle_continues_after_ffmpeg_failure(self, service, tmp_path):
        """Se ffmpeg falha no .pt.vtt, tenta próximo da lista (pt-BR.vtt)."""
        vtt_pt = tmp_path / "temp_abc.pt.vtt"
        vtt_pt.write_bytes(_VTT_CONTENT)
        vtt_ptbr = tmp_path / "temp_abc.pt-BR.vtt"
        vtt_ptbr.write_bytes(_VTT_CONTENT)
        temp_file = tmp_path / "temp_abc.mp4"
        final_name = tmp_path / "Aula_01_1080p.mp4"
        summary = DownloadSummary()

        call_count = 0
        def flaky_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            # First call (pt.vtt) fails; second (pt-BR.vtt) succeeds
            rc = 1 if call_count == 1 else 0
            return MagicMock(returncode=rc, stderr=b"fail")

        with patch("app.service.subprocess.run", side_effect=flaky_run):
            service._move_subtitle(temp_file, final_name, summary)

        assert call_count == 2
        assert summary.subtitle_success == 1

    # ------------------------------------------------------------------
    # _move_subtitle — SRT encontrado diretamente (sem conversão)
    # ------------------------------------------------------------------

    def test_move_subtitle_renames_srt_directly(self, service, tmp_path):
        srt_src = tmp_path / "temp_abc.pt.srt"
        srt_src.write_bytes(_VTT_CONTENT)  # conteúdo irrelevante, tamanho > 100
        temp_file = tmp_path / "temp_abc.mp4"
        final_name = tmp_path / "Aula_01_1080p.mp4"
        summary = DownloadSummary()

        with patch("app.service.subprocess.run") as mock_run:
            service._move_subtitle(temp_file, final_name, summary)

        # Não chamou ffmpeg (já era SRT)
        assert not mock_run.called
        assert not srt_src.exists()
        assert (tmp_path / "Aula_01_1080p.srt").exists()
        assert summary.subtitle_success == 1

    # ------------------------------------------------------------------
    # _check_existing_subtitle
    # ------------------------------------------------------------------

    def test_check_existing_subtitle_skips_if_srt_exists(self, service, tmp_path, logs):
        final_name = tmp_path / "Aula_01_1080p.mp4"
        srt = final_name.with_suffix(".srt")
        srt.write_bytes(_VTT_CONTENT)
        summary = DownloadSummary()

        service._check_existing_subtitle(None, final_name, True, summary)

        assert summary.subtitle_skipped == 1
        assert any("já existe" in m for m in logs)

    def test_check_existing_subtitle_removes_invalid_srt(self, service, tmp_path):
        final_name = tmp_path / "Aula_01_1080p.mp4"
        srt = final_name.with_suffix(".srt")
        srt.write_bytes(b"tiny")  # < 100 bytes
        summary = DownloadSummary()

        service._check_existing_subtitle(None, final_name, True, summary)

        assert not srt.exists()
        assert summary.subtitle_skipped == 0

    def test_check_existing_subtitle_noop_when_disabled(self, service, tmp_path, logs):
        final_name = tmp_path / "Aula_01_1080p.mp4"
        summary = DownloadSummary()

        service._check_existing_subtitle(None, final_name, False, summary)

        assert summary.subtitle_skipped == 0
        assert not any("legenda" in m.lower() for m in logs)
