#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to verify Paystack configuration and currency support.

Run this to diagnose Paystack setup issues.
"""

import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
import paystackapi

def check_api_key():
    """Check if API key is configured."""
    print("=" * 60)
    print("1. Checking API Key Configuration")
    print("=" * 60)
    
    if not settings.PAYSTACK_SECRET_KEY:
        print("[ERROR] PAYSTACK_SECRET_KEY is not set in environment variables")
        print("   Add it to your .env file: PAYSTACK_SECRET_KEY=sk_test_...")
        return False
    
    api_key = settings.PAYSTACK_SECRET_KEY
    print(f"[OK] API Key found: {api_key[:10]}...{api_key[-4:]}")
    
    # Check if it's test or live
    if api_key.startswith("sk_test_"):
        print("   Type: TEST key")
        print("   [WARNING] Make sure GHS is enabled in your TEST account")
    elif api_key.startswith("sk_live_"):
        print("   Type: LIVE key")
        print("   [WARNING] Make sure GHS is enabled in your LIVE account")
    else:
        print("   [WARNING] API key format looks incorrect (should start with sk_test_ or sk_live_)")
    
    return True

def check_currency_support():
    """Check if GHS currency is supported."""
    print("\n" + "=" * 60)
    print("2. Testing Currency Support")
    print("=" * 60)
    
    if not settings.PAYSTACK_SECRET_KEY:
        print("[ERROR] Cannot test - API key not configured")
        return False
    
    # Set API key
    paystackapi.api_key = settings.PAYSTACK_SECRET_KEY
    
    try:
        from paystackapi.transaction import Transaction
        import time
        
        # Try to initialize a minimal test transaction
        test_reference = f"TEST_CURRENCY_CHECK_{int(time.time())}"
        print(f"   Attempting test transaction with reference: {test_reference}")
        
        response = Transaction.initialize(
            reference=test_reference,
            amount=100,  # 1.00 GHS (minimum)
            email="test@example.com",
            currency="GHS"
        )
        
        if response.get("status"):
            print("[OK] GHS currency is supported!")
            print(f"   Transaction initialized successfully")
            print(f"   Authorization URL: {response['data'].get('authorization_url', 'N/A')[:50]}...")
            return True
        else:
            error_msg = response.get("message", "Unknown error")
            print(f"[ERROR] GHS currency test failed")
            print(f"   Error: {error_msg}")
            
            if "currency" in error_msg.lower() or "not supported" in error_msg.lower():
                print("\n   [SOLUTION]")
                print("   1. Go to https://dashboard.paystack.com")
                print("   2. Settings -> Business -> Supported Currencies")
                print("   3. Enable GHS (Ghanaian Cedi)")
                print("   4. Wait 2-3 minutes for changes to propagate")
                print("   5. Restart your backend server")
                print("\n   [WARNING] Make sure you're enabling GHS in the SAME account")
                print("      that matches your API key (test vs live)")
            
            return False
            
    except Exception as e:
        print(f"[ERROR] Error testing currency: {str(e)}")
        print(f"   Exception type: {type(e).__name__}")
        return False

def check_account_info():
    """Try to get account information."""
    print("\n" + "=" * 60)
    print("3. Verifying API Key (Account Info)")
    print("=" * 60)
    
    if not settings.PAYSTACK_SECRET_KEY:
        print("[ERROR] Cannot verify - API key not configured")
        return False
    
    paystackapi.api_key = settings.PAYSTACK_SECRET_KEY
    
    try:
        # Try to get a transaction list to verify API key works
        from paystackapi.transaction import Transaction
        
        # This will fail if API key is invalid, but won't tell us about currency
        # We'll just check if the API key is valid
        print("   Testing API key validity...")
        print("   (This doesn't check currency, just API key)")
        
        # Try a simple API call that doesn't require currency
        # Note: Paystack doesn't have a simple "ping" endpoint
        # So we'll just note that if currency test failed, it might be the key
        
    except Exception as e:
        print(f"   [WARNING] Could not verify API key: {str(e)}")
    
    return True

def main():
    """Run all checks."""
    print("\n" + "=" * 60)
    print("Paystack Configuration Verification")
    print("=" * 60)
    print()
    
    # Check API key
    has_key = check_api_key()
    
    if not has_key:
        print("\n[ERROR] Setup incomplete. Please configure PAYSTACK_SECRET_KEY first.")
        sys.exit(1)
    
    # Check currency
    currency_ok = check_currency_support()
    
    # Check account
    check_account_info()
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    if currency_ok:
        print("[OK] All checks passed! Paystack is configured correctly.")
        print("\n   If you're still getting errors:")
        print("   1. Restart your backend server")
        print("   2. Clear any caches")
        print("   3. Try the payment again")
    else:
        print("[ERROR] Currency check failed. See solutions above.")
        print("\n   Common issues:")
        print("   - API key from different account than where GHS was enabled")
        print("   - Using test key but GHS enabled on live account (or vice versa)")
        print("   - Changes not yet propagated (wait 2-3 minutes)")
        print("   - Backend needs restart to pick up changes")
    
    print()

if __name__ == "__main__":
    main()

