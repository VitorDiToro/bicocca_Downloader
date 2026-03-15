#!/usr/bin/env python3
"""
yt-dlp Downloader - GUI para download de vídeos
Suporta download de URL única, arquivo TXT ou arquivo YAML
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import sys
import threading
import re
from pathlib import Path


def sanitize_name(name):
    """Remove ou substitui caracteres inválidos para nomes de arquivo/diretório

    Args:
        name: Nome a ser sanitizado

    Returns:
        Nome sanitizado seguro para uso como arquivo ou diretório
    """
    # Substituir dois-pontos por " -" (mais legível)
    name = name.replace(':', ' -')

    # Caracteres inválidos no Windows: < > " / \ | ? *
    # No Windows, também não pode terminar com ponto ou espaço
    invalid_chars = '<>"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '_')

    # Remove espaços e pontos no final
    name = name.rstrip('. ')

    # Se ficou vazio, usar nome padrão
    if not name:
        name = "sem_nome"

    return name


def remove_ansi_codes(text):
    """Remove códigos ANSI de escape (cores de terminal) de uma string

    Args:
        text: String que pode conter códigos ANSI

    Returns:
        String sem códigos ANSI
    """
    # Padrão regex para remover códigos ANSI: \x1b\[[0-9;]*m ou \033\[[0-9;]*m
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    return ansi_escape.sub('', text)


class DownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Moodle video downloader")
        self.root.geometry("600x500")
        self.root.resizable(False, False)

        # Variável para controlar o modo
        self.mode = tk.StringVar(value="single")
        self.file_path = tk.StringVar()
        self.downloading = False
        self.download_subtitles = tk.BooleanVar(value=True)  # Padrão: habilitado

        self._create_widgets()
        self._center_window()

    def _center_window(self):
        """Centraliza a janela na tela"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def _create_widgets(self):
        """Cria os widgets da interface"""
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Título
        title_label = ttk.Label(
            main_frame,
            text="Moodle video downloader",
            font=("Arial", 12, "bold")
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 15))

        # Modo de download
        mode_frame = ttk.LabelFrame(main_frame, text="Modo de Download", padding="10")
        mode_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Radiobutton(
            mode_frame,
            text="URL única",
            variable=self.mode,
            value="single",
            command=self._update_mode
        ).grid(row=0, column=0, sticky=tk.W, padx=(0, 20))

        ttk.Radiobutton(
            mode_frame,
            text="Arquivo TXT",
            variable=self.mode,
            value="file",
            command=self._update_mode
        ).grid(row=0, column=1, sticky=tk.W, padx=(0, 20))

        ttk.Radiobutton(
            mode_frame,
            text="Arquivo YAML",
            variable=self.mode,
            value="yaml",
            command=self._update_mode
        ).grid(row=0, column=2, sticky=tk.W)

        # Checkbox para habilitar/desabilitar legendas
        subtitle_checkbox = ttk.Checkbutton(
            mode_frame,
            text="Baixar legendas em português",
            variable=self.download_subtitles
        )
        subtitle_checkbox.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(10, 0))

        # Frame para URL única
        self.single_frame = ttk.LabelFrame(main_frame, text="URL única", padding="10")
        self.single_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(self.single_frame, text="Cole a URL da aula:").grid(
            row=0, column=0, sticky=tk.W, pady=(0, 5)
        )

        self.url_entry = ttk.Entry(self.single_frame, width=70)
        self.url_entry.grid(row=1, column=0, sticky=(tk.W, tk.E))

        # Frame para arquivo TXT
        self.file_frame = ttk.LabelFrame(main_frame, text="Arquivo TXT", padding="10")
        self.file_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        self.file_frame.grid_remove()  # Esconde inicialmente

        ttk.Label(self.file_frame, text="Selecione um arquivo .txt com URLs (uma por linha):").grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 5)
        )

        file_input_frame = ttk.Frame(self.file_frame)
        file_input_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E))

        self.file_entry = ttk.Entry(file_input_frame, textvariable=self.file_path, width=55, state="readonly")
        self.file_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))

        ttk.Button(
            file_input_frame,
            text="Procurar...",
            command=self._browse_file
        ).grid(row=0, column=1)

        # Frame para arquivo YAML
        self.yaml_path = tk.StringVar()
        self.yaml_frame = ttk.LabelFrame(main_frame, text="Arquivo YAML", padding="10")
        self.yaml_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        self.yaml_frame.grid_remove()  # Esconde inicialmente

        ttk.Label(self.yaml_frame, text="Selecione um arquivo .yaml com disciplina e aulas:").grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 5)
        )

        yaml_input_frame = ttk.Frame(self.yaml_frame)
        yaml_input_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E))

        self.yaml_entry = ttk.Entry(yaml_input_frame, textvariable=self.yaml_path, width=55, state="readonly")
        self.yaml_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))

        ttk.Button(
            yaml_input_frame,
            text="Procurar...",
            command=self._browse_yaml
        ).grid(row=0, column=1)

        # Log de saída
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        log_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=12,
            width=70,
            state="disabled",
            wrap=tk.WORD,
            font=("Consolas", 9)
        )
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Botão de download
        self.download_btn = ttk.Button(
            main_frame,
            text="Baixar",
            command=self._start_download
        )
        self.download_btn.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E))

        # Configurar expansão
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(5, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

    def _update_mode(self):
        """Atualiza a interface baseado no modo selecionado"""
        mode = self.mode.get()

        # Esconde todos os frames
        self.single_frame.grid_remove()
        self.file_frame.grid_remove()
        self.yaml_frame.grid_remove()

        # Mostra apenas o frame correspondente ao modo
        if mode == "single":
            self.single_frame.grid()
        elif mode == "file":
            self.file_frame.grid()
        else:  # yaml
            self.yaml_frame.grid()

    def _browse_file(self):
        """Abre diálogo para selecionar arquivo de URLs (TXT)"""
        filename = filedialog.askopenfilename(
            title="Selecione o arquivo de URLs",
            filetypes=[("Arquivos de texto", "*.txt"), ("Todos os arquivos", "*.*")]
        )
        if filename:
            self.file_path.set(filename)

    def _browse_yaml(self):
        """Abre diálogo para selecionar arquivo YAML"""
        filename = filedialog.askopenfilename(
            title="Selecione o arquivo YAML",
            filetypes=[("Arquivos YAML", "*.yaml *.yml"), ("Todos os arquivos", "*.*")]
        )
        if filename:
            self.yaml_path.set(filename)

    def _log(self, message):
        """Adiciona mensagem ao log"""
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        self.root.update_idletasks()

    def _parse_yaml_file(self, file_path):
        """Parse YAML file and return disciplina and list of (url, custom_name) tuples"""
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML não está instalado.\nInstale com: pip install pyyaml")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Erro ao ler arquivo YAML:\n{e}")

        if not isinstance(data, dict):
            raise ValueError("Formato YAML inválido. Arquivo deve conter um objeto YAML.")

        disciplina = data.get('disciplina', 'Disciplina não especificada')
        aulas = data.get('aulas', [])

        if not aulas:
            raise ValueError("Nenhuma aula encontrada no arquivo YAML.")

        # Validar estrutura das aulas
        items = []
        for idx, aula in enumerate(aulas, 1):
            if not isinstance(aula, dict):
                raise ValueError(f"Aula {idx}: formato inválido. Cada aula deve ter 'url' e 'nome'.")

            url = aula.get('url', '').strip()
            nome = aula.get('nome', '').strip()

            if not url:
                raise ValueError(f"Aula {idx}: campo 'url' está vazio ou ausente.")
            if not nome:
                raise ValueError(f"Aula {idx}: campo 'nome' está vazio ou ausente.")

            items.append((url, nome))

        return disciplina, items

    def _start_download(self):
        """Inicia o processo de download em uma thread separada"""
        if self.downloading:
            messagebox.showwarning("Aviso", "Um download já está em andamento.")
            return

        # Variáveis para controlar o modo YAML
        disciplina = None
        items = None

        # Validação e preparação de dados
        mode = self.mode.get()

        if mode == "single":
            url = self.url_entry.get().strip()
            if not url:
                messagebox.showwarning("Aviso", "Por favor, cole uma URL válida.")
                return
            items = [url]

        elif mode == "file":
            file_path = self.file_path.get()
            if not file_path:
                messagebox.showwarning("Aviso", "Por favor, selecione um arquivo TXT.")
                return

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    items = [line.strip() for line in f if line.strip()]

                if not items:
                    messagebox.showwarning("Aviso", "O arquivo está vazio ou não contém URLs válidas.")
                    return
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao ler o arquivo:\n{e}")
                return

        else:  # yaml
            yaml_path = self.yaml_path.get()
            if not yaml_path:
                messagebox.showwarning("Aviso", "Por favor, selecione um arquivo YAML.")
                return

            try:
                disciplina, items = self._parse_yaml_file(yaml_path)
            except Exception as e:
                messagebox.showerror("Erro", str(e))
                return

        # Verifica se cookies.txt existe
        script_dir = Path(__file__).parent
        cookies_path = script_dir / "cookies.txt"

        if not cookies_path.exists():
            messagebox.showerror(
                "Erro",
                "Arquivo cookies.txt não encontrado na mesma pasta do script."
            )
            return

        # Inicia download em thread separada
        self.downloading = True
        self.download_btn.config(state="disabled")
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state="disabled")

        thread = threading.Thread(
            target=self._download_videos,
            args=(items, cookies_path, disciplina, self.download_subtitles.get()),
            daemon=True
        )
        thread.start()

    def _download_videos(self, items, cookies_path, disciplina=None, download_subtitles=True):
        """Faz o download dos vídeos

        Args:
            items: Lista de URLs (str) ou tuplas (url, nome_customizado)
            cookies_path: Caminho para arquivo de cookies
            disciplina: Nome da disciplina (opcional, usado no modo YAML)
        """
        try:
            import yt_dlp
        except ImportError:
            self.root.after(0, lambda: messagebox.showerror(
                "Erro",
                "yt-dlp não está instalado.\nInstale com: pip install yt-dlp"
            ))
            self._finish_download()
            return

        total = len(items)

        # Cabeçalho do log
        if disciplina:
            self._log(f"Disciplina: {disciplina}")
            self._log("=" * 60)
        self._log(f"Iniciando download de {total} vídeo(s)...\n")

        # Criar diretório da disciplina (se modo YAML)
        output_dir = None
        if disciplina:
            # Sanitizar nome da disciplina
            dir_name = sanitize_name(disciplina)
            output_dir = Path(dir_name)

            # Criar diretório se não existir
            output_dir.mkdir(exist_ok=True)
            self._log(f"Pasta de saída: {output_dir}\n")

        success_count = 0
        error_count = 0
        skipped_count = 0
        downloaded_video_ids = set()  # Track video IDs to detect duplicates

        # Contadores de legendas
        subtitle_success_count = 0
        subtitle_skipped_count = 0

        # Escanear arquivos existentes para detectar IDs já baixados
        if output_dir and output_dir.exists():
            self._log("  Escaneando arquivos existentes...")
            for existing_file in output_dir.glob("*.mp4"):
                # Tentar extrair ID do arquivo temporário se ainda existir
                if existing_file.name.startswith("temp_"):
                    vid_id = existing_file.stem.replace("temp_", "")
                    downloaded_video_ids.add(vid_id)
            if downloaded_video_ids:
                self._log(f"  Encontrados {len(downloaded_video_ids)} vídeo(s) já baixado(s)\n")

        for idx, item in enumerate(items, 1):
            # Verificar se é tupla (url, nome) ou apenas url
            if isinstance(item, tuple):
                url, custom_name = item
                use_custom_name = True
            else:
                url = item
                custom_name = None
                use_custom_name = False

            self._log(f"[{idx}/{total}] Processando: {url}")
            if use_custom_name:
                self._log(f"  Nome: {custom_name}")

            try:
                # Pré-validação: extrair informações primeiro para verificar se arquivo já existe
                self._log("  Verificando informações do vídeo...")

                ydl_opts_info = {
                    'cookiefile': str(cookies_path),
                    'quiet': True,
                    'no_warnings': True,
                }

                with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                    info = ydl.extract_info(url, download=False)

                # Verificar se este vídeo já foi baixado (por ID)
                video_id = info.get('id', '')
                if video_id in downloaded_video_ids:
                    self._log(f"  ⊘ Vídeo duplicado detectado (ID: {video_id}), pulando")
                    skipped_count += 1
                    continue

                # Construir nome do arquivo final
                if use_custom_name:
                    height = info.get('height', 'unknown')
                    resolution = f"{height}p" if height != 'unknown' else "unknown"
                    safe_custom_name = sanitize_name(custom_name)

                    if output_dir:
                        final_name = output_dir / f"{safe_custom_name}_{resolution}.mp4"
                    else:
                        final_name = Path(f"{safe_custom_name}_{resolution}.mp4")
                else:
                    # Modo URL única ou TXT: usar título original
                    title = info.get('title', 'video')
                    final_name = Path(f"{title}.mp4")

                # Verificar se arquivo já existe
                if final_name.exists():
                    # Validar tamanho do arquivo existente
                    existing_size = final_name.stat().st_size
                    expected_size = info.get('filesize') or info.get('filesize_approx') or 0

                    if expected_size and expected_size > 0:
                        size_diff_percent = abs(existing_size - expected_size) / expected_size * 100

                        if size_diff_percent > 5:  # Diferença > 5%
                            self._log(f"  ⚠ Arquivo existe mas parece incompleto:")
                            self._log(f"    Tamanho atual: {existing_size / (1024*1024):.1f} MB")
                            self._log(f"    Tamanho esperado: {expected_size / (1024*1024):.1f} MB")
                            self._log(f"    Diferença: {size_diff_percent:.1f}%")
                            self._log(f"  Removendo arquivo incompleto e re-baixando...")
                            final_name.unlink()  # Remove arquivo incompleto
                        else:
                            self._log(f"  ✓ Arquivo já existe e está completo, pulando: {final_name}")
                            self._log(f"    Tamanho: {existing_size / (1024*1024):.1f} MB")
                            skipped_count += 1
                            continue
                    else:
                        # Não conseguimos obter tamanho esperado, assumir que está OK
                        self._log(f"  ⊘ Arquivo já existe (tamanho não verificável), pulando: {final_name}")
                        self._log(f"    Tamanho: {existing_size / (1024*1024):.1f} MB")
                        skipped_count += 1
                        continue

                self._log("  Arquivo não existe, iniciando download...")

                # Validação de legenda existente (se download habilitado)
                subtitle_exists = False
                if download_subtitles:
                    # Verificar se legenda já existe (pt-BR ou pt)
                    for lang in ['pt-BR', 'pt']:
                        subtitle_final = final_name.with_suffix(f'.{lang}.srt')
                        if subtitle_final.exists():
                            # Validar tamanho (arquivos muito pequenos são inválidos)
                            subtitle_size = subtitle_final.stat().st_size
                            if subtitle_size >= 100:  # Mínimo 100 bytes
                                self._log(f"  ✓ Legenda já existe: {subtitle_final} ({subtitle_size} bytes)")
                                subtitle_skipped_count += 1
                                subtitle_exists = True
                                break
                            else:
                                self._log(f"  ⚠ Legenda existente é inválida ({subtitle_size} bytes), será re-baixada")
                                subtitle_final.unlink()  # Remove legenda inválida

            except Exception as e:
                error_count += 1
                self._log(f"✗ Erro ao verificar vídeo: {e}\n")
                continue

            try:
                # Configuração do yt-dlp
                if use_custom_name:
                    # Modo YAML: download com nome temporário na pasta da disciplina
                    if output_dir:
                        outtmpl = str(output_dir / 'temp_%(id)s.%(ext)s')
                    else:
                        outtmpl = 'temp_%(id)s.%(ext)s'

                    ydl_opts = {
                        'format': 'bestvideo+bestaudio/best',
                        'merge_output_format': 'mp4',
                        'outtmpl': outtmpl,
                        'cookiefile': str(cookies_path),
                        'progress_hooks': [self._progress_hook],
                        'encoding': 'utf-8',
                        'restrictfilenames': False,
                    }

                    # Opções de legenda condicionalmente
                    if download_subtitles:
                        ydl_opts['writesubtitles'] = True           # Baixar legendas manuais
                        ydl_opts['writeautomaticsub'] = True        # Baixar legendas auto-geradas (fallback)
                        ydl_opts['subtitleslangs'] = 'pt-BR,pt'     # Português brasileiro, depois português genérico
                        ydl_opts['subtitlesformat'] = 'srt'         # Formato SRT
                else:
                    # Modo normal: usar título original (sem subpasta)
                    ydl_opts = {
                        'format': 'bestvideo+bestaudio/best',
                        'merge_output_format': 'mp4',
                        'outtmpl': '%(title)s.%(ext)s',
                        'cookiefile': str(cookies_path),
                        'progress_hooks': [self._progress_hook],
                        'encoding': 'utf-8',
                        'restrictfilenames': False,
                    }

                    # Opções de legenda condicionalmente
                    if download_subtitles:
                        ydl_opts['writesubtitles'] = True           # Baixar legendas manuais
                        ydl_opts['writeautomaticsub'] = True        # Baixar legendas auto-geradas (fallback)
                        ydl_opts['subtitleslangs'] = 'pt-BR,pt'     # Português brasileiro, depois português genérico
                        ydl_opts['subtitlesformat'] = 'srt'         # Formato SRT

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Baixar o vídeo (info já foi extraído anteriormente)
                    ydl.download([url])

                    if use_custom_name:
                        # Renomear arquivo com nome customizado + resolução
                        video_id = info['id']

                        # Construir paths considerando a pasta da disciplina
                        if output_dir:
                            temp_file = output_dir / f"temp_{video_id}.mp4"
                        else:
                            temp_file = Path(f"temp_{video_id}.mp4")

                        if temp_file.exists():
                            os.rename(temp_file, final_name)
                            self._log(f"✓ Salvo como: {final_name}\n")

                            # Processar legenda se download habilitado
                            if download_subtitles:
                                # Tentar pt-BR primeiro, depois pt
                                subtitle_found = False
                                for lang in ['pt-BR', 'pt']:
                                    # temp_1234.pt-BR.srt ou temp_1234.pt.srt
                                    subtitle_temp = temp_file.with_suffix(f'.{lang}.srt')

                                    if subtitle_temp.exists():
                                        # Aula 01_1080p.pt-BR.srt ou Aula 01_1080p.pt.srt
                                        subtitle_final = final_name.with_suffix(f'.{lang}.srt')

                                        # Validar tamanho do arquivo de legenda (deve ter pelo menos 100 bytes)
                                        subtitle_size = subtitle_temp.stat().st_size
                                        if subtitle_size < 100:
                                            self._log(f"  ⚠ Legenda muito pequena ({subtitle_size} bytes), pulando\n")
                                            subtitle_temp.unlink()  # Remove legenda inválida
                                            continue

                                        os.rename(subtitle_temp, subtitle_final)
                                        self._log(f"✓ Legenda salva como: {subtitle_final}\n")
                                        subtitle_success_count += 1
                                        subtitle_found = True
                                        break  # Parar após encontrar a primeira legenda

                                if not subtitle_found:
                                    # Legenda pode não estar disponível para alguns vídeos
                                    self._log(f"  ⓘ Nenhuma legenda em português encontrada para este vídeo\n")
                        else:
                            self._log(f"✗ Arquivo temporário não encontrado: {temp_file}\n")
                            error_count += 1
                            continue
                    else:
                        self._log("✓ Download concluído!\n")

                success_count += 1
                # Registrar ID do vídeo como baixado
                if video_id:
                    downloaded_video_ids.add(video_id)
            except Exception as e:
                error_count += 1
                self._log(f"✗ Erro: {e}\n")

        # Resumo
        self._log("=" * 60)
        self._log("Download finalizado!")
        self._log(f"Sucessos: {success_count}")
        self._log(f"Pulados (já existentes): {skipped_count}")
        self._log(f"Erros: {error_count}")
        # Estatísticas de legendas (se download habilitado)
        if download_subtitles:
            self._log(f"Legendas baixadas: {subtitle_success_count}")
            self._log(f"Legendas puladas (já existentes): {subtitle_skipped_count}")
        self._log("=" * 60)

        # Limpa campo URL única após download
        if self.mode.get() == "single":
            self.url_entry.delete(0, tk.END)

        self._finish_download()

    def _progress_hook(self, d):
        """Hook para mostrar progresso do download"""
        if d['status'] == 'downloading':
            # Garantir encoding correto das strings
            percent = d.get('_percent_str', 'N/A')
            speed = d.get('_speed_str', 'N/A')
            eta = d.get('_eta_str', 'N/A')

            # Tratar possíveis problemas de encoding
            if isinstance(percent, bytes):
                percent = percent.decode('utf-8', errors='replace')
            if isinstance(speed, bytes):
                speed = speed.decode('utf-8', errors='replace')
            if isinstance(eta, bytes):
                eta = eta.decode('utf-8', errors='replace')

            # Remover códigos ANSI (cores de terminal)
            percent = remove_ansi_codes(str(percent))
            speed = remove_ansi_codes(str(speed))
            eta = remove_ansi_codes(str(eta))

            self.root.after(0, lambda: self._update_progress(percent, speed, eta))

    def _update_progress(self, percent, speed, eta):
        """Atualiza o log com informações de progresso"""
        self.log_text.config(state="normal")

        # Pegar conteúdo da última linha (antes da linha vazia final)
        try:
            last_line_start = self.log_text.index("end-2l linestart")  # 2 linhas antes do fim
            last_line_end = self.log_text.index("end-1l linestart")    # 1 linha antes do fim
            last_line_content = self.log_text.get(last_line_start, last_line_end)

            # Se a última linha é uma linha de progresso, deletá-la
            if last_line_content.strip().startswith('Progresso:'):
                self.log_text.delete(last_line_start, last_line_end)
        except tk.TclError:
            # Ignorar se houver erro ao acessar índices
            pass

        # Inserir nova linha de progresso
        self.log_text.insert(tk.END, f"  Progresso: {percent} | Velocidade: {speed} | ETA: {eta}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        self.root.update_idletasks()

    def _finish_download(self):
        """Finaliza o processo de download"""
        self.downloading = False
        self.download_btn.config(state="normal")


def main():
    """Função principal"""
    root = tk.Tk()
    app = DownloaderGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
