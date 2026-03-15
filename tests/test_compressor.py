import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.compressor import VideoCompressor

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
        assert '-c:v' in cmd
        assert cmd[cmd.index('-c:v') + 1] == 'libx264'
        assert cmd[cmd.index('-b:v') + 1] == '3000k'
        assert cmd[cmd.index('-maxrate') + 1] == '3000k'
        assert cmd[cmd.index('-bufsize') + 1] == '6000k'
        assert cmd[cmd.index('-c:a') + 1] == 'copy'

    def test_replaces_original_on_success(self, compressor, tmp_path):
        """Quando ffmpeg tem sucesso, os.replace é chamado com (temp, original)."""
        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"x")
        expected_temp = tmp_path / "video_tmp_compress.mp4"
        expected_temp.write_bytes(b"compressed")  # simula saída do ffmpeg

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
