# ha_telemetry

ha_telemetry is a Home Assistant custom integration that publishes periodic
snapshots of selected entities to a remote MQTT broker and accepts remote
commands for a smaller allow-listed subset of those entities.

The repo root is the install path for Home Assistant. This means you can clone
it directly into:

    /config/custom_components/ha_telemetry

and then pull updates in place.

## Repo Layout

Runtime integration files live at the repo root.

Development-only directories live beside them and do not affect Home Assistant:

- tests/
- scripts/
- docs/

## Features

- config flow in the Home Assistant UI
- managed enrollment over HTTPS
- direct MQTT setup for self-hosted or lab use
- MQTT 5 over TLS with broker credentials
- explicit site_id per Home Assistant instance
- selected telemetry entity allow-list
- separate command entity allow-list
- hub-controlled telemetry rate through retained desired config
- heartbeat and reported-state publishing
- remote command execution with acknowledgements
- reauth and reconfigure flows

## Installation

Clone the repo directly into the Home Assistant custom_components directory:

    cd /config/custom_components
    git clone <repo-url> ha_telemetry

Then restart Home Assistant.

## Managed Hub Setup

Use this path when the hub operator provides a hosted service.

Requirements:

- the data_hub API must be reachable over HTTPS
- the MQTT broker must present a publicly trusted TLS certificate
- you need an enrollment token from the hub operator

Steps:

1. Go to Settings, Devices and Services, Add Integration.
2. Search for Home Assistant Telemetry.
3. Choose Managed hub.
4. Enter:

- Hub URL
- Enrollment token
- Telemetry entities
- Command-enabled entities
- Fallback telemetry interval
- Fallback heartbeat interval

The integration exchanges the enrollment token for:

- site_id
- MQTT broker host and port
- topic prefix
- transport mode
- MQTT username and password

## Advanced Setup

Use this path for self-hosted or lab environments.

Enter:

- Broker host
- Broker port
- Site ID
- Topic prefix
- MQTT username
- MQTT password
- Optional custom CA certificate path
- Transport
- Telemetry entities
- Command-enabled entities
- Fallback telemetry interval
- Fallback heartbeat interval

For local development with a private CA, copy the CA certificate into your Home
Assistant config directory and use a relative path such as:

    ha_telemetry/ca/ca.crt

## Data Flow

Topics used by the integration:

- <topic_prefix>/sites/<site_id>/telemetry
- <topic_prefix>/sites/<site_id>/desired
- <topic_prefix>/sites/<site_id>/reported
- <topic_prefix>/sites/<site_id>/heartbeat
- <topic_prefix>/sites/<site_id>/commands/request
- <topic_prefix>/sites/<site_id>/commands/ack

Telemetry is sent as periodic batches, not one MQTT message per entity change.
That scales better and lets the hub control the send rate cleanly.

## Remote Commands

A command is accepted only when all of the following are true:

- the entity is in the telemetry allow-list
- the entity is also in the command-enabled allow-list
- the requested service is in the integration allowed service list
- the command is addressed to the correct site_id
- the hub desired config has commands_enabled set to true

Supported services in this version:

- button.press
- cover.close_cover
- cover.open_cover
- cover.stop_cover
- homeassistant.toggle
- homeassistant.turn_off
- homeassistant.turn_on
- input_boolean.toggle
- input_boolean.turn_off
- input_boolean.turn_on
- input_number.set_value
- input_select.select_option
- number.set_value
- scene.turn_on
- select.select_option

## Updating Credentials Or Settings

- Use Reauthenticate if the managed hub rotates the broker credentials or if direct MQTT credentials change.
- Use Reconfigure to change local entity selections or broker settings.

## Operational Notes

- Managed setup is intended for publicly trusted hub deployments.
- Advanced setup is the right choice for local development with a private CA.
- Keep the command allow-list intentionally small.
- Commands stay disabled unless both the hub and the local integration configuration allow them.
