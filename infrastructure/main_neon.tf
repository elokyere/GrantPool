# GrantPool Infrastructure - Updated for Neon Database
# This replaces the Digital Ocean database with Neon PostgreSQL

terraform {
  required_version = ">= 1.0"

  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}

provider "digitalocean" {
  token = var.do_token
}

# Variables
variable "do_token" {
  description = "Digital Ocean API token"
  type        = string
  sensitive   = true
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "grantpool"
}

variable "region" {
  description = "Digital Ocean region"
  type        = string
  default     = "nyc1"
}

variable "environment" {
  description = "Environment (production, staging)"
  type        = string
  default     = "production"
}

variable "domain" {
  description = "Domain name for the application"
  type        = string
  default     = ""
}

# Neon Database Variables (database created manually in Neon dashboard)
variable "neon_database_url" {
  description = "Neon PostgreSQL connection string (from Neon dashboard)"
  type        = string
  sensitive   = true
}

variable "neon_user" {
  description = "Neon database user"
  type        = string
  sensitive   = true
}

variable "neon_password" {
  description = "Neon database password"
  type        = string
  sensitive   = true
}

variable "neon_db_name" {
  description = "Neon database name"
  type        = string
  default     = "grantpool"
}

# API Keys
variable "secret_key" {
  description = "JWT secret key"
  type        = string
  sensitive   = true
}

variable "anthropic_api_key" {
  description = "Anthropic API key for LLM evaluations"
  type        = string
  sensitive   = true
  default     = ""
}

variable "paystack_secret_key" {
  description = "Paystack secret key"
  type        = string
  sensitive   = true
}

variable "paystack_public_key" {
  description = "Paystack public key"
  type        = string
  sensitive   = true
}

# Note: Paystack does NOT use a separate webhook secret
# Webhooks are signed using PAYSTACK_SECRET_KEY (same as API key)
# This variable is kept for backward compatibility but is not used
variable "paystack_webhook_secret" {
  description = "Paystack webhook secret (DEPRECATED - not used, webhooks use Secret Key)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "slack_signing_secret" {
  description = "Slack signing secret for interactive components"
  type        = string
  sensitive   = true
  default     = ""
}

variable "slack_workspace_id" {
  description = "Slack workspace ID (allowlist)"
  type        = string
  sensitive   = false
  default     = ""
}

variable "slack_admin_user_ids" {
  description = "Slack admin user IDs (comma-separated allowlist)"
  type        = string
  sensitive   = false
  default     = ""
}

variable "slack_webhook_url" {
  description = "Slack incoming webhook URL for notifications"
  type        = string
  sensitive   = true
  default     = ""
}

variable "sendgrid_api_key" {
  description = "SendGrid API key for email service"
  type        = string
  sensitive   = true
  default     = ""
}

variable "app_url" {
  description = "Application URL for Paystack callback"
  type        = string
  default     = ""
}

variable "app_platform_url" {
  description = "Digital Ocean App Platform URL (with random suffix, e.g., grantpool-production-bhqbr.ondigitalocean.app)"
  type        = string
  default     = ""
}

variable "cors_origins" {
  description = "CORS allowed origins (comma-separated)"
  type        = string
  default     = ""
}

variable "github_repo" {
  description = "GitHub repository (format: owner/repo)"
  type        = string
  default     = ""
}

variable "github_branch" {
  description = "GitHub branch to deploy"
  type        = string
  default     = "main"
}

variable "auto_deploy" {
  description = "Auto-deploy on push"
  type        = bool
  default     = false
}

