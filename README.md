# Gemini Live MCP

Gemini Live MCP is an MCP client that utilizes the Gemini Live API to enable voice-based interaction with Gemini. Additionally, it now supports adding MCP servers for extended functionality.

## Features
- Voice-based interaction with Gemini via the Gemini Live API
- Support for multiple MCP servers

## Installation

1. **Clone the repository**:
   ```sh
   git clone https://github.com/SmartManoj/Gemini-Live-MCP.git
   cd Gemini-Live-MCP
   ```

2. **Set up environment variables**:
   Create a `.env` file in the project root and add your Google API key:
   ```
   GOOGLE_API_KEY=your_google_api_key_here
   ```
## Usage

Run the application using the following command:
```sh
uv run main.py --mode=none
```

### Command Line Options

- `--mode`: Interaction mode (default: screen)
  - `none`: Runs without any visual input
  - `screen`: Uses the screen for visual input
  - `camera`: Uses the camera for visual input

## Configuration

### MCP Server Setup

The application can integrate with MCP servers to provide additional tools and capabilities:

1. **FastMCP Server**: The application connects to a FastMCP server running on `http://localhost:8000/mcp/`
2. **Tool Integration**: MCP servers can provide tools that are automatically available during conversations
3. **Dynamic Tool Loading**: Tools are loaded dynamically when connecting to MCP servers

### Audio Configuration

The application uses the following audio settings:
- **Input**: 16-bit PCM, 16kHz sample rate, mono channel
- **Output**: 24kHz sample rate for playback
- **Chunk Size**: 1024 samples for processing

## Development

### Project Structure

```
Gemini-Live-MCP/
├── main.py              # Main application entry point
├── mcp_handler.py       # MCP server integration
├── mcp_config.json      # MCP server configuration
├── pyproject.toml       # Project dependencies
├── .env                 # Environment variables (create this)
└── system_instruction.txt # Custom system instructions (optional)
```

### Dependencies

Key dependencies include:
- `google-genai`: Gemini API client
- `fastmcp`: MCP client implementation
- `pyaudio`: Audio processing
- `opencv-python`: Camera and screen capture
- `mss`: Screen capture functionality

## Troubleshooting

### Common Issues

1. **Audio not working**: Ensure your microphone and speakers are properly configured
2. **API key issues**: Verify your Google API key has Gemini Live API access
3. **MCP server connection**: Check that your FastMCP server is running on `localhost:8000`

### Getting Help

- Check the [GitHub Issues](https://github.com/SmartManoj/Gemini-Live-MCP/issues) for known problems
- Ensure all dependencies are properly installed with `uv sync`
- Verify your Google API key permissions

## License

This project is licensed under the MIT License.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests to improve the project.

## Contact

For questions or support, reach out via [GitHub Issues](https://github.com/SmartManoj/Gemini-Live-MCP/issues).

