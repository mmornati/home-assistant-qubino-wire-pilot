# Home Assistant Component for Qubino Wire Pilot

Home Assistant Component for Qubino Wire Pilot

![CleanShot 2024-09-04 at 12 36 52](https://github.com/user-attachments/assets/0b2f4bc7-35c6-43e4-9050-02696c9f1b9f)

## Introduction

The Qubino ZMNHJD1 is not recognized as a thermostat in Home Assistant but as a light.

The brightness percentage of the light entity is mapped to a mode.

| Mode             | Default % | Description                       |
| :--------------- | :-------- | :-------------------------------- |
| Off              | 10%       | Heater completely off             |
| Frost protection | 20%       | Minimal heating to prevent frost  |
| Eco              | 25%       | Energy saving mode                |
| Comfort -2       | 40%       | Comfort minus 2 degrees           |
| Comfort -1       | 50%       | Comfort minus 1 degree            |
| Comfort          | 99%       | Full comfort mode                 |

> **Note:** The default values above work for most devices. However, some Qubino devices may interpret brightness values differently. For example, some devices activate Eco mode at 25% instead of 30%. All threshold values are now configurable through the UI or YAML.
>
> For more details about device behavior variations, see [this blog post](https://blog.mornati.net/qubino-zmnhjd1-and-home-assistant-installation).

This integration creates a `climate` entity using the `light` entity for easy control of your heater.

The climate will have 2 modes:

- `heat` - split into 3 or 5 presets:
  - `comfort` - mapped qubino "Comfort" mode
  - `comfort-1` - mapped qubino "Comfort -1" mode (optional)
  - `comfort-2` - mapped qubino "Comfort -2" mode (optional)
  - `eco` - mapped qubino "Eco" mode
  - `away` - mapped qubino "Frost protection" mode
- `off` - mapped qubino "Off" mode (reported as the `none` preset)

Turning `heat` back on resumes the last order that was active (restored after a restart), or `comfort` if there is none.

Reading the module back, each configured value is the upper bound of its order, except eco: with the defaults, 21-30% reads as eco, as in the Qubino manual, even though eco is sent as 25%.

The thermostat also reports `hvac_action`: `off`, `idle` in frost protection, and `heating` otherwise. With a power sensor configured, `heating` and `idle` follow the radiator's power draw instead (above 5 W means heating).

The thermostat is unavailable while the light is unavailable. If the light, the temperature sensor or the power sensor does not exist (for example after renaming it), a warning is logged and a repair issue appears in Settings > System > Repairs. The issue is cleared once the entity exists again. Renaming the light from its settings is followed automatically.

:warning: "Comfort -1" and "Comfort -2" are not available by default because Home Assistant doesn't have comfort-1 and comfort-2 preset. If you want to support these modes, add `additional_modes: true` in your configuration.

## Installation

This is a fork of [piitaya/home-assistant-qubino-wire-pilot](https://github.com/piitaya/home-assistant-qubino-wire-pilot) and is not in the default HACS catalog. Add it as a custom repository:

1. HACS > ⋮ (top right) > Custom repositories.
2. Repository `https://github.com/mmornati/home-assistant-qubino-wire-pilot`, type Integration, Add.
3. Open "Qubino Wire Pilot" from this repository, Download, then restart Home Assistant.

Then convert the `light` to a `climate` entity by searching "Qubino Wire Pilot" in the integration page or helper page.

### Migrating from upstream 3.x

The fork keeps the same domain (`qubino_wire_pilot`), so existing thermostats, entity ids and automations keep working.

1. In HACS, open the upstream "Qubino Wire Pilot" (piitaya) and remove it. If HACS deletes the `custom_components/qubino_wire_pilot` folder, the next step puts it back.
2. Add this repository as a custom repository and download it (see above).
3. Restart Home Assistant. Existing entries keep their settings, and the threshold options become available in the helper's options.

Keep only one of the two repositories installed in HACS: if both are tracked, an update of one overwrites the other. An entry configured with this fork's threshold options does not load on upstream 3.x ("not a valid option at 'value_comfort'"), so do not switch back without removing those options.

## Configuration

### UI Configuration

When adding the integration through the UI, you can configure:

- **Light**: The light entity used to control the heating
- **Temperature sensor**: Optional sensor to display current temperature
- **Power sensor**: Optional power sensor of the radiator, used for `hvac_action`
- **Additional modes**: Enable Comfort -1 and Comfort -2 presets
- **Custom thresholds**: Override the default brightness percentages for each mode

### YAML configuration

If you prefer to use `yaml`, you can, but it's not recommended as more and more integrations are moved to the UI. All the options are available in the UI.

| Key                | Type    | Required | Default | Description                                                                |
| :----------------- | :------ | :------- | :------ | :------------------------------------------------------------------------- |
| `platform`         | string  | yes      | -       | Platform name (`qubino_wire_pilot`)                                        |
| `heater`           | string  | yes      | -       | Light entity                                                               |
| `sensor`           | string  | no       | -       | Temperature sensor (for display)                                           |
| `power_sensor`     | string  | no       | -       | Power sensor of the radiator (for `hvac_action`)                           |
| `additional_modes` | boolean | no       | false   | 6-order support (add Comfort -1 and Comfort -2 preset)                     |
| `name`             | string  | no       | -       | Name to use in the frontend                                                |
| `unique_id`        | string  | no       | -       | An ID that uniquely identifies this climate                                |
| `value_off`        | int     | no       | 10      | Brightness % threshold for Off mode                                        |
| `value_frost`      | int     | no       | 20      | Brightness % threshold for Frost protection mode                           |
| `value_eco`        | int     | no       | 25      | Brightness % threshold for Eco mode                                        |
| `value_comfort_2`  | int     | no       | 40      | Brightness % threshold for Comfort -2 mode                                 |
| `value_comfort_1`  | int     | no       | 50      | Brightness % threshold for Comfort -1 mode                                 |
| `value_comfort`    | int     | no       | 99      | Brightness % threshold for Comfort mode                                    |

The unique id is recommended to allow icon, entity_id or name changes from the UI.

> **Note:** Threshold values must be in ascending order (Off < Frost < Eco < Comfort-2 < Comfort-1 < Comfort). Invalid combinations will be rejected.

### Example

Basic configuration:

```yaml
climate:
  - platform: qubino_wire_pilot
    heater: light.heater_living_room_dimmer
```

With 6 order modes:

```yaml
climate:
  - platform: qubino_wire_pilot
    heater: light.heater_living_room_dimmer
    additional_modes: true
```

With optional sensor:

```yaml
climate:
  - platform: qubino_wire_pilot
    heater: light.heater_living_room_dimmer
    sensor: sensor.temperature_living_room
```

With custom thresholds (for devices that behave differently):

```yaml
climate:
  - platform: qubino_wire_pilot
    heater: light.heater_living_room_dimmer
    value_off: 10
    value_frost: 20
    value_eco: 25
    value_comfort_2: 40
    value_comfort_1: 50
    value_comfort: 99
```

### Unique ID

The `unique_id` is used to edit the entity from the GUI. It's automatically generated from heater entity_id. As the `unique_id` must be unique, you can not create 2 entities with the same heater.

If you want to have 2 climate with the same heater, you must specify the `unique_id` in the config.

```yaml
climate:
  - platform: qubino_wire_pilot
    heater: light.heater_living_room_dimmer
    unique_id: qubino_heater_living_room_1
  - platform: qubino_wire_pilot
    heater: light.heater_living_room_dimmer
    unique_id: qubino_heater_living_room_2
```

## Lovelace

You can use the [climate-mode-entity-row](https://github.com/piitaya/lovelace-climate-mode-entity-row) card in your lovelace dashboard to easily switch between modes.

## Troubleshooting

### Mode not activating at expected brightness level

Some Qubino devices interpret brightness values differently. If your device activates Eco mode at 25% instead of the expected range, use the custom threshold configuration to adjust the values.

See [this blog post](https://blog.mornati.net/qubino-zmnhjd1-and-home-assistant-installation) for detailed information about how different devices behave.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

Run `make install-dev`, then `make check lint test` before opening it.

## Credits

- Original integration by [@piitaya](https://github.com/piitaya)
- Additional contributions by [@dx44](https://github.com/dx44)
- Configurable thresholds feature by [@mmornati](https://github.com/mmornati)