# App Platform Application
# NOTE: No Digital Ocean database - using Neon instead
resource "digitalocean_app" "grantpool" {
  spec {
    name   = "${var.project_name}-${var.environment}"
    region = var.region

    # Backend Service
    service {
      name               = "backend"
      instance_count     = 1
      instance_size_slug = "basic-xxs"

      github {
        repo           = var.github_repo
        branch         = var.github_branch
        deploy_on_push = var.auto_deploy
      }

      dockerfile_path = "backend/Dockerfile"

      http_port = 8000

      health_check {
        http_path             = "/health"
        initial_delay_seconds = 10
        period_seconds        = 10
        timeout_seconds       = 5
        success_threshold     = 1
        failure_threshold     = 3
      }

      # Neon Database Configuration (NOT Digital Ocean database)
      env {
        key   = "DATABASE_URL"
        value = var.neon_database_url
        type  = "SECRET"
      }

      env {
        key   = "POSTGRES_USER"
        value = var.neon_user
        type  = "SECRET"
      }

      env {
        key   = "POSTGRES_PASSWORD"
        value = var.neon_password
        type  = "SECRET"
      }

      env {
        key   = "POSTGRES_DB"
        value = var.neon_db_name
        type  = "SECRET"
      }

      # Security
      env {
        key   = "SECRET_KEY"
        value = var.secret_key
        type  = "SECRET"
      }

      # API Keys
      env {
        key   = "ANTHROPIC_API_KEY"
        value = var.anthropic_api_key
        type  = "SECRET"
      }

      env {
        key   = "PAYSTACK_SECRET_KEY"
        value = var.paystack_secret_key
        type  = "SECRET"
      }

      env {
        key   = "PAYSTACK_PUBLIC_KEY"
        value = var.paystack_public_key
        type  = "SECRET"
      }

      # Note: PAYSTACK_WEBHOOK_SECRET is not needed - Paystack uses PAYSTACK_SECRET_KEY for webhook signing
      # Keeping this for backward compatibility but setting to empty
      env {
        key   = "PAYSTACK_WEBHOOK_SECRET"
        value = ""
      }

      # Slack Configuration (optional - for admin orchestration)
      env {
        key   = "SLACK_SIGNING_SECRET"
        value = var.slack_signing_secret
        type  = "SECRET"
      }
      env {
        key   = "SLACK_WORKSPACE_ID"
        value = var.slack_workspace_id
      }
      env {
        key   = "SLACK_ADMIN_USER_IDS"
        value = var.slack_admin_user_ids
      }
      env {
        key   = "SLACK_WEBHOOK_URL"
        value = var.slack_webhook_url
        type  = "SECRET"
      }

      env {
        key   = "APP_URL"
        value = var.app_url != "" ? var.app_url : (var.domain != "" ? "https://${var.domain}" : (var.app_platform_url != "" ? "https://${var.app_platform_url}" : "https://${var.project_name}-${var.environment}.ondigitalocean.app"))
      }

      env {
        key   = "FRONTEND_URL"
        value = var.domain != "" ? "https://${var.domain}" : (var.app_platform_url != "" ? "https://${var.app_platform_url}" : "https://${var.project_name}-${var.environment}.ondigitalocean.app")
      }

      # Payment Pricing - Locked GHS prices (authoritative)
      env {
        key   = "USD_PRICE_REFINEMENT"
        value = "300"
      }
      env {
        key   = "USD_PRICE_STANDARD"
        value = "700"
      }
      env {
        key   = "USD_PRICE_BUNDLE"
        value = "1800"
      }
      env {
        key   = "GHS_PRICE_REFINEMENT"
        value = "3217"
      }
      env {
        key   = "GHS_PRICE_STANDARD"
        value = "7507"
      }
      env {
        key   = "GHS_PRICE_BUNDLE"
        value = "19305"
      }
      # Legacy pricing (for backward compatibility)
      env {
        key   = "USD_PRICE"
        value = "700"
      }
      env {
        key   = "GHS_PRICE"
        value = "7507"
      }

      # Application
      env {
        key   = "ENVIRONMENT"
        value = var.environment
      }

      env {
        key   = "DEBUG"
        value = "false"
      }

      env {
        key   = "CORS_ORIGINS"
        value = var.cors_origins != "" ? var.cors_origins : (var.domain != "" ? "https://${var.domain},https://www.${var.domain}" : "*")
      }

      # Email Configuration (SendGrid)
      env {
        key   = "EMAIL_PROVIDER"
        value = "sendgrid"
      }
      env {
        key   = "EMAIL_FROM"
        value = "noreply@grantpool.org"
      }
      env {
        key   = "EMAIL_FROM_NAME"
        value = "GrantPool"
      }
      env {
        key   = "SENDGRID_API_KEY"
        value = var.sendgrid_api_key
        type  = "SECRET"
      }

      # Startup script handles migrations and app startup
    }

    # Frontend Service
    service {
      name               = "frontend"
      instance_count     = 1
      instance_size_slug = "basic-xxs"

      github {
        repo           = var.github_repo
        branch         = var.github_branch
        deploy_on_push = var.auto_deploy
      }

      dockerfile_path = "frontend/Dockerfile"

      http_port = 80

      env {
        key   = "VITE_API_URL"
        # Note: Do NOT include /api/v1 here - frontend code already includes it in all API calls
        value = var.domain != "" ? "https://${var.domain}" : (var.app_platform_url != "" ? "https://${var.app_platform_url}" : "https://${var.project_name}-${var.environment}.ondigitalocean.app")
      }

      env {
        key   = "VITE_PAYSTACK_PUBLIC_KEY"
        value = var.paystack_public_key
        type  = "SECRET"
      }
    }

    # Domain configuration (if provided)
    # Add both root domain and www subdomain
    dynamic "domain" {
      for_each = var.domain != "" ? [1] : []
      content {
        name = var.domain
        type = "PRIMARY"
      }
    }
    # Also add www subdomain explicitly (if root domain is configured)
    dynamic "domain" {
      for_each = var.domain != "" ? [1] : []
      content {
        name = "www.${var.domain}"
        type = "ALIAS"
      }
    }

    # Ingress routing - Backend handles /api/*, Frontend handles everything else
    # IMPORTANT: preserve_path_prefix ensures /api prefix is NOT stripped
    # Without this, /api/v1/health becomes /v1/health at the backend
    ingress {
      rule {
        component {
          name                 = "backend"
          preserve_path_prefix = true  # Keep /api prefix when forwarding to backend
        }
        match {
          path {
            prefix = "/api"
          }
        }
      }
      rule {
        component {
          name = "frontend"
        }
        match {
          path {
            prefix = "/"
          }
        }
      }
    }
  }
}

