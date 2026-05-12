# POS-MCP

MCP server for 80mm thermal printers over Ethernet. Exposes four tools that any MCP-compatible LLM client can call to print formatted text, images, diagrams, and barcodes to physical paper.

Built for the Bisofice 80mm, but works with any ESC/POS printer reachable via TCP on port 9100.

## How it works

```
LLM Client  -->  MCP (stdio)  -->  server.py  -->  renderer  -->  printer  -->  TCP:9100
                                                                      |
                                                              preview=true
                                                                      |
                                                              returns image
                                                              to LLM client
```

The server accepts tool calls over stdio, renders the content to a 384px-wide 1-bit bitmap (matching 80mm paper at 203 DPI), and either sends it to the printer or returns a preview image inline.

## Tools

### print_markdown

Render and print a Markdown document. Supports headings (h1-h6), paragraphs,
ordered/unordered lists, GitHub task lists (`- [x] / - [ ]`), tables,
fenced code blocks, blockquotes, and thematic breaks. In `mode="confirm"` the
browser exposes a textarea so you can edit the Markdown and re-render before
committing to paper.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | str | required | Markdown source |
| `cut` | bool | `true` | Cut paper after printing |
| `mode` | str | `"print"` | `"print"`, `"preview"`, or `"confirm"` |

### print_blocks

Print a composed document from typed block specs, as a single atomic ESC/POS
job (one cut at the end). Each block is a dict with a `type` field. Supported
types: `title`, `paragraph`, `separator`, `spacer`, `bullet`, `checklist`,
`keyvalue`, `table`, `code`, `box`.

Example:

```json
[
  {"type": "title", "text": "Component"},
  {"type": "keyvalue", "pairs": [
    ["Part", "NE555"],
    ["Pkg",  "DIP-8"]
  ]},
  {"type": "table",
   "headers": ["Pin", "Function"],
   "rows": [["1", "GND"], ["2", "TRIG"], ["3", "OUT"]]}
]
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `blocks` | list[dict] | required | Ordered list of block specs |
| `cut` | bool | `true` | Cut paper after printing |
| `mode` | str | `"print"` | `"print"`, `"preview"`, or `"confirm"` |

### print_text

Print formatted text with ESC/POS styling. Auto-switches to bitmap rendering when content contains non-ASCII characters (accents, CJK, emoji, …) so the preview matches the print exactly.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | str | required | Text to print (supports `\n`) |
| `bold` | bool | `false` | Bold font |
| `size` | str | `"normal"` | `"small"`, `"normal"`, or `"large"` |
| `align` | str | `"left"` | `"left"`, `"center"`, or `"right"` |
| `cut` | bool | `true` | Cut paper after printing |
| `render` | str | `"auto"` | `"auto"`, `"native"`, or `"bitmap"` |
| `mode` | str | `"print"` | `"print"`, `"preview"`, or `"confirm"` |

### print_image

Print a base64-encoded image. Auto-resizes to paper width and converts to 1-bit monochrome.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image_base64` | str | required | PNG or JPG image as base64 string |
| `dither` | bool | `true` | Floyd-Steinberg dithering for 1-bit conversion |
| `cut` | bool | `true` | Cut paper after printing |
| `mode` | str | `"print"` | `"print"`, `"preview"`, or `"confirm"` |

### print_diagram

Render and print diagrams from Graphviz DOT code or matplotlib Python code.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `code` | str | required | DOT syntax (graphviz) or Python code (matplotlib) |
| `engine` | str | `"graphviz"` | `"graphviz"` or `"matplotlib"` |
| `cut` | bool | `true` | Cut paper after printing |
| `mode` | str | `"print"` | `"print"`, `"preview"`, or `"confirm"` |

The matplotlib engine runs code in a restricted sandbox. Only `matplotlib`, `numpy`, and `math` imports are allowed.

### print_barcode

Print QR codes or linear barcodes.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `data` | str | required | Data to encode |
| `type` | str | `"qr"` | `"qr"`, `"ean13"`, `"ean8"`, `"code128"`, `"code39"` |
| `label` | str | `""` | Text label below the barcode |
| `cut` | bool | `true` | Cut paper after printing |
| `mode` | str | `"print"` | `"print"`, `"preview"`, or `"confirm"` |

## Preview and confirm modes

Every tool accepts a `mode` parameter:

| Mode | Behavior |
|------|----------|
| `"print"` (default) | Render and send to the printer. |
| `"preview"` | Render and return the bitmap as an MCP image content block. Nothing is sent to the printer. |
| `"confirm"` | Render, open a browser preview, and block until the user clicks **Print** or **Cancel**. Basic edits (text content, alignment, size, bold, dithering) can be applied in the browser before printing. |

The legacy `preview=True` flag is still accepted for backwards compatibility.

### Browser preview sidecar

When the server starts, an HTTP server runs alongside on `http://127.0.0.1:7878` (configurable). It exposes:

