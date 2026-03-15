# Bitrate Limit (~2 Mbps) Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar um checkbox na GUI que, quando marcado, instrui o yt-dlp a **preferir** streams com bitrate de vídeo próximo a 2000 kbps, evitando downloads desnecessariamente grandes (ex: 5.5 Mbps quando 1.7 Mbps já é suficiente).

**Architecture:** O parâmetro `max_bitrate_kbps: Optional[int]` desce pela cadeia `download_items → _process_item → _build_ydl_opts`. Quando definido, `format_sort` é adicionado tanto em `ydl_opts_info` (metadata extraction) quanto nos opts de download — garantindo que o filename suffix e o arquivo real usem a mesma seleção de formato. A GUI adiciona um `Checkbutton` ao frame "Modo de Download" e passa `max_bitrate_kbps=2000` ou `None`.

**Tech Stack:** Python 3.6+, tkinter, yt-dlp (`format_sort`), pytest + unittest.mock

---

## Decisão de design: preferência suave, não hard-limit

O `format_sort` do yt-dlp **ordena** formatos elegíveis por proximidade ao valor fornecido — não os exclui. `['vbr:2000', 'tbr:2000', 'res:1080']` diz: "entre os streams com height ≤ 1080p, prefira os com vbr ≤ ~2000 kbps; se não existirem, use o melhor disponível."

Este comportamento é **intencional**: o label da GUI diz "~2 Mbps" (com til) para comunicar que é uma preferência, não um limite absoluto. Se a fonte tiver apenas streams de 5.5 Mbps, o yt-dlp baixará o melhor disponível em vez de falhar. Isso é preferível a um hard-limit que poderia resultar em erro ou vídeo de qualidade muito baixa.

O `format_sort` coexiste com `format` (que já faz hard-limit de height ≤ 1080p) sem conflito.

---

## Arquivos Afetados

| Ação | Arquivo | O que muda |
|------|---------|-----------|
| Modificar | `app/service.py` | `download_items`, `_process_item`, `_build_ydl_opts` recebem `max_bitrate_kbps`; `ydl_opts_info` e opts de download ganham `format_sort` condicional |
| Modificar | `app/gui/main_window.py` | Novo `BooleanVar` + `Checkbutton` em `mode_frame`; passa `max_bitrate_kbps` ao service |
| Modificar | `tests/test_service.py` | 3 testes novos cobrindo ausência e presença de `format_sort` |

---

## Contexto crítico: `ydl_opts_info` TAMBÉM precisa de `format_sort`

Em `_process_item`, o `ydl_opts_info` faz `extract_info(download=False)` para obter metadata, incluindo `info.get('height')` usado para nomear o arquivo (ex: `_1080p.mp4`). O yt-dlp respeita `format_sort` também durante `extract_info` — aplica o sort e retorna a altura do formato selecionado.

Se `format_sort` só fosse aplicado nos opts de download (segundo `YoutubeDL`), o resultado seria inconsistente:
- `extract_info` selecionaria o formato por height ≤ 1080p apenas → retornaria `height=1080`
- O download selecionaria por bitrate → poderia baixar `height=720`
- O arquivo seria `720p` mas nomeado `_1080p.mp4` ← **BUG**

**Solução:** Quando `max_bitrate_kbps` é definido, adicionar `format_sort` em **ambos os lugares**, exatamente como `_FORMAT_WITH_CAP` já é aplicado em ambos. Isso é responsabilidade de `_process_item` (que constrói `ydl_opts_info` inline) e de `_build_ydl_opts` (que constrói os opts de download).

---

## Chunk 1: Suporte a `max_bitrate_kbps` no Service

### Task 1: Propagar `max_bitrate_kbps` e aplicar `format_sort` nos dois pontos de download

**Files:**
- Modify: `app/service.py`
- Test: `tests/test_service.py`

**Mudanças em `app/service.py`:**

1. **`download_items`** — adicionar parâmetro como último keyword arg:
   ```python
   def download_items(
       self,
       items: List[DownloadItem],
       output_dir: Optional[Path] = None,
       download_subtitles: bool = True,
       disciplina: Optional[str] = None,
       max_bitrate_kbps: Optional[int] = None,   # ← NOVO
   ) -> DownloadSummary:
   ```

2. **`_process_item`** — adicionar como último parâmetro (após `summary`):
   ```python
   def _process_item(self, item, output_dir, download_subtitles, downloaded_ids, yt_dlp, summary,
                     max_bitrate_kbps=None):   # ← NOVO, após summary
   ```

3. **Call de `_process_item` dentro de `download_items`** — adicionar o argumento:
   ```python
   result = self._process_item(
       item, output_dir, download_subtitles, downloaded_ids, yt_dlp, summary,
       max_bitrate_kbps   # ← NOVO
   )
   ```

4. **`ydl_opts_info` dentro de `_process_item`** — adicionar `format_sort` condicional:
   ```python
   ydl_opts_info = {
       'cookiefile': str(self._cookies),
       'quiet': True,
       'no_warnings': True,
       'format': _FORMAT_WITH_CAP,
   }
   if max_bitrate_kbps is not None:           # ← NOVO bloco
       ydl_opts_info['format_sort'] = [
           f'vbr:{max_bitrate_kbps}',
           f'tbr:{max_bitrate_kbps}',
           'res:1080',
       ]
   ```

