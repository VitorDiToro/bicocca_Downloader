# Download Path e Quality Cap (1080p) — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que o usuário escolha a pasta de destino dos downloads e limitar a qualidade máxima a 1080p para economizar espaço em disco.

**Architecture:**
- **Quality cap:** Alterar o `format` do yt-dlp em `_build_ydl_opts` para `bestvideo[height<=1080]+bestaudio/best[height<=1080]/bestvideo+bestaudio/best`. Crucialmente, aplicar a mesma string também em `ydl_opts_info` (usado apenas para `extract_info`), pois sem o cap o campo `info['height']` pode retornar 2160 (4K), gerando nomes de arquivo como `Aula_2160p.mp4` enquanto o arquivo real é 1080p — inconsistência de nome que o cap resolve.
- **Pasta de destino:** Adicionar função pura `resolve_output_dir` em `app/utils.py` (onde já vive lógica de paths) e um widget Entry+Button na GUI para todos os modos. Comportamento: se nenhuma pasta for selecionada → comportamento atual preservado; se pasta selecionada → modos single/TXT usam a pasta diretamente; modo YAML usa `pasta / sanitize_name(disciplina)` (mantendo a subpasta da disciplina dentro da pasta escolhida).

**Tech Stack:** Python 3.6+, tkinter, yt-dlp, pytest + unittest.mock

---

## Arquivos Afetados

| Ação | Arquivo | Responsabilidade |
|------|---------|-----------------|
| Modificar | `app/service.py` | Aplicar cap 1080p no format yt-dlp (download e info extraction) |
| Modificar | `app/utils.py` | Adicionar `resolve_output_dir` como função pura |
| Modificar | `app/gui/main_window.py` | Adicionar widget de seleção de pasta; usar `resolve_output_dir` |
| Modificar | `tests/test_service.py` | Testes para quality cap |
| Modificar | `tests/test_utils.py` | Testes para `resolve_output_dir` |

---

## Chunk 1: Quality Cap (1080p) no Service

### Task 1: Limitar qualidade a 1080p

**Files:**
- Modify: `app/service.py` — `_process_item` (ydl_opts_info) e `_build_ydl_opts`
- Test: `tests/test_service.py`

**Por que dois lugares:** `ydl_opts_info` faz `extract_info(download=False)` para obter metadados antes do download. Sem o cap, `info['height']` retorna a maior resolução disponível na fonte (ex: 4K), que é usada em `_build_final_name` para gerar o sufixo `_Xp.mp4`. O arquivo baixado teria 1080p (graças ao cap em `_build_ydl_opts`), mas o nome diria `_2160p`. Aplicar o mesmo cap nos dois lados garante consistência.

**Format string correta:**
```
bestvideo[height<=1080]+bestaudio/best[height<=1080]/bestvideo+bestaudio/best
```
O terceiro fallback `bestvideo+bestaudio/best` garante compatibilidade caso não haja stream com height<=1080 disponível.

- [ ] **Step 1: Escrever testes (comportamental + configuração)**

Em `tests/test_service.py`, adicionar na classe `TestDownloadItems`:

```python
def test_ydl_opts_format_caps_at_1080p(self, service):
    """_build_ydl_opts deve produzir format com cap de 1080p."""
    item = DownloadItem(url="http://x.com", custom_name="Aula 01")
    opts = service._build_ydl_opts(item, output_dir=None, download_subtitles=False)
    assert "height<=1080" in opts['format']


def test_filename_suffix_reflects_1080p_cap_not_source_resolution(self, service, tmp_path):
    """
    Quando a fonte seria 4K, o nome do arquivo deve usar a altura retornada
    pelo extract_info (que, com o cap aplicado nos ydl_opts_info, retornará 1080).
    Isso garante que o sufixo _1080p.mp4 corresponde ao que foi baixado.
    """
    item = DownloadItem(url="http://x.com", custom_name="Aula 01")
    with patch('yt_dlp.YoutubeDL') as mock_ydl:
        mock_ctx = MagicMock()
        # Simula yt-dlp retornando height=1080 (como retornaria com o cap aplicado)
        mock_ctx.extract_info.return_value = {
            'id': 'abc123', 'height': 1080,
            'filesize': None, 'filesize_approx': None,
        }
        mock_ydl.return_value.__enter__ = lambda s: mock_ctx
        mock_ydl.return_value.__exit__ = MagicMock(return_value=False)
        service.download_items([item], output_dir=tmp_path)

    # Verifica que ydl_opts_info (1ª chamada ao YoutubeDL) tem o cap
    first_call_opts = mock_ydl.call_args_list[0][0][0]
    assert "height<=1080" in first_call_opts.get('format', ''), \
        "ydl_opts_info também deve ter o cap para garantir height correto no nome"
```

