# Technology Stack

## Platform

Home Assistant custom component (Python-based integration)

## Core Dependencies

- Python 3.x
- Home Assistant >= 2026.2.0
- denonavr 1.2.0 (Denon AVR control library)

## Development Tools

- ruff 0.15.5 (linting and formatting)
- colorlog 6.10.1 (logging)
- pip >= 21.3.1

## Integration Type

- Device integration with local push (local network communication)
- Config flow enabled for UI-based setup
- SSDP discovery support for automatic device detection
- Telnet support for real-time updates
- Platforms: Media Player, Number

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
- Current version: 0.1.0

## Development Workflow

### Feature Development
- Create a new feature branch for each feature: `git checkout -b feature/feature-name`
- Make changes and test locally using `scripts/develop`
- Run linting before committing: `scripts/lint`
- Commit changes with descriptive messages
- Push branch and create pull request for review
- Merge to main after review and testing
