# GrantPool System Architecture & Deployment Guide

## System Overview

GrantPool is a full-stack grant evaluation platform that helps users determine if grants are worth applying to. The system uses AI-powered assessments with a payment model: 1 free assessment per user, then $5 USD (or 20 GHS for Ghana) per assessment.

---

## How The System Works

### Architecture Components

1. **Backend (FastAPI)**
   - Location: `backend/`
   - Framework: FastAPI (Python)
   - Database: PostgreSQL (via Neon)
   - Authentication: JWT with bcrypt
   - Payment: Stripe integration
   - AI: Claude API for LLM evaluations

2. **Frontend (React)**
   - Location: `frontend/`
   - Framework: React + Vite
   - UI: Modern responsive design
   - State: React Query for API calls

3. **Database (Neon PostgreSQL)**
   - Managed PostgreSQL database
   - Connection via connection string
   - Migrations via Alembic

4. **Infrastructure (Terraform)**
   - Location: `infrastructure/`
   - Provider: Digital Ocean App Platform
   - Database: Neon (external, not Digital Ocean)

---

## API Routing Architecture - CRITICAL

### ⚠️ Important: This configuration is critical for the system to function

The routing between frontend, ingress, and backend must be correctly configured:

```
Browser Request: https://grantpool.org/api/v1/auth/login
         ↓
Digital Ocean Ingress (preserve_path_prefix=true)
         ↓
Backend receives: /api/v1/auth/login
         ↓
FastAPI route: /api/v1/auth/login ✅
```

### Configuration Requirements

1. **Digital Ocean Ingress:**
   ```hcl
   # infrastructure/main_neon.tf
   ingress {
     rule {
       component {
         name                 = "backend"
         preserve_path_prefix = true  # ⚠️ REQUIRED
       }
       match {
         path {
           prefix = "/api"
         }
       }
     }
   }
   ```

2. **Backend Route Prefix:**
   ```python
   # backend/main.py
   # ⚠️ MUST be /api/v1 (not /v1) because ingress preserves /api
   app.include_router(api_router, prefix="/api/v1")
   ```

3. **Frontend API Base URL:**
   ```hcl
   # infrastructure/main_neon.tf
   env {
     key   = "VITE_API_URL"
     value = "https://grantpool.org"  # ⚠️ NO /api/v1 suffix
   }
   ```
   ```javascript
   // frontend/src/services/api.js
   // Frontend calls: api.post('/api/v1/auth/login', ...)
   // Final URL: https://grantpool.org + /api/v1/auth/login ✅
   ```

### Why This Matters

- **Without `preserve_path_prefix=true`:** Ingress strips `/api`, backend receives `/v1/auth/login` → 404
- **Wrong backend prefix:** If backend uses `/v1` but ingress preserves `/api`, routes don't match → 404
- **VITE_API_URL with `/api/v1`:** Causes duplicate paths → `/api/v1/api/v1/auth/login` → 404

**For complete details, see [CRITICAL_CONFIGURATION.md](./CRITICAL_CONFIGURATION.md)**

---

## Payment Data Security - CRITICAL

### ✅ What We DO NOT Store

**The system NEVER stores sensitive payment information:**
- ❌ Credit card numbers
- ❌ CVV codes
- ❌ Card expiration dates
- ❌ Full payment method details
- ❌ Billing addresses (except country for currency)

### ✅ What We DO Store

**Only non-sensitive payment metadata:**
- ✅ `stripe_payment_intent_id` - Stripe's payment intent ID (not card info)
- ✅ `stripe_customer_id` - Stripe's customer ID (not card info)
- ✅ `amount` - Payment amount in cents
- ✅ `currency` - Currency code (USD, GHS)
- ✅ `status` - Payment status (pending, succeeded, failed)
- ✅ `country_code` - User's country (for currency determination)

### Payment Flow (No Card Data Stored)

1. **User initiates payment:**
   - Frontend calls `POST /api/v1/payments/create-intent`
   - Backend creates Stripe Payment Intent
   - Returns `client_secret` to frontend

2. **User enters card details:**
   - **Card details go DIRECTLY to Stripe via Stripe.js**
   - **Our servers NEVER see card numbers**
   - Payment processed by Stripe

3. **Payment succeeds:**
   - Stripe sends webhook to our backend
   - We update payment status to "succeeded"
   - We store: `payment_intent_id`, `amount`, `currency`, `status`
   - **NO card details stored**

4. **After payment:**
   - Payment metadata stored in database
   - Card details remain ONLY in Stripe (PCI compliant)
   - Our database has no sensitive payment data

### Database Schema - Payment Tables

