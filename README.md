# ha_telemetry

`ha_telemetry` is a Home Assistant custom integration that publishes telemetry snapshots to a remotely hosted `data_hub` over MQTT.

The supported workflow is the managed public-hub workflow:

1. the operator gives Home Assistant a public Hub API URL
2. the operator gives Home Assistant an `enrollment_token`
3. Home Assistant enrolls through the Hub API
4. the hub returns broker credentials and topic details
5. Home Assistant connects directly to the MQTT broker over TLS

The repo root is the install path for Home Assistant. Clone it directly into:

    /config/custom_components/ha_telemetry

## Install

1. Clone the repo.

   ```bash
   cd /config/custom_components
   git clone <repo-url> ha_telemetry
   ```

2. Restart Home Assistant.

## Supported Setup

Use the integration only with managed hub enrollment.
You need:

- a public Hub API URL such as `https://hub.example.com`
- an `enrollment_token` issued by `data_hub`

In the Home Assistant form, enter:

- Hub API URL
- Enrollment token
- Telemetry entities
- Fallback telemetry interval
- Fallback heartbeat interval

The integration then validates the hub response and verifies that the returned
MQTT broker is reachable.

## Notes

- This integration supports managed hub enrollment only.
- This generic integration does not enforce project-specific unit or sensor rules on the selected entities.
- This integration assumes a publicly trusted broker certificate and the supported `data_hub` deployment shape.
- If setup says it cannot reach the hub, check the public Hub API URL, DNS, firewall, and reverse proxy configuration.
- If setup says it cannot connect to the MQTT broker returned by the hub, check public reachability to port `8883`, TLS certificate validity, and the broker hostname returned by the hub.
