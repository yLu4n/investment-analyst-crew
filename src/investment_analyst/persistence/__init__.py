from __future__ import annotations

from typing import Any

_EXPORTS = {
    "AnalysisJob": "investment_analyst.persistence.models",
    "AnalysisResult": "investment_analyst.persistence.models",
    "Asset": "investment_analyst.persistence.models",
    "AssetCacheEntry": "investment_analyst.persistence.models",
    "AuditEvent": "investment_analyst.persistence.models",
    "AuditEventStatus": "investment_analyst.persistence.models",
    "Base": "investment_analyst.persistence.base",
    "CreditEventType": "investment_analyst.persistence.models",
    "CreditLedgerEntry": "investment_analyst.persistence.models",
    "DATABASE_URL_ENV": "investment_analyst.persistence.database_config",
    "JobStatus": "investment_analyst.persistence.models",
    "Portfolio": "investment_analyst.persistence.models",
    "PortfolioPosition": "investment_analyst.persistence.models",
    "PortfolioSource": "investment_analyst.persistence.models",
    "PortfolioTransaction": "investment_analyst.persistence.models",
    "SubscriptionPlan": "investment_analyst.persistence.models",
    "SubscriptionStatus": "investment_analyst.persistence.models",
    "TEST_DATABASE_URL_ENV": "investment_analyst.persistence.database_config",
    "TimestampMixin": "investment_analyst.persistence.base",
    "TransactionType": "investment_analyst.persistence.models",
    "UserAccount": "investment_analyst.persistence.models",
    "UserExternalIdentity": "investment_analyst.persistence.models",
    "UserPlanSubscription": "investment_analyst.persistence.models",
    "UUIDPrimaryKeyMixin": "investment_analyst.persistence.base",
    "get_database_url": "investment_analyst.persistence.database_config",
    "get_test_database_url": "investment_analyst.persistence.database_config",
    "load_database_env": "investment_analyst.persistence.database_config",
    "require_test_database_url": "investment_analyst.persistence.database_config",
    "utcnow": "investment_analyst.persistence.base",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from importlib import import_module

    module = import_module(_EXPORTS[name])
    value = getattr(module, name)
    globals()[name] = value
    return value
