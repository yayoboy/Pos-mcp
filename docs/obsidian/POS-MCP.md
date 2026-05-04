# POS-MCP

#project #mcp #python #hardware

MCP server per stampante termica 80mm Bisofice Ethernet. Qualsiasi client LLM compatibile MCP puo stampare testo, immagini, diagrammi e barcode su carta fisica.

## Architettura

```
LLM Client --> MCP stdio --> server.py --> renderer --> printer --> TCP:9100
                                                          |
                                                    preview=true
                                                          |
                                                    immagine inline
```

## Stack

| Componente | Tecnologia |
|------------|-----------|
| Server MCP | FastMCP Python SDK (stdio) |
| Comunicazione | python-escpos via TCP:9100 |
| Rendering testo | Pillow (ImageDraw, ImageFont) |
| Diagrammi | Graphviz (DOT) + matplotlib |
| Conversione | 1-bit Floyd-Steinberg dithering |

## Tool esposti

| Tool | Funzione |
|------|----------|
| `print_text` | Testo formattato (bold, size, align) |
| `print_image` | Immagine base64 con auto-resize e dithering |
| `print_diagram` | Codice Graphviz DOT o matplotlib Python |
| `print_barcode` | QR code e barcode lineari (EAN13, Code128, etc.) |

Tutti i tool supportano `preview=true` per anteprima senza stampare.

## Configurazione

File `pos-mcp.json` nella root del progetto:

```json
{
  "printer": {
    "ip": "192.168.1.100",
    "port": 9100,
    "width_px": 384,
    "timeout": 5
  }
}
```

## Setup client

Claude Desktop / Claude Code / qualsiasi client MCP:

```json
{
  "mcpServers": {
    "pos-printer": {
      "command": "/path/to/pos-mcp/.venv/bin/python",
      "args": ["-m", "pos_mcp.server"],
      "cwd": "/path/to/pos-mcp"
    }
  }
}
```

## Vincoli hardware

- 384px larghezza (80mm @ 203 DPI)
- Monocromatica 1-bit
- Dithering Floyd-Steinberg per immagini con gradazioni

## Struttura progetto

```
src/pos_mcp/
  server.py      -- FastMCP, 4 tool
  renderer.py    -- text/DOT/matplotlib/image -> PIL.Image 1-bit
  printer.py     -- ESC/POS TCP + preview base64
  config.py      -- JSON config, PrinterConfig dataclass
tests/           -- 22 test
```

## Sicurezza

Il tool `print_diagram` con engine matplotlib esegue codice Python in un namespace ristretto. Solo `matplotlib`, `numpy` e `math` sono consentiti come import.

## Links

- Repo: [[GitHub/Pos-mcp]]
- Spec: `docs/superpowers/specs/2026-05-04-pos-mcp-design.md`
- Piano: `docs/superpowers/plans/2026-05-04-pos-mcp.md`

---
*Creato: 2026-05-04*
