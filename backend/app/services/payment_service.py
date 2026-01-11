"""
Service for handling Paystack payments.
"""

import paystackapi
import hmac
import hashlib
import time
import logging
from typing import Optional, Dict
from sqlalchemy.orm import Session
from app.db import models
from app.core.config import settings
from app.services.credit_service import CreditService
from app.services.payment_analytics import PaymentAnalytics
from app.utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)

# Initialize Paystack
if settings.PAYSTACK_SECRET_KEY:
    paystackapi.api_key = settings.PAYSTACK_SECRET_KEY
else:
    # In development, allow payment service to be called but will fail with clear error
    paystackapi.api_key = ""


class PaymentService:
    """Service for managing Paystack payments."""
    
    @staticmethod
    def get_ghs_price(payment_type: str = "standard") -> int:
        """
        Get locked GHS price in pesewas.
        
        All payments are charged in GHS. This is the authoritative pricing.
        FX rates are used for display only, never for charging.
        
        Args:
            payment_type: "refinement", "standard", or "bundle"
        
        Returns:
        - Refinement: 3217 pesewas (32.17 GHS) ≈ $3.00
        - Standard: 7507 pesewas (75.07 GHS) ≈ $7.00
        - Bundle: 19305 pesewas (193.05 GHS) ≈ $18.00
        """
        if payment_type == "refinement":
            return settings.GHS_PRICE_REFINEMENT
        elif payment_type == "bundle":
            return settings.GHS_PRICE_BUNDLE
        else:  # standard
            return settings.GHS_PRICE_STANDARD
    
    @staticmethod
    def initialize_transaction(
        user_id: int,
        country_code: Optional[str],
        db: Session,
        payment_type: str = "standard"
    ) -> Dict:
        """
        Initialize a Paystack transaction for an assessment.
        
        Args:
            user_id: User ID
            country_code: User's country code
            db: Database session
            payment_type: "refinement", "standard", or "bundle"
        
        Returns:
        {
            "authorization_url": str,
            "access_code": str,
            "reference": str,
            "amount": int,
            "currency": str,
            "payment_type": str,
            "assessment_count": int  # 1 for standard/refinement, 3 for bundle
        }
        """
        # Check if Paystack is configured
        if not settings.PAYSTACK_SECRET_KEY:
            raise ValueError("Paystack is not configured. Please set PAYSTACK_SECRET_KEY in environment variables.")
        
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        
        # Always charge in GHS (locked prices)
        currency = "GHS"
        amount = PaymentService.get_ghs_price(payment_type)
        
        # Set assessment count based on payment type
        assessment_count = 3 if payment_type == "bundle" else 1
        
        # Get or create Paystack customer
        customer_code = user.paystack_customer_code
        if not customer_code:
            # Create customer in Paystack with retry logic
            from paystackapi.customer import Customer
            
            first_name = user.full_name.split()[0] if user.full_name else ""
            last_name = " ".join(user.full_name.split()[1:]) if user.full_name and len(user.full_name.split()) > 1 else ""
            
            @retry_with_backoff(max_retries=3, initial_delay=1.0, exceptions=(Exception,))
            def create_customer():
                return Customer.create(
                email=user.email,
                first_name=first_name,
                last_name=last_name,
                metadata={"user_id": str(user_id)}
            )
            
            customer_response = create_customer()
            
            if not customer_response.get("status"):
                raise ValueError(f"Failed to create Paystack customer: {customer_response.get('message', 'Unknown error')}")
            
            customer = customer_response["data"]
            customer_code = customer["customer_code"]
            user.paystack_customer_code = customer_code
            db.commit()
        
        # Initialize transaction
        # NOTE: No refunds policy - digital assessments are non-refundable
        from paystackapi.transaction import Transaction
        
        reference = f"GRANT_{user_id}_{int(time.time())}"  # Unique reference
        
        # Log exact payload before sending to Paystack (for debugging currency issues)
        payload = {
            "reference": reference,
            "amount": amount,
            "email": user.email,
            "currency": currency,
            "callback_url": f"{settings.APP_URL}/api/v1/webhooks/paystack/callback?ref={reference}",
            "metadata": {
                "user_id": str(user_id),
                "assessment_count": str(assessment_count),
                "country_code": country_code or user.country_code or "US",
                "no_refunds": "true",
                "product_type": "digital_assessment",
                "payment_type": payment_type
            }
        }
        
        # CRITICAL: Log exact payload to verify currency value
        logger.info("=" * 80)
        logger.info("PAYSTACK INIT PAYLOAD (EXACT VALUES):")
        logger.info(f"  currency (type: {type(currency).__name__}): {repr(currency)}")
        logger.info(f"  currency length: {len(currency) if currency else 'None'}")
        logger.info(f"  currency bytes: {currency.encode('utf-8') if currency else 'None'}")
        logger.info(f"  amount: {amount}")
        logger.info(f"  reference: {reference}")
        logger.info(f"  email: {user.email}")
        logger.info(f"  API Key (first 10 chars): {settings.PAYSTACK_SECRET_KEY[:10] if settings.PAYSTACK_SECRET_KEY else 'NOT SET'}...")
        logger.info(f"  API Key type: {'LIVE' if settings.PAYSTACK_SECRET_KEY and settings.PAYSTACK_SECRET_KEY.startswith('sk_live_') else 'TEST' if settings.PAYSTACK_SECRET_KEY and settings.PAYSTACK_SECRET_KEY.startswith('sk_test_') else 'UNKNOWN'}")
        logger.info("=" * 80)
        
        @retry_with_backoff(max_retries=3, initial_delay=1.0, exceptions=(Exception,))
        def initialize_transaction():
            return Transaction.initialize(
            reference=payload["reference"],
            amount=payload["amount"],
            email=payload["email"],
            currency=payload["currency"],
            callback_url=payload["callback_url"],
            metadata=payload["metadata"]
        )
        
        transaction_response = initialize_transaction()
        
        if not transaction_response.get("status"):
            error_message = transaction_response.get('message', 'Unknown error')
            # Log full Paystack response for debugging
            logger.error(f"Paystack transaction initialization failed:")
            logger.error(f"  Full response: {transaction_response}")
            logger.error(f"  Error message: {error_message}")
            logger.error(f"  Currency attempted: {currency}")
            logger.error(f"  Amount: {amount} ({amount/100} {currency})")
            
            # Provide helpful error message for currency issues
            if 'currency' in error_message.lower() or 'not supported' in error_message.lower():
                raise ValueError(
                    f"Currency error: {error_message}. "
                    f"Your Paystack account needs to have GHS enabled. "
                    f"Please enable GHS in your Paystack dashboard (Settings → Business → Supported Currencies) "
                    f"or contact Paystack support to enable GHS transactions. "
                    f"Full Paystack response logged in server logs."
                )
            raise ValueError(f"Failed to initialize Paystack transaction: {error_message}")
        
        transaction = transaction_response["data"]
        reference = transaction["reference"]
        authorization_url = transaction["authorization_url"]
        access_code = transaction["access_code"]
        
        # Create payment record
        payment = models.Payment(
            user_id=user_id,
            paystack_reference=reference,
            paystack_customer_code=customer_code,
            amount=amount,
            currency=currency,
            status="pending",
            assessment_count=assessment_count,
            payment_type=payment_type,
            country_code=country_code or user.country_code,
            payment_metadata={
                "paystack_reference": reference,
                "paystack_customer_code": customer_code,
                "authorization_url": authorization_url,
                "access_code": access_code,
                "payment_type": payment_type
            }
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)
        
        # Track payment initialization
        PaymentAnalytics.track_payment_initialization(
            payment.id, payment_type, amount, currency, db
        )
        
        return {
            "authorization_url": authorization_url,
            "access_code": access_code,
            "reference": reference,
            "amount": amount,
            "currency": currency,
            "payment_type": payment_type,
            "assessment_count": assessment_count
        }
    
    @staticmethod
    def verify_transaction(reference: str, db: Session) -> Optional[models.Payment]:
        """
        Verify a Paystack transaction.
        
        Returns Payment object if transaction is successful, None otherwise.
        """
        payment = db.query(models.Payment).filter(
            models.Payment.paystack_reference == reference
        ).first()
        
        if not payment:
            return None
        
        # Verify with Paystack (with retry logic)
        from paystackapi.transaction import Transaction
        
        @retry_with_backoff(max_retries=3, initial_delay=1.0, exceptions=(Exception,))
        def verify_transaction():
            return Transaction.verify(reference=reference)
        
        verify_response = verify_transaction()
        
        if not verify_response.get("status"):
            payment.status = "failed"
            PaymentAnalytics.track_payment_completion(payment.id, "failed", db)
            db.commit()
            return None
        
        transaction = verify_response["data"]
        
        # Check if transaction was successful
        if transaction["status"] != "success":
            payment.status = "failed"
            PaymentAnalytics.track_payment_completion(payment.id, "failed", db)
            db.commit()
            return None
        
        # Update payment status
        payment.status = "succeeded"
        payment.payment_metadata = payment.payment_metadata or {}
        payment.payment_metadata["verified_at"] = transaction.get("paid_at")
        payment.payment_metadata["paystack_transaction_id"] = transaction.get("id")
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(payment, "payment_metadata")
        
        # Track payment completion
        PaymentAnalytics.track_payment_completion(payment.id, "succeeded", db)
        db.commit()
        
        return payment
    
    @staticmethod
    def handle_payment_success(reference: str, db: Session) -> Optional[models.Payment]:
        """
        Handle successful payment webhook from Paystack.
        
        Updates payment status and allows assessment creation.
        """
        return PaymentService.verify_transaction(reference, db)
    
    @staticmethod
    def handle_payment_failure(reference: str, db: Session) -> Optional[models.Payment]:
        """Handle failed payment webhook from Paystack."""
        payment = db.query(models.Payment).filter(
            models.Payment.paystack_reference == reference
        ).first()
        
        if not payment:
            return None
        
        payment.status = "failed"
        PaymentAnalytics.track_payment_completion(payment.id, "failed", db)
        db.commit()
        
        return payment
    
    @staticmethod
    def link_payment_to_assessment(
        payment_id: int,
        user_id: int,
        evaluation_id: int,
        db: Session
    ) -> bool:
        """
        Link a successful payment to an assessment.
        
        Creates AssessmentPurchase record.
        For bundle payments, links one assessment from the bundle.
        """
        payment = db.query(models.Payment).filter(
            models.Payment.id == payment_id,
            models.Payment.user_id == user_id,
            models.Payment.status == "succeeded"
        ).first()
        
        if not payment:
            return False
        
        # For bundle payments, check if bundle is already fully used
        if payment.payment_type == "bundle":
            used_count = db.query(models.AssessmentPurchase).filter(
                models.AssessmentPurchase.payment_id == payment_id,
                models.AssessmentPurchase.user_id == user_id
            ).count()
            
            if used_count >= payment.assessment_count:
                return False  # Bundle fully used
        
        # Check if purchase already exists for this evaluation
        existing = db.query(models.AssessmentPurchase).filter(
            models.AssessmentPurchase.evaluation_id == evaluation_id
        ).first()
        
        if existing:
            return True  # Already linked
        
        # Calculate amount per assessment for bundles
        amount_per_assessment = payment.amount
        if payment.payment_type == "bundle" and payment.assessment_count > 1:
            # Divide bundle amount by number of assessments
            amount_per_assessment = payment.amount // payment.assessment_count
        
        # Create purchase record
        purchase = models.AssessmentPurchase(
            user_id=user_id,
            evaluation_id=evaluation_id,
            payment_id=payment_id,
            purchase_type="paid",
            currency=payment.currency,
            amount_paid=amount_per_assessment,  # Amount per assessment
        )
        db.add(purchase)
        db.commit()
        
        return True
