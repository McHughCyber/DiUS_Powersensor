# DiUS Powersensor

![coverage badge](./coverage.svg)
[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]
[![hacs_downloads](https://img.shields.io/github/downloads/McHughCyber/DiUS_Powersensor/latest/total)](https://github.com/McHughCyber/DiUS_Powersensor/releases/latest)

[![Discord][discord-shield]][discord]
[![Community Forum][forum-shield]][forum]

## Maintenance Status

This is a maintained fork of the original [DiUS Powersensor](https://github.com/drc38/DiUS_Powersensor) integration by [@drc38](https://github.com/drc38). The original repository has been inactive for several years, so this fork has been created to continue development and provide ongoing support for users.

**Original Author:** [@drc38](https://github.com/drc38)
**Current Maintainer:** [@McHughCyber](https://github.com/McHughCyber)

We acknowledge and thank the original author for their excellent work in creating this integration. This fork maintains compatibility with the original while providing active maintenance, bug fixes, and new features.

# Powersensor Home Assistant full integration prototype

This is an attempt at a standalone [Powersensor](https://www.powersensor.com.au) integration with Home Assistant. Kudos to [@izevaka](https://github.com/izevaka/powersensor-home-assistant) for figuring out the sensor interface.

# Integration status

This fork supports multiple PowerSensor devices and plugs reporting through a
single relay. The integration uses Home Assistant's config flow, dynamically
adds newly discovered devices, and exposes primary power sensors plus solar
energy sensors where the relay payload identifies a sensor as solar.

The current release targets Home Assistant 2025.1.0 or newer.

# Installation

## HACS

HACS is recommended as it provides automated install and will notify you when updates are available.

This assumes you have [HACS](https://github.com/hacs/integration) installed and know how to use it. If you need help with this, go to the HACS project documentation.

Add custom repository in _HACS_

1. Click on HACS in your menu to open the HACS panel, then click on integrations (https://your.domain/hacs/integrations).
1. Click on the 3 dots in the top right corner.
1. Select "Custom repositories"
1. Add the URL to the repository: `https://github.com/McHughCyber/DiUS_Powersensor`
1. Select the integration category.
1. Click the "ADD" button.

Once done, you should see the new repository, appearing in a list like this. Click the **Download** button

## Manual Installation

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `dius`.
4. Download _all_ the files from the `custom_components/dius/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant
7. In the HA UI go to "Integrations" click "+" and search for "DiUS_Powersensor"

## Migrating from the Original Repository

If you're currently using the original integration from `drc38/DiUS_Powersensor` and want to migrate to this maintained fork:

### HACS Users

1. Remove the old custom repository:

   - Go to HACS → Integrations
   - Click the 3 dots on "DiUS Powersensor"
   - Select "Remove custom repository"
   - Uninstall the integration (if prompted)

2. Add the new repository:
   - Follow the HACS installation instructions above using `https://github.com/McHughCyber/DiUS_Powersensor`
   - Install the integration
   - Restart Home Assistant

Your existing configuration will be preserved automatically. You may need to reconfigure the integration if there have been breaking changes (check release notes).

### Manual Installation Users

1. Remove the old integration files from `custom_components/dius/`
2. Follow the manual installation steps above
3. Restart Home Assistant

Your configuration entries should remain intact, but you may need to reconfigure if prompted.

# Configuration

Configuration of the integration is done within the Integrations Panel in Home Assistant.

1. Navigate to Integrations
1. Click _Add Integration_
1. Search for DiUS Powersensor
1. Find your plug/gateway's IP address in the Powersensor mobile app

![image](https://user-images.githubusercontent.com/20024196/173300192-4092430e-3421-4a5c-a422-3ba066e58856.png)

1. Enter the IP address in the configuration, NB set your router to prevent the IP changing. Click _Submit_
1. Click _Configure_ on the newly created integration. Device entities can be
enabled or disabled after they are discovered. A power offset can also be
applied to PowerSensor readings, for example `-100 W`.
<!---->

# Entities

The integration creates entities as relay payloads arrive:

- `Power Sensor <MAC suffix> Power` for each discovered PowerSensor.
- `Power Sensor <MAC suffix> Energy` for PowerSensors reporting `role: solar`.
- `Power Plug <MAC suffix> Power` for each discovered plug.

Energy sensors prefer the relay payload's cumulative `summation` value. If a
solar sensor does not provide `summation`, Home Assistant derives energy from
the sample's power and duration. Derived energy is stored defensively so reading
the entity state repeatedly does not double-count the same sample.

# Troubleshooting

## No devices appear

The relay only exposes devices after it sends data. Confirm the relay IP/port is
correct, then wait for the PowerSensor or plug to report. The integration marks
devices unavailable if they stop reporting for the configured stale timeout.

## Relay reconnects

The integration subscribes to the UDP stream and will resubscribe on warning
messages, reconnect on expiry, and retry with backoff after transport errors.
Diagnostics include the current connection state, reconnect count, parser error
counts, and the known device list.

## Incorrect PowerSensor readings

PowerSensor payloads may use unit `U`. The `U to W conversion` option converts
these readings to watts before entity state is published. The `Offset W reported` option applies only to PowerSensor devices, not plugs.

## Entity IDs changed after upgrading

This modernization uses stable unique IDs based on MAC address, device type, and
measurement type. If Home Assistant creates new entity IDs after upgrading,
rename them in the entity registry to match your existing dashboards and
automations.

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

## Credits

This project was generated from [@oncleben31](https://github.com/oncleben31)'s [Home Assistant Custom Component Cookiecutter](https://github.com/oncleben31/cookiecutter-homeassistant-custom-component) template.

Code template was mainly taken from [@Ludeeus](https://github.com/ludeeus)'s [integration_blueprint][integration_blueprint] template

---

[integration_blueprint]: https://github.com/custom-components/integration_blueprint
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg
[discord]: https://discord.gg/Qa5fW2R
[discord-shield]: https://img.shields.io/discord/330944238910963714.svg
[exampleimg]: example.png
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/McHughCyber/DiUS_Powersensor.svg
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40McHughCyber-blue.svg
[releases-shield]: https://img.shields.io/github/release/McHughCyber/DiUS_Powersensor.svg
[releases]: https://github.com/McHughCyber/DiUS_Powersensor/releases
[user_profile]: https://github.com/McHughCyber
