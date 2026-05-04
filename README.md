# POS-MCP: 80mm Thermal Printer Server

An MCP server for controlling 80mm thermal POS printers (Bisofice) via any MCP-compatible LLM client. Print formatted text, images, diagrams, QR codes, and barcodes directly from Claude Desktop, Claude Code, or any MCP-enabled application.

## Features

- **Text Printing**: Formatted output with bold, size, and alignment options
- **Image Printing**: Base64-encoded images with auto-resize and dithering
- **Diagrams**: Graphviz DOT or matplotlib Python code rendering
- **Barcodes**: QR codes and linear barcodes (Code128, EAN13, etc.)
- **Preview Mode**: Test output before printing to the physical device
- **Smart Defaults**: Automatic paper width handling (384px) and monochrome conversion

## Installation

### Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd pos-mcp

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e ".[dev]"
```

### System Dependencies

**macOS:**
```bash
brew install graphviz
```

**Linux:**
```bash
apt install graphviz
```

## Configuration

Edit `pos-mcp.json` with your printer settings:

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

### Configuration Options

| Key | Type | Description |
|-----|------|-------------|
| `printer.ip` | string | Printer IP address on your network |
| `printer.port` | int | Network port (typically 9100) |
| `printer.width_px` | int | Print width in pixels (usually 384) |
| `printer.timeout` | int | Connection timeout in seconds |
| `defaults.cut_after_print` | bool | Auto-cut paper after each print job |
| `defaults.dither` | bool | Enable dithering for images |

## MCP Client Setup

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

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

### Claude Code

Edit `.claude/settings.json` in your Claude Code workspace:

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

Replace `/path/to/pos-mcp` with the absolute path to your installation.

## Available Tools

### print_text
Print formatted text to the thermal printer.

**Parameters:**
- `text` (string): The text to print
- `bold` (bool, optional): Bold formatting
- `size` (string, optional): Text size (small, normal, large)
- `alignment` (string, optional): Text alignment (left, center, right)
- `preview` (bool, optional): Show preview without printing

### print_image
Print images from base64-encoded data.

**Parameters:**
- `image_base64` (string): Base64-encoded image data
- `dither` (bool, optional): Enable dithering for better quality
- `preview` (bool, optional): Show preview without printing

### print_diagram
Render and print diagrams from Graphviz DOT or matplotlib code.

**Parameters:**
- `diagram_type` (string): "graphviz" or "matplotlib"
- `content` (string): DOT syntax or Python matplotlib code
- `preview` (bool, optional): Show preview without printing

### print_barcode
Print QR codes and linear barcodes.

**Parameters:**
- `barcode_type` (string): "qr", "code128", "ean13", etc.
- `data` (string): Data to encode
- `preview` (bool, optional): Show preview without printing

## Usage Example

Once configured, use the tools in any MCP-compatible client:

```
User: Print "Hello World" in bold, centered
Claude: [Uses print_text tool with bold=true, alignment="center"]

User: Create a QR code for https://example.com
Claude: [Uses print_barcode tool with barcode_type="qr"]

User: Print this chart as a barcode
Claude: [Uses print_diagram tool to render and print]
```

## Constraints and Specifications

- **Width**: Fixed at 384 pixels (standard 80mm thermal paper)
- **Color**: 1-bit monochrome (black and white only)
- **Paper**: 80mm thermal receipt paper
- **Dithering**: Applied by default for better image quality

## Preview Mode

All tools support `preview=true` parameter to display output as an image without physically printing. Use this to verify formatting before committing to paper.

## Troubleshooting

**Connection Issues:**
- Verify printer IP and port in `pos-mcp.json`
- Check network connectivity: `ping <printer-ip>`
- Ensure printer is powered on and connected to network

**Quality Issues:**
- Enable dithering in config for better image quality
- Check image resolution before printing
- Use appropriate font sizes for readability

## License

See LICENSE file for details.
