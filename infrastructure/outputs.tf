# Additional outputs can be defined here
# Main outputs are in main_neon.tf

# Database cluster output removed - using Neon database (external, not managed by Terraform)
# output "database_cluster_id" {
#   description = "Database cluster ID"
#   value       = digitalocean_database_cluster.postgres.id
# }

output "app_id" {
  description = "App Platform application ID"
  value       = digitalocean_app.grantpool.id
}

// NOTE: `app_default_ingress` is defined in `main_neon.tf`.
// Keeping it here too causes: "Error: Duplicate output definition"