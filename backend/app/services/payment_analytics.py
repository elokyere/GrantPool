"""
Payment analytics service for tracking payment metrics.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.db import models

logger = logging.getLogger(__name__)


class PaymentAnalytics:
    """Service for tracking and analyzing payment metrics."""
    
    @staticmethod
    def track_payment_initialization(
        payment_id: int,
        payment_type: str,
        amount: int,
        currency: str,
        db: Session
    ):
        """
        Track payment initialization.
        
        Stores initialization timestamp in payment metadata.
        """
        payment = db.query(models.Payment).filter(
            models.Payment.id == payment_id
        ).first()
        
        if payment:
            payment.payment_metadata = payment.payment_metadata or {}
            payment.payment_metadata["initialized_at"] = datetime.utcnow().isoformat()
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(payment, "payment_metadata")
            db.commit()
            logger.info(f"Tracked payment initialization: payment_id={payment_id}, type={payment_type}")
    
    @staticmethod
    def track_payment_completion(
        payment_id: int,
        status: str,
        db: Session
    ):
        """
        Track payment completion (success or failure).
        
        Calculates completion time and stores in payment metadata.
        """
        payment = db.query(models.Payment).filter(
            models.Payment.id == payment_id
        ).first()
        
        if payment:
            payment.payment_metadata = payment.payment_metadata or {}
            completed_at = datetime.utcnow()
            payment.payment_metadata["completed_at"] = completed_at.isoformat()
            payment.payment_metadata["final_status"] = status
            
            # Calculate completion time if initialization time exists
            if "initialized_at" in payment.payment_metadata:
                initialized_at = datetime.fromisoformat(
                    payment.payment_metadata["initialized_at"]
                )
                completion_time_seconds = (completed_at - initialized_at).total_seconds()
                payment.payment_metadata["completion_time_seconds"] = completion_time_seconds
                logger.info(
                    f"Tracked payment completion: payment_id={payment_id}, "
                    f"status={status}, time={completion_time_seconds:.2f}s"
                )
            
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(payment, "payment_metadata")
            db.commit()
    
    @staticmethod
    def get_payment_success_rate(
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        payment_type: Optional[str] = None,
        db: Session = None
    ) -> Dict:
        """
        Calculate payment success rate.
        
        Args:
            start_date: Start date for analysis (defaults to 30 days ago)
            end_date: End date for analysis (defaults to now)
            payment_type: Filter by payment type (optional)
            db: Database session
        
        Returns:
            {
                "total": int,
                "succeeded": int,
                "failed": int,
                "pending": int,
                "success_rate": float,
                "period": {
                    "start": str,
                    "end": str
                }
            }
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        query = db.query(models.Payment).filter(
            and_(
                models.Payment.created_at >= start_date,
                models.Payment.created_at <= end_date
            )
        )
        
        if payment_type:
            query = query.filter(models.Payment.payment_type == payment_type)
        
        total = query.count()
        succeeded = query.filter(models.Payment.status == "succeeded").count()
        failed = query.filter(models.Payment.status == "failed").count()
        pending = query.filter(models.Payment.status == "pending").count()
        
        success_rate = (succeeded / total * 100) if total > 0 else 0.0
        
        return {
            "total": total,
            "succeeded": succeeded,
            "failed": failed,
            "pending": pending,
            "success_rate": round(success_rate, 2),
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "payment_type": payment_type or "all"
        }
    
    @staticmethod
    def get_average_completion_time(
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        payment_type: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Dict:
        """
        Calculate average payment completion time.
        
        Args:
            start_date: Start date for analysis (defaults to 30 days ago)
            end_date: End date for analysis (defaults to now)
            payment_type: Filter by payment type (optional)
            db: Database session
        
        Returns:
            {
                "average_seconds": float,
                "average_minutes": float,
                "count": int,
                "period": {
                    "start": str,
                    "end": str
                }
            }
        """
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()
        
        query = db.query(models.Payment).filter(
            and_(
                models.Payment.created_at >= start_date,
                models.Payment.created_at <= end_date,
                models.Payment.status == "succeeded"
            )
        )
        
        if payment_type:
            query = query.filter(models.Payment.payment_type == payment_type)
        
        payments = query.all()
        
        completion_times = []
        for payment in payments:
            metadata = payment.payment_metadata or {}
            if "completion_time_seconds" in metadata:
                completion_times.append(metadata["completion_time_seconds"])
        
        if not completion_times:
            return {
                "average_seconds": 0.0,
                "average_minutes": 0.0,
                "count": 0,
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "payment_type": payment_type or "all"
            }
        
        avg_seconds = sum(completion_times) / len(completion_times)
        
        return {
            "average_seconds": round(avg_seconds, 2),
            "average_minutes": round(avg_seconds / 60, 2),
            "count": len(completion_times),
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "payment_type": payment_type or "all"
        }
    
    @staticmethod
    def get_payment_metrics(
        days: int = 30,
        payment_type: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Dict:
        """
        Get comprehensive payment metrics.
        
        Args:
            days: Number of days to analyze
            payment_type: Filter by payment type (optional)
            db: Database session
        
        Returns:
            Combined metrics including success rate and completion time
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        end_date = datetime.utcnow()
        
        success_rate = PaymentAnalytics.get_payment_success_rate(
            start_date, end_date, payment_type, db
        )
        
        completion_time = PaymentAnalytics.get_average_completion_time(
            start_date, end_date, payment_type, db
        )
        
        return {
            "success_rate": success_rate,
            "completion_time": completion_time,
            "summary": {
                "total_payments": success_rate["total"],
                "success_rate_percent": success_rate["success_rate"],
                "average_completion_minutes": completion_time["average_minutes"]
            }
        }

