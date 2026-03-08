# Product Overview

Marantz+ is a Home Assistant custom component for controlling Denon and Marantz AVR (Audio/Video Receiver) network receivers. It provides local network integration with these devices, enabling control and monitoring through Home Assistant.

The integration uses the `denonavr` Python library to communicate with receivers over the local network, supporting both HTTP API and optional Telnet connections for real-time status updates.

## Key Features

- Local network control of Denon and Marantz AVR receivers
- Multi-zone support (Main Zone, Zone 2, Zone 3)
- Automatic device discovery via SSDP
- Optional Telnet connection for real-time push updates
- Audyssey audio calibration settings support
- Config flow UI for easy setup and options management
- Media player platform with full playback control
- Number entities for individual channel volume control (FL, FR, C, SL, SR, SW)
- Source selection and input management
- Volume and sound mode control
- Device integration type (local_push)
- HACS compatible distribution
- Multi-language support (English, German, Spanish, French, Dutch)

## Supported Devices

- Denon AVR network receivers
- Denon Professional AVR receivers
- Marantz AVR network receivers

## Communication Methods

- HTTP API for commands and polling
- SSDP for automatic discovery
- Optional Telnet for real-time status updates
