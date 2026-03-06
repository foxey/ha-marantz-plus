# Technology Stack

## Platform

Home Assistant custom component (Python-based integration)

## Core Dependencies

- Python 3.x
- Home Assistant >= 2026.2.0
- denonavr 1.2.0 (Denon AVR control library)

## Development Tools

- ruff 0.14.14 (linting and formatting)
- colorlog 6.10.1 (logging)
- pip >= 21.3.1

## Integration Type

- Device integration with local push (local network communication)
- Config flow enabled for UI-based setup
- SSDP discovery support for automatic device detection
- Telnet support for real-time updates
- Platform: Media Player

## Common Commands

### Development
```bash
scripts/develop
```
Starts a local Home Assistant instance with the custom component loaded. Uses the `config/` directory for HA configuration and sets PYTHONPATH to include `custom_components/`.

### Linting
```bash
scripts/lint
```
Runs ruff formatter and linter with auto-fix enabled.

### Setup
```bash
scripts/setup
```
Initial setup script (if needed for environment preparation).

## Distribution

- HACS compatible (zip release)
- Minimum HACS version: 2.0.5
- Minimum Home Assistant version: 2026.2.0
