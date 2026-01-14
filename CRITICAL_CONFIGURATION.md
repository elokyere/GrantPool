# Critical Configuration Guide - GrantPool

**⚠️ READ THIS FIRST** - This document contains critical configuration requirements that MUST be correct for the system to function. Misconfiguration here will cause production failures.

## Table of Contents
1. [API Routing Configuration](#api-routing-configuration)
2. [Frontend Environment Variables](#frontend-environment-variables)
3. [Backend Route Prefixes](#backend-route-prefixes)
4. [HTTPS Redirect Configuration](#https-redirect-configuration)
5. [Deployment Checklist](#deployment-checklist)
6. [Common Configuration Mistakes](#common-configuration-mistakes)

---

## API Routing Configuration

### ⚠️ CRITICAL: Digital Ocean Ingress + Backend Route Prefix

**The Problem:**
Digital Ocean App Platform's ingress **strips path prefixes by default**. This causes route mismatches if not configured correctly.

**The Solution:**
1. **Ingress must preserve path prefix:**
   ```hcl
   # infrastructure/main_neon.tf
   ingress {
     rule {
       component {
         name                 = "backend"
         preserve_path_prefix = true  # ⚠️ REQUIRED - DO NOT REMOVE
       }
       match {
         path {
           prefix = "/api"
         }
       }
     }
   }
   ```

2. **Backend route prefix MUST match:**
   ```python
   # backend/main.py
   # ⚠️ MUST be /api/v1 (not /v1) because ingress preserves /api prefix
   app.include_router(api_router, prefix="/api/v1")
   ```

**Why This Matters:**
- Without `preserve_path_prefix=true`: `/api/v1/health` → backend receives `/v1/health` → 404 Not Found
- With `preserve_path_prefix=true`: `/api/v1/health` → backend receives `/api/v1/health` → ✅ Works
- Backend route prefix must be `/api/v1` to match the preserved path

**Verification:**
```bash
# Should return JSON, not HTML
curl https://grantpool.org/api/v1/health
# Expected: {"status":"healthy"}
```

---

## Frontend Environment Variables

### ⚠️ CRITICAL: VITE_API_URL Configuration

**The Problem:**
Vite embeds environment variables at **build time**, not runtime. If `VITE_API_URL` includes `/api/v1`, it causes duplicate paths: `/api/v1/api/v1/auth/login`.

**The Solution:**

1. **Terraform Configuration:**
   ```hcl
   # infrastructure/main_neon.tf
   env {
     key   = "VITE_API_URL"
     # ⚠️ MUST NOT include /api/v1 - frontend code already includes it
     value = "https://grantpool.org"  # ✅ Correct
     # value = "https://grantpool.org/api/v1"  # ❌ WRONG - causes duplicates
   }
   ```

2. **Frontend Normalization (Safety Net):**
   ```javascript
   // frontend/src/services/api.js
   // Automatically strips /api/v1 if accidentally included
   const rawBaseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
   let normalizedBaseURL = rawBaseURL.replace(/\/api\/v1\/?$/, '')
   normalizedBaseURL = normalizedBaseURL.replace(/\/+$/, '')
   ```

**Why This Matters:**
- Frontend code calls: `api.post('/api/v1/auth/login', ...)`
- If `VITE_API_URL = "https://grantpool.org/api/v1"`:
  - Final URL: `https://grantpool.org/api/v1` + `/api/v1/auth/login` = ❌ `/api/v1/api/v1/auth/login`
- If `VITE_API_URL = "https://grantpool.org"`:
  - Final URL: `https://grantpool.org` + `/api/v1/auth/login` = ✅ `/api/v1/auth/login`

**After Changing VITE_API_URL:**
- ⚠️ **Frontend MUST be rebuilt** - Vite embeds env vars at build time
- Changes take effect only after new deployment
- See [Frontend Rebuild Guide](./docs/operational/FRONTEND_REBUILD_GUIDE.md)

**Verification:**
Check browser console after deployment:
```javascript
[API Config] Raw VITE_API_URL: https://grantpool.org  // ✅ Should NOT have /api/v1
[API Config] Normalized baseURL: https://grantpool.org
[API Config] Example full URL will be: https://grantpool.org/api/v1/auth/login
```

---

## Backend Route Prefixes

### ⚠️ CRITICAL: Route Prefix Must Match Ingress

**Configuration:**
```python
# backend/main.py
# ⚠️ MUST be /api/v1 because ingress preserves /api prefix
app.include_router(api_router, prefix="/api/v1")
```

**Why `/api/v1` and not `/v1`:**
- Ingress rule: `preserve_path_prefix = true` with `prefix = "/api"`
- Request: `https://grantpool.org/api/v1/auth/login`
- Ingress forwards: `/api/v1/auth/login` (preserves `/api`)
- Backend must match: `/api/v1/auth/login` → route prefix `/api/v1` ✅

**If you change ingress configuration:**
- If you remove `preserve_path_prefix`, backend prefix must be `/v1`
- If you keep `preserve_path_prefix`, backend prefix must be `/api/v1`
- **Never mix them** - they must match

---

## HTTPS Redirect Configuration

### ⚠️ CRITICAL: X-Forwarded-Proto Header

**The Problem:**
When running behind Cloudflare/DigitalOcean proxy, the app server sees requests as `http` even though the browser uses `https`, causing infinite redirect loops.

**The Solution:**
```python
# backend/main.py
@app.middleware("http")
async def https_redirect_middleware(request: Request, call_next):
    """Redirect HTTP to HTTPS in production."""
    if request.url.path == "/health":
        return await call_next(request)
    
    # ⚠️ CRITICAL: Check X-Forwarded-Proto header from proxy
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").lower()
    effective_scheme = forwarded_proto or request.url.scheme
    
    if not settings.DEBUG and effective_scheme != "https":
        https_url = str(request.url).replace("http://", "https://", 1)
        return RedirectResponse(url=https_url, status_code=301)
    return await call_next(request)
```

**Why This Matters:**
- Without X-Forwarded-Proto check: `https://grantpool.org/api/v1/auth/login` → backend sees `http` → redirects to `https` → infinite loop
- With X-Forwarded-Proto check: `https://grantpool.org/api/v1/auth/login` → backend sees `x-forwarded-proto: https` → ✅ No redirect

**Verification:**
```bash
# Should NOT redirect (already HTTPS)
curl -I https://grantpool.org/api/v1/health
# Should return 200, not 301
```

---

## Deployment Checklist

### Before Every Deployment

- [ ] **Verify Terraform ingress configuration:**
  - [ ] `preserve_path_prefix = true` is set for backend ingress rule
  - [ ] Ingress rule matches `/api` prefix

- [ ] **Verify backend route prefix:**
  - [ ] `app.include_router(api_router, prefix="/api/v1")` in `backend/main.py`
  - [ ] Matches ingress configuration

- [ ] **Verify frontend VITE_API_URL:**
  - [ ] In Terraform: `VITE_API_URL = "https://grantpool.org"` (no `/api/v1`)
  - [ ] Frontend normalization code is present in `frontend/src/services/api.js`

- [ ] **Verify HTTPS redirect:**
  - [ ] Backend checks `X-Forwarded-Proto` header
  - [ ] No infinite redirect loops

- [ ] **After deployment:**
  - [ ] Test: `curl https://grantpool.org/api/v1/health` returns JSON
  - [ ] Check browser console for correct API URL logs
  - [ ] Test login/register endpoints
  - [ ] Verify no duplicate `/api/v1/api/v1` in requests

---

## Common Configuration Mistakes

### ❌ Mistake 1: Missing preserve_path_prefix
```hcl
# WRONG
ingress {
  rule {
    component {
      name = "backend"  # Missing preserve_path_prefix
    }
  }
}
```
**Result:** Backend receives `/v1/health` instead of `/api/v1/health` → 404 errors

### ❌ Mistake 2: Wrong backend route prefix
```python
# WRONG - if preserve_path_prefix=true
app.include_router(api_router, prefix="/v1")
```
**Result:** Routes don't match → 404 errors

### ❌ Mistake 3: VITE_API_URL includes /api/v1
```hcl
# WRONG
env {
  key   = "VITE_API_URL"
  value = "https://grantpool.org/api/v1"  # ❌ Causes duplicates
}
```
**Result:** Requests go to `/api/v1/api/v1/auth/login` → 404 errors

### ❌ Mistake 4: Not rebuilding frontend after VITE_API_URL change
**Result:** Old build still has wrong URL embedded → errors persist

### ❌ Mistake 5: Not checking X-Forwarded-Proto
```python
# WRONG
if request.url.scheme != "https":  # Doesn't account for proxy
```
**Result:** Infinite redirect loops

---

## Quick Reference

| Configuration | Value | Location |
|--------------|-------|----------|
| Ingress preserve_path_prefix | `true` | `infrastructure/main_neon.tf` |
| Backend route prefix | `/api/v1` | `backend/main.py` |
| VITE_API_URL | `https://grantpool.org` (no `/api/v1`) | `infrastructure/main_neon.tf` |
| HTTPS redirect | Check `X-Forwarded-Proto` | `backend/main.py` |

---

## Related Documentation

- [API Routing Fix Guide](./docs/operational/API_ROUTING_FIX.md)
- [Frontend Rebuild Guide](./docs/operational/FRONTEND_REBUILD_GUIDE.md)
- [Production Changes Guide](./PRODUCTION_CHANGES_GUIDE.md)
- [System Architecture](./SYSTEM_ARCHITECTURE.md)

---

**Last Updated:** January 14, 2025  
**Status:** Production-ready configuration verified
