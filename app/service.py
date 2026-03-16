import os
import subprocess
from pathlib import Path
from typing import Callable, List, Optional

from app.compressor import VideoCompressor
from app.models import DownloadItem, DownloadResult, DownloadStatus, DownloadSummary
from app.utils import sanitize_name, remove_ansi_codes

_FORMAT_WITH_CAP = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/bestvideo+bestaudio/best'
_SUBTITLE_LANGS = ['pt', 'pt-BR']
_SUBTITLE_EXTS = ['vtt', 'srt']


class VideoDownloader:
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
                'format': _FORMAT_WITH_CAP,
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
                if download_subtitles and item.use_custom_name:
                    self._download_subtitle_if_missing(
                        item, info, final_name, output_dir, summary, yt_dlp
                    )
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
                    self._compressor.compress_if_large(final_name)
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
        sub = final_name.with_suffix('.srt')
        if sub.exists() and sub.stat().st_size >= 100:
            self._log_cb(f"  ✓ Legenda já existe: {sub}")
            summary.subtitle_skipped += 1
        elif sub.exists():
            self._log_cb(f"  ⚠ Legenda inválida, será re-baixada")
            sub.unlink()

    def _download_subtitle_if_missing(self, item, info, final_name, output_dir, summary, yt_dlp):
        """Baixa a legenda separadamente quando o vídeo já existe no disco."""
        sub = final_name.with_suffix('.srt')
        if sub.exists() and sub.stat().st_size >= 100:
            self._log_cb(f"  ✓ Legenda já existe: {sub}")
            summary.subtitle_skipped += 1
            return
        self._log_cb("  Baixando legenda (vídeo já existe)...")
        video_id = info['id']
        base = output_dir if output_dir else Path('.')
        ydl_opts = self._build_ydl_opts(item, output_dir, download_subtitles=True)
        ydl_opts['skip_download'] = True
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([item.url])
            temp_file = base / f"temp_{video_id}.mp4"
            self._move_subtitle(temp_file, final_name, summary)
        except Exception as e:
            self._log_cb(f"  ⚠ Erro ao baixar legenda: {e}\n")

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
        if download_subtitles:
            opts.update({
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': _SUBTITLE_LANGS,
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
        for lang in _SUBTITLE_LANGS:
            for src_ext in _SUBTITLE_EXTS:
                subtitle_temp = temp_file.with_suffix(f'.{lang}.{src_ext}')
                if not subtitle_temp.exists():
                    continue
                if subtitle_temp.stat().st_size < 100:
                    self._log_cb(f"  ⚠ Legenda muito pequena, pulando\n")
                    subtitle_temp.unlink()
                    continue
                subtitle_final = final_name.with_suffix('.srt')
                if src_ext == 'vtt':
                    ok = self._convert_vtt_to_srt(subtitle_temp, subtitle_final)
                    subtitle_temp.unlink(missing_ok=True)
                    if not ok:
                        continue
                else:
                    os.rename(subtitle_temp, subtitle_final)
                self._log_cb(f"✓ Legenda salva como: {subtitle_final}\n")
                summary.subtitle_success += 1
                return
        self._log_cb("  ⓘ Nenhuma legenda em português encontrada\n")

    def _convert_vtt_to_srt(self, vtt_path: Path, srt_path: Path) -> bool:
        """Converte legenda VTT → SRT via ffmpeg (UTF-8). Retorna True em caso de sucesso."""
        try:
            result = subprocess.run(
                ['ffmpeg', '-i', str(vtt_path),
                 '-metadata:s:0', 'charset=UTF-8', '-y', str(srt_path)],
                stderr=subprocess.PIPE,
            )
            if result.returncode != 0:
                stderr_text = result.stderr.decode('utf-8', errors='replace')
                self._log_cb(f"  ⚠ Erro na conversão VTT→SRT: {stderr_text[-300:]}\n")
                return False
            return True
        except Exception as e:
            self._log_cb(f"  ⚠ Erro ao executar ffmpeg para legenda: {e}\n")
            return False

    def _progress_hook(self, d):
        if d['status'] == 'downloading':
            percent = remove_ansi_codes(str(d.get('_percent_str', 'N/A')))
            speed = remove_ansi_codes(str(d.get('_speed_str', 'N/A')))
            eta = remove_ansi_codes(str(d.get('_eta_str', 'N/A')))
            self._progress_cb(percent, speed, eta)