# DNS Domain Management
# Note: Digital Ocean App Platform automatically creates DNS records when you add a domain
# However, for root domains, you may need to manually configure DNS at your registrar
# 
# IMPORTANT: If your domain is NOT managed by Digital Ocean DNS:
# 1. Go to your domain registrar (where you bought grantpool.org)
# 2. Add a CNAME record: www -> grantpool-production-bhqbr.ondigitalocean.app
# 3. For root domain, you have two options:
#    a) Use ALIAS/ANAME record (if supported): @ -> grantpool-production-bhqbr.ondigitalocean.app
#    b) Use A record pointing to App Platform's load balancer IP (contact Digital Ocean support for IP)
#    c) Redirect root to www (recommended workaround)
#
# If domain IS managed by Digital Ocean DNS, the domain resource below will handle it
resource "digitalocean_domain" "grantpool" {
  count = var.domain != "" ? 1 : 0
  name  = var.domain
  # This will only work if the domain is added to Digital Ocean DNS first
  # Go to: https://cloud.digitalocean.com/networking/domains
  # Add the domain there, then this resource will manage it
}

# Outputs
output "app_url" {
  description = "URL of the deployed application"
  value       = digitalocean_app.grantpool.live_url
}

output "app_default_ingress" {
  description = "Default ingress URL for DNS configuration"
  value       = digitalocean_app.grantpool.default_ingress
}

output "neon_database_info" {
  description = "Neon database connection info (for reference)"
  value       = "Database: ${var.neon_db_name}, User: ${var.neon_user}"
  sensitive   = true
}

