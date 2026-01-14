# Production Changes Guide for GrantPool

This guide explains how to safely make changes to your deployed GrantPool system on Digital Ocean.

**⚠️ CRITICAL:** Before making any changes, read [CRITICAL_CONFIGURATION.md](./CRITICAL_CONFIGURATION.md) - it contains essential configuration requirements that MUST be correct.

## Table of Contents
1. [Critical Configuration (Read First!)](#critical-configuration)
2. [Adding/Changing Environment Variables](#environment-variables)
3. [Adding Frontend Features](#frontend-features)
4. [Adding Backend Features](#backend-features)
5. [Database Migrations](#database-migrations)
6. [Safe Deployment Workflow](#deployment-workflow)
7. [Troubleshooting Common Issues](#troubleshooting-common-issues)

---

## Critical Configuration

**⚠️ READ THIS FIRST** - These configurations are critical and must be correct:

1. **API Routing:**
   - Ingress must have `preserve_path_prefix = true` (see `infrastructure/main_neon.tf`)
   - Backend route prefix must be `/api/v1` (see `backend/main.py`)
   - **Never change one without the other** - they must match

2. **Frontend VITE_API_URL:**
   - Must be `https://grantpool.org` (NO `/api/v1` suffix)
   - Frontend code already includes `/api/v1` in all API calls
   - **After changing, frontend MUST be rebuilt** (Vite embeds at build time)

3. **HTTPS Redirect:**
   - Backend must check `X-Forwarded-Proto` header to prevent redirect loops
   - Already configured in `backend/main.py`

**For complete details, see [CRITICAL_CONFIGURATION.md](./CRITICAL_CONFIGURATION.md)**

---

## Environment Variables

### Adding a New Environment Variable

**Step 1: Update Terraform Configuration**

Edit `infrastructure/main_neon.tf` and add the environment variable to the appropriate service (backend or frontend):

```terraform
# For backend service
env {
  key   = "NEW_ENV_VAR_NAME"
  value = var.new_env_var_name
  type  = "SECRET"  # Use "SECRET" for sensitive data, omit for non-sensitive
}

# For frontend service (VITE_ prefix required)
env {
  key   = "VITE_NEW_FRONTEND_VAR"
  value = var.new_frontend_var
  type  = "SECRET"  # Frontend vars are exposed to browser, be careful!
}
```

**Step 2: Add Variable to Terraform Variables**

Edit `infrastructure/terraform.tfvars.example`:
```hcl
new_env_var_name = "your-value-here"
```

Edit `infrastructure/terraform.tfvars` (your actual values):
```hcl
new_env_var_name = "your-actual-secret-value"
```

**Step 3: Update Backend Code (if needed)**

If the backend needs to read this variable, update `backend/app/core/config.py`:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    NEW_ENV_VAR_NAME: str = ""
    
    class Config:
        env_file = ".env"
```

**Step 4: Apply Changes**

```bash
cd infrastructure
terraform plan  # Review changes
terraform apply  # Apply changes
```

**Important Notes:**
- Never commit `terraform.tfvars` (it's in .gitignore)
- Use `type = "SECRET"` for sensitive data (encrypted in Digital Ocean)
- Frontend env vars are public - never put secrets there
- **CRITICAL for VITE_API_URL:** Must NOT include `/api/v1` - see [CRITICAL_CONFIGURATION.md](./CRITICAL_CONFIGURATION.md)
- **Frontend env vars require rebuild:** Vite embeds env vars at build time, not runtime
- Changes take effect after deployment (automatic or manual)

---

## Frontend Features

### Adding a New Frontend Component

**Step 1: Develop Locally**

```bash
cd frontend
npm run dev  # Start local development server
```

**Step 2: Test Thoroughly**

- Test in multiple browsers
- Test responsive design
- Test with actual API endpoints (use local backend or staging)

**Step 3: Commit and Push**

```bash
git add frontend/src/components/YourNewComponent.jsx
git commit -m "Add new feature: YourComponent"
git push origin main
```

**Step 4: Deploy**

If `auto_deploy` is enabled in Terraform, deployment is automatic.
Otherwise, trigger deployment in Digital Ocean dashboard or:

```bash
cd infrastructure
terraform apply  # This will trigger a new deployment
```

**Best Practices:**
- Use feature branches for major changes
- Test with backend API locally first
- Use environment variables for API URLs (already configured)
- Follow React best practices (hooks, error handling, loading states)

---

## Backend Features

### Adding a New Backend Endpoint

**Step 1: Develop Locally**

```bash
cd backend
source .venv/bin/activate  # Activate virtual environment
uvicorn main:app --reload  # Start with auto-reload
```

**Step 2: Create API Endpoint**

Add to `backend/app/api/v1/your_feature.py`:

```python
from fastapi import APIRouter, Depends
from app.api.v1.auth import get_current_user
from app.db import models

router = APIRouter()

@router.get("/your-endpoint")
async def your_endpoint(current_user: models.User = Depends(get_current_user)):
    return {"message": "Your feature"}
```

Register in `backend/app/api/v1/__init__.py`:

```python
from app.api.v1 import your_feature
api_router.include_router(your_feature.router, prefix="/your-prefix", tags=["your-tag"])
```

**Step 3: Test Locally**

```bash
# Test with curl or use FastAPI docs
curl http://localhost:8000/api/v1/your-endpoint \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Step 4: Database Changes (if needed)**

If you need database changes:

```bash
cd backend
alembic revision --autogenerate -m "Add your feature tables"
# Review the generated migration file
alembic upgrade head  # Test locally
```

**Step 5: Commit and Deploy**

```bash
git add backend/app/api/v1/your_feature.py
git add backend/alembic/versions/xxx_your_migration.py
git commit -m "Add backend feature: your feature"
git push origin main
cd infrastructure
terraform apply
```

---

## Database Migrations

### Creating and Running Migrations

**Step 1: Create Migration**

```bash
cd backend
alembic revision --autogenerate -m "Description of changes"
```

**Step 2: Review Migration File**

Always review the generated migration in `backend/alembic/versions/`:
- Check for data loss risks
- Verify column types
- Check for index creation/dropping
- Ensure foreign key constraints are correct

**Step 3: Test Locally**

```bash
# Test migration up
alembic upgrade head

# Test migration down (rollback)
alembic downgrade -1

# Test migration up again
alembic upgrade head
```

**Step 4: Deploy**

Migrations run automatically on deployment via `backend/start.sh`:
```bash
alembic upgrade head
```

**Important Notes:**
- Migrations run on every deployment (in start.sh)
- Always backup database before major migrations
- Test migrations on staging first (if you have one)
- Consider data migrations for existing data

---

## LLM Services Integration

### Adding LLM Service (e.g., Claude, OpenAI)

**Step 1: Add API Key to Terraform**

```hcl
# In infrastructure/main_neon.tf (backend service)
env {
  key   = "ANTHROPIC_API_KEY"  # Already exists for Claude
  value = var.anthropic_api_key
  type  = "SECRET"
}

# Or for OpenAI
env {
  key   = "OPENAI_API_KEY"
  value = var.openai_api_key
  type  = "SECRET"
}
```

**Step 2: Create Service**

Create `backend/app/services/llm_service.py`:

```python
from anthropic import Anthropic
from app.core.config import settings

class LLMService:
    def __init__(self):
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    
    async def generate_response(self, prompt: str):
        message = self.client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
```

**Step 3: Use in API Endpoint**

```python
from app.services.llm_service import LLMService

@router.post("/llm-endpoint")
async def llm_endpoint(request: Request):
    llm_service = LLMService()
    result = await llm_service.generate_response(request.json()["prompt"])
    return {"result": result}
```

**Step 4: Deploy**

Follow backend feature deployment steps above.

---

## Safe Deployment Workflow

### Recommended Workflow

**1. Development Environment**

```bash
# Always test locally first
cd backend && uvicorn main:app --reload
cd frontend && npm run dev
```

**2. Feature Branch (for major changes)**

```bash
git checkout -b feature/your-feature-name
# Make changes
git commit -m "Add feature: description"
git push origin feature/your-feature-name
# Create PR, review, merge to main
```

**3. Staging/Testing (Optional but Recommended)**

- Set up a separate Digital Ocean app for staging
- Use a separate database (Neon has branching)
- Test changes in staging before production

**4. Production Deployment**

```bash
# Review what will change
cd infrastructure
terraform plan

# Apply changes
terraform apply

# Monitor deployment
# Check Digital Ocean dashboard for deployment status
# Check logs for errors
```

### Rollback Strategy

**If Deployment Fails:**

1. **Automatic Rollback**: Digital Ocean automatically rolls back on health check failure

2. **Manual Rollback via Git:**
```bash
# Revert commit
git revert HEAD
git push origin main
terraform apply  # Redeploy previous version
```

3. **Database Rollback:**
```bash
# Connect to database and run
alembic downgrade -1  # Rollback last migration
```

### Monitoring After Deployment

1. **Check Application Logs**
   - Digital Ocean Dashboard → Your App → Runtime Logs
   - Look for errors, warnings

2. **Test Critical Paths**
   - User registration/login
   - Payment flow
   - API endpoints
   - Database operations

3. **Monitor Metrics**
   - Response times
   - Error rates
   - Database connections

---

## Quick Reference

### Common Commands

```bash
# Local Development
cd backend && uvicorn main:app --reload
cd frontend && npm run dev

# Database Migrations
cd backend && alembic revision --autogenerate -m "description"
cd backend && alembic upgrade head

# Deploy Changes
cd infrastructure && terraform plan
cd infrastructure && terraform apply

# Check Deployment Status
# Visit: https://cloud.digitalocean.com/apps
```

### File Locations

- **Terraform Config**: `infrastructure/main_neon.tf`
- **Environment Variables**: `infrastructure/terraform.tfvars` (not in git)
- **Backend Code**: `backend/app/`
- **Frontend Code**: `frontend/src/`
- **Database Migrations**: `backend/alembic/versions/`
- **Dockerfiles**: `backend/Dockerfile`, `frontend/Dockerfile`

### Important Reminders

✅ **DO:**
- Test locally before deploying
- Review Terraform plan before applying
- Use environment variables for configuration
- Keep secrets in `terraform.tfvars` (not committed)
- Use database migrations for schema changes
- Monitor logs after deployment

❌ **DON'T:**
- Commit secrets to git
- Skip testing
- Deploy without reviewing changes
- Make database changes without migrations
- Deploy on Fridays (if possible) 😄

---

## Example: Adding Paystack Webhook Secret

```bash
# 1. Edit infrastructure/main_neon.tf (already done for Paystack)
# 2. Edit infrastructure/terraform.tfvars
paystack_webhook_secret = "whsec_your_actual_webhook_secret"

# 3. Apply
cd infrastructure
terraform plan  # Verify only webhook secret changes
terraform apply

# 4. Verify in Digital Ocean dashboard that env var is set
# 5. Test webhook endpoint
```

---

## Troubleshooting Common Issues

### Issue: API Returns HTML Instead of JSON

**Symptoms:**
- API calls return HTML (404 page) instead of JSON
- Browser console shows: "API returned HTML instead of JSON"

**Causes:**
1. Ingress not preserving path prefix
2. Backend route prefix mismatch
3. Request falling through to frontend

**Fix:**
1. Verify `preserve_path_prefix = true` in `infrastructure/main_neon.tf`
2. Verify backend route prefix is `/api/v1` in `backend/main.py`
3. Run `terraform apply` to update ingress
4. See [API Routing Fix Guide](./docs/operational/API_ROUTING_FIX.md)

### Issue: Duplicate `/api/v1/api/v1` in URLs

**Symptoms:**
- Browser console shows: `POST https://grantpool.org/api/v1/api/v1/auth/login`
- Backend logs show: `POST /api/v1/api/v1/auth/login 404`

**Causes:**
- `VITE_API_URL` includes `/api/v1` when it shouldn't
- Frontend build has old embedded URL

**Fix:**
1. Check `VITE_API_URL` in Terraform - should be `https://grantpool.org` (no `/api/v1`)
2. Run `terraform apply` to update env var
3. **Trigger frontend rebuild** (make code change and push, or redeploy)
4. Frontend normalization code will auto-fix, but rebuild is required
5. See [Frontend Rebuild Guide](./docs/operational/FRONTEND_REBUILD_GUIDE.md)

### Issue: Infinite Redirect Loop (ERR_TOO_MANY_REDIRECTS)

**Symptoms:**
- Browser shows: `net::ERR_TOO_MANY_REDIRECTS`
- Backend logs show repeated `301 Moved Permanently`

**Causes:**
- Backend redirecting HTTP to HTTPS, but proxy already provides HTTPS
- Not checking `X-Forwarded-Proto` header

**Fix:**
1. Verify backend checks `X-Forwarded-Proto` header (already fixed in `backend/main.py`)
2. Backend should use: `forwarded_proto = request.headers.get("x-forwarded-proto")`
3. See [CRITICAL_CONFIGURATION.md](./CRITICAL_CONFIGURATION.md) for details

### Issue: Frontend Changes Not Appearing After Deployment

**Symptoms:**
- Code changes pushed but frontend still shows old behavior
- Environment variable changes not taking effect

**Causes:**
- Frontend build cache
- Vite env vars embedded at build time

**Fix:**
1. **Hard refresh browser:** Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)
2. **Clear browser cache**
3. **Verify deployment completed:** Check Digital Ocean dashboard
4. **For env var changes:** Frontend MUST be rebuilt (make code change and push)
5. See [Frontend Rebuild Guide](./docs/operational/FRONTEND_REBUILD_GUIDE.md)

### Issue: 401 Unauthorized on Login

**Symptoms:**
- Login returns `401 Unauthorized`
- Registration works but login fails

**Causes:**
- Wrong email/password
- User account inactive
- JWT token issues

**Fix:**
1. Verify credentials are correct
2. Check backend logs for specific error message
3. Verify user account exists and is active
4. Check JWT secret key is set correctly

### Issue: 400 Bad Request on Registration

**Symptoms:**
- Registration returns `400 Bad Request`
- No specific error message shown

**Causes:**
- Email already registered
- Validation errors (password too short, invalid email)
- Missing required fields

**Fix:**
1. Check backend logs for specific validation error
2. Verify email format is valid
3. Verify password meets requirements (min 6 characters)
4. Check if email already exists in database

---

## Need Help?

- **Critical Configuration:** See [CRITICAL_CONFIGURATION.md](./CRITICAL_CONFIGURATION.md)
- **API Routing Issues:** See [API Routing Fix Guide](./docs/operational/API_ROUTING_FIX.md)
- **Frontend Rebuilds:** See [Frontend Rebuild Guide](./docs/operational/FRONTEND_REBUILD_GUIDE.md)
- **Digital Ocean Logs:** Check App Platform → Runtime Logs
- **Terraform Docs:** https://registry.terraform.io/providers/digitalocean/digitalocean/latest/docs
- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **React/Vite Docs:** https://vitejs.dev/