- The preview UI at `/` — a single-page editor showing the exact bitmap that will be printed, with a ruler in mm and inline controls.
- WebSocket at `/ws` — pushes new previews to the browser as Claude calls tools.
- JSON API at `/api/jobs/{id}/{confirm,cancel,update}`.

The browser auto-opens at the first job (toggle with `preview.auto_open: false`).

### Text rendering: native vs bitmap

Text content is rendered by one of two paths depending on its characters:

- **Native ESC/POS** (fast, low memory) — used when the entire string is pure ASCII (`< 0x80`).
- **Bitmap** (full Unicode, emoji, mixed scripts) — used when any non-ASCII character is present, or when `render="bitmap"` is forced.

You can override with the `render` parameter (`"auto"` | `"native"` | `"bitmap"`). When the bitmap path is used the browser preview is pixel-perfect; for the native path the preview is an approximation with matching layout and metrics.

### Font fallback

The renderer discovers system fonts at startup (via `fc-list` on Linux, plus common font directories on macOS/Windows). For each character it picks the first font in the chain that has the glyph, allowing Latin + CJK + Arabic + emoji to coexist on the same line. Add your own family substrings to `fonts.fallback_chain` to override the order.

## Installation

```bash
git clone https://github.com/yourusername/pos-mcp.git
cd pos-mcp

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

System dependency (required for diagram rendering):

```bash
# macOS
brew install graphviz

# Debian / Ubuntu
sudo apt install graphviz
```

## Configuration

Copy and edit `pos-mcp.json` in the project root:

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
  },
  "preview": {
    "enabled": true,
    "host": "127.0.0.1",
    "port": 7878,
    "auto_open": true,
    "confirm_timeout": 120
  },
  "fonts": {
    "fallback_chain": []
  }
}
```

| Field | Description |
|-------|-------------|
| `printer.ip` | Your printer's IP address |
| `printer.port` | TCP port (9100 is standard for ESC/POS raw) |
| `printer.width_px` | Print width in dots (384 = 80mm at 203 DPI) |
| `printer.timeout` | Connection timeout in seconds |
| `defaults.cut_after_print` | Default cut behavior |
| `defaults.dither` | Default dithering for images |
| `preview.enabled` | Start the browser preview sidecar |
| `preview.port` | HTTP port for the preview UI |
| `preview.auto_open` | Auto-launch the browser on the first job |
| `preview.confirm_timeout` | Seconds the MCP tool waits for user approval |
| `fonts.fallback_chain` | Custom font-family priority list (substrings); auto-discovered Noto/DejaVu are appended |

The config file path can also be overridden via the `POS_MCP_CONFIG` environment variable.

## Client setup

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "pos-printer": {
      "command": "/absolute/path/to/pos-mcp/.venv/bin/python",
      "args": ["-m", "pos_mcp.server"],
      "cwd": "/absolute/path/to/pos-mcp"
    }
  }
}
```

### Claude Code

Add to project `.claude/settings.json` or global `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "pos-printer": {
      "command": "/absolute/path/to/pos-mcp/.venv/bin/python",
      "args": ["-m", "pos_mcp.server"],
      "cwd": "/absolute/path/to/pos-mcp"
    }
  }
}
```

### Any MCP client

The server uses stdio transport. Point your client at:

```
command: /path/to/pos-mcp/.venv/bin/python
args: -m pos_mcp.server
cwd: /path/to/pos-mcp
```

## Project structure

```
pos-mcp/
├── src/pos_mcp/
│   ├── server.py          FastMCP server, 4 tool definitions, sidecar boot
│   ├── renderer.py        Text/DOT/matplotlib/image -> 1-bit PIL.Image
│   ├── fonts.py           Font discovery + per-character Unicode fallback
│   ├── printer.py         ESC/POS via TCP, preview as base64 PNG
│   ├── jobstore.py        In-memory job queue for the confirm/approval flow
│   ├── preview_server.py  FastAPI + WebSocket sidecar
│   ├── preview.html       Browser preview UI (single file, vanilla JS)
│   └── config.py          JSON config loader, dataclasses
├── tests/                 38 tests (config, fonts, renderer, printer,
│                          jobstore, preview server, server)
├── pos-mcp.json           Printer + preview + fonts configuration
└── pyproject.toml         Dependencies and entry point
```

## Running tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

## Constraints

- 384 pixels wide (80mm paper at 203 DPI)
- 1-bit monochrome (black and white only)
- Floyd-Steinberg dithering applied by default for grayscale/color sources
- No native grayscale support on thermal printers

## Troubleshooting

**Printer not reachable**: Verify the IP in `pos-mcp.json`. Test connectivity with `ping <ip>`. Ensure the printer is on the same network and port 9100 is not firewalled.

**Graphviz errors**: Make sure the system `dot` binary is installed (`which dot`). The Python `graphviz` package is a binding, not the engine itself.

**Matplotlib sandbox errors**: Only `matplotlib`, `numpy`, and `math` imports are allowed in diagram code. Other imports will be rejected.

## License

MIT
