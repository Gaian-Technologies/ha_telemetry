# ha_telemetry

`ha_telemetry` is a Home Assistant custom integration that publishes
telemetry snapshots to a remotely hosted `data_hub` over MQTT.

If you are discovering the stack from this repo first, the server-side
counterpart is [`data_hub`](/ssd2/Gaian/Workspace/data_hub), and the optional
public token-distribution flow is handled by
[`enrollment_portal`](/ssd2/Gaian/Workspace/enrollment_portal).

The supported workflow is the managed public-hub workflow:

1. the operator gives Home Assistant a public Hub API URL
2. the operator gives Home Assistant an `enrollment_token`
3. Home Assistant enrolls through the Hub API
4. the hub returns broker credentials and topic details
5. Home Assistant connects directly to the MQTT broker over TLS

## Install

### Preferred: Manual Install

For early rollout, the simplest and most reproducible path is to copy the repo
root into:

    /config/custom_components/ha_telemetry

The easiest manual path is usually the Home Assistant `Terminal & SSH`
add-on web terminal:

```bash
cd /config/custom_components
git clone https://github.com/Gaian-Technologies/ha_telemetry.git ha_telemetry
```

You can also download the GitHub ZIP and copy the extracted
`ha_telemetry` folder into `/config/custom_components/` using `Studio Code
Server`, `File editor`, Samba, or another file access method.

Reboot Home Assistant after installing or updating the integration. If you are
using a terminal, the simplest path is usually:

```bash
sudo reboot
```

### Optional: HACS Custom Repository

If you already use HACS, you can install this repo as a custom repository
instead.

1. Make sure HACS is already installed in Home Assistant.
2. Open `HACS`.
3. Open the top-right 3 dot menu, choose `Custom repositories`, and add:

   - Repository: `https://github.com/Gaian-Technologies/ha_telemetry`
   - Category: `Integration`

4. Find `Home Assistant Telemetry` in HACS and download it.
5. Reboot Home Assistant.

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
- A bundled `brand/icon.png` is included so recent Home Assistant versions can show the custom integration icon for both manual installs and HACS installs.
- This integration assumes a publicly trusted broker certificate and the supported `data_hub` deployment shape.
- If setup says it cannot reach the hub, check the public Hub API URL, DNS, firewall, and reverse proxy configuration.
- If setup says it cannot connect to the MQTT broker returned by the hub, check public reachability to port `8883`, TLS certificate validity, and the broker hostname returned by the hub.
