from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from .config import get_settings
from db.crypto.actor_context import create_actor_context

# Two engines: one per Postgres role
_hr_admin_engine = None
_compliance_auditor_engine = None
_hr_admin_session_factory = None
_compliance_auditor_session_factory = None


async def init_engines():
    """Initialize both connection pool engines. Called during app lifespan startup."""
    global _hr_admin_engine, _compliance_auditor_engine
    global _hr_admin_session_factory, _compliance_auditor_session_factory
    
    settings = get_settings()
    # Fail during startup instead of accepting API traffic that could create
    # employee/salary writes without a DB-verifiable actor assertion.
    create_actor_context(
        actor_user_id=1,
        actor_employee_id=0,
        db_role="hr_admin",
        secret_hex=settings.AUDIT_CONTEXT_SECRET,
        key_id=settings.AUDIT_CONTEXT_KEY_ID,
        now=1,
    )
    
    _hr_admin_engine = create_async_engine(
        settings.DATABASE_URL_HR_ADMIN,
        echo=False,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=10,
        pool_pre_ping=True,
        pool_recycle=1800,
        hide_parameters=True,
    )
    _compliance_auditor_engine = create_async_engine(
        settings.DATABASE_URL_COMPLIANCE_AUDITOR,
        echo=False,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=10,
        pool_pre_ping=True,
        pool_recycle=1800,
        hide_parameters=True,
    )
    
    _hr_admin_session_factory = async_sessionmaker(
        _hr_admin_engine, class_=AsyncSession, expire_on_commit=False
    )
    _compliance_auditor_session_factory = async_sessionmaker(
        _compliance_auditor_engine, class_=AsyncSession, expire_on_commit=False
    )


async def dispose_engines():
    """Dispose both engines. Called during app lifespan shutdown."""
    if _hr_admin_engine:
        await _hr_admin_engine.dispose()
    if _compliance_auditor_engine:
        await _compliance_auditor_engine.dispose()


def get_session_factory(role: str):
    """Return the session factory for the given role."""
    if role == "hr_admin":
        if _hr_admin_session_factory is None:
            raise RuntimeError("Database engines not initialized")
        return _hr_admin_session_factory
    elif role == "compliance_auditor":
        if _compliance_auditor_session_factory is None:
            raise RuntimeError("Database engines not initialized")
        return _compliance_auditor_session_factory
    else:
        raise ValueError(f"Unknown role: {role}")
