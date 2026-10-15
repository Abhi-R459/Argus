from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.asyncio


def employee(index=1):
    return {'full_name': f'QA Employee {index}', 'email': f'qa-{index}@example.com',
        'role_id': 1, 'national_id': f'QA-NATIONAL-{index}', 'contact_info': 'Fictional QA contact',
        'date_hired': '2024-01-01', 'salary': '500000.00'}


@pytest.mark.parametrize('rows', [[], [employee(index) for index in range(21)],
    [employee(), {**employee(2), 'email': 'QA-1@example.com'}],
    [{**employee(), 'salary': '10000000000.00'}],
    [{**employee(), 'date_hired': '2024-02-30'}]])
async def test_batch_rejects_invalid_payload_before_writing(client_hr, rows):
    with patch('api.routers.employees.create_employee', new_callable=AsyncMock) as create:
        response = await client_hr.post('/api/employees/batch', json={'employees': rows})
    assert response.status_code == 422
    create.assert_not_awaited()


async def test_batch_requires_hr_role(client_auditor):
    response = await client_auditor.post('/api/employees/batch', json={'employees': [employee()]})
    assert response.status_code == 403


async def test_batch_reuses_normal_employee_creation_and_same_transaction(client_hr, mock_db_session, mock_hr_user):
    from api.schemas.employee import EmployeeCreateResponse
    created = [EmployeeCreateResponse(employee_id=index, full_name=f'QA Employee {index}',
        email=f'qa-{index}@example.com', role_id=1, date_hired=date(2024, 1, 1), is_active=True) for index in (1, 2)]
    with patch('api.routers.employees.create_employee', new_callable=AsyncMock, side_effect=created) as create:
        response = await client_hr.post('/api/employees/batch', json={'employees': [employee(1), employee(2)]})
    assert response.status_code == 201, response.text
    assert [item['employee_id'] for item in response.json()] == [1, 2]
    assert create.await_count == 2
    assert all(call.args[1:] == (mock_hr_user, mock_db_session) for call in create.await_args_list)
    mock_db_session.commit.assert_not_awaited()  # Only the real dependency commits.


async def test_batch_stops_at_failed_row_and_explains_atomicity(client_hr):
    with patch('api.routers.employees.create_employee', new_callable=AsyncMock,
            side_effect=[object(), HTTPException(409, 'An employee with this email already exists.')]) as create:
        response = await client_hr.post('/api/employees/batch', json={'employees': [employee(1), employee(2), employee(3)]})
    assert response.status_code == 409
    assert 'Batch row 2:' in response.json()['detail']
    assert 'No employees were added from this batch.' in response.json()['detail']
    assert create.await_count == 2


async def test_batch_does_not_expose_database_errors(client_hr):
    with patch('api.routers.employees.create_employee', new_callable=AsyncMock,
            side_effect=IntegrityError('private SQL', {}, Exception('private address'))):
        response = await client_hr.post('/api/employees/batch', json={'employees': [employee()]})
    assert response.status_code == 409
    assert 'private' not in response.text
