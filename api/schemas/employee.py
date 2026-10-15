from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from datetime import date
from decimal import Decimal
from typing import Optional

class EmployeeListItem(BaseModel):
    employee_id: int
    full_name: str
    email: str
    role_title: str
    department_name: str
    salary: Optional[Decimal] = None
    date_hired: date
    is_active: bool
    pii_redacted: bool = False
    
    model_config = ConfigDict(from_attributes=True)

class EmployeeCreate(BaseModel):
    full_name: str = Field(..., max_length=255)
    email: EmailStr
    role_id: int
    national_id: str = Field(..., max_length=255)  # plaintext, encrypted before storage
    contact_info: str = Field(..., max_length=500)
    date_hired: date
    salary: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)

class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None
    role_id: Optional[int] = None
    contact_info: Optional[str] = Field(None, max_length=500)


class EmployeeBatchCreate(BaseModel):
    employees: list[EmployeeCreate] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def distinct_emails(self):
        emails = [str(employee.email).casefold() for employee in self.employees]
        if len(set(emails)) != len(emails):
            raise ValueError("Each employee in a batch must have a different email.")
        return self

class EmployeeCreateResponse(BaseModel):
    employee_id: int
    full_name: str
    email: str
    role_id: int
    date_hired: date
    is_active: bool
    
    model_config = ConfigDict(from_attributes=True)

class EmployeeUpdateResponse(BaseModel):
    employee_id: int
    full_name: str
    email: str
    role_id: int
    is_active: bool
    
    model_config = ConfigDict(from_attributes=True)

class EmployeeDeactivateResponse(BaseModel):
    employee_id: int
    is_active: bool
