import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
from pathlib import Path

from app.models import DownloadItem
from app.parsers import parse_yaml_file, parse_txt_file
from app.service import VideoDownloader
from app.utils import resolve_output_dir


class DownloaderGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Moodle video downloader")
        self.root.geometry("600x500")
        self.root.resizable(False, False)

        self.mode = tk.StringVar(value="single")
        self.file_path = tk.StringVar()
        self.yaml_path = tk.StringVar()
        self.download_subtitles = tk.BooleanVar(value=True)
        self.output_dir = tk.StringVar()
        self.limit_bitrate = tk.BooleanVar(value=True)
        self.downloading = False

        self._create_widgets()
        self._center_window()

    def _center_window(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f'{w}x{h}+{x}+{y}')

    def _create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        ttk.Label(main_frame, text="Moodle video downloader",
                  font=("Arial", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 15))

        mode_frame = ttk.LabelFrame(main_frame, text="Modo de Download", padding="10")
        mode_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        for col, (text, value) in enumerate([("URL única", "single"),
                                              ("Arquivo TXT", "file"),
                                              ("Arquivo YAML", "yaml")]):
            ttk.Radiobutton(mode_frame, text=text, variable=self.mode,
                            value=value, command=self._update_mode).grid(
                row=0, column=col, sticky=tk.W, padx=(0, 20))

        ttk.Checkbutton(mode_frame, text="Baixar legendas em português",
                        variable=self.download_subtitles).grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(10, 0))

        ttk.Checkbutton(mode_frame, text="Limitar qualidade de vídeo (~2 Mbps)",
                        variable=self.limit_bitrate).grid(
            row=2, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))

        # Seção de pasta de destino
        dest_frame = ttk.LabelFrame(main_frame, text="Pasta de destino (opcional)", padding="10")
        dest_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        d_inner = ttk.Frame(dest_frame)
        d_inner.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E))
        d_inner.columnconfigure(0, weight=1)
        ttk.Entry(d_inner, textvariable=self.output_dir, width=55, state="readonly").grid(
            row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(d_inner, text="Escolher...", command=self._browse_output_dir).grid(row=0, column=1)
        ttk.Label(dest_frame,
                  text="Se não selecionada, os vídeos serão salvos na pasta atual.",
                  font=("Arial", 8), foreground="gray").grid(row=1, column=0, columnspan=2, sticky=tk.W)

        # URL single frame
        self.single_frame = ttk.LabelFrame(main_frame, text="URL única", padding="10")
        self.single_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        ttk.Label(self.single_frame, text="Cole a URL da aula:").grid(row=0, column=0, sticky=tk.W)
        self.url_entry = ttk.Entry(self.single_frame, width=70)
        self.url_entry.grid(row=1, column=0, sticky=(tk.W, tk.E))

        # TXT file frame
        self.file_frame = ttk.LabelFrame(main_frame, text="Arquivo TXT", padding="10")
        self.file_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        self.file_frame.grid_remove()
        ttk.Label(self.file_frame, text="Selecione um arquivo .txt com URLs (uma por linha):").grid(
            row=0, column=0, columnspan=2, sticky=tk.W)
        f_inner = ttk.Frame(self.file_frame)
        f_inner.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E))
        ttk.Entry(f_inner, textvariable=self.file_path, width=55, state="readonly").grid(
            row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(f_inner, text="Procurar...", command=self._browse_file).grid(row=0, column=1)

        # YAML file frame
        self.yaml_frame = ttk.LabelFrame(main_frame, text="Arquivo YAML", padding="10")
        self.yaml_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        self.yaml_frame.grid_remove()
        ttk.Label(self.yaml_frame, text="Selecione um arquivo .yaml com disciplina e aulas:").grid(
            row=0, column=0, columnspan=2, sticky=tk.W)
        y_inner = ttk.Frame(self.yaml_frame)
        y_inner.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E))
        ttk.Entry(y_inner, textvariable=self.yaml_path, width=55, state="readonly").grid(
            row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(y_inner, text="Procurar...", command=self._browse_yaml).grid(row=0, column=1)

        # Log
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        log_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, width=70,
                                                   state="disabled", wrap=tk.WORD,
                                                   font=("Consolas", 9))
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.download_btn = ttk.Button(main_frame, text="Baixar", command=self._start_download)
        self.download_btn.grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E))

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(6, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

    def _update_mode(self):
        self.single_frame.grid_remove()
        self.file_frame.grid_remove()
        self.yaml_frame.grid_remove()
        {'single': self.single_frame, 'file': self.file_frame,
         'yaml': self.yaml_frame}[self.mode.get()].grid()

    def _browse_file(self):
        f = filedialog.askopenfilename(title="Selecione o arquivo de URLs",
                                       filetypes=[("Arquivos de texto", "*.txt"), ("Todos", "*.*")])
        if f:
            self.file_path.set(f)

    def _browse_yaml(self):
        f = filedialog.askopenfilename(title="Selecione o arquivo YAML",
                                       filetypes=[("Arquivos YAML", "*.yaml *.yml"), ("Todos", "*.*")])
        if f:
            self.yaml_path.set(f)

    def _browse_output_dir(self):
        d = filedialog.askdirectory(title="Selecione a pasta de destino dos downloads")
        if d:
            self.output_dir.set(d)

    def _log(self, message: str):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        self.root.update_idletasks()

    def _update_progress(self, percent: str, speed: str, eta: str):
        self.log_text.config(state="normal")
        try:
            last_start = self.log_text.index("end-2l linestart")
            last_end = self.log_text.index("end-1l linestart")
            if self.log_text.get(last_start, last_end).strip().startswith('Progresso:'):
                self.log_text.delete(last_start, last_end)
        except tk.TclError:
            pass
        self.log_text.insert(tk.END, f"  Progresso: {percent} | Velocidade: {speed} | ETA: {eta}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        self.root.update_idletasks()

    def _start_download(self):
        if self.downloading:
            messagebox.showwarning("Aviso", "Um download já está em andamento.")
            return

        mode = self.mode.get()
        items = []
        disciplina = None

        try:
            if mode == "single":
                url = self.url_entry.get().strip()
                if not url:
                    messagebox.showwarning("Aviso", "Por favor, cole uma URL válida.")
                    return
                items = [DownloadItem(url=url)]

            elif mode == "file":
                path = self.file_path.get()
                if not path:
                    messagebox.showwarning("Aviso", "Por favor, selecione um arquivo TXT.")
                    return
                items = parse_txt_file(path)

            else:  # yaml
                path = self.yaml_path.get()
                if not path:
                    messagebox.showwarning("Aviso", "Por favor, selecione um arquivo YAML.")
                    return
                disciplina, items = parse_yaml_file(path)

        except Exception as e:
            messagebox.showerror("Erro", str(e))
            return

        output_dir = resolve_output_dir(self.output_dir.get(), mode, disciplina)

        cookies_path = Path(__file__).parent.parent.parent / "cookies.txt"
        if not cookies_path.exists():
            messagebox.showerror("Erro", "Arquivo cookies.txt não encontrado.")
            return

        try:
            service = VideoDownloader(
                cookies_path=cookies_path,
                log_callback=lambda m: self.root.after(0, lambda msg=m: self._log(msg)),
                progress_callback=lambda p, s, e: self.root.after(
                    0, lambda pp=p, ss=s, ee=e: self._update_progress(pp, ss, ee)
                ),
            )
        except FileNotFoundError as e:
            messagebox.showerror("Erro", str(e))
            return

        self.downloading = True
        self.download_btn.config(state="disabled")
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state="disabled")

        def run():
            try:
                service.download_items(
                    items=items,
                    output_dir=output_dir,
                    download_subtitles=self.download_subtitles.get(),
                    disciplina=disciplina,
                    max_bitrate_kbps=2000 if self.limit_bitrate.get() else None,
                )
            finally:
                self.downloading = False
                self.root.after(0, lambda: self.download_btn.config(state="normal"))
                if mode == "single":
                    self.root.after(0, lambda: self.url_entry.delete(0, tk.END))

        threading.Thread(target=run, daemon=True).start()


def main():
    root = tk.Tk()
    DownloaderGUI(root)
    root.mainloop()