5. **`_build_ydl_opts`** — adicionar parâmetro e `format_sort` condicional:
   ```python
   def _build_ydl_opts(self, item, output_dir, download_subtitles, max_bitrate_kbps=None):   # ← NOVO
   ```
   Após a chave `'restrictfilenames': False,` no dict `opts`, adicionar antes do `if download_subtitles:`:
   ```python
   if max_bitrate_kbps is not None:
       opts['format_sort'] = [
           f'vbr:{max_bitrate_kbps}',
           f'tbr:{max_bitrate_kbps}',
           'res:1080',
       ]
   ```

6. **Call de `_build_ydl_opts` dentro de `_process_item`**:
   ```python
   # ANTES:
   ydl_opts = self._build_ydl_opts(item, output_dir, download_subtitles)
   # DEPOIS:
   ydl_opts = self._build_ydl_opts(item, output_dir, download_subtitles, max_bitrate_kbps)
   ```

---

- [ ] **Step 1: Escrever os testes**

Em `tests/test_service.py`, adicionar na classe `TestDownloadItems`:

```python
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
```

- [ ] **Step 2: Rodar para confirmar que falham**

```bash
cd /c/git/download_bicocca && .venv/Scripts/python -m pytest tests/test_service.py::TestDownloadItems::test_build_ydl_opts_without_bitrate_limit_has_no_format_sort tests/test_service.py::TestDownloadItems::test_build_ydl_opts_with_bitrate_limit_adds_format_sort tests/test_service.py::TestDownloadItems::test_download_items_passes_bitrate_limit_to_both_ydl_calls -v
```
Esperado: `FAILED` — `TypeError: _build_ydl_opts() got an unexpected keyword argument`

- [ ] **Step 3: Aplicar todas as mudanças em `app/service.py`**

Aplicar os 6 itens descritos acima (assinaturas + `ydl_opts_info` + `_build_ydl_opts` + calls).

- [ ] **Step 4: Rodar todos os testes do service**

```bash
cd /c/git/download_bicocca && .venv/Scripts/python -m pytest tests/test_service.py -v
```
Esperado: todos `PASSED` (incluindo os 3 novos, total = 10)

- [ ] **Step 5: Commit**

```bash
cd /c/git/download_bicocca && git add app/service.py tests/test_service.py
git commit -m "feat: adicionar suporte a max_bitrate_kbps para preferência de bitrate no download"
```

---

## Chunk 2: Checkbox de Bitrate Limit na GUI

### Task 2: Adicionar checkbox "Limitar qualidade de vídeo (~2 Mbps)"

**Files:**
- Modify: `app/gui/main_window.py`

**Contexto:** O `mode_frame` atualmente tem:
- `row=0`: radio buttons (URL única / Arquivo TXT / Arquivo YAML)
- `row=1`: checkbox "Baixar legendas em português"

O novo checkbox vai em `row=2` do mesmo `mode_frame`. Nenhum outro frame precisa ser deslocado.

O valor `2000` (kbps) é fixo e invisível para o usuário — o checkbox apenas ativa/desativa a preferência. Esta é uma decisão de design intencional: o label "~2 Mbps" comunica o comportamento sem expor controle granular.

- [ ] **Step 1: Adicionar `self.limit_bitrate` em `__init__`**

Após `self.output_dir = tk.StringVar()`:

```python
self.limit_bitrate = tk.BooleanVar(value=True)
```

- [ ] **Step 2: Adicionar o `Checkbutton` em `_create_widgets`**

Após o `ttk.Checkbutton` de legendas (row=1 do `mode_frame`):

```python
ttk.Checkbutton(mode_frame, text="Limitar qualidade de vídeo (~2 Mbps)",
                variable=self.limit_bitrate).grid(
    row=2, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
```

- [ ] **Step 3: Passar `max_bitrate_kbps` na call a `service.download_items`**

Em `_start_download`, atualizar a call (linhas ~226-231):

```python
# ANTES:
service.download_items(
    items=items,
    output_dir=output_dir,
    download_subtitles=self.download_subtitles.get(),
    disciplina=disciplina,
)

# DEPOIS:
service.download_items(
    items=items,
    output_dir=output_dir,
    download_subtitles=self.download_subtitles.get(),
    disciplina=disciplina,
    max_bitrate_kbps=2000 if self.limit_bitrate.get() else None,
)
```

- [ ] **Step 4: Rodar todos os testes**

```bash
cd /c/git/download_bicocca && .venv/Scripts/python -m pytest -v
```
Esperado: todos `PASSED` (35 existentes + 3 novos = 38 testes)

- [ ] **Step 5: Smoke test manual**

```bash
cd /c/git/download_bicocca && python downloader.py
```

Verificar:
- [ ] Checkbox "Limitar qualidade de vídeo (~2 Mbps)" aparece dentro de "Modo de Download", abaixo de "Baixar legendas em português"
- [ ] Checkbox está marcado por padrão
- [ ] Layout não quebra com o elemento adicional

- [ ] **Step 6: Commit**

```bash
cd /c/git/download_bicocca && git add app/gui/main_window.py
git commit -m "feat: adicionar checkbox para preferência de bitrate ~2 Mbps na GUI"
```

---

## Chunk 3: Verificação Final

- [ ] **Step 1: Rodar suite completa**

```bash
cd /c/git/download_bicocca && .venv/Scripts/python -m pytest -v
```
Esperado: **38 passed** (35 existentes + 3 novos), zero falhas.
