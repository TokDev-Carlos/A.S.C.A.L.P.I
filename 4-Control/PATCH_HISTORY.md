# ASCALPI Control Center — Histórico acumulativo

Timezone oficial deste histórico: `America/Sao_Paulo`.

## Fundação visual
- Interface principal migrada para HTML/CSS/JavaScript.
- Backend local PowerShell 5.1 em `127.0.0.1`.
- `Documentation/` preservado.
- Painel WinForms anterior preservado em `Legacy/`.

## Janela
- Experimento 800x450 rejeitado por compressão do layout.
- Modo final desta base: aplicativo maximizado, moldura/barra de título nativas e redimensionável.
- Navegador comum não é usado como fallback.

## Ciclo de vida
- Fechar a janela solicita `/api/shutdown`.
- Backend possui fail-safe para não permanecer órfão.

## R2 rejeitada
- A revisão R2 foi descartada e não é base desta entrega.

## 30/08/2026 21:13:27 — CLEAN R3
Base: última revisão maximizada funcional.

### UI / JavaScript
- `UI/app.js` reconstruído integralmente.
- Ripple por JavaScript.
- Estado pressionado por JavaScript.
- Spinner e estado `Executando...`.
- Feedback visual de sucesso/erro.
- Transição JS de páginas.
- Nenhuma alteração estrutural no launcher estável.

### 1-Dev Linux
- Abertura refeita usando o mesmo mecanismo do `Legacy/CJL-Control.ps1`:
  `wsl.exe -d Ubuntu-24.04 -- bash "/mnt/c/.Dev CJL/1-Dev/INICIAR-CJL-LINUX.sh"`.
- `ProcessStartInfo` oculto reproduzido sem pré-validações extras.

### Explorer
- Todas as ações de pasta passam por `Open-FolderFocused`.
- Se a pasta já está aberta, sua janela existente é restaurada e trazida para frente.
- Se não está aberta, Explorer é iniciado e o painel procura a nova janela para trazê-la ao foco.
- Resultado operacional: `FOCUSED_EXISTING`, `OPENED_AND_FOCUSED` ou `OPENED`.

### Restrições preservadas
- Compiler: `PAUSED`.
- GitHub write: `NO`.
- Production write: `NO`.

## 30/08/2026 21:22 — PROFESSIONAL R4

### Posicionamento e linguagem
- Produto apresentado como `ASCALPI Control Center`.
- Removidos rótulos infantis, caracteres usados como ícones e excesso de caixa alta.
- Linguagem unificada em português com foco em governança operacional.
- Removidas a identificação fixa de usuário e a alegação genérica de conexão segura.

### Estrutura e experiência
- Navegação separada entre Operação e Governança.
- Dashboard reorganizado em panorama, postura operacional e acessos rápidos.
- Registro técnico tornou-se secundário e recolhível.
- Ações indisponíveis de Git passam a ser desabilitadas em vez de falharem ao clique.
- Atualizações automáticas não repetem a animação de entrada da página.
- Requisições da interface agora possuem timeout operacional.

### Diagnóstico
- Postura global deixa de declarar o ambiente pronto quando há componentes ausentes ou incompletos.
- Corrigida a leitura da saída UTF-16 de `wsl.exe`, que podia produzir falso negativo para a distribuição configurada.
- O inicializador Linux passou a derivar distribuição e caminho diretamente do arquivo de configuração.

### Restrições preservadas
- Compiler: `PAUSED`.
- GitHub write: `NO`.
- Production write: `NO`.
