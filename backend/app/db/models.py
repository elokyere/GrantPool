"""
Database models.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import sqlalchemy as sa
from app.db.database import Base


class User(Base):
    """User model."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    country_code = Column(String(2), nullable=True)  # ISO 3166-1 alpha-2 country code
    paystack_customer_code = Column(String(255), nullable=True, unique=True)
    free_assessment_used = Column(Boolean, default=False)
    password_reset_token = Column(String(255), nullable=True, index=True)
    password_reset_expires = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    projects = relationship("Project", back_populates="owner")
    evaluations = relationship("Evaluation", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    assessment_purchases = relationship("AssessmentPurchase", back_populates="user")
    grant_contributions = relationship("GrantDataContribution", foreign_keys="GrantDataContribution.user_id")


class Project(Base):
    """User project context model."""
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    stage = Column(String, nullable=False)  # e.g., "Early prototype", "MVP", "Scaling"
    funding_need = Column(String, nullable=False)  # Legacy field - kept for backward compatibility
    urgency = Column(String, nullable=False)  # "critical", "moderate", "flexible"
    founder_type = Column(String, nullable=True)  # "solo", "startup", "institution"
    timeline_constraints = Column(Text, nullable=True)
    
    # New profile fields (core columns for paid assessments)
    organization_country = Column(String(2), nullable=True, index=True)  # ISO 3166-1 alpha-2
    organization_type = Column(String(50), nullable=True, index=True)  # 'NGO', 'Research', 'Government', 'Community', 'Individual'
    funding_need_amount = Column(Integer, nullable=True)  # Amount in cents
    funding_need_currency = Column(String(3), nullable=True, index=True)  # ISO 4217 code (USD, GHS, etc.)
    has_prior_grants = Column(Boolean, nullable=True)
    
    # Extended/evolving fields (JSONB for flexibility)
    profile_metadata = Column(JSONB, nullable=True)  # Stores: team_size, education_level, career_stage, sectors, geographic_focus, project_keywords, timeline, confidence_flags
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    owner = relationship("User", back_populates="projects")
    evaluations = relationship("Evaluation", back_populates="project")


class Grant(Base):
    """Grant information model (Source of Record - immutable raw data)."""
    __tablename__ = "grants"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    mission = Column(Text, nullable=True)
    deadline = Column(String, nullable=True)
    decision_date = Column(String, nullable=True)
    award_amount = Column(String, nullable=True)
    award_structure = Column(Text, nullable=True)
    eligibility = Column(Text, nullable=True)
    preferred_applicants = Column(Text, nullable=True)
    application_requirements = Column(JSON, nullable=True)  # List of strings
    reporting_requirements = Column(Text, nullable=True)
    restrictions = Column(JSON, nullable=True)  # List of strings
    source_url = Column(String, nullable=True)
    
    # Raw data fields (Source of Record - immutable after initial save)
    raw_title = Column(String, nullable=True)  # Raw title from source (never overwritten)
    raw_content = Column(Text, nullable=True)  # Raw scraped content (never overwritten)
    fetched_at = Column(DateTime(timezone=True), nullable=True)  # When raw data was fetched
    
    approval_status = Column(String, default='pending', nullable=False)  # 'pending', 'approved', 'rejected'
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # Admin user who approved/rejected
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)  # Reason if rejected
    
    # Recipient patterns and competition stats (JSONB with source/confidence tagging)
    recipient_patterns = Column(JSONB, nullable=True)  # Stores recipient data and competition statistics
    
    # Decision Readiness System (5 bucket states)
    timeline_clarity = Column(sa.Enum('known', 'partial', 'unknown', name='bucket_state'), nullable=True)
    winner_signal = Column(sa.Enum('known', 'partial', 'unknown', name='bucket_state'), nullable=True)
    mission_specificity = Column(sa.Enum('known', 'partial', 'unknown', name='bucket_state'), nullable=True)
    application_burden = Column(sa.Enum('known', 'partial', 'unknown', name='bucket_state'), nullable=True)
    award_structure_clarity = Column(sa.Enum('known', 'partial', 'unknown', name='bucket_state'), nullable=True)
    
    # Derived/computed fields
    decision_readiness = Column(String(50), nullable=True)  # 'Ready for Evaluation', 'Partial — Missing Signals', 'Low Confidence Grant'
    status_of_knowledge = Column(String(50), nullable=True)  # 'Well-Specified', 'Partially Opaque', 'Structurally Vague'
    scope = Column(sa.Enum('Local', 'National', 'International', 'Unclear', name='grant_scope'), nullable=True)
    
    # Source verification
    source_verified = Column(Boolean, nullable=True, default=False)
    source_verified_checked_at = Column(DateTime(timezone=True), nullable=True)
    
    # Evaluation completion flag
    evaluation_complete = Column(Boolean, nullable=False, default=False, server_default='false')
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    evaluations = relationship("Evaluation", back_populates="grant")
    approver = relationship("User", foreign_keys=[approved_by])
    normalization = relationship("GrantNormalization", back_populates="grant", uselist=False)


