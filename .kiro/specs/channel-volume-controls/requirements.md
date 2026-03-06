# Requirements Document

## Introduction

This feature adds individual speaker channel volume control to the marantzplus Home Assistant custom component. Users will be able to adjust volume levels for individual channels (front left, front right, center, surround left, surround right, subwoofer) through Home Assistant number entities. The implementation extends the existing denonavr library integration by adding channel volume management while maintaining all existing functionality and backward compatibility.

## Glossary

- **Channel_Volume_Manager**: Component responsible for managing channel volume entities and communication
- **Number_Entity**: Home Assistant entity type representing a numeric value with min/max bounds
- **CV_Command**: Denon/Marantz protocol command for channel volume control (CVFL, CVFR, CVC, CVSL, CVSR, CVSW)
- **CV_Event**: Telnet feedback message indicating channel volume change on the receiver
- **Persistent_Telnet_Connection**: Long-lived telnet connection managed by denonavr library for receiving real-time updates
- **Short_Lived_Telnet_Connection**: Temporary telnet connection created specifically to send CV commands
- **Feedback_Loop**: Condition where entity update triggers receiver change which triggers entity update repeatedly
- **Pending_Counter**: Mechanism to track expected CV events and prevent feedback loops
- **Receiver**: Denon or Marantz AVR network device
- **Zone**: Audio output zone on the receiver (Main, Zone2, Zone3)
- **Integration**: The marantzplus Home Assistant custom component
- **denonavr_Library**: Python library (v1.2.0) used for receiver communication

## Requirements

### Requirement 1: Channel Volume Number Entities

**User Story:** As a Home Assistant user, I want individual number entities for each speaker channel, so that I can adjust channel volumes through the Home Assistant UI.

#### Acceptance Criteria

1. THE Channel_Volume_Manager SHALL create Number_Entity instances for front left, front right, center, surround left, surround right, and subwoofer channels
2. THE Number_Entity SHALL have a minimum value of -12.0 dB and maximum value of 12.0 dB
3. THE Number_Entity SHALL have a step size of 0.5 dB
4. THE Number_Entity SHALL display the unit of measurement as "dB"
5. THE Number_Entity SHALL have a unique entity ID following the pattern `number.{device_name}_channel_{channel_name}_volume`

### Requirement 2: Send Channel Volume Commands

**User Story:** As a Home Assistant user, I want my channel volume adjustments to be sent to the receiver, so that the physical speaker output changes.

#### Acceptance Criteria

1. WHEN a Number_Entity value changes, THE Channel_Volume_Manager SHALL send the corresponding CV_Command to the Receiver
2. THE Channel_Volume_Manager SHALL use a Short_Lived_Telnet_Connection to send CV_Command messages
3. THE Channel_Volume_Manager SHALL close the Short_Lived_Telnet_Connection after sending the CV_Command
4. THE Channel_Volume_Manager SHALL convert the dB value to the receiver protocol format (2-digit for whole dB, 3-digit for half dB, with offset of 50)
5. THE Channel_Volume_Manager SHALL increment the Pending_Counter before sending a CV_Command

**Protocol Format Examples:**
- +3.0 dB → "53" (2-digit: value + offset)
- +3.5 dB → "535" (3-digit: (value + offset) * 10)
- 0.0 dB → "50" (2-digit)
- -12.0 dB → "38" (2-digit)
- +12.0 dB → "62" (2-digit)

### Requirement 3: Receive Channel Volume Updates

**User Story:** As a Home Assistant user, I want channel volume changes made on the receiver to be reflected in Home Assistant, so that the UI shows the current state.

#### Acceptance Criteria

1. WHEN a CV_Event is received via the Persistent_Telnet_Connection, THE Channel_Volume_Manager SHALL update the corresponding Number_Entity
2. THE Channel_Volume_Manager SHALL extend the denonavr_Library telnet callback to handle CV_Event messages
3. THE Channel_Volume_Manager SHALL convert the receiver protocol format to dB values for display (2-digit for whole dB, 3-digit for half dB)
4. WHEN the Pending_Counter is greater than zero, THE Channel_Volume_Manager SHALL decrement the counter and skip the entity update

**Protocol Format Examples:**
- "53" (2-digit) → +3.0 dB (value - offset)
- "535" (3-digit) → +3.5 dB (value / 10 - offset)
- "50" → 0.0 dB
- "38" → -12.0 dB
- "62" → +12.0 dB
5. WHEN the Pending_Counter is zero, THE Channel_Volume_Manager SHALL update the Number_Entity with the received value

### Requirement 4: Feedback Loop Prevention

**User Story:** As a Home Assistant user, I want channel volume adjustments to happen smoothly without oscillation, so that the system remains stable.

#### Acceptance Criteria

