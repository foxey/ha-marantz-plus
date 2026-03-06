"""Denon/Marantz AVR Channel Level Controller for AppDaemon.

Controls individual speaker channel levels on Denon/Marantz receivers via
their telnet interface, exposing them as input_number helpers in Home Assistant.

Features:
  - Two-way sync: HA slider changes are sent to the receiver, and receiver
    changes (via remote, app, etc.) update the HA sliders in real time.
  - Single-app architecture: no cross-app communication needed.
  - Future-proof: uses plain sockets instead of the deprecated telnetlib.
  - Clean shutdown: persistent listener connection is properly closed on
    app termination or receiver power-off.
  - Feedback-loop prevention: programmatic entity updates are tracked with
    a counter so they don't trigger a command back to the receiver.

Prerequisites:
  The following input_number helpers must be created in HA before use
  (Settings > Devices & Services > Helpers > Add Helper > Number).

  For each channel listed in the `channels` config arg, create an
  input_number with:
    - Entity ID:  input_number.<media_player_id>_<channel_id>
    - Min:        -12
    - Max:         12
    - Step:        0.5
    - Unit:        dB
    - Mode:        Slider

  Example for media_player.marantz_nr1711:
    input_number.marantz_nr1711_front_left
    input_number.marantz_nr1711_front_right
    input_number.marantz_nr1711_center
    input_number.marantz_nr1711_surround_left
    input_number.marantz_nr1711_surround_right
    input_number.marantz_nr1711_subwoofer

YAML configuration (apps.yaml):
  denon_avr_control:
    module: denon_avr_control
    class: DenonAVRControl
    media_player: media_player.marantz_nr1711
    host: 192.168.1.100
    # Optional: override the default channel list.
    # Each key is the full Denon command (e.g. CVFL, CVSW) so you can
    # also add non-CV commands in the future.
    # `id` becomes the input_number suffix and `offset` is the protocol
    # offset (almost always 50 for CV commands).
    # channels:
    #   CVFL:  { id: front_left,      offset: 50 }
    #   CVFR:  { id: front_right,     offset: 50 }
    #   CVC:   { id: center,          offset: 50 }
    #   CVSL:  { id: surround_left,   offset: 50 }
    #   CVSR:  { id: surround_right,  offset: 50 }
    #   CVSW:  { id: subwoofer,       offset: 50 }
    # Optional: telnet port (default 23) and command timeout in seconds.
    # port: 23
    # command_timeout: 1
    # Optional: delay in seconds after power-on before querying channels.
    # power_on_delay: 3
"""

from __future__ import annotations

import socket
import threading
from typing import Any

import appdaemon.plugins.hass.hassapi as hass

# ---------------------------------------------------------------------------
# Default channel mapping: Denon CV command suffix → helper entity suffix
# and the numeric offset the receiver uses (0 dB = offset on the wire).
# ---------------------------------------------------------------------------
DEFAULT_CHANNELS: dict[str, dict[str, Any]] = {
    "CVFL": {"id": "front_left",      "offset": 50},
    "CVFR": {"id": "front_right",     "offset": 50},
    "CVC":  {"id": "center",          "offset": 50},
    "CVSL": {"id": "surround_left",   "offset": 50},
    "CVSR": {"id": "surround_right",  "offset": 50},
    "CVSW": {"id": "subwoofer",       "offset": 50},
}

TELNET_PORT = 23
COMMAND_TIMEOUT = 1        # seconds
POWER_ON_DELAY = 3         # seconds
RECONNECT_DELAY = 30       # seconds before retrying the persistent listener
LISTENER_RECV_SIZE = 4096  # bytes per recv() call


