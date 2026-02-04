terraform {
  required_version = ">= 1.6.0"

  required_providers {
    local = {
      source  = "hashicorp/local"
      version = ">= 2.5.0"
    }
  }
}

locals {
  inventory_path = abspath("${path.module}/${var.inventory_path}")

  inventory_content = <<-EOT
[harborline]
${var.host_name} ansible_host=${var.server_host} ansible_user=${var.ssh_user}

[harborline:vars]
harborline_dir=${var.harborline_dir}
harborline_api_image=${var.harborline_api_image}
EOT
}

resource "local_file" "ansible_inventory" {
  filename             = local.inventory_path
  content              = local.inventory_content
  file_permission      = "0644"
  directory_permission = "0755"
}