class Evaluation(Base):
    """Grant evaluation result model."""
    __tablename__ = "evaluations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    grant_id = Column(Integer, ForeignKey("grants.id"), nullable=True)  # Nullable for Option A: in-memory grants
    
    # Grant snapshot fields (Option A: store grant data directly in evaluation)
    grant_url = Column(String, nullable=True)  # URL used for evaluation
    grant_name = Column(String, nullable=True)  # Grant name at time of evaluation
    grant_snapshot_json = Column(JSON, nullable=True)  # Full grant data snapshot (immutable)
    
    # Scores
    timeline_viability = Column(Integer, nullable=False)
    winner_pattern_match = Column(Integer, nullable=True)  # NULL for free tier (no project data)
    mission_alignment = Column(Integer, nullable=True)  # NULL for free tier (no project data)
    application_burden = Column(Integer, nullable=False)
    award_structure = Column(Integer, nullable=False)
    composite_score = Column(Integer, nullable=False)
    
    # Recommendation
    recommendation = Column(String, nullable=False)  # "APPLY", "CONDITIONAL", "PASS"
    
    # Detailed results
    reasoning = Column(JSON, nullable=False)  # Dict with reasoning for each dimension
    key_insights = Column(JSON, nullable=True)  # List of strings
    red_flags = Column(JSON, nullable=True)  # List of strings
    confidence_notes = Column(Text, nullable=True)
    
    # Metadata
    evaluator_type = Column(String, nullable=False)  # "rule_based" or "llm"
    evaluation_tier = Column(String(20), nullable=False, default="standard")  # "free", "refined", "standard" (deprecated, kept for legacy)
    assessment_type = Column(String(10), nullable=False, default='free', server_default='free')  # 'free' or 'paid' - New two-tier framework
    is_legacy = Column(Boolean, nullable=False, default=False, server_default='false')  # True for evaluations created before new framework
    parent_evaluation_id = Column(Integer, ForeignKey("evaluations.id"), nullable=True)  # For refinements (deprecated)
    is_refinement = Column(Boolean, default=False)  # True if this is a refinement of another evaluation (deprecated)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="evaluations")
    project = relationship("Project", back_populates="evaluations")
    grant = relationship("Grant", back_populates="evaluations")
    assessment_purchase = relationship("AssessmentPurchase", back_populates="evaluation", uselist=False)
    parent_evaluation = relationship("Evaluation", remote_side=[id], backref="refined_evaluations")


class Payment(Base):
    """Payment model for Paystack transactions."""
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    paystack_reference = Column(String(255), unique=True, nullable=True, index=True)
    paystack_customer_code = Column(String(255), nullable=True)
    amount = Column(Integer, nullable=False)  # Amount in cents/pesewas (smallest currency unit)
    currency = Column(String(3), nullable=False)  # ISO 4217 currency code (USD, GHS, etc.)
    status = Column(String(50), nullable=False)  # pending, succeeded, failed, refunded, canceled
    assessment_count = Column(Integer, default=1)  # How many assessments this payment covers
    payment_type = Column(String(20), nullable=False, default="standard")  # "refinement", "standard", "bundle"
    country_code = Column(String(2), nullable=True)  # User's country at time of payment
    payment_metadata = Column(JSON, nullable=True)  # Additional Paystack data (renamed from 'metadata' - SQLAlchemy reserved word)
    converted_to_credit = Column(Boolean, nullable=True, default=False, server_default='false')  # True if refinement payment was converted to bundle credit
    
    # Refund tracking fields
    refund_status = Column(String(20), nullable=True)  # 'none', 'requested', 'approved', 'processed', 'denied'
    refund_amount = Column(Integer, nullable=True)  # Amount refunded in cents/pesewas
    refund_reason = Column(Text, nullable=True)  # Reason for refund
    refunded_at = Column(DateTime(timezone=True), nullable=True)
    refund_metadata = Column(JSON, nullable=True)  # Additional refund information
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="payments")
    assessment_purchases = relationship("AssessmentPurchase", back_populates="payment")
    support_requests = relationship("SupportRequest", back_populates="payment")


