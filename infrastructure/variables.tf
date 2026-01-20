# This file can be used to define additional variables
# Main variables are defined in main.tf for simplicity

# Example: Additional configuration variables
variable "database_size" {
  description = "Database instance size"
  type        = string
  default     = "db-s-1vcpu-1gb"
}

variable "app_instance_size" {
  description = "App Platform instance size"
  type        = string
  default     = "basic-xxs"
}

variable "enable_backups" {
  description = "Enable database backups"
  type        = bool
  default     = true
}

