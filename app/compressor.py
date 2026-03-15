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

        if not temp_path.exists():
            self._log("  ✗ ffmpeg saiu com sucesso mas o arquivo temporário não foi criado")
            return

        new_size = os.path.getsize(temp_path)
        os.replace(temp_path, file_path)
        self._log(
            f"  ✓ Compressão concluída: {original_size / 1024 ** 3:.2f} GB "
            f"→ {new_size / 1024 ** 3:.2f} GB"
        )
