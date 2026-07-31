from pydantic import BaseModel, ConfigDict, Field
from datetime import date
from decimal import Decimal

class SalaryCreate(BaseModel):
    amount: Decimal = Field(..., gt=0)
    effective_date: date

class SalaryCreateResponse(BaseModel):
    salary_history_id: int
    employee_id: int
    amount: Decimal
    effective_date: date
    
    model_config = ConfigDict(from_attributes=True)
