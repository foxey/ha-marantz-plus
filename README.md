# Marantz+ for Home Assistant

A custom Home Assistant integration for controlling Denon and Marantz AVR (Audio/Video Receiver) network receivers. This integration extends the core `denonavr` integration with additional features and improvements.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/foxey/ha-marantz-plus.svg)](https://github.com/foxey/ha-marantz-plus/releases)

## Features

- **Local Network Control**: Direct communication with your AVR over your local network
- **Multi-Zone Support**: Control Main Zone, Zone 2, and Zone 3
- **Automatic Discovery**: SSDP-based auto-discovery of compatible receivers
- **Real-Time Updates**: Optional Telnet connection for instant status updates
- **Audyssey Settings**: Configure and update Audyssey audio calibration
- **Full Media Player Integration**: Complete playback control, source selection, volume, and sound modes
- **Config Flow UI**: Easy setup and configuration through the Home Assistant UI

## Supported Devices

- Denon AVR network receivers
- Denon Professional AVR receivers  
- Marantz AVR network receivers

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/foxey/ha-marantz-plus`
6. Select category "Integration"
7. Click "Add"
8. Find "Marantz+" in the integration list and click "Download"
9. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/foxey/ha-marantz-plus/releases)
2. Extract the `marantzplus` folder from the zip file
3. Copy the `marantzplus` folder to your `custom_components` directory
4. Restart Home Assistant

## Configuration

### Adding the Integration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for **Marantz+**
4. Follow the setup wizard:
   - Leave the IP address blank for auto-discovery, or
   - Enter your receiver's IP address for manual setup

### Options

After adding the integration, you can configure additional options:

- **Show all sources**: Display all available input sources
- **Zone 2**: Enable Zone 2 control
- **Zone 3**: Enable Zone 3 control
- **Use Telnet connection**: Enable real-time updates via Telnet (recommended)
- **Update Audyssey settings**: Enable Audyssey configuration

## Services

The integration provides the following services:

### `marantzplus.get_command`

Send a generic HTTP GET command to the receiver.

```yaml
service: marantzplus.get_command
target:
  entity_id: media_player.marantz_avr
data:
  command: "/goform/formiPhoneAppDirect.xml?SYSTANDBY"
```

### `marantzplus.set_dynamic_eq`

Enable or disable DynamicEQ.

```yaml
service: marantzplus.set_dynamic_eq
target:
  entity_id: media_player.marantz_avr
data:
  dynamic_eq: true
```

### `marantzplus.update_audyssey`

Update Audyssey settings from the receiver.

```yaml
service: marantzplus.update_audyssey
target:
  entity_id: media_player.marantz_avr
```

## Development

### Prerequisites

- Python 3.x
- Home Assistant >= 2026.2.0
- Git

### Setup Development Environment

1. Clone the repository:
   ```bash
   git clone https://github.com/foxey/ha-marantz-plus.git
   cd ha-marantz-plus
   ```

2. Run the setup script:
   ```bash
   scripts/setup
   ```

3. Start the development server:
   ```bash
   scripts/develop
   ```

   This will start a local Home Assistant instance at `http://localhost:8123` with the integration loaded.

### Linting

Run the linter to check code quality:

```bash
scripts/lint
```

## Technical Details

- **Integration Type**: Device integration with local push
- **Communication**: HTTP API with optional Telnet for real-time updates
- **Discovery**: SSDP for automatic device detection
- **Library**: Uses the [denonavr](https://github.com/ol-iver/denonavr) Python library (v1.2.0)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Based on the core Home Assistant [denonavr](https://www.home-assistant.io/integrations/denonavr) integration
- Uses the [denonavr](https://github.com/ol-iver/denonavr) Python library by @ol-iver
- Marantz logo trademark of [Marantz](https://www.marantz.com/)

## Support

If you encounter any issues or have questions:

- Check the [Issues](https://github.com/foxey/ha-marantz-plus/issues) page
- Create a new issue with detailed information about your problem
- Include Home Assistant logs and your receiver model

---

**Note**: This is a custom integration and is not officially supported by Home Assistant or Marantz/Denon.