1. WHEN the Channel_Volume_Manager sends a CV_Command, THE Channel_Volume_Manager SHALL increment the Pending_Counter for that channel
2. WHEN a CV_Event is received and the Pending_Counter is greater than zero, THE Channel_Volume_Manager SHALL decrement the counter without updating the Number_Entity
3. WHEN a CV_Event is received and the Pending_Counter is zero, THE Channel_Volume_Manager SHALL update the Number_Entity
4. THE Pending_Counter SHALL be maintained separately for each channel
5. THE Pending_Counter SHALL never be negative

### Requirement 5: Telnet Connection Management

**User Story:** As a Home Assistant user, I want the integration to use network resources efficiently, so that my network and receiver are not overloaded.

#### Acceptance Criteria

1. THE Channel_Volume_Manager SHALL reuse the existing Persistent_Telnet_Connection managed by the denonavr_Library for receiving CV_Event messages
2. THE Channel_Volume_Manager SHALL NOT create a second persistent telnet connection
3. WHEN sending a CV_Command, THE Channel_Volume_Manager SHALL create a Short_Lived_Telnet_Connection
4. THE Channel_Volume_Manager SHALL close the Short_Lived_Telnet_Connection within 5 seconds of creation
5. IF the Persistent_Telnet_Connection is not enabled, THE Channel_Volume_Manager SHALL still allow sending CV_Command messages via Short_Lived_Telnet_Connection

### Requirement 6: Backward Compatibility

**User Story:** As an existing user of the marantzplus integration, I want the channel volume feature to be added without breaking my current setup, so that I can upgrade safely.

#### Acceptance Criteria

1. THE Integration SHALL maintain all existing functionality provided by the denonavr_Library
2. THE Integration SHALL continue to support receivers without telnet enabled
3. THE Integration SHALL continue to support multi-zone configurations
4. WHERE telnet is not enabled, THE Channel_Volume_Manager SHALL create Number_Entity instances that can send commands but not receive updates
5. THE Integration SHALL NOT require configuration changes for existing users

### Requirement 7: Multi-Zone Support

**User Story:** As a Home Assistant user with a multi-zone receiver, I want channel volume controls for each zone, so that I can adjust channels independently per zone.

#### Acceptance Criteria

1. THE Channel_Volume_Manager SHALL create Number_Entity instances for each configured Zone
2. THE Number_Entity SHALL include the zone name in the entity ID for Zone2 and Zone3, following the pattern `number.{device_name}_zone{N}_channel_{channel_name}_volume`, and omit the zone name for Main Zone following the pattern `number.{device_name}_channel_{channel_name}_volume`
3. WHEN sending a CV_Command, THE Channel_Volume_Manager SHALL prefix the command with the appropriate zone identifier
4. WHEN receiving a CV_Event, THE Channel_Volume_Manager SHALL route the update to the Number_Entity for the correct Zone
5. THE Channel_Volume_Manager SHALL support Main Zone, Zone2, and Zone3

### Requirement 8: Optional Channel Support

**User Story:** As a Home Assistant user with a receiver that doesn't support all channels, I want only the supported channels to appear, so that my UI is not cluttered with non-functional controls.

#### Acceptance Criteria

1. THE Channel_Volume_Manager SHALL query the Receiver for supported channels during initialization
2. THE Channel_Volume_Manager SHALL create Number_Entity instances only for channels supported by the Receiver
3. IF a channel is not supported, THE Channel_Volume_Manager SHALL NOT create a Number_Entity for that channel
4. THE Channel_Volume_Manager SHALL handle receivers that support a subset of channels (front left, front right, center, surround left, surround right, subwoofer)
5. IF the Receiver does not respond to channel capability queries, THE Channel_Volume_Manager SHALL create Number_Entity instances for all standard channels

### Requirement 9: Error Handling

**User Story:** As a Home Assistant user, I want the integration to handle communication errors gracefully, so that temporary network issues don't crash the integration.

#### Acceptance Criteria

1. IF a Short_Lived_Telnet_Connection fails to connect, THEN THE Channel_Volume_Manager SHALL log an error and leave the Number_Entity unchanged
2. IF a CV_Command fails to send, THEN THE Channel_Volume_Manager SHALL decrement the Pending_Counter
3. IF the Persistent_Telnet_Connection disconnects, THEN THE Channel_Volume_Manager SHALL continue to allow sending CV_Command messages
4. IF a CV_Event contains invalid data, THEN THE Channel_Volume_Manager SHALL log a warning and ignore the event
5. THE Channel_Volume_Manager SHALL NOT raise exceptions that would cause the Integration to unload

### Requirement 10: Configuration and Setup

**User Story:** As a Home Assistant user, I want channel volume controls to be automatically available when I set up the integration, so that I don't need additional configuration steps.

#### Acceptance Criteria

1. WHEN the Integration is set up via config flow, THE Channel_Volume_Manager SHALL be initialized automatically
2. THE Channel_Volume_Manager SHALL register the number platform with Home Assistant
3. THE Number_Entity instances SHALL appear in Home Assistant within 30 seconds of integration setup
4. THE Channel_Volume_Manager SHALL use the same connection parameters (host, port) as the denonavr_Library
5. THE Integration SHALL NOT require users to enable a separate option for channel volume controls
