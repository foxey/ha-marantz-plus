# Project Structure

## Root Layout

```
.
├── custom_components/marantzplus/  # Main integration code
├── config/                          # Home Assistant test configuration
├── scripts/                         # Development and maintenance scripts
├── .devcontainer/                  # Dev container setup files
├── .devcontainer.json              # VS Code dev container config
├── .kiro/                          # Kiro AI assistant configuration
├── hacs.json                       # HACS distribution metadata
└── requirements.txt                # Python dependencies
```

## Integration Structure

The custom component follows Home Assistant's standard integration pattern:

```
custom_components/marantzplus/
├── __init__.py           # Entry point: async_setup_entry, async_unload_entry
├── config_flow.py        # UI configuration flow with options
├── const.py              # Constants and configuration keys
├── receiver.py           # Receiver connection and initialization logic
├── media_player.py       # Media player platform implementation
├── manifest.json         # Integration metadata
├── strings.json          # UI strings (English)
├── icons.json            # Icon definitions
├── services.yaml         # Service definitions
└── brand/                # Brand assets (Marantz logo)
```

## Key Patterns

### Entry Points
- `async_setup_entry()` in `__init__.py` handles integration setup
- `async_unload_entry()` handles cleanup including Telnet disconnection
- Platform forwarding to `PLATFORMS` (currently just media_player)
- Uses `ConnectDenonAVR` class from `receiver.py` for device connection

### Configuration
- All config constants defined in `const.py` with `CONF_*` prefix
- Default values use `DEFAULT_*` prefix
- Domain constant: `DOMAIN = "denonavr"` (note: domain differs from package name)
- Supports multiple zones (Main, Zone2, Zone3)
- Optional Telnet support for real-time updates
- Audyssey settings support

### Naming Conventions
- Integration domain: `denonavr`
- Display name: `Denon AVR Network Receivers`
- Python package: `custom_components.marantzplus`
- HACS package name: `DNS IP Plus` (legacy naming in hacs.json)

### Device Discovery
- SSDP discovery for automatic device detection
- Supports Denon, Denon Professional, and Marantz manufacturers
- Multiple device types: MediaRenderer, MediaServer, AiosDevice

## Development Environment

The `config/` directory contains a working Home Assistant instance for testing:
- Configuration files in `config/`
- Storage in `config/.storage/`
- Logs in `config/home-assistant.log*`
- Database in `config/home-assistant_v2.db`

The dev environment uses PYTHONPATH manipulation to load the custom component without symlinks.
