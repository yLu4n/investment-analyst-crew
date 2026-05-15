from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from investment_analyst.persistence.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    EXPIRED = "expired"


class PortfolioSource(str, Enum):
    MANUAL = "manual"
    IMPORT = "import"
    SYNC = "sync"


class TransactionType(str, Enum):
    BUY = "buy"
    SELL = "sell"


class CreditEventType(str, Enum):
    GRANT = "grant"
    CONSUME = "consume"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"
    EXPIRE = "expire"


class AuditEventStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    WARNING = "warning"


class SubscriptionPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscription_plans"
    __table_args__ = (
        UniqueConstraint("code"),
        CheckConstraint("monthly_price_cents >= 0", name="monthly_price_cents_non_negative"),
        CheckConstraint(
            "monthly_credit_allowance >= 0",
            name="monthly_credit_allowance_non_negative",
        ),
    )

    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    monthly_price_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    monthly_credit_allowance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_analysis_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    features_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    users: Mapped[list["UserAccount"]] = relationship(
        back_populates="current_plan",
        foreign_keys="UserAccount.current_plan_id",
    )
    subscriptions: Mapped[list["UserPlanSubscription"]] = relationship(back_populates="plan")


class UserAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_accounts"
    __table_args__ = (
        UniqueConstraint("primary_email"),
        CheckConstraint("credits_balance >= 0", name="credits_balance_non_negative"),
    )

    primary_email: Mapped[str | None] = mapped_column(String(320))
    display_name: Mapped[str | None] = mapped_column(String(255))
    current_plan_id: Mapped[str | None] = mapped_column(
        ForeignKey("subscription_plans.id", ondelete="SET NULL"),
    )
    credits_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    profile_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    app_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    current_plan: Mapped[SubscriptionPlan | None] = relationship(
        back_populates="users",
        foreign_keys=[current_plan_id],
    )
    external_identities: Mapped[list["UserExternalIdentity"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    subscriptions: Mapped[list["UserPlanSubscription"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    portfolios: Mapped[list["Portfolio"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    analysis_jobs: Mapped[list["AnalysisJob"]] = relationship(back_populates="user")
    credit_ledger_entries: Mapped[list["CreditLedgerEntry"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        back_populates="subject_user",
        foreign_keys="AuditEvent.subject_user_id",
    )
    authored_audit_events: Mapped[list["AuditEvent"]] = relationship(
        back_populates="actor_user",
        foreign_keys="AuditEvent.actor_user_id",
    )


class UserExternalIdentity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_external_identities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_subject"),
        Index("ix_user_external_identities_user_provider", "user_id", "provider"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_email: Mapped[str | None] = mapped_column(String(320))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    last_authenticated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[UserAccount] = relationship(back_populates="external_identities")


class UserPlanSubscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_plan_subscriptions"
    __table_args__ = (
        Index("ix_user_plan_subscriptions_user_status", "user_id", "status"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        SAEnum(SubscriptionStatus, native_enum=False),
        default=SubscriptionStatus.ACTIVE,
        nullable=False,
    )
    external_customer_ref: Mapped[str | None] = mapped_column(String(255))
    external_subscription_ref: Mapped[str | None] = mapped_column(String(255))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    renews_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    billing_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    user: Mapped[UserAccount] = relationship(back_populates="subscriptions")
    plan: Mapped[SubscriptionPlan] = relationship(back_populates="subscriptions")


class Asset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("ticker"),)

    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    display_ticker: Mapped[str | None] = mapped_column(String(32))
    name: Mapped[str | None] = mapped_column(String(255))
    asset_type: Mapped[str] = mapped_column(String(64), default="stock", nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str] = mapped_column(String(8), default="BRL", nullable=False)
    isin: Mapped[str | None] = mapped_column(String(32))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    positions: Mapped[list["PortfolioPosition"]] = relationship(back_populates="asset")
    transactions: Mapped[list["PortfolioTransaction"]] = relationship(back_populates="asset")
    cache_entries: Mapped[list["AssetCacheEntry"]] = relationship(back_populates="asset")


class Portfolio(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "portfolios"
    __table_args__ = (
        Index("ix_portfolios_user_name", "user_id", "name"),
    )

    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="SET NULL"),
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), default="BRL", nullable=False)
    risk_profile: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[PortfolioSource] = mapped_column(
        SAEnum(PortfolioSource, native_enum=False),
        default=PortfolioSource.MANUAL,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    snapshot_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    user: Mapped[UserAccount | None] = relationship(back_populates="portfolios")
    positions: Mapped[list["PortfolioPosition"]] = relationship(
        back_populates="portfolio",
        cascade="all, delete-orphan",
    )
    transactions: Mapped[list["PortfolioTransaction"]] = relationship(
        back_populates="portfolio",
        cascade="all, delete-orphan",
    )
    analysis_jobs: Mapped[list["AnalysisJob"]] = relationship(back_populates="portfolio")


class PortfolioPosition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "portfolio_positions"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "ticker"),
        CheckConstraint("quantity >= 0", name="quantity_non_negative"),
        CheckConstraint("average_price >= 0", name="average_price_non_negative"),
        CheckConstraint("cost_basis >= 0", name="cost_basis_non_negative"),
        CheckConstraint(
            "target_allocation IS NULL OR target_allocation >= 0",
            name="target_allocation_non_negative",
        ),
    )

    portfolio_id: Mapped[str] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"))
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(64), default="stock", nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=Decimal("0"), nullable=False)
    average_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        default=Decimal("0"),
        nullable=False,
    )
    cost_basis: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        default=Decimal("0"),
        nullable=False,
    )
    target_allocation: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    source: Mapped[PortfolioSource] = mapped_column(
        SAEnum(PortfolioSource, native_enum=False),
        default=PortfolioSource.MANUAL,
        nullable=False,
    )
    extra_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    portfolio: Mapped[Portfolio] = relationship(back_populates="positions")
    asset: Mapped[Asset | None] = relationship(back_populates="positions")


class PortfolioTransaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "portfolio_transactions"
    __table_args__ = (
        Index("ix_portfolio_transactions_portfolio_executed_at", "portfolio_id", "executed_at"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("price >= 0", name="price_non_negative"),
        CheckConstraint("fees >= 0", name="fees_non_negative"),
    )

    portfolio_id: Mapped[str] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"))
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    transaction_type: Mapped[TransactionType] = mapped_column(
        SAEnum(TransactionType, native_enum=False),
        nullable=False,
    )
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    fees: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        default=Decimal("0"),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(8), default="BRL", nullable=False)
    broker_reference: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[PortfolioSource] = mapped_column(
        SAEnum(PortfolioSource, native_enum=False),
        default=PortfolioSource.MANUAL,
        nullable=False,
    )
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    portfolio: Mapped[Portfolio] = relationship(back_populates="transactions")
    asset: Mapped[Asset | None] = relationship(back_populates="transactions")


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    __table_args__ = (
        CheckConstraint("progress_percentage >= 0 AND progress_percentage <= 100", name="progress_percentage_range"),
        CheckConstraint("attempt_count >= 0", name="attempt_count_non_negative"),
        CheckConstraint("max_attempts >= 1", name="max_attempts_positive"),
        Index("ix_analysis_jobs_user_request_hash", "user_id", "request_hash"),
        Index("ix_analysis_jobs_status_next_retry", "status", "next_retry_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("user_accounts.id", ondelete="SET NULL"))
    portfolio_id: Mapped[str | None] = mapped_column(ForeignKey("portfolios.id", ondelete="SET NULL"))
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, native_enum=False),
        default=JobStatus.PENDING,
        nullable=False,
    )
    current_step: Mapped[str] = mapped_column(String(64), default="queued", nullable=False)
    progress_percentage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    retry_backoff_seconds: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    cache_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    user: Mapped[UserAccount | None] = relationship(back_populates="analysis_jobs")
    portfolio: Mapped[Portfolio | None] = relationship(back_populates="analysis_jobs")
    result: Mapped["AnalysisResult | None"] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        uselist=False,
    )
    credit_ledger_entries: Mapped[list["CreditLedgerEntry"]] = relationship(back_populates="job")
    audit_events: Mapped[list["AuditEvent"]] = relationship(back_populates="job")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    __table_args__ = (UniqueConstraint("job_id"),)

    job_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    result_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    report_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    pdf_path: Mapped[str | None] = mapped_column(String(512))
    report_checksum: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

    job: Mapped[AnalysisJob] = relationship(back_populates="result")


class AssetCacheEntry(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "asset_cache_entries"
    __table_args__ = (
        UniqueConstraint("ticker", "analysis_type", "provider"),
        Index("ix_asset_cache_entries_expires_at", "expires_at"),
    )

    asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"))
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    analysis_type: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), default="default", nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    payload_hash: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    asset: Mapped[Asset | None] = relationship(back_populates="cache_entries")


class CreditLedgerEntry(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "credit_ledger_entries"
    __table_args__ = (
        CheckConstraint("amount != 0", name="amount_non_zero"),
        CheckConstraint("balance_after >= 0", name="balance_after_non_negative"),
        Index("ix_credit_ledger_entries_user_created_at", "user_id", "created_at"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_jobs.id", ondelete="SET NULL"))
    event_type: Mapped[CreditEventType] = mapped_column(
        SAEnum(CreditEventType, native_enum=False),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    reference_id: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

    user: Mapped[UserAccount] = relationship(back_populates="credit_ledger_entries")
    job: Mapped[AnalysisJob | None] = relationship(back_populates="credit_ledger_entries")


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_entity", "entity_type", "entity_id"),
        Index("ix_audit_events_subject_created_at", "subject_user_id", "created_at"),
    )

    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("user_accounts.id", ondelete="SET NULL"))
    subject_user_id: Mapped[str | None] = mapped_column(ForeignKey("user_accounts.id", ondelete="SET NULL"))
    job_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_jobs.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[AuditEventStatus] = mapped_column(
        SAEnum(AuditEventStatus, native_enum=False),
        default=AuditEventStatus.SUCCESS,
        nullable=False,
    )
    source: Mapped[str | None] = mapped_column(String(64))
    event_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

    actor_user: Mapped[UserAccount | None] = relationship(
        back_populates="authored_audit_events",
        foreign_keys=[actor_user_id],
    )
    subject_user: Mapped[UserAccount | None] = relationship(
        back_populates="audit_events",
        foreign_keys=[subject_user_id],
    )
    job: Mapped[AnalysisJob | None] = relationship(back_populates="audit_events")


__all__ = [
    "AnalysisJob",
    "AnalysisResult",
    "Asset",
    "AssetCacheEntry",
    "AuditEvent",
    "AuditEventStatus",
    "CreditEventType",
    "CreditLedgerEntry",
    "JobStatus",
    "Portfolio",
    "PortfolioPosition",
    "PortfolioSource",
    "PortfolioTransaction",
    "SubscriptionPlan",
    "SubscriptionStatus",
    "TransactionType",
    "UserAccount",
    "UserExternalIdentity",
    "UserPlanSubscription",
]