```sql
-- payments table - NO sensitive data
CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    stripe_payment_intent_id VARCHAR(255),  -- Stripe ID, not card info
    stripe_customer_id VARCHAR(255),       -- Stripe customer ID
    amount INTEGER,                         -- Amount in cents
    currency VARCHAR(3),                    -- USD, GHS
    status VARCHAR(50),                     -- pending, succeeded, failed
    country_code VARCHAR(2),                -- Country only
    metadata JSONB,                         -- Additional Stripe metadata (no card data)
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**Key Point:** The `metadata` field contains Stripe's payment intent metadata (user_id, assessment_count, etc.) - NOT card details. Stripe handles all PCI compliance.

---

## Database Configuration - Neon

### Current Setup

The system is configured to use **Neon PostgreSQL** (not Digital Ocean's managed database).

### Database Connection

**Location:** `backend/app/core/config.py`

```python
DATABASE_URL: str  # Neon connection string
POSTGRES_USER: str
POSTGRES_PASSWORD: str
POSTGRES_DB: str
```

### Neon Database Setup

1. **Create Neon Account:**
   - Go to https://neon.tech
   - Create account and project
   - Create PostgreSQL database

2. **Get Connection String:**
   - Format: `postgresql://user:password@host/database?sslmode=require`
   - Neon provides this in dashboard

3. **Configure Environment:**
   ```bash
   DATABASE_URL=postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/grantpool?sslmode=require
   POSTGRES_USER=your_user
   POSTGRES_PASSWORD=your_password
   POSTGRES_DB=grantpool
   ```

### Data Safety with Neon

- ✅ **Automatic Backups:** Neon provides automatic backups
- ✅ **Point-in-Time Recovery:** Can restore to any point in time
- ✅ **SSL/TLS:** All connections encrypted
- ✅ **Branching:** Can create database branches for testing
- ✅ **No Data Loss:** Neon ensures data durability

---

## Deployment to Digital Ocean

### Prerequisites

1. **Digital Ocean Account**
   - Sign up at https://digitalocean.com
   - Get API token from https://cloud.digitalocean.com/account/api/tokens

2. **Terraform** (>= 1.0)
   ```bash
   brew install terraform  # macOS
   # or download from https://terraform.io/downloads
   ```

3. **Required API Keys:**
   - ✅ Digital Ocean API token
   - ⚠️ Claude API key (ANTHROPIC_API_KEY) - **REQUIRED for LLM evaluations**
   - ⚠️ Stripe API keys - **REQUIRED for payments**
     - STRIPE_SECRET_KEY
     - STRIPE_PUBLISHABLE_KEY
     - STRIPE_WEBHOOK_SECRET

### Deployment Steps

1. **Configure Terraform:**
   ```bash
   cd infrastructure
   cp terraform.tfvars.example terraform.tfvars
   ```

2. **Edit `terraform.tfvars`:**
   ```hcl
   do_token = "your-digital-ocean-token"
   project_name = "grantpool"
   region = "nyc1"
   environment = "production"
   
   # Neon Database (NOT Digital Ocean database)
   # These come from Neon dashboard
   # Note: Terraform will NOT create Neon database - create it manually
   
   # API Keys
   secret_key = "generate-with-openssl-rand-hex-32"
   anthropic_api_key = "sk-ant-..."  # REQUIRED
   stripe_secret_key = "sk_live_..."  # REQUIRED
   stripe_publishable_key = "pk_live_..."  # REQUIRED
   stripe_webhook_secret = "whsec_..."  # REQUIRED
   
   # Neon Database Connection (set in App Platform env vars)
   # These are set as environment variables, not Terraform variables
   ```

3. **Update Terraform for Neon:**
   - The current `main.tf` creates Digital Ocean database
   - **We need to remove that and use Neon instead**
   - See updated configuration below

4. **Initialize Terraform:**
   ```bash
   terraform init
   ```

5. **Plan Deployment:**
   ```bash
   terraform plan
   ```

6. **Deploy:**
   ```bash
   terraform apply
   ```

### Important: Neon Database Configuration

**The Terraform config needs to be updated** because:
- Current config creates Digital Ocean managed database
- We want to use Neon instead
- Neon database must be created manually
- Connection string set as environment variable

---

## Updated Terraform Configuration for Neon

The `infrastructure/main.tf` needs these changes:

1. **Remove Digital Ocean database creation**
2. **Add Neon connection string as environment variable**
3. **Keep App Platform configuration**

---

## System Flow

### 1. User Registration
```
User → Frontend → POST /api/v1/auth/register
  → Backend creates user
  → Stores: email, hashed_password, country_code
  → Returns: user_id, email
```

### 2. First Assessment (Free)
```
User → Frontend → POST /api/v1/evaluations/
  → Backend checks: free_assessment_available = true
  → Creates evaluation (LLM or rule-based)
  → Marks free_assessment_used = true
  → Creates AssessmentPurchase (type="free")
  → Returns: evaluation results
```

### 3. Subsequent Assessment (Paid)
```
User → Frontend → POST /api/v1/payments/create-intent
  → Backend creates Stripe Payment Intent
  → Returns: client_secret, payment_intent_id
  
User → Frontend → Stripe.js collects card details
  → Card details go DIRECTLY to Stripe (not our servers)
  → Stripe processes payment
  
Stripe → Webhook → POST /api/v1/webhooks/stripe
  → Backend verifies webhook signature
  → Updates payment status = "succeeded"
  → NO card details stored
  
User → Frontend → POST /api/v1/evaluations/ (with payment_intent_id)
  → Backend verifies payment succeeded
  → Creates evaluation
  → Links payment to assessment
  → Returns: evaluation results
```

