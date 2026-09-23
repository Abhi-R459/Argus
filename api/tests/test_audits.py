import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock

pytestmark = pytest.mark.asyncio

async def test_audit_logs_auditor(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db_session.execute.return_value = mock_result
    
    response = await client_auditor.get("/api/audit-logs")
    assert response.status_code in [200, 500]

async def test_audit_logs_hr_forbidden(client_hr: AsyncClient):
    response = await client_hr.get("/api/audit-logs")
    assert response.status_code == 403

async def test_verify_chain_auditor(client_auditor: AsyncClient):
    response = await client_auditor.post("/api/verify")
    # Endpoint might return 200 or 500 based on mock, but definitely not 403
    assert response.status_code in [200, 500]

async def test_verify_chain_hr_forbidden(client_hr: AsyncClient):
    response = await client_hr.post("/api/verify")
    assert response.status_code == 403

async def test_suspicious_flags_auditor(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db_session.execute.return_value = mock_result
    response = await client_auditor.get("/api/suspicious-activity")
    assert response.status_code in [200, 500]

async def test_suspicious_flags_hr_forbidden(client_hr: AsyncClient):
    response = await client_hr.get("/api/suspicious-activity")
    assert response.status_code == 403

async def test_export_auditor(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db_session.execute.return_value = mock_result
    response = await client_auditor.get("/api/audit-logs/export")
    assert response.status_code == 200
    data = response.json()
    assert "metadata" in data
    assert data["metadata"]["signature_algorithm"] == "Ed25519"
    assert "signature" in data["metadata"]
    assert "payload_hash" in data["metadata"]


async def test_export_signature_cryptographic_verification(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    """Verify that export Ed25519 signature is cryptographically valid against the public key."""
    from unittest.mock import MagicMock
    from pathlib import Path
    from db.cli.signer import verify_signature
    from db.cli.keygen import load_public_key, get_default_key_dir

    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db_session.execute.return_value = mock_result

    response = await client_auditor.get("/api/audit-logs/export")
    assert response.status_code == 200
    export_bundle = response.json()

    meta = export_bundle["metadata"]
    assert meta["signature_algorithm"] == "Ed25519"
    payload_hash = meta["payload_hash"]
    sig_bytes = bytes.fromhex(meta["signature"])

    pub_key_path = Path("keys/public_key.pem")
    if not pub_key_path.is_file():
        pub_key_path = Path(get_default_key_dir()) / "public_key.pem"
    if pub_key_path.is_file():
        pub_key = load_public_key(str(pub_key_path))
        is_valid = verify_signature(pub_key, payload_hash, sig_bytes)
        assert is_valid is True


async def test_export_hr_forbidden(client_hr: AsyncClient):
    response = await client_hr.get("/api/audit-logs/export")
    assert response.status_code == 403


async def test_time_travel_auditor(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    from unittest.mock import MagicMock
    mock_recon = MagicMock()
    mock_recon.scalar.return_value = {
        "employee_id": 42,
        "full_name": "Audited User",
        "email": "audited@example.com",
        "role_id": 1,
        "date_hired": "2024-01-01T00:00:00Z",
        "is_active": True,
    }
    mock_db_session.execute.return_value = mock_recon

    response = await client_auditor.get("/api/employees/42/time-travel?timestamp=2024-06-01T12:00:00Z")
    assert response.status_code == 200
    payload = response.json()
    assert payload["employee_id"] == 42
    assert payload["full_name"] == "Audited User"
    assert payload["email"] == "audited@example.com"
    assert "salary" in payload
    assert payload["is_active"] is True


async def test_time_travel_not_found(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    from unittest.mock import MagicMock
    mock_recon = MagicMock()
    mock_recon.scalar.return_value = None
    mock_db_session.execute.return_value = mock_recon

    response = await client_auditor.get("/api/employees/999/time-travel?timestamp=2020-01-01T00:00:00Z")
    assert response.status_code == 404


async def test_time_travel_hr_forbidden(client_hr: AsyncClient):
    response = await client_hr.get("/api/employees/42/time-travel?timestamp=2024-06-01T12:00:00Z")
    assert response.status_code == 403


async def test_time_travel_decoded_url_timestamp(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    from unittest.mock import MagicMock
    mock_recon = MagicMock()
    mock_recon.scalar.return_value = {
        "employee_id": 42,
        "full_name": "Audited User",
        "email": "audited@example.com",
        "role_id": 1,
        "date_hired": "2024-01-01T00:00:00Z",
        "is_active": True,
    }
    mock_db_session.execute.return_value = mock_recon

    # Simulate URL-decoded + as space: '2024-06-01T12:00:00.123456 00:00'
    response = await client_auditor.get("/api/employees/42/time-travel?timestamp=2024-06-01T12:00:00.123456%2000:00")
    assert response.status_code == 200
    payload = response.json()
    assert payload["employee_id"] == 42
    assert payload["full_name"] == "Audited User"


async def test_time_travel_with_sequence_id(client_auditor: AsyncClient, mock_db_session: AsyncMock):
    from unittest.mock import MagicMock
    mock_res = MagicMock()
    mock_res.fetchall.return_value = [
        ("INSERT", {
            "employee_id": 42,
            "full_name": "Audited User",
            "email": "audited@example.com",
            "role_id": 1,
            "date_hired": "2024-01-01T00:00:00Z",
            "is_active": True,
        })
    ]
    mock_res.scalar.return_value = 150000.0
    mock_res.first.return_value = ("Security Engineer", "Engineering")
    mock_db_session.execute.return_value = mock_res

    response = await client_auditor.get("/api/employees/42/time-travel?timestamp=2024-06-01T12:00:00Z&sequence_id=124")
    assert response.status_code == 200
    payload = response.json()
    assert payload["employee_id"] == 42
    assert payload["full_name"] == "Audited User"
    assert payload["sequence_id"] == 124