- [ ] **Step 2: Rodar para confirmar que falham**

```bash
cd /c/git/download_bicocca && python -m pytest tests/test_service.py::TestDownloadItems::test_ydl_opts_format_caps_at_1080p tests/test_service.py::TestDownloadItems::test_filename_suffix_reflects_1080p_cap_not_source_resolution -v
```
Esperado: `FAILED` — `AssertionError`

- [ ] **Step 3: Aplicar cap em `_build_ydl_opts`**

Em `app/service.py`, linha `'format': 'bestvideo+bestaudio/best'`:

```python
# ANTES:
'format': 'bestvideo+bestaudio/best',

# DEPOIS:
'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/bestvideo+bestaudio/best',
```

- [ ] **Step 4: Aplicar cap em `ydl_opts_info` dentro de `_process_item`**

Em `app/service.py`, no dict `ydl_opts_info`:

```python
# ANTES:
ydl_opts_info = {
    'cookiefile': str(self._cookies),
    'quiet': True,
    'no_warnings': True,
}

# DEPOIS:
ydl_opts_info = {
    'cookiefile': str(self._cookies),
    'quiet': True,
    'no_warnings': True,
    'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/bestvideo+bestaudio/best',
}
```

- [ ] **Step 5: Rodar todos os testes**

```bash
cd /c/git/download_bicocca && python -m pytest tests/test_service.py -v
```
Esperado: todos `PASSED`

- [ ] **Step 6: Commit**

```bash
cd /c/git/download_bicocca && git add app/service.py tests/test_service.py
git commit -m "feat: limitar qualidade máxima de download a 1080p"
```

---

## Chunk 2: Seletor de Pasta de Destino

### Task 2a: Adicionar `resolve_output_dir` em `app/utils.py`

**Files:**
- Modify: `app/utils.py`
- Modify: `tests/test_utils.py`

**Comportamento de `resolve_output_dir`:**
- `base_dir=None` ou `""` → retorna `None` (comportamento atual preservado)
- `base_dir` definido + `mode='yaml'` + `disciplina` → `Path(base_dir) / sanitize_name(disciplina)`
- `base_dir` definido + outros modos ou sem disciplina → `Path(base_dir)`

- [ ] **Step 1: Escrever testes em `tests/test_utils.py`**

Adicionar ao final de `tests/test_utils.py`:

```python
from app.utils import resolve_output_dir


class TestResolveOutputDir:
    def test_returns_none_when_base_dir_is_none(self):
        assert resolve_output_dir(None, "single", None) is None

    def test_returns_none_when_base_dir_is_empty_string(self):
        assert resolve_output_dir("", "yaml", "Disciplina X") is None

    def test_single_mode_returns_path_of_base_dir(self, tmp_path):
        result = resolve_output_dir(str(tmp_path), "single", None)
        assert result == tmp_path

    def test_file_mode_returns_path_of_base_dir(self, tmp_path):
        result = resolve_output_dir(str(tmp_path), "file", None)
        assert result == tmp_path

    def test_yaml_mode_appends_sanitized_disciplina_as_subdir(self, tmp_path):
        result = resolve_output_dir(str(tmp_path), "yaml", "Democracia: poder popular")
        assert result == tmp_path / "Democracia - poder popular"

    def test_yaml_mode_without_disciplina_returns_base(self, tmp_path):
        result = resolve_output_dir(str(tmp_path), "yaml", None)
        assert result == tmp_path
```

- [ ] **Step 2: Rodar para confirmar que falha**

```bash
cd /c/git/download_bicocca && python -m pytest tests/test_utils.py::TestResolveOutputDir -v
```
Esperado: `FAILED` — `ImportError: cannot import name 'resolve_output_dir'`

- [ ] **Step 3: Implementar `resolve_output_dir` em `app/utils.py`**

Adicionar ao final de `app/utils.py`:

```python
from pathlib import Path
from typing import Optional


def resolve_output_dir(
    base_dir: Optional[str],
    mode: str,
    disciplina: Optional[str],
) -> Optional[Path]:
    """
    Resolve o diretório de saída final.

    - base_dir vazio/None → None (salva no diretório atual, comportamento legado)
    - modo yaml + disciplina → base_dir / sanitize_name(disciplina)
    - outros modos → Path(base_dir)
    """
    if not base_dir:
        return None
    base = Path(base_dir)
    if mode == "yaml" and disciplina:
        return base / sanitize_name(disciplina)
    return base
```

> **Nota:** `sanitize_name` já está definida no mesmo arquivo. O import de `Path` e `Optional` deve ser adicionado ao topo de `utils.py` caso não existam.

- [ ] **Step 4: Verificar e adicionar imports necessários no topo de `app/utils.py`**

Conferir se `from pathlib import Path` e `from typing import Optional` já existem. Se não, adicionar.