class AssessmentPurchase(Base):
    """Links evaluations to payments or free assessments."""
    __tablename__ = "assessment_purchases"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    evaluation_id = Column(Integer, ForeignKey("evaluations.id"), nullable=False, unique=True, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    purchase_type = Column(String(20), nullable=False)  # 'free' or 'paid'
    currency = Column(String(3), nullable=True)  # Currency if paid
    amount_paid = Column(Integer, nullable=True)  # Amount in cents, NULL for free
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="assessment_purchases")
    evaluation = relationship("Evaluation", back_populates="assessment_purchase")
    payment = relationship("Payment", back_populates="assessment_purchases")


class AuditLog(Base):
    """Audit log for security and compliance."""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)  # 'assessment_created', 'payment_initiated', etc.
    resource_type = Column(String(50), nullable=True)  # 'evaluation', 'payment', etc.
    resource_id = Column(Integer, nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(Text, nullable=True)
    log_metadata = Column(JSON, nullable=True)  # Additional context (renamed from 'metadata' - SQLAlchemy reserved word)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class GrantNormalization(Base):
    """Grant normalization model (Presentation Layer - editable, auditable).
    
    This stores curated/canonical versions of grant data for presentation.
    Source of truth remains in Grant.raw_* fields which are immutable.
    """
    __tablename__ = "grant_normalizations"
    
    id = Column(Integer, primary_key=True, index=True)
    grant_id = Column(Integer, ForeignKey("grants.id"), nullable=False, unique=True, index=True)
    
    # Canonical presentation fields
    canonical_title = Column(String, nullable=True)  # Standardized title
    canonical_summary = Column(Text, nullable=True)  # One-paragraph summary
    timeline_status = Column(String(20), nullable=True)  # 'active', 'closed', 'rolling', 'unknown'
    
    # Metadata
    normalized_by = Column(String(20), nullable=False, default='system')  # 'system' or 'admin'
    confidence_level = Column(String(10), nullable=True)  # 'high', 'medium', 'low'
    revision_notes = Column(Text, nullable=True)  # Notes about changes/edits
    
    # Approval tracking
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Admin who approved
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    grant = relationship("Grant", back_populates="normalization")
    approver = relationship("User", foreign_keys=[approved_by_user_id])


class SupportRequest(Base):
    """Support requests for refunds and technical issues."""
    __tablename__ = "support_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    evaluation_id = Column(Integer, ForeignKey("evaluations.id"), nullable=True)
    issue_type = Column(String(50), nullable=False, index=True)  # 'duplicate_payment', 'technical_error', 'payment_issue', 'other'
    status = Column(String(20), nullable=False, default="pending", index=True)  # 'pending', 'in_review', 'resolved', 'denied'
    description = Column(Text, nullable=False)
    resolution_type = Column(String(20), nullable=True)  # 'credit', 'refund', 'none'
    resolution_amount = Column(Integer, nullable=True)  # Amount in cents/pesewas
    resolution_currency = Column(String(3), nullable=True)  # USD, GHS, etc.
    admin_notes = Column(Text, nullable=True)
    auto_verified = Column(Boolean, nullable=False, default=False)  # True if system auto-verified
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User")
    payment = relationship("Payment")
    evaluation = relationship("Evaluation")


class GrantDataContribution(Base):
    """User contributions for missing grant data."""
    __tablename__ = "grant_data_contributions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    grant_id = Column(Integer, ForeignKey("grants.id"), nullable=True, index=True)  # Nullable for in-memory grants
    evaluation_id = Column(Integer, ForeignKey("evaluations.id"), nullable=True, index=True)  # Link to evaluation if grant not indexed
    
    # Grant identification (for in-memory grants)
    grant_name = Column(String, nullable=True)  # Grant name if grant not indexed
    grant_url = Column(String, nullable=True)  # Grant URL if grant not indexed
    
    # Contribution data
    field_name = Column(String(50), nullable=False, index=True)  # 'award_amount', 'deadline', 'acceptance_rate', 'past_recipients', etc.
    field_value = Column(Text, nullable=False)  # The value provided by user
    source_url = Column(String, nullable=True)  # URL where user found the data
    source_description = Column(Text, nullable=True)  # Additional context about the source
    
    # Status tracking
    status = Column(String(20), nullable=False, default="pending", index=True)  # 'pending', 'approved', 'rejected', 'merged'
    admin_notes = Column(Text, nullable=True)  # Admin review notes
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # Admin who reviewed
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    grant = relationship("Grant")
    evaluation = relationship("Evaluation")
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    
    # Index for efficient queries
    __table_args__ = (
        Index('idx_contributions_grant_status', 'grant_id', 'status'),
        Index('idx_contributions_user_status', 'user_id', 'status'),
    )