### 4. Viewing Assessments
```
User → Frontend → GET /api/v1/evaluations/{id}
  → Backend checks: AssessmentPurchase exists?
  → If yes: Returns evaluation
  → If no: Returns 403 Forbidden
```

---

## Security Features

### 1. Payment Security
- ✅ **No card data stored** - Stripe handles all PCI compliance
- ✅ **Webhook signature verification** - Prevents fake webhooks
- ✅ **Payment intent validation** - Verifies with Stripe before creating assessment

### 2. Authentication Security
- ✅ **JWT tokens** - Secure token-based auth
- ✅ **Bcrypt password hashing** - Passwords never stored in plain text
- ✅ **Rate limiting** - Prevents brute force attacks
  - Login: 5 attempts per 15 minutes
  - Registration: 3 per hour

### 3. Data Security
- ✅ **SQL injection protection** - SQLAlchemy ORM
- ✅ **Input validation** - Pydantic models
- ✅ **Audit logging** - All requests logged
- ✅ **HTTPS only** - All connections encrypted

### 4. Database Security (Neon)
- ✅ **SSL/TLS required** - All connections encrypted
- ✅ **Automatic backups** - Data protected
- ✅ **Connection string security** - Stored as environment variable

---

## Environment Variables Required

### Backend Environment Variables

```bash
# Database (Neon)
DATABASE_URL=postgresql://user:password@ep-xxx.neon.tech/grantpool?sslmode=require
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=grantpool

# Security
SECRET_KEY=<generate-strong-key>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# API Keys (REQUIRED)
ANTHROPIC_API_KEY=sk-ant-...  # For LLM evaluations
STRIPE_SECRET_KEY=sk_live_...  # For payments
STRIPE_PUBLISHABLE_KEY=pk_live_...  # For frontend
STRIPE_WEBHOOK_SECRET=whsec_...  # For webhook verification

# Payment Pricing
USD_PRICE=500  # $5.00 in cents
GHS_PRICE=2000  # 20.00 GHS in pesewas

# Application
ENVIRONMENT=production
DEBUG=false
CORS_ORIGINS=https://yourdomain.com
```

---

## Deployment Checklist

### Before Deployment

- [ ] Create Neon database account
- [ ] Create Neon PostgreSQL database
- [ ] Get Neon connection string
- [ ] Get Claude API key
- [ ] Get Stripe API keys (test mode first)
- [ ] Set up Stripe webhook endpoint
- [ ] Generate strong SECRET_KEY
- [ ] Update Terraform variables

### During Deployment

- [ ] Run `terraform init`
- [ ] Review `terraform plan`
- [ ] Apply Terraform configuration
- [ ] Verify App Platform deployment
- [ ] Check database connection
- [ ] Run migrations: `alembic upgrade head`
- [ ] Test API endpoints
- [ ] Test payment flow (test mode)

### After Deployment

- [ ] Verify HTTPS is working
- [ ] Test user registration
- [ ] Test free assessment
- [ ] Test payment flow
- [ ] Verify webhook is receiving events
- [ ] Check audit logs
- [ ] Monitor error logs
- [ ] Set up monitoring/alerts

---

## What Gets Deployed

### Digital Ocean App Platform

1. **Backend Service**
   - FastAPI application
   - Runs on port 8000
   - Health check: `/health`
   - Auto-scales based on traffic

2. **Frontend Service**
   - React application
   - Served via Nginx
   - Runs on port 80
   - Static files served

3. **Environment Variables**
   - All secrets stored securely
   - Not exposed in code
   - Managed via App Platform

### Neon Database (External)

- PostgreSQL database
- Managed by Neon
- Connection via connection string
- Automatic backups enabled
- SSL/TLS required

---

## Cost Estimation

### Digital Ocean App Platform
- Backend (basic-xxs): ~$5/month
- Frontend (basic-xxs): ~$5/month
- **Total App Platform: ~$10/month**

### Neon Database
- Free tier: 0.5 GB storage, shared CPU
- Paid tier: Starts at ~$19/month for dedicated
- **Recommended: Start with free tier, upgrade as needed**

### Total Estimated Cost
- **Minimum: ~$10/month** (App Platform + Neon free tier)
- **Recommended: ~$29/month** (App Platform + Neon paid tier)

---

## Next Steps

1. **Update Terraform** to use Neon (remove DO database)
2. **Set up Neon database** manually
3. **Configure environment variables** in App Platform
4. **Deploy with Terraform**
5. **Test payment flow** in test mode
6. **Switch to production** Stripe keys when ready

---

## Important Notes

1. **Payment Data:** Never stored on our platform - Stripe handles all card data
2. **Database:** Use Neon for managed PostgreSQL with automatic backups
3. **API Keys:** Required before deployment (Claude + Stripe)
4. **Webhooks:** Must be publicly accessible for Stripe
5. **HTTPS:** Required for production (App Platform provides automatically)
















