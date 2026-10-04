from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from .config import get_settings

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
    
    _hr_admin_engine = create_async_engine(
        settings.DATABASE_URL_HR_ADMIN,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=1800,
    )
    _compliance_auditor_engine = create_async_engine(
        settings.DATABASE_URL_COMPLIANCE_AUDITOR,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=1800,
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
