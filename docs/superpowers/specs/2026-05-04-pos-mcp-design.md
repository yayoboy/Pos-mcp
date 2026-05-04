# POS MCP Server — Design Spec

## Overview

MCP server Python per stampante termica Bisofice 80mm Ethernet. Output fisico generico dall'LLM: testo formattato, immagini, diagrammi (Graphviz/Matplotlib), QR code, barcode. Agnostico, compatibile con qualsiasi client LLM via stdio transport.

## Architecture

```
pos-mcp/
├── server.py          # FastMCP server, tool definitions
├── renderer.py        # Matplotlib/Graphviz/Pillow → PIL.Image 1-bit
├── printer.py         # python-escpos Network wrapper, preview logic
├── config.py          # Carica config da pos-mcp.json
├── pos-mcp.json       # Configurazione stampante
├── pyproject.toml     # Dipendenze, entry point
└── README.md
```

### Data Flow

```
LLM → MCP tool call → server.py → renderer.py (se necessario) → printer.py → TCP:9100 → stampante
                                                                ↘ preview=true → MCP Image content block
```

- `server.py`: FastMCP con `mcp.run(transport="stdio")`, definisce i 4 tool
- `renderer.py`: input (codice DOT, codice matplotlib, testo) → `PIL.Image` a 384px width, 1-bit
- `printer.py`: `PIL.Image` o testo → stampante via `escpos.printer.Network`, oppure ritorna Image MCP se preview
- `config.py`: legge `pos-mcp.json`, valida, espone come dataclass

## Tools

### `print_text`

Stampa testo formattato con opzioni ESC/POS.

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `content` | str | required | Testo da stampare (supporta `\n`) |
| `bold` | bool | false | Grassetto |
| `size` | str | "normal" | "normal", "large", "small" |
| `align` | str | "left" | "left", "center", "right" |
| `cut` | bool | true | Taglia carta dopo stampa |
| `preview` | bool | false | Ritorna immagine MCP invece di stampare |

Returns: `"OK"` o MCP Image content block se preview.

### `print_image`

Stampa un'immagine fornita in base64. Il server ridimensiona a 384px width e converte a 1-bit.

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `image_base64` | str | required | Immagine PNG/JPG codificata base64 |
| `dither` | bool | true | Floyd-Steinberg dithering per conversione 1-bit |
| `cut` | bool | true | Taglia carta dopo stampa |
| `preview` | bool | false | Ritorna immagine MCP invece di stampare |

### `print_diagram`

Renderizza ed stampa diagrammi da codice Graphviz DOT o Python matplotlib.

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `code` | str | required | Codice DOT (Graphviz) o Python (matplotlib) |
| `engine` | str | "graphviz" | "graphviz" o "matplotlib" |
| `cut` | bool | true | Taglia carta dopo stampa |
| `preview` | bool | false | Ritorna immagine MCP invece di stampare |

Per `matplotlib`: esecuzione in namespace limitato (matplotlib, numpy, math). Il codice deve produrre una figura — il server la cattura via `plt.savefig()`.

Per `graphviz`: il codice DOT viene renderizzato via `graphviz` Python bindings a PNG, poi convertito 1-bit.

### `print_barcode`

Stampa barcode lineari o QR code.

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `data` | str | required | Dati del barcode |
| `type` | str | "qr" | "qr", "ean13", "ean8", "code128", "code39" |
| `label` | str | "" | Testo sotto il barcode |
| `cut` | bool | true | Taglia carta dopo stampa |
| `preview` | bool | false | Ritorna immagine MCP invece di stampare |

## Configuration

### `pos-mcp.json`

```json
{
  "printer": {
    "ip": "192.168.1.100",
    "port": 9100,
    "width_px": 384,
    "timeout": 5
  },
  "defaults": {
    "cut_after_print": true,
    "dither": true
  }
}
```

## Dependencies

### Python packages

- `mcp[cli]` — FastMCP SDK + stdio transport
- `python-escpos` — comunicazione ESC/POS
- `Pillow` — manipolazione immagini, resize, dithering 1-bit
- `matplotlib` — rendering grafici
- `graphviz` — Python bindings per rendering DOT

### System

- `graphviz` — engine nativo (`brew install graphviz` su macOS, `apt install graphviz` su Linux)

## Constraints

- Larghezza carta: 80mm = 384 dots @ 203 DPI
- Monocromatica: 1-bit, bianco e nero
- Dithering Floyd-Steinberg per immagini con gradazioni
- Nessun grayscale nativo

## Error Handling

- **Stampante non raggiungibile**: messaggio con IP/porta tentati, timeout configurabile
- **Codice DOT/matplotlib invalido**: errore con dettaglio parser/traceback filtrato
- **Immagine base64 corrotta**: errore specifico con tipo rilevato
- **Nessun retry automatico**: l'LLM decide se riprovare

## Security

- `print_diagram` con `engine="matplotlib"` esegue codice Python in namespace limitato
- Namespace consentito: `matplotlib`, `matplotlib.pyplot`, `numpy`, `math`
- Import arbitrari bloccati
- Il server gira in locale, accesso controllato dall'utente

## Preview Mode

Ogni tool supporta `preview=true`. Invece di inviare alla stampante:
1. Genera l'output come `PIL.Image` (per testo: renderizza con font monospace su immagine bianca)
2. Ritorna come MCP Image content block (il client LLM mostra l'anteprima inline)
3. L'LLM può iterare prima di stampare fisicamente
