# Terraform automation (optional)

This repo is primarily deployed via Docker Compose, but this folder gives you a starting point for Terraform-based automation.

## Included: local bootstrap (generate Ansible inventory)
`infra/terraform/local` can generate an Ansible inventory file (`infra/ansible/inventory/hosts.ini`) from a few Terraform variables.

### Usage
```bash
cd infra/terraform/local
terraform init
terraform apply -var 'server_host=203.0.113.10' -var 'ssh_user=ubuntu'
```

Then deploy with Ansible:
```bash
ansible-playbook -i infra/ansible/inventory/hosts.ini infra/ansible/playbooks/deploy.yml
```

## Next steps
- Add a cloud-specific module (AWS/GCP/Azure/DO/etc.) that provisions a VM and outputs `server_host`, then reuse the Ansible playbook for deployment.

