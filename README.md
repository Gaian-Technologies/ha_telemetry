# ha_telemetry

ha_telemetry is a Home Assistant custom integration that publishes periodic telemetry snapshots to a remote MQTT broker and can accept remote commands for a smaller allow-listed subset of entities.

The repo root is the install path for Home Assistant. Clone it directly into:

    /config/custom_components/ha_telemetry

## Install

1. Clone the repo.

    cd /config/custom_components
    git clone <repo-url> ha_telemetry

2. Restart Home Assistant.

## Managed Setup

Use managed setup when a data_hub operator gives you:

- a Hub API URL
- an enrollment token

The Hub API URL is the base URL of the data_hub HTTP API.
Examples:

- `http://100.118.146.18:8000`
- `http://192.168.1.50:8000`
- `https://hub.example.com`

The enrollment token is the value returned by the data_hub invite API as `enrollment_token`.

In the Home Assistant form, enter:

- Hub API URL
- Enrollment token
- Telemetry entities
- Command-enabled entities
- Optional custom CA certificate path
- Fallback telemetry interval
- Fallback heartbeat interval

### Optional Custom CA Certificate Path

Use the optional custom CA certificate path when the broker certificate is signed by a private certificate authority, such as a local or Tailscale development hub.

If the file exists at:

- `/root/config/custom_components/ha_telemetry/ca/ca.crt`

then the preferred value to enter in Home Assistant is the path relative to the Home Assistant config directory:

- `custom_components/ha_telemetry/ca/ca.crt`

Absolute paths also work, but relative paths are cleaner and more portable.

If you are testing against a local data_hub with generated development certificates:

1. Copy `data_hub/certs/generated/ca/ca.crt` into your Home Assistant config directory.
2. Enter `custom_components/ha_telemetry/ca/ca.crt` in the managed setup form.

## Advanced Setup

Use advanced setup when you are configuring the broker directly instead of using the managed enrollment API.

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

## Notes

- Managed setup first contacts the Hub API URL, then validates the MQTT broker returned by the hub.
- If managed setup says it cannot reach the hub, check the URL, Tailscale connectivity, and port `8000`.
- If managed setup says it cannot connect to the MQTT broker, check port `8883`, certificate trust, and certificate host or IP matching.
- Command-enabled entities must also be selected for telemetry.
