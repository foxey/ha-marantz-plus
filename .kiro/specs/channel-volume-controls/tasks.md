# Implementation Plan: Channel Volume Controls

## Overview

This implementation adds individual speaker channel volume control to the marantzplus Home Assistant custom component. The approach leverages the existing denonavr library's CV event support while adding a new ChannelVolumeManager class to coordinate entity creation, command sending, and state synchronization. The implementation uses a hybrid telnet approach (persistent connection for events, short-lived for commands) and a pending counter pattern to prevent feedback loops.

## Tasks

- [ ] 1. Add channel volume constants to const.py
  - Add CHANNEL_MAP dictionary mapping channel codes to display names
  - Add MIN_CHANNEL_VOLUME_DB, MAX_CHANNEL_VOLUME_DB, CHANNEL_VOLUME_STEP_DB constants
  - Add MIN_CHANNEL_VOLUME_PROTOCOL, MAX_CHANNEL_VOLUME_PROTOCOL constants
  - Add CV_TELNET_TIMEOUT constant
  - Add ZONE_PREFIXES dictionary for multi-zone command prefixes
  - _Requirements: 1.2, 1.3, 1.4, 2.4, 7.3_

- [ ] 2. Implement ChannelVolumeManager class
  - [ ] 2.1 Create channel_volume.py with ChannelVolumeManager class structure
    - Implement __init__ method accepting receiver, zone, and hass parameters
    - Initialize pending_counters dictionary for all channels
    - Initialize channel_volumes dictionary for state tracking
    - Initialize entities dictionary for entity references
    - Store receiver, zone, and hass references
    - _Requirements: 4.4, 4.5, 10.1_
  
  - [ ]* 2.2 Write property test for pending counter initialization
    - **Property 10: Counter non-negativity invariant**
    - **Validates: Requirements 4.5**
  
  - [ ] 2.3 Implement value conversion helper functions
    - Implement protocol_to_db function for 2-digit and 3-digit protocol values
    - Implement db_to_protocol function with whole/half dB detection
    - Handle offset of 50 for protocol conversion
    - _Requirements: 2.4, 3.3_
  
  - [ ]* 2.4 Write property test for value conversion round trip
    - **Property 3: Value conversion round trip**
    - **Validates: Requirements 2.4, 3.3**
  
  - [ ] 2.5 Implement async_send_cv_command method
    - Increment pending counter for the channel before sending
    - Format CV command with zone prefix and channel code
    - Create short-lived telnet connection using receiver host and port
    - Send CV command via telnet connection
    - Close connection in finally block
    - Handle connection failures and decrement counter on error
    - Log errors with receiver host and channel information
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 4.1, 5.3, 5.4, 7.3, 9.1, 9.2, 10.4_
  
  - [ ]* 2.6 Write property test for pending counter increment
    - **Property 6: Pending counter increment**
    - **Validates: Requirements 2.5, 4.1**
  
  - [ ]* 2.7 Write unit tests for async_send_cv_command
    - Test CV command format for each channel
    - Test zone prefix application for Main, Zone2, Zone3
    - Test connection failure error handling
    - Test counter recovery on send failure
    - _Requirements: 2.1, 2.2, 2.3, 7.3, 9.1, 9.2_
  
  - [ ] 2.8 Implement _cv_callback method for CV event handling
    - Parse CV event parameter to extract channel code and protocol value
    - Validate channel code against CHANNEL_MAP
    - Check if pending counter for channel is greater than zero
    - If counter > 0, decrement counter and skip entity update
    - If counter == 0, convert protocol value to dB and update entity
    - Handle zone routing for multi-zone events
    - Log warnings for invalid events or unknown channels
    - _Requirements: 3.1, 3.3, 3.4, 3.5, 4.2, 4.3, 7.4, 9.4_
  
  - [ ]* 2.9 Write property test for pending counter prevents update
    - **Property 7: Pending counter prevents update**
    - **Validates: Requirements 3.4, 4.2**
  
  - [ ]* 2.10 Write property test for zero counter allows update
    - **Property 8: Zero counter allows update**
    - **Validates: Requirements 3.5, 4.3**
  
  - [ ]* 2.11 Write unit tests for _cv_callback
    - Test CV event parsing and entity update
    - Test pending counter decrement on event
    - Test entity update skip when counter > 0
    - Test zone routing for events
    - Test invalid event handling
    - _Requirements: 3.1, 3.4, 3.5, 7.4, 9.4_
  
  - [ ] 2.12 Implement _get_supported_channels method
    - Query receiver for supported channels via telnet
    - Parse response to extract channel list
    - Return list of supported channel codes
    - Handle query failures by returning all standard channels as fallback
    - Log warnings if query fails
    - _Requirements: 8.1, 8.2, 8.4, 8.5_
  
  - [ ]* 2.13 Write unit tests for _get_supported_channels
    - Test channel query and parsing
    - Test fallback to all channels on failure
    - Test subset channel support
    - _Requirements: 8.1, 8.2, 8.4, 8.5_
  
  - [ ] 2.14 Implement async_setup method
    - Call _get_supported_channels to determine available channels
    - Create ChannelVolumeNumber entity for each supported channel
    - Store entity references in entities dictionary
    - Register _cv_callback with receiver's telnet callback system
    - Return list of created entities
    - _Requirements: 1.1, 8.2, 8.3, 10.1_
  
  - [ ]* 2.15 Write property test for multi-zone entity creation
    - **Property 14: Multi-zone entity creation**
    - **Validates: Requirements 7.1**
  
  - [ ]* 2.16 Write unit tests for async_setup
    - Test entity creation for all channels
    - Test conditional entity creation based on supported channels
    - Test callback registration with denonavr library
    - _Requirements: 1.1, 8.2, 8.3, 10.1_

