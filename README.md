# GrantPool

A full-stack grant evaluation platform that helps users determine if grants are worth applying to. Uses AI-powered assessments with a payment model: **1 free assessment per user (lifetime), then $5 USD (or 20 GHS for Ghana) per assessment**.

## Quick Start

- **⚠️ CRITICAL CONFIGURATION**: See [CRITICAL_CONFIGURATION.md](./CRITICAL_CONFIGURATION.md) - **READ THIS FIRST**
- **System Overview**: See [SYSTEM_DESCRIPTION.md](./SYSTEM_DESCRIPTION.md)
- **Architecture Details**: See [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md)
- **Making Changes**: See [PRODUCTION_CHANGES_GUIDE.md](./PRODUCTION_CHANGES_GUIDE.md)

## Documentation Structure

### 📚 Essential Documentation (Root)
- **[SYSTEM_DESCRIPTION.md](./SYSTEM_DESCRIPTION.md)** - High-level system overview and user flow
- **[SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md)** - Technical architecture, deployment, and security
- **[PRODUCTION_CHANGES_GUIDE.md](./PRODUCTION_CHANGES_GUIDE.md)** - How to safely make changes in production

### 🔧 Operational Guides (`docs/operational/`)
- [API Routing Fix](./docs/operational/API_ROUTING_FIX.md) - Fixing API routing issues
- [DNS Migration Checklist](./docs/operational/DNS_MIGRATION_CHECKLIST.md) - DNS migration steps
- [DigitalOcean DNS Records Guide](./docs/operational/DIGITALOCEAN_DNS_RECORDS_GUIDE.md) - DNS configuration
- [Frontend Rebuild Guide](./docs/operational/FRONTEND_REBUILD_GUIDE.md) - Triggering frontend rebuilds
- [SendGrid Email Setup](./docs/operational/SENDGRID_EMAIL_SETUP.md) - Email service configuration
- [Deployment Guide](./docs/operational/DEPLOYMENT_GUIDE.md) - General deployment instructions
- [Setup Guide](./docs/operational/SETUP.md) - Initial setup instructions

### 🚀 Deployment (`docs/deployment/`)
- [Deployment Fix Summary](./docs/deployment/DEPLOYMENT_FIX_SUMMARY.md) - Recent deployment fixes
- [Deployment Issues Summary](./docs/deployment/DEPLOYMENT_ISSUES_SUMMARY.md) - Known deployment issues
- [Quick Fix Steps](./docs/deployment/QUICK_FIX_STEPS.md) - Quick troubleshooting steps

### 🏗️ Architecture (`docs/architecture/`)
- [Payment Security Architecture](./docs/architecture/PAYMENT_SECURITY_ARCHITECTURE.md) - Payment security design
- [Payment Data Security](./docs/architecture/PAYMENT_DATA_SECURITY.md) - Payment data handling

### 📦 Archived Documentation (`docs/archive/`)
Historical assessments, implementation summaries, and security audits. Kept for reference but not actively maintained.

## Project Structure

```
grantpool/
├── backend/              # FastAPI backend application
│   ├── app/             # Application code
│   │   ├── api/        # API endpoints
│   │   ├── core/       # Core utilities (config, security, middleware)
│   │   ├── db/         # Database models and connection
│   │   ├── services/   # Business logic services
│   │   └── utils/       # Utility functions
│   ├── alembic/        # Database migrations
│   └── main.py         # Application entry point
│
├── frontend/            # React frontend application
│   ├── src/
│   │   ├── components/ # React components
│   │   ├── contexts/   # React contexts (Auth)
│   │   ├── pages/      # Page components
│   │   └── services/   # API service layer
│   └── vite.config.js  # Vite configuration
│
├── infrastructure/      # Terraform infrastructure as code
│   ├── main_neon.tf    # Main Terraform configuration
│   ├── outputs.tf      # Terraform outputs
│   └── terraform.tfvars # Environment-specific variables
│
├── docs/                # Organized documentation
│   ├── operational/    # Operational guides
│   ├── deployment/     # Deployment-specific docs
│   ├── architecture/  # Architecture documentation
│   └── archive/        # Historical documentation
│
├── evaluator.py        # Standalone evaluator script
└── llm_evaluator.py    # LLM evaluator script
```

## Tech Stack

- **Backend**: FastAPI (Python), PostgreSQL (Neon), JWT auth, Paystack payments
- **Frontend**: React, Vite, React Query, Axios
- **Infrastructure**: Digital Ocean App Platform, Terraform
- **AI**: Claude API (Anthropic)
- **Email**: SendGrid

## Key Features

- ✅ AI-powered grant evaluation
- ✅ Payment processing (Paystack)
- ✅ User authentication (JWT)
- ✅ Project and grant management
- ✅ Evaluation history tracking
- ✅ Multi-currency support (USD/GHS)
- ✅ Email notifications (SendGrid)

## Development

See [PRODUCTION_CHANGES_GUIDE.md](./PRODUCTION_CHANGES_GUIDE.md) for detailed instructions on:
- Adding environment variables
- Making code changes
- Database migrations
- Deployment workflow

## Security

- Payment data is **never stored** - all payment processing is handled by Paystack
- JWT tokens for authentication
- Rate limiting on API endpoints
- Audit logging for security events
- See [Payment Security Architecture](./docs/architecture/PAYMENT_SECURITY_ARCHITECTURE.md) for details

## License

[Add your license here]
