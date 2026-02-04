variable "inventory_path" {
  description = "Relative path (from this module) for the generated Ansible inventory file."
  type        = string
  default     = "../../ansible/inventory/hosts.ini"
}

variable "host_name" {
  description = "Inventory hostname label."
  type        = string
  default     = "harborline-1"
}

variable "server_host" {
  description = "Server IP/hostname to SSH into."
  type        = string
}

variable "ssh_user" {
  description = "SSH username for the target server."
  type        = string
  default     = "ubuntu"
}

variable "harborline_dir" {
  description = "Remote path where the compose project will live."
  type        = string
  default     = "/opt/harborline"
}

variable "harborline_api_image" {
  description = "Container image used by deploy/docker-compose.prod.yml."
  type        = string
  default     = "ghcr.io/your-org/harborline-commerce-api:latest"
}

