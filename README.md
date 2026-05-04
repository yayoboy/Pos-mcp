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

### print_text

Print formatted text with ESC/POS styling.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | str | required | Text to print (supports `\n`) |
| `bold` | bool | `false` | Bold font |
| `size` | str | `"normal"` | `"small"`, `"normal"`, or `"large"` |
| `align` | str | `"left"` | `"left"`, `"center"`, or `"right"` |
| `cut` | bool | `true` | Cut paper after printing |
| `preview` | bool | `false` | Return preview image instead of printing |

### print_image

Print a base64-encoded image. Auto-resizes to paper width and converts to 1-bit monochrome.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image_base64` | str | required | PNG or JPG image as base64 string |
| `dither` | bool | `true` | Floyd-Steinberg dithering for 1-bit conversion |
| `cut` | bool | `true` | Cut paper after printing |
| `preview` | bool | `false` | Return preview image instead of printing |

### print_diagram

Render and print diagrams from Graphviz DOT code or matplotlib Python code.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `code` | str | required | DOT syntax (graphviz) or Python code (matplotlib) |
| `engine` | str | `"graphviz"` | `"graphviz"` or `"matplotlib"` |
| `cut` | bool | `true` | Cut paper after printing |
| `preview` | bool | `false` | Return preview image instead of printing |

The matplotlib engine runs code in a restricted sandbox. Only `matplotlib`, `numpy`, and `math` imports are allowed.

### print_barcode

Print QR codes or linear barcodes.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `data` | str | required | Data to encode |
| `type` | str | `"qr"` | `"qr"`, `"ean13"`, `"ean8"`, `"code128"`, `"code39"` |
| `label` | str | `""` | Text label below the barcode |
| `cut` | bool | `true` | Cut paper after printing |
| `preview` | bool | `false` | Return preview image instead of printing |

## Preview mode

Every tool supports `preview=true`. Instead of printing, the server renders the output and returns it as an MCP image content block. The LLM client shows the preview inline, letting you iterate before committing to paper.

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
│   ├── server.py      FastMCP server, 4 tool definitions
│   ├── renderer.py    Text/DOT/matplotlib/image -> 1-bit PIL.Image
│   ├── printer.py     ESC/POS via TCP, preview as base64 PNG
│   └── config.py      JSON config loader, PrinterConfig dataclass
├── tests/             22 tests (config, renderer, printer, server)
├── pos-mcp.json       Printer configuration
└── pyproject.toml     Dependencies and entry point
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
