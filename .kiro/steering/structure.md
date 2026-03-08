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
├── number.py             # Number platform for channel volume control
├── channel_volume.py     # Channel volume helper class
├── manifest.json         # Integration metadata
├── strings.json          # UI strings (English)
├── icons.json            # Icon definitions
├── services.yaml         # Service definitions
├── brand/                # Brand assets (Marantz logo)
└── translations/         # Localized strings (de, en, es, fr, nl)
```

## Key Patterns

### Entry Points
- `async_setup_entry()` in `__init__.py` handles integration setup
- `async_unload_entry()` handles cleanup including Telnet disconnection
- Platform forwarding to `PLATFORMS` (media_player, number)
- Uses `ConnectDenonAVR` class from `receiver.py` for device connection

### Configuration
- All config constants defined in `const.py` with `CONF_*` prefix
- Default values use `DEFAULT_*` prefix
- Domain constant: `DOMAIN = "marantzplus"`
- Supports multiple zones (Main, Zone2, Zone3)
- Optional Telnet support for real-time updates
- Audyssey settings support
- Channel volume control with protocol-to-dB conversion

### Naming Conventions
- Integration domain: `marantzplus`
- Display name: `Marantz+`
- Python package: `custom_components.marantzplus`
- HACS package name: `Marantz+`
- Repository: `ha-marantz-plus`

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

## Git Workflow

### Feature Branches
- Always create a new feature branch for each feature or bug fix
- Branch naming: `feature/feature-name` or `fix/bug-description`
- Work on the feature branch, commit regularly
- Test thoroughly using the local dev environment
- Create pull request when ready for review
- Merge to main after approval
