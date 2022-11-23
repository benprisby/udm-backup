# Unifi Dream Machine (UDM) Backup <!-- omit in toc -->

[![python](https://img.shields.io/badge/python-3.10-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)
[![linting: pylint](https://img.shields.io/badge/linting-pylint-yellowgreen)](https://github.com/PyCQA/pylint)
[![mypy: checked](https://img.shields.io/badge/mypy-checked-blue)](http://mypy-lang.org/)
[![code style: yapf](https://img.shields.io/badge/code%20style-yapf-blue)](https://github.com/google/yapf)

- [Overview](#overview)
- [Security Considerations](#security-considerations)
- [Prerequisites](#prerequisites)
    - [UDM](#udm)
        - [Automatic Backups](#automatic-backups)
        - [SSH Access](#ssh-access)
    - [SMB Share](#smb-share)
- [Configuration File](#configuration-file)
- [Running](#running)
- [Development](#development)
- [Deployment](#deployment)

## Overview

UDM Backup is a small application to copy automatic backups on a
[Unifi Dream Machine (UDM)](https://store.ui.com/collections/unifi-network-unifi-os-consoles/products/udm-us) to an SMB
share on a specified schedule.

As part of my backup plan, I want a copy of these backup files stored on my NAS in addition to the local copies on the
Dream Machine. While I also enable automatic cloud backups of the Console itself, the Network application contains the
most important settings to me. And even if I wanted to, downloading the full Console backups does not seem to be
possible at time of creating this, so this will have to suffice.

## Security Considerations

The UDM does not currently support installing a persistent SSH key on it to use in lieu of password-based
authentication at time of creating this. Furthermore, SSH access is granted to the root user. Thus, this is nowhere
close to a secure method of accessing a server, so any utilization of this project is at your own risk.

However, I am willing to assume the risk of lax security posture in my own network in exchange for the backup security
peace-of-mind given that:

- SSH access is restricted only to the LAN side
- Untrusted devices are isolated using VLANs
- Firewall rules have been added to explicitly block SSHing into the UDM from these untrusted VLANs

## Prerequisites

### UDM

#### Automatic Backups

To minimize the amount of work done by the application, I let Unifi's own software do most of the heavy lifting. To
enable automatic backups:

1. Open the Network application.
2. Navigate to Settings (gear icon in the left-hand pane).
3. Navigate to System in the left-hand pane.
4. Ensure Auto Backup is enabled on the desired schedule (I chose daily at 2AM).
5. Set the desired retention policy (I chose 30 files, i.e. days, and "Settings only")

#### SSH Access

The application uses SCP to transfer the backup files off the UDM. Thus, the SSH server must be enabled:

1. Open the Unifi OS application.
2. Navigate to Settings (gear icon in the left-hand pane).
3. Navigate to System in the left-hand pane.
4. Ensure SSH is enabled under "Console Controls" and set a secure password (this is for the root user).

### SMB Share

Create an SMB share on the target server (in my case a NAS) with a secure username and password. Ideally, create a new
user that is only able to access that single share.

## Configuration File

Copy _config.sample.json_ to _config.json_ (which is in the _.gitignore_) and fill in the values.

The file format is a JSON object. Dot notation is used to indicate nested heirarchies (e.g. `a.b` translates to
`{"a":{"b":"<value>"}}`).

A schema file has been created inside the module to validate both the _config.sample.json_ and _config.json_ files (if
created). A Visual Studio Code settings file has been checked in to enforce this schema against those files when editing
them.

| Property           | Data Type | Description |
| ------------------ | --------- | ----------- |
| `cron_schedule`    | `string`  | UTC [Cron expression](https://crontab.guru) to perform backups on, which should closely align with the Auto Backup settings on the UDM |
| `udm.address`      | `string`  | UDM IP address or hostname |
| `udm.ssh_password` | `string`  | UDM root SSH password |
| `smb.username`     | `string`  | SMB username |
| `smb.password`     | `string`  | SMB password |
| `smb.share`        | `string`  | SMB share to back up to |

**NOTE**: The backup schedule configured on the UDM is likely represented in local time, while the above schedule is
interpreted as UTC. Ensure any timezone offsets are taken into account when setting this property.

## Running

[Install Poetry](https://python-poetry.org/docs/#installation) and the required plugin:

```shell
poetry self add "poetry-dynamic-versioning[plugin]"
```

Install the required packages:

```shell
poetry install
```

Run the application:

```shell
poetry run python -m bdp.udmbackup <arguments>
```

For supported command line arguments, run:

```shell
poetry run python -m bdp.udmbackup --help
```

## Development

Install the required packages:

```shell
poetry install --with dev
```

Install the pre-commit hooks:

```shell
poetry run pre-commit install
```

If desired, pre-commit hooks can be run manually:

```shell
poetry run pre-commit run --all-files
```

## Deployment

A Dockerfile has been provided that installs the required Poetry environment and then runs the application using a
mapped configuration file:

```shell
docker build -t udm-backup .
docker run -d --restart=on-failure --name udm-backup \
    -v /path/to/config.json:/config.json udm-backup
```

Then, to stop the container:

```shell
docker stop udm-backup
```

Or to see log output:

```shell
docker logs udm-backup
```
