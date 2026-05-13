# Release Notes

## 0.2.0

- Raises the minimum supported Home Assistant version to 2025.1.0.
- Replaces blocking UDP socket reads with an async datagram client.
- Adds connection state, resubscribe, reconnect, and stale-device handling.
- Adds normalized device snapshots for multiple PowerSensors and plugs.
- Dynamically creates entities as devices report through the relay.
- Uses stable unique IDs based on MAC, device type, and measurement type.
- Prefers solar sensor `summation` values for energy and uses idempotent derived
  energy as a fallback.
- Adds diagnostics, repair issues, modern options selectors, and reconfigure
  support.
- Updates tests to cover model parsing, dynamic entities, and energy semantics.
