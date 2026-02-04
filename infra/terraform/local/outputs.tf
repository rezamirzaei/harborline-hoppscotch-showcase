output "ansible_inventory_path" {
  description = "Path to the generated Ansible inventory file."
  value       = local_file.ansible_inventory.filename
}

