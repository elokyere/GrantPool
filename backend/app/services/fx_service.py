"""
FX service for display-only USD/GHS conversion.

This service is for DISPLAY purposes only.
Payment amounts are ALWAYS locked in GHS and never affected by FX rates.
"""

import httpx
import logging
from typing import Optional
from datetime import datetime, timedelta
from app.core.config import settings

logger = logging.getLogger(__name__)

# In-memory cache (24h TTL)
_fx_cache = {
    "rate": None,
    "fetched_at": None,
    "ttl_hours": 24
}


def get_usd_to_ghs_rate() -> Optional[float]:
    """
    Get USD to GHS exchange rate for display purposes only.
    
    Cached for 24 hours. Falls back to last known rate if API fails.
    If no rate available, returns None (caller should handle gracefully).
    
    Returns:
        USD to GHS rate (e.g., 10.6647 means 1 USD = 10.6647 GHS)
        None if rate unavailable and no cached rate exists
    """
    global _fx_cache
    
    # Check cache validity
    if _fx_cache["rate"] is not None and _fx_cache["fetched_at"] is not None:
        cache_age = datetime.now() - _fx_cache["fetched_at"]
        if cache_age < timedelta(hours=_fx_cache["ttl_hours"]):
            return _fx_cache["rate"]
    
    # Cache expired or missing - fetch new rate
    try:
        # Using exchangerate-api.io (free tier, no API key required)
        # Alternative: fixer.io, currencylayer.com, etc.
        response = httpx.get(
            "https://api.exchangerate-api.com/v4/latest/USD",
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        
        ghs_rate = data.get("rates", {}).get("GHS")
        if ghs_rate and isinstance(ghs_rate, (int, float)) and ghs_rate > 0:
            _fx_cache["rate"] = float(ghs_rate)
            _fx_cache["fetched_at"] = datetime.now()
            logger.info(f"Fetched USD/GHS rate: {ghs_rate}")
            return _fx_cache["rate"]
        else:
            logger.warning("Invalid rate data from FX API")
    except Exception as e:
        logger.warning(f"Failed to fetch FX rate: {e}")
        # Fallback to cached rate if available (even if expired)
        if _fx_cache["rate"] is not None:
            logger.info(f"Using cached FX rate: {_fx_cache['rate']}")
            return _fx_cache["rate"]
    
    # No rate available
    return None


def ghs_to_usd_display(ghs_amount_pesewas: int) -> Optional[float]:
    """
    Convert GHS amount (in pesewas) to USD for display purposes only.
    
    Args:
        ghs_amount_pesewas: Amount in pesewas (e.g., 2800 = 28.00 GHS)
    
    Returns:
        USD equivalent (e.g., 7.00) or None if rate unavailable
    """
    rate = get_usd_to_ghs_rate()
    if rate is None:
        return None
    
    ghs_amount = ghs_amount_pesewas / 100.0
    usd_amount = ghs_amount / rate
    return round(usd_amount, 2)







