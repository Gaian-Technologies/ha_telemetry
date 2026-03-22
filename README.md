# ha_telemetry

`ha_telemetry` is a Home Assistant custom integration that securely publishes
periodic snapshots of selected entities to a remote MQTT broker and accepts
remote commands for a smaller allow-listed subset of those entities.

The integration is designed around a two-way control model:

- `data_hub` publishes retained desired telemetry policy for each site
- `ha_telemetry` reports the applied policy and health status
- `ha_telemetry` publishes periodic telemetry snapshots
- `data_hub` can send remote commands to command-enabled entities
- `ha_telemetry` acknowledges each remote command

## Features In This First Pass

- config flow in the Home Assistant UI
- MQTT 5 over TLS with mutual TLS
- explicit `site_id` per Home Assistant instance
- selected telemetry entity allow-list
- separate command entity allow-list
- hub-controlled telemetry rate through retained desired config
- heartbeat and reported-state publishing
- remote command execution with acknowledgements

## Install The Custom Integration

1. Copy `custom_components/ha_telemetry` into your Home Assistant config directory:

```text
/config/custom_components/ha_telemetry
```

2. Copy the certificate files for this site into your Home Assistant config directory.
A clean layout is:

```text
/config/ha_telemetry/certs/site_a/ca.crt
/config/ha_telemetry/certs/site_a/client.crt
/config/ha_telemetry/certs/site_a/client.key
```

3. Restart Home Assistant.

4. Go to `Settings -> Devices & Services -> Add Integration`.

5. Search for `Home Assistant Telemetry`.

6. Fill in:

- `Broker host`: the public DNS name or IP of the remote EMQX broker
- `Broker port`: usually `8883`
- `Site ID`: must match the client certificate CN exactly
- `Topic prefix`: keep `ha_telemetry/v1` unless you changed both sides
- `CA certificate path`: for example `ha_telemetry/certs/site_a/ca.crt`
- `Client certificate path`: for example `ha_telemetry/certs/site_a/client.crt`
- `Client key path`: for example `ha_telemetry/certs/site_a/client.key`
- `Telemetry entities`: entities to publish in periodic snapshots
- `Command-enabled entities`: subset of telemetry entities that may receive remote commands
- `Default telemetry interval`: local fallback interval before the hub sends desired config
- `Default heartbeat interval`: local fallback heartbeat interval before the hub sends desired config

The integration validates the broker connection during setup.

## Data Flow

Topics used by the integration:

- `<topic_prefix>/sites/<site_id>/telemetry`
- `<topic_prefix>/sites/<site_id>/desired`
- `<topic_prefix>/sites/<site_id>/reported`
- `<topic_prefix>/sites/<site_id>/heartbeat`
- `<topic_prefix>/sites/<site_id>/commands/request`
- `<topic_prefix>/sites/<site_id>/commands/ack`

Telemetry is sent as periodic batches, not one MQTT message per entity state change.
That scales better and gives the hub a clean way to control the publishing rate.

## Remote Commands

Commands are accepted only when all of the following are true:

- the entity is in the `Telemetry entities` allow-list
- the entity is also in the `Command-enabled entities` allow-list
- the requested Home Assistant service is in the integration's allowed service list
- the command is addressed to the correct `site_id`

Supported service names in this first pass:

- `button.press`
- `cover.close_cover`
- `cover.open_cover`
- `cover.stop_cover`
- `homeassistant.toggle`
- `homeassistant.turn_off`
- `homeassistant.turn_on`
- `input_boolean.toggle`
- `input_boolean.turn_off`
- `input_boolean.turn_on`
- `input_number.set_value`
- `input_select.select_option`
- `number.set_value`
- `scene.turn_on`
- `select.select_option`

Example command from `data_hub` to switch on an input boolean:

```json
{
  "schema": "command_request.v1",
  "site_id": "site_a",
  "command_id": "5fce0a18-0d07-4ff8-9f4d-0d8bb9870c2e",
  "entity_id": "input_boolean.remote_test",
  "service": "homeassistant.turn_on",
  "service_data": {},
  "issued_at": "2026-03-22T00:00:00+00:00"
}
```

## Operational Notes

- Keep the client certificate CN equal to the configured `site_id`.
- Prefer DNS names over raw IPs so the broker certificate can use a clean SAN.
- Do not reuse the same client certificate across multiple Home Assistant instances.
- Keep the command allow-list intentionally small.
- If you change the entity selections or certificates later, use the integration options flow.
