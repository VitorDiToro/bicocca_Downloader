# Limitar Bitrate de Vídeo (Max ~2 Mbps)

O objetivo é adicionar uma opção na interface para limitar o download de vídeos a aproximadamente 2 Mbps. Isso evitará que vídeos com qualidades desnecessariamente altas (como 5.5 Mbps) gerem arquivos gigantescos, forçando o download de uma qualidade mais aceitável (como 1.7 Mbps).

## Proposed Changes

---

### Backend (Serviço de Download)
#### [MODIFY] [service.py](file:///c:/git/download_bicocca_bitrate_limit/app/service.py)
- Alterar a assinatura de `VideoDownloader.download_items` para aceitar um novo argumento: `max_bitrate_kbps: Optional[int] = None`.
- Modificar o fluxo interno (`_process_item` e `_build_ydl_opts`) para espalhar essa variável.
- Em `_build_ydl_opts`, se `max_bitrate_kbps` não for `None`, adicionar a chave `'format_sort'` ao dicionário de opções do yt-dlp: `['vbr:' + str(max_bitrate_kbps), 'tbr:' + str(max_bitrate_kbps), 'res:1080']`. Essa configuração orienta o yt-dlp a priorizar formatos com bitrate de vídeo e bitrate total menores ou iguais ao limite estipulado, mas mantendo a preferência pela resolução original alta (ex: 1080p).

---

### Frontend (Interface Gráfica)
#### [MODIFY] [main_window.py](file:///c:/git/download_bicocca_bitrate_limit/app/gui/main_window.py)
- Na janela principal, dentro do quadro "Modo de Download", adicionar um checkbox com o texto "Limitar qualidade de vídeo (~2 Mbps)".
- Criar a variável `self.limit_bitrate = tk.BooleanVar(value=True)` (marcada por padrão).
- Na função `_start_download`, ao chamar `service.download_items()`, passar `max_bitrate_kbps=2000` se o checkbox estiver marcado, ou `None` caso contrário.

---

### Testes
#### [MODIFY] [test_service.py](file:///c:/git/download_bicocca_bitrate_limit/tests/test_service.py)
- Adicionar ou atualizar cenários de teste para mockar a chamada ao `YoutubeDL` e validar se o construtor é chamado com o dicionário de opções (`ydl_opts`) contendo o `'format_sort'` configurado corretamente quando passamos o limite de bitrate.

## Verification Plan

### Automated Tests
- Executar os testes automatizados da aplicação:
  ```bash
  cd c:\git\download_bicocca_bitrate_limit
  pytest tests/test_service.py
  ```
  Isso garantirá que as opções do yt-dlp (ydl_opts) estão sendo geradas e injetadas de acordo.

### Manual Verification
1. Rodar a aplicação gráfica: `python downloader.py` via terminal ou atalho.
2. Com o checkbox de limite ativado, colar a URL de um dos vídeos conhecidos que estava vindo com 5.5 Mbps.
3. Iniciar o download e verificar, na pasta de saída, se o bitrate do arquivo final gerado está em torno de 1-2 Mbps (e não o bitrate total máximo da fonte).
4. Opcionalmente desmarcar o checkbox e baixar novamente para verificar se a qualidade volta para os 5.5 Mbps.
