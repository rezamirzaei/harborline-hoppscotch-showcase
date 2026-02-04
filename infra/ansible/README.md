# Ansible automation (optional)

This folder contains an Ansible playbook to deploy the Harborline stack to a Linux host using Docker Compose (production compose file).

## Prereqs
- Control machine: `ansible` / `ansible-core` installed
- Target host: Ubuntu/Debian recommended (the playbook uses `apt` + the official Docker install script)
- SSH access to the target host

## Quickstart
1) Copy and edit the inventory:

```bash
cp infra/ansible/inventory/hosts.ini.example infra/ansible/inventory/hosts.ini
```

2) Run the deploy playbook:

```bash
ansible-playbook -i infra/ansible/inventory/hosts.ini infra/ansible/playbooks/deploy.yml
```

## What it does
- Installs Docker (if missing) and ensures the `docker` service is running
- Copies `deploy/docker-compose.prod.yml` to the server as `docker-compose.yml`
- Copies the repo `config/` folder (for `config/api.env` + `config/hoppscotch.env`)
- Writes a `.env` file to set `HARBORLINE_API_IMAGE`
- Runs `docker compose up -d --pull always`

## Notes
- Update `harborline_api_image` in the inventory to deploy a specific image tag/digest.
- The committed `config/*.env` files contain demo defaults. For real deployments, replace them with production values (secrets, URLs, etc.).

