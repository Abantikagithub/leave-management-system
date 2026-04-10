"""
Leave Management System — FastAPI Backend
==========================================
Run with:  uvicorn main:app --reload
Docs at:   http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Generic, List, Optional, TypeVar

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field, field_validator

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH = os.path.join(os.path.dirname(__file__), "database.json")
_db_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

@contextmanager
def db_transaction():
    """Thread-safe read-modify-write block over database.json."""
    with _db_lock:
        with open(DB_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        try:
            yield data
        finally:
            with open(DB_PATH, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, default=str)


def read_db() -> dict:
    with _db_lock:
        with open(DB_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)


def next_id(data: dict, key: str) -> int:
    data["_meta"][key] += 1
    return data["_meta"][key]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class LeaveType(str, Enum):
    annual = "Annual"
    sick = "Sick"
    casual = "Casual"


class LeaveStatus(str, Enum):
    pending = "Pending"
    approved = "Approved"
    rejected = "Rejected"


# ---------------------------------------------------------------------------
# Pydantic schemas — Request bodies
# ---------------------------------------------------------------------------

class EmployeeCreate(BaseModel):
    firstName: str = Field(..., min_length=1, max_length=80, examples=["Arjun"])
    lastName: str = Field(..., min_length=1, max_length=80, examples=["Sharma"])
    email: EmailStr = Field(..., examples=["arjun@company.com"])
    department: str = Field(..., min_length=1, max_length=100, examples=["Engineering"])
    joinDate: str = Field(..., examples=["2024-01-15"],
                          description="ISO-8601 date: YYYY-MM-DD")

    @field_validator("joinDate")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("joinDate must be YYYY-MM-DD")
        return v


class EmployeeUpdate(BaseModel):
    firstName: Optional[str] = Field(None, min_length=1, max_length=80)
    lastName: Optional[str] = Field(None, min_length=1, max_length=80)
    email: Optional[EmailStr] = None
    department: Optional[str] = Field(None, min_length=1, max_length=100)
    joinDate: Optional[str] = None

    @field_validator("joinDate")
    @classmethod
    def validate_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("joinDate must be YYYY-MM-DD")
        return v


class LeaveRequest(BaseModel):
    employeeId: int = Field(..., gt=0, examples=[1])
    startDate: str = Field(..., examples=["2025-08-01"])
    endDate: str = Field(..., examples=["2025-08-05"])
    leaveType: LeaveType = Field(..., examples=["Annual"])
    reason: str = Field(..., min_length=5, max_length=500,
                        examples=["Family vacation"])

    @field_validator("startDate", "endDate")
    @classmethod
    def validate_dates(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Dates must be YYYY-MM-DD")
        return v


class LeaveStatusUpdate(BaseModel):
    status: LeaveStatus


# ---------------------------------------------------------------------------
# Pydantic schemas — Response wrapper
# ---------------------------------------------------------------------------

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: Optional[T] = None


def ok(message: str, data: Any = None) -> ApiResponse:
    return ApiResponse(success=True, message=message, data=data)


def fail(message: str, data: Any = None) -> ApiResponse:
    return ApiResponse(success=False, message=message, data=data)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _calc_leave_days(start: str, end: str) -> int:
    """Returns inclusive count of calendar days (≥ 1)."""
    s = datetime.strptime(start, "%Y-%m-%d").date()
    e = datetime.strptime(end, "%Y-%m-%d").date()
    return (e - s).days + 1


def _find_employee(data: dict, emp_id: int) -> Optional[dict]:
    return next((e for e in data["employees"] if e["employeeId"] == emp_id), None)


def _find_balance(data: dict, emp_id: int, year: int, leave_type: str) -> Optional[dict]:
    return next(
        (b for b in data["leaveBalances"]
         if b["employeeId"] == emp_id and b["year"] == year
         and b["leaveType"] == leave_type),
        None,
    )


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Leave Management System",
    description=(
        "A RESTful API for managing employee leave requests, balances, and records. "
        "Uses a flat-file JSON database with thread-safe locking."
    ),
    version="1.0.0",
    contact={"name": "HR Systems Team", "email": "hr-systems@company.com"},
    license_info={"name": "MIT"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===========================================================================
# EMPLOYEE ENDPOINTS
# ===========================================================================

@app.get(
    "/api/employees",
    tags=["Employees"],
    summary="List all employees",
    response_model=ApiResponse,
)
def list_employees(department: Optional[str] = Query(None, description="Filter by department")):
    data = read_db()
    employees = data["employees"]
    if department:
        employees = [e for e in employees if e["department"].lower() == department.lower()]
    return ok(f"Retrieved {len(employees)} employee(s).", employees)


@app.get(
    "/api/employees/{employee_id}",
    tags=["Employees"],
    summary="Get a single employee by ID",
    response_model=ApiResponse,
)
def get_employee(employee_id: int):
    data = read_db()
    emp = _find_employee(data, employee_id)
    if not emp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Employee {employee_id} not found.")
    return ok("Employee retrieved successfully.", emp)


@app.post(
    "/api/employees",
    tags=["Employees"],
    summary="Create a new employee",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse,
)
def create_employee(body: EmployeeCreate):
    with db_transaction() as data:
        # Guard duplicate email
        if any(e["email"].lower() == body.email.lower() for e in data["employees"]):
            raise HTTPException(status.HTTP_409_CONFLICT,
                                detail=f"Email '{body.email}' is already registered.")
        new_id = next_id(data, "lastEmployeeId")
        employee = {"employeeId": new_id, **body.model_dump()}
        data["employees"].append(employee)
    return ok(f"Employee created with ID {new_id}.", employee)


@app.put(
    "/api/employees/{employee_id}",
    tags=["Employees"],
    summary="Update an existing employee",
    response_model=ApiResponse,
)
def update_employee(employee_id: int, body: EmployeeUpdate):
    with db_transaction() as data:
        emp = _find_employee(data, employee_id)
        if not emp:
            raise HTTPException(status.HTTP_404_NOT_FOUND,
                                detail=f"Employee {employee_id} not found.")
        updates = body.model_dump(exclude_none=True)
        if "email" in updates:
            conflict = next(
                (e for e in data["employees"]
                 if e["email"].lower() == updates["email"].lower()
                 and e["employeeId"] != employee_id),
                None,
            )
            if conflict:
                raise HTTPException(status.HTTP_409_CONFLICT,
                                    detail=f"Email '{updates['email']}' already in use.")
        emp.update(updates)
    return ok(f"Employee {employee_id} updated successfully.", emp)


# ===========================================================================
# LEAVE ENDPOINTS
# ===========================================================================

@app.get(
    "/api/leaves",
    tags=["Leaves"],
    summary="List leave requests (filterable by status or employeeId)",
    response_model=ApiResponse,
)
def list_leaves(
    status_filter: Optional[LeaveStatus] = Query(None, alias="status",
                                                  description="Filter by leave status"),
    employee_id: Optional[int] = Query(None, alias="employeeId",
                                        description="Filter by employee ID"),
):
    data = read_db()
    leaves = data["leaves"]
    if status_filter:
        leaves = [l for l in leaves if l["status"] == status_filter.value]
    if employee_id:
        leaves = [l for l in leaves if l["employeeId"] == employee_id]
    return ok(f"Retrieved {len(leaves)} leave request(s).", leaves)


@app.get(
    "/api/leaves/employee/{employee_id}",
    tags=["Leaves"],
    summary="Get all leave requests for a specific employee",
    response_model=ApiResponse,
)
def get_leaves_by_employee(
    employee_id: int,
    status_filter: Optional[LeaveStatus] = Query(None, alias="status"),
):
    data = read_db()
    if not _find_employee(data, employee_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            detail=f"Employee {employee_id} not found.")
    leaves = [l for l in data["leaves"] if l["employeeId"] == employee_id]
    if status_filter:
        leaves = [l for l in leaves if l["status"] == status_filter.value]
    return ok(f"Retrieved {len(leaves)} leave request(s) for employee {employee_id}.", leaves)


@app.get(
    "/api/leaves/{leave_id}",
    tags=["Leaves"],
    summary="Get a single leave request by ID",
    response_model=ApiResponse,
)
def get_leave(leave_id: int):
    data = read_db()
    leave = next((l for l in data["leaves"] if l["leaveId"] == leave_id), None)
    if not leave:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            detail=f"Leave request {leave_id} not found.")
    return ok("Leave request retrieved successfully.", leave)


@app.post(
    "/api/leaves",
    tags=["Leaves"],
    summary="Submit a new leave request",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse,
)
def create_leave(body: LeaveRequest):
    # Validate date order
    start = datetime.strptime(body.startDate, "%Y-%m-%d").date()
    end = datetime.strptime(body.endDate, "%Y-%m-%d").date()
    if end < start:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="endDate must be on or after startDate.")

    total_days = _calc_leave_days(body.startDate, body.endDate)

    with db_transaction() as data:
        if not _find_employee(data, body.employeeId):
            raise HTTPException(status.HTTP_404_NOT_FOUND,
                                detail=f"Employee {body.employeeId} not found.")

        # Check balance
        year = start.year
        balance = _find_balance(data, body.employeeId, year, body.leaveType.value)
        if not balance:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(f"No {body.leaveType.value} leave balance found for employee "
                        f"{body.employeeId} in {year}."),
            )
        if balance["remainingDays"] < total_days:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(f"Insufficient balance. Requested {total_days} day(s) but only "
                        f"{balance['remainingDays']} remaining."),
            )

        new_id = next_id(data, "lastLeaveId")
        leave = {
            "leaveId": new_id,
            "employeeId": body.employeeId,
            "startDate": body.startDate,
            "endDate": body.endDate,
            "leaveType": body.leaveType.value,
            "reason": body.reason,
            "totalDays": total_days,
            "status": LeaveStatus.pending.value,
            "appliedOn": date.today().isoformat(),
        }
        data["leaves"].append(leave)

    return ok(f"Leave request submitted. {total_days} day(s) pending approval.", leave)


@app.patch(
    "/api/leaves/{leave_id}/status",
    tags=["Leaves"],
    summary="Approve or Reject a leave request",
    response_model=ApiResponse,
)
def update_leave_status(leave_id: int, body: LeaveStatusUpdate):
    if body.status == LeaveStatus.pending:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Cannot manually set status back to 'Pending'.")

    with db_transaction() as data:
        leave = next((l for l in data["leaves"] if l["leaveId"] == leave_id), None)
        if not leave:
            raise HTTPException(status.HTTP_404_NOT_FOUND,
                                detail=f"Leave request {leave_id} not found.")
        if leave["status"] != LeaveStatus.pending.value:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"Leave request is already '{leave['status']}' and cannot be changed.",
            )

        leave["status"] = body.status.value

        # Deduct from balance only on approval
        if body.status == LeaveStatus.approved:
            start_year = datetime.strptime(leave["startDate"], "%Y-%m-%d").year
            balance = _find_balance(data, leave["employeeId"], start_year, leave["leaveType"])
            if balance:
                balance["usedDays"] += leave["totalDays"]
                balance["remainingDays"] -= leave["totalDays"]

    action = "approved" if body.status == LeaveStatus.approved else "rejected"
    return ok(f"Leave request {leave_id} has been {action}.", leave)


# ===========================================================================
# LEAVE BALANCE ENDPOINTS
# ===========================================================================

@app.get(
    "/api/leavebalances/employee/{employee_id}/year/{year}",
    tags=["Leave Balances"],
    summary="Get all leave balances for an employee in a given year",
    response_model=ApiResponse,
)
def get_leave_balances(employee_id: int, year: int):
    data = read_db()
    if not _find_employee(data, employee_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            detail=f"Employee {employee_id} not found.")
    balances = [
        b for b in data["leaveBalances"]
        if b["employeeId"] == employee_id and b["year"] == year
    ]
    if not balances:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"No leave balance records found for employee {employee_id} in {year}.",
        )
    return ok(f"Retrieved {len(balances)} balance record(s) for employee {employee_id}.", balances)


@app.get(
    "/api/leavebalances/employee/{employee_id}/year/{year}/check",
    tags=["Leave Balances"],
    summary="Check if an employee has enough balance for a requested leave",
    response_model=ApiResponse,
)
def check_leave_balance(
    employee_id: int,
    year: int,
    leave_type: LeaveType = Query(..., alias="leaveType"),
    days: int = Query(..., gt=0, description="Number of days requested"),
):
    data = read_db()
    if not _find_employee(data, employee_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            detail=f"Employee {employee_id} not found.")
    balance = _find_balance(data, employee_id, year, leave_type.value)
    if not balance:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"No {leave_type.value} balance found for employee {employee_id} in {year}.",
        )
    has_enough = balance["remainingDays"] >= days
    result = {
        "employeeId": employee_id,
        "leaveType": leave_type.value,
        "year": year,
        "requestedDays": days,
        "remainingDays": balance["remainingDays"],
        "sufficient": has_enough,
    }
    msg = (
        f"Sufficient balance: {balance['remainingDays']} days available, {days} requested."
        if has_enough
        else f"Insufficient balance: only {balance['remainingDays']} days available, {days} requested."
    )
    return ok(msg, result)

import uvicorn

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)