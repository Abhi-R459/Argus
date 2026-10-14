"""Database business-rule responses must remain actionable without leaking PII."""
import json
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import DBAPIError, TimeoutError

from api.main import database_error_handler


@pytest.mark.asyncio
@pytest.mark.parametrize("sqlstate,status,message", [
    ("P0002", 422, "Salary cannot decrease by more than 30%"),
    ("P0003", 403, "You cannot change your own salary"),
    ("08006", 503, "temporarily unavailable"),
    ("P0001", 503, "temporarily unavailable"),
])
async def test_database_errors_redact_driver_details(sqlstate, status, message):
    original = Exception("PRIVATE-NATIONAL-ID")
    original.sqlstate = sqlstate
    error = DBAPIError("INSERT private data", {"contact": "PRIVATE-CONTACT"}, original)
    response = await database_error_handler(SimpleNamespace(), error)
    assert response.status_code == status
    assert message in json.loads(response.body)["detail"]
    assert b"PRIVATE" not in response.body
    assert b"INSERT" not in response.body


@pytest.mark.asyncio
async def test_pool_timeout_remains_a_service_error():
    response = await database_error_handler(SimpleNamespace(), TimeoutError("PRIVATE-CONNECTION"))
    assert response.status_code == 503
    assert b"PRIVATE" not in response.body