class DenonAVRControl(hass.Hass):
    """Single AppDaemon app that manages Denon/Marantz channel levels."""

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def initialize(self) -> None:
        # ---- Required args ------------------------------------------------
        self.media_player: str = self.args["media_player"]
        self.host: str = self.args["host"]
        self.port: int = int(self.args.get("port", TELNET_PORT))
        self.command_timeout: float = float(
            self.args.get("command_timeout", COMMAND_TIMEOUT)
        )
        self.power_on_delay: int = int(
            self.args.get("power_on_delay", POWER_ON_DELAY)
        )

        # ---- Validate media_player entity ---------------------------------
        if not self.entity_exists(self.media_player):
            self.log(
                f"Entity {self.media_player} does not exist. "
                "Check your media_player arg.",
                level="ERROR",
            )
            return

        self.media_player_id: str = self.media_player.split(".", 1)[1]

        # ---- Build channel map from config or defaults --------------------
        raw_channels = self.args.get("channels", DEFAULT_CHANNELS)
        self._channels: dict[str, dict[str, Any]] = {}  # keyed by CV prefix
        self._entity_to_channel: dict[str, dict[str, Any]] = {}

        missing_entities: list[str] = []
        for command, cfg in raw_channels.items():
            entity_id = f"input_number.{self.media_player_id}_{cfg['id']}"
            channel = {
                "command": command,
                "entity_id": entity_id,
                "offset": int(cfg.get("offset", 50)),
                "id": cfg["id"],
            }
            self._channels[command] = channel
            self._entity_to_channel[entity_id] = channel

            if not self.entity_exists(entity_id):
                missing_entities.append(entity_id)

        if missing_entities:
            self._log_missing_entities(missing_entities)

        # ---- State tracking -----------------------------------------------
        self._pending: dict[str, int] = {}  # in-flight programmatic updates
        self._listener_stop = threading.Event()  # signals listener to quit
        self._listener_thread: threading.Thread | None = None

        # ---- Register HA state listeners ----------------------------------
        # Media player power state → sync channels / start-stop listener.
        self.listen_state(
            self._on_media_player_state,
            self.media_player,
        )

        # Input_number sliders → send commands to the receiver.
        for entity_id in self._entity_to_channel:
            if self.entity_exists(entity_id):
                self.listen_state(self._on_slider_change, entity_id)

        # ---- If receiver is already on, do an initial sync ----------------
        if self.get_state(self.media_player) == "on":
            self.run_in(self._sync_channels_from_receiver, self.power_on_delay)
            self._start_listener()

        self.log(
            f"DenonAVRControl started for {self.media_player} "
            f"at {self.host}:{self.port}",
        )

    def terminate(self) -> None:
        """Clean up the persistent listener thread on app shutdown."""
        self._stop_listener()

    # -----------------------------------------------------------------------
    # Media player state handler
    # -----------------------------------------------------------------------

    def _on_media_player_state(
        self, entity: str, attribute: str, old: str, new: str, cb_args: dict,
    ) -> None:
        self.log(f"Media player state: {old} -> {new}")
        if new == "on":
            self.run_in(self._sync_channels_from_receiver, self.power_on_delay)
            self._start_listener()
        elif new in ("off", "unavailable"):
            self._stop_listener()

    # -----------------------------------------------------------------------
    # Slider → Receiver (user moves a slider in HA)
    # -----------------------------------------------------------------------

    def _on_slider_change(
        self, entity_id: str, attribute: str, old: str, new: str, cb_args: dict,
    ) -> None:
        # Ignore non-numeric states (e.g. "unavailable").
        try:
            value = float(new)
        except (ValueError, TypeError):
            return

        # If this change was caused by us (programmatic update), skip it.
        count = self._pending.get(entity_id, 0)
        if count > 0:
            self._pending[entity_id] = count - 1
            self.log(f"Skipping echo for {entity_id} (value={value})")
            return

        channel = self._entity_to_channel.get(entity_id)
        if channel is None:
            return

        cmd = (
            f"{channel['command']} "
            f"{self._format_value(value, channel['offset'])}"
        )
        self.log(f"User changed {entity_id} -> {value} dB, sending: {cmd}")
        self._send_command(cmd)

    # -----------------------------------------------------------------------
    # Receiver → Sliders (receiver reports new channel levels)
    # -----------------------------------------------------------------------

    def _sync_channels_from_receiver(self, kwargs: dict) -> None:
        """Query the receiver for current channel levels and update HA."""
        raw = self._send_command("CV?")
        if not raw:
            self.log("No response to CV? query", level="WARNING")
            return
        self._apply_receiver_response(raw)

    def _apply_receiver_response(self, raw: str) -> None:
        """Parse raw telnet output and push channel values into HA."""
        for command, parameter in self._parse_response(raw).items():
            channel = self._channels.get(command)
            if channel is None:
                continue

            entity_id = channel["entity_id"]
            if not self.entity_exists(entity_id):
                continue

            try:
                value = self._parse_value(parameter, channel["offset"])
            except ValueError:
                self.log(
                    f"Cannot parse '{parameter}' for {channel['id']}",
                    level="WARNING",
                )
                continue

            # Only push if the value actually changed; otherwise HA won't
            # fire state_changed and the pending counter would leak.
            try:
                current = float(self.get_state(entity_id))
            except (ValueError, TypeError):
                current = None
            if current == value:
                continue

            self._pending[entity_id] = self._pending.get(entity_id, 0) + 1
            self.call_service(
                "input_number/set_value",
                entity_id=entity_id,
                value=value,
            )
            self.log(f"Receiver → {entity_id} = {value} dB")

    # -----------------------------------------------------------------------
    # Persistent telnet listener (runs in a background thread)
    # -----------------------------------------------------------------------

    def _start_listener(self) -> None:
        """Start (or restart) the persistent telnet listener thread."""
        self._stop_listener()
        self._listener_stop.clear()
        self._listener_thread = threading.Thread(
            target=self._listener_loop,
            name=f"denon-listener-{self.media_player_id}",
            daemon=True,
        )
        self._listener_thread.start()

    def _stop_listener(self) -> None:
        """Signal the listener thread to stop and wait for it."""
        self._listener_stop.set()
        thread = self._listener_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=5)
        self._listener_thread = None

    def _listener_loop(self) -> None:
        """Maintain a persistent connection and process real-time events.

        Runs in a daemon thread. The thread exits when ``_listener_stop``
        is set or when the receiver sends a PWSTANDBY message.
        """
        while not self._listener_stop.is_set():
            sock: socket.socket | None = None
            try:
                sock = socket.create_connection(
                    (self.host, self.port), timeout=5,
                )
                self.log(f"Listener connected to {self.host}:{self.port}")
                # Ask for current channel levels on connect.
                sock.sendall(b"CV?\r")
                buf = ""
                while not self._listener_stop.is_set():
                    # Use a short timeout so we can check the stop flag.
                    sock.settimeout(2.0)
                    try:
                        data = sock.recv(LISTENER_RECV_SIZE)
                    except socket.timeout:
                        continue
                    if not data:
                        # Connection closed by the receiver.
                        self.log("Listener: connection closed by receiver")
                        break

                    buf += data.decode("ascii", errors="replace")

                    # Process complete lines (CR-delimited).
                    while "\r" in buf:
                        line, buf = buf.split("\r", 1)
                        line = line.strip()
                        if not line:
                            continue
                        if line == "PWSTANDBY":
                            self.log("Receiver entered standby")
                            return  # exit thread cleanly
                        self._handle_listener_line(line)

            except Exception as exc:
                if not self._listener_stop.is_set():
                    self.log(
                        f"Listener error: {exc}; "
                        f"retrying in {RECONNECT_DELAY}s",
                        level="WARNING",
                    )
            finally:
                if sock is not None:
                    try:
                        sock.close()
                    except OSError:
                        pass

            # Wait before reconnecting (but honour the stop flag).
            self._listener_stop.wait(RECONNECT_DELAY)

    def _handle_listener_line(self, line: str) -> None:
        """Process a single CR-delimited line from the receiver."""
        # Lines look like "CVFL 53" or "CVSW 485".
        parts = line.split(" ", 1)
        command = parts[0]
        parameter = parts[1] if len(parts) > 1 else ""

        channel = self._channels.get(command)
        if channel is None:
            return  # not a channel-level message

        entity_id = channel["entity_id"]
        if not self.entity_exists(entity_id):
            return

        try:
            value = self._parse_value(parameter, channel["offset"])
        except ValueError:
            return

        try:
            current = float(self.get_state(entity_id))
        except (ValueError, TypeError):
            current = None
        if current == value:
            return

        self._pending[entity_id] = self._pending.get(entity_id, 0) + 1
        self.call_service(
            "input_number/set_value",
            entity_id=entity_id,
            value=value,
        )
        self.log(f"Listener -> {entity_id} = {value} dB")

    # -----------------------------------------------------------------------
    # Telnet command helper (short-lived connection for one-off commands)
    # -----------------------------------------------------------------------

    def _send_command(self, command: str) -> str:
        """Send a command to the receiver and return the raw response.

        Opens a new TCP connection, sends the command, reads until the
        receiver stops sending (timeout), and returns all received data.
        """
        try:
            sock = socket.create_connection(
                (self.host, self.port), timeout=self.command_timeout,
            )
        except OSError as exc:
            self.log(
                f"Cannot connect to {self.host}:{self.port}: {exc}",
                level="ERROR",
            )
            return ""

        try:
            sock.sendall(f"{command}\r".encode("ascii"))
            sock.settimeout(self.command_timeout)
            response = b""
            while True:
                try:
                    chunk = sock.recv(LISTENER_RECV_SIZE)
                    if not chunk:
                        break
                    response += chunk
                except socket.timeout:
                    break
            return response.decode("ascii", errors="replace")
        except OSError as exc:
            self.log(f"Command '{command}' failed: {exc}", level="ERROR")
            return ""
        finally:
            sock.close()

    # -----------------------------------------------------------------------
    # Protocol helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _parse_response(raw: str) -> dict[str, str]:
        """Parse CR-delimited receiver output into a {command: parameter} dict.

        Example input:  "CVFL 53\\rCVFR 50\\rCVC 48\\r"
        Example output: {"CVFL": "53", "CVFR": "50", "CVC": "48"}
        """
        result: dict[str, str] = {}
        for element in raw.split("\r"):
            element = element.strip()
            if not element:
                continue
            parts = element.split(" ", 1)
            result[parts[0]] = parts[1] if len(parts) > 1 else ""
        return result

    @staticmethod
    def _parse_value(parameter: str, offset: int) -> float:
        """Convert a receiver parameter string to a dB float.

        The receiver encodes values as:
          - 2-digit string for whole dB:   "53" → 53 − 50 = +3.0 dB
          - 3-digit string for half dB:    "535" → 535/10 − 50 = +3.5 dB
        """
        parameter = parameter.strip()
        raw = int(parameter)
        if len(parameter) == 3:
            return raw / 10 - offset
        return float(raw - offset)

    @staticmethod
    def _format_value(value: float, offset: int) -> str:
        """Convert a dB float to a receiver parameter string.

        Whole dB values produce 2-digit strings:  +3.0 → "53"
        Half dB values produce 3-digit strings:   +3.5 → "535"
        """
        if value % 1 == 0:
            return str(int(value) + offset)
        return str(int((value + offset) * 10))

    # -----------------------------------------------------------------------
    # Setup helpers
    # -----------------------------------------------------------------------

    def _log_missing_entities(self, missing: list[str]) -> None:
        """Log clear instructions for creating missing helper entities."""
        self.log(
            "----------------------------------------------------------",
            level="WARNING",
        )
        self.log(
            "The following input_number helpers need to be created in "
            "Home Assistant (Settings > Devices & Services > Helpers > "
            "Add Helper > Number):",
            level="WARNING",
        )
        for entity_id in missing:
            self.log(f"  - {entity_id}", level="WARNING")
        self.log(
            "Settings for each: min=-12, max=12, step=0.5, "
            "unit_of_measurement=dB, mode=slider",
            level="WARNING",
        )
        self.log(
            "----------------------------------------------------------",
            level="WARNING",
        )
