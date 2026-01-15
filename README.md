# GrantPool

A full-stack grant evaluation platform that helps users determine if grants are worth applying to. Uses AI-powered assessments with a payment model

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

##
## Security

- Payment data is **never stored** - all payment processing is handled by Paystack
- JWT tokens for authentication
- Rate limiting on API endpoints
- Audit logging for security events
- See [Payment Security Architecture](./docs/architecture/PAYMENT_SECURITY_ARCHITECTURE.md) for details

## License

[Add your license here]