- [ ] 3. Checkpoint - Ensure ChannelVolumeManager tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Implement ChannelVolumeNumber entity class
  - [ ] 4.1 Create ChannelVolumeNumber class in channel_volume.py
    - Inherit from NumberEntity
    - Implement __init__ with manager, channel, zone, device_info, unique_id_base parameters
    - Set entity attributes: name, unique_id, device_info
    - Generate entity ID following pattern with zone suffix logic
    - Store manager and channel references
    - _Requirements: 1.5, 7.2_
  
  - [ ]* 4.2 Write property test for entity ID format
    - **Property 2: Entity ID format**
    - **Validates: Requirements 1.5, 7.2**
  
  - [ ] 4.3 Implement async_set_native_value method
    - Call manager.async_send_cv_command with channel and value
    - Handle exceptions gracefully without propagating
    - _Requirements: 2.1_
  
  - [ ] 4.4 Implement native_value property
    - Return current channel volume from manager's channel_volumes dictionary
    - Return None if value not yet received
    - _Requirements: 3.1_
  
  - [ ] 4.5 Implement native_min_value, native_max_value, native_step properties
    - Return MIN_CHANNEL_VOLUME_DB for min_value
    - Return MAX_CHANNEL_VOLUME_DB for max_value
    - Return CHANNEL_VOLUME_STEP_DB for step
    - _Requirements: 1.2, 1.3_
  
  - [ ] 4.6 Implement native_unit_of_measurement property
    - Return "dB" as unit of measurement
    - _Requirements: 1.4_
  
  - [ ]* 4.7 Write property test for entity configuration consistency
    - **Property 1: Entity configuration consistency**
    - **Validates: Requirements 1.2, 1.3, 1.4**
  
  - [ ]* 4.8 Write unit tests for ChannelVolumeNumber
    - Test entity configuration properties (bounds, step, unit)
    - Test entity ID formatting with various device/zone names
    - Test async_set_native_value calls manager correctly
    - Test native_value returns correct state
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 2.1, 3.1, 7.2_

- [ ] 5. Checkpoint - Ensure ChannelVolumeNumber tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Create number platform setup
  - [ ] 6.1 Create number.py with async_setup_entry function
    - Import ChannelVolumeManager and required Home Assistant types
    - Get receiver instances from config_entry runtime_data
    - Create ChannelVolumeManager for each zone in each receiver
    - Call async_setup on each manager to get entities
    - Add all entities via async_add_entities callback
    - Handle errors gracefully and log failures
    - _Requirements: 7.1, 10.1, 10.2, 10.3_
  
  - [ ]* 6.2 Write unit tests for async_setup_entry
    - Test platform registration with Home Assistant
    - Test multi-zone entity creation
    - Test automatic initialization on setup
    - Test error handling during setup
    - _Requirements: 7.1, 10.1, 10.2, 10.3_

- [ ] 7. Integrate number platform into integration
  - [ ] 7.1 Modify __init__.py to add number platform
    - Add Platform.NUMBER to PLATFORMS list
    - Verify platform forwarding handles number platform automatically
    - _Requirements: 10.2_
  
  - [ ]* 7.2 Write integration test for platform registration
    - Test number platform loads with integration
    - Test entities appear within 30 seconds
    - _Requirements: 10.2, 10.3_

- [ ] 8. Add telnet callback registration
  - [ ] 8.1 Verify denonavr library CV event support
    - Confirm CV is in TELNET_EVENTS set in denonavr library
    - Confirm callback registration API is available
    - Document any library version requirements
    - _Requirements: 3.2, 5.1_
  
  - [ ] 8.2 Implement callback registration in ChannelVolumeManager.async_setup
    - Register _cv_callback with receiver using receiver.register_callback("CV", callback)
    - Handle case where telnet is not enabled (no error, just no updates)
    - Store callback reference for potential unregistration
    - _Requirements: 3.2, 5.1, 5.2, 6.4_
  
  - [ ]* 8.3 Write unit tests for callback registration
    - Test callback registration with denonavr library
    - Test operation without persistent telnet
    - Test persistent telnet disconnection handling
    - _Requirements: 3.2, 5.1, 5.2, 6.4, 9.3_

- [ ] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Integration and wiring
  - [ ] 10.1 Verify backward compatibility
    - Test existing media player functionality unchanged
    - Test integration works with telnet disabled
    - Test multi-zone configurations work correctly
    - Test no configuration changes required for existing users
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
  
  - [ ] 10.2 Add error handling and logging
    - Add appropriate log levels (error, warning, debug) throughout
    - Ensure no unhandled exceptions can crash integration
    - Test exception safety across all error conditions
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
  
  - [ ]* 10.3 Write property test for exception safety
    - **Property 19: Exception safety**
    - **Validates: Requirements 9.5**
  
  - [ ]* 10.4 Write integration tests
    - Test end-to-end flow: entity creation, command sending, event receiving
    - Test multi-zone operation with all three zones
    - Test feedback loop prevention with rapid changes
    - Test connection parameter consistency
    - _Requirements: 2.1, 3.1, 4.1, 4.2, 4.3, 7.1, 7.3, 7.4, 10.4_

- [ ] 11. Final checkpoint - Complete integration verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The implementation uses Python 3.x with Home Assistant >= 2026.2.0
- The denonavr library v1.2.0 already includes CV event support
- Hybrid telnet approach: persistent connection for events, short-lived for commands
- Pending counter pattern prevents feedback loops during command/event cycles
- Multi-zone support with cleaner entity names (omit "main" for main zone)