- [ ] **Step 5: Rodar os testes**

```bash
cd /c/git/download_bicocca && python -m pytest tests/test_utils.py -v
```
Esperado: todos `PASSED`

- [ ] **Step 6: Commit**

```bash
cd /c/git/download_bicocca && git add app/utils.py tests/test_utils.py
git commit -m "feat: adicionar resolve_output_dir para calcular pasta de destino"
```

---

### Task 2b: Integrar pasta de destino na GUI

**Files:**
- Modify: `app/gui/main_window.py`

**Mudanças necessárias:**
1. Importar `resolve_output_dir` de `app.utils`
2. Adicionar `self.output_dir = tk.StringVar()` em `__init__`
3. Adicionar seção "Pasta de destino (opcional)" em `_create_widgets`
4. Adicionar método `_browse_output_dir`
5. Atualizar `_start_download` para usar `resolve_output_dir` e remover `output_dir = Path(sanitize_name(disciplina))`

- [ ] **Step 1: Adicionar import de `resolve_output_dir`**

Em `app/gui/main_window.py`, linha do import de `app.utils`:

```python
# ANTES:
from app.utils import sanitize_name

# DEPOIS:
from app.utils import sanitize_name, resolve_output_dir
```

- [ ] **Step 2: Adicionar variável de estado em `__init__`**

Após `self.download_subtitles = tk.BooleanVar(value=True)`:

```python
self.output_dir = tk.StringVar()
```

- [ ] **Step 3: Adicionar seção de pasta de destino em `_create_widgets`**

Inserir novo frame entre `mode_frame` (row=1) e `single_frame`. O novo frame vai em `row=2`. Deslocar todos os frames subsequentes em +1:

```python
# Seção de pasta de destino (inserir após mode_frame, antes de single_frame)
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
```

Atualizar os `row=` dos frames seguintes:
- `self.single_frame` → `row=3`
- `self.file_frame` → `row=4`
- `self.yaml_frame` → `row=5`
- `log_frame` → `row=6`
- `self.download_btn` → `row=7`
- `main_frame.rowconfigure(5, weight=1)` → `main_frame.rowconfigure(6, weight=1)`

- [ ] **Step 4: Adicionar método `_browse_output_dir`**

Após o método `_browse_yaml`:

```python
def _browse_output_dir(self):
    d = filedialog.askdirectory(title="Selecione a pasta de destino dos downloads")
    if d:
        self.output_dir.set(d)
```

- [ ] **Step 5: Atualizar `_start_download`**

No início do método `_start_download`, `output_dir = None` já existe. Localizar e modificar:

```python
# ANTES (variável inicializada no topo do método):
output_dir = None

# no bloco else: # yaml
disciplina, items = parse_yaml_file(path)
output_dir = Path(sanitize_name(disciplina))   # ← REMOVER esta linha

# DEPOIS — após todo o bloco de parsing (após o try/except de items):
output_dir = resolve_output_dir(self.output_dir.get(), mode, disciplina)
```

Resultado esperado do `_start_download` após a mudança (trecho relevante):

```python
output_dir = None
disciplina = None

try:
    if mode == "single":
        ...
        items = [DownloadItem(url=url)]

    elif mode == "file":
        ...
        items = parse_txt_file(path)

    else:  # yaml
        ...
        disciplina, items = parse_yaml_file(path)
        # NÃO há mais: output_dir = Path(sanitize_name(disciplina))

except Exception as e:
    messagebox.showerror("Erro", str(e))
    return

output_dir = resolve_output_dir(self.output_dir.get(), mode, disciplina)
```

- [ ] **Step 6: Rodar todos os testes**

```bash
cd /c/git/download_bicocca && python -m pytest -v
```
Esperado: todos `PASSED`

- [ ] **Step 7: Smoke test manual**

```bash
cd /c/git/download_bicocca && python downloader.py
```

Verificar:
- [ ] Seção "Pasta de destino (opcional)" aparece abaixo dos radio buttons
- [ ] Botão "Escolher..." abre diálogo de seleção de diretório
- [ ] Modo YAML sem pasta selecionada: comportamento legado (cria subpasta da disciplina no diretório atual)
- [ ] Modo YAML com pasta selecionada: cria `<pasta_escolhida>/<disciplina>/`
- [ ] Modo single com pasta selecionada: salva diretamente em `<pasta_escolhida>/`

- [ ] **Step 8: Commit**

```bash
cd /c/git/download_bicocca && git add app/gui/main_window.py
git commit -m "feat: adicionar seletor de pasta de destino para downloads"
```

---

## Chunk 3: Verificação Final

- [ ] **Step 1: Rodar suite completa**

```bash
cd /c/git/download_bicocca && python -m pytest -v
```
Esperado: todos `PASSED`, zero falhas.
