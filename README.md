# 🗓️ Leave Management System

A lightweight, high-performance RESTful API for managing employee leave requests, balances, and records. Built with **FastAPI** and a flat-file JSON database — zero infrastructure needed.

---

## ✨ Features

| Feature | Detail |
|---|---|
| **Thread-Safe I/O** | File-level locking via `threading.Lock` for concurrent safety |
| **Auto-Increment IDs** | Unique IDs managed in `_meta` of `database.json` |
| **Consistent Responses** | All endpoints return `{ success, message, data }` |
| **Auto Docs** | Swagger UI at `/docs`, ReDoc at `/redoc`, OpenAPI JSON at `/openapi.json` |
| **Balance Validation** | Prevents submission if remaining days are insufficient |
| **Approval Workflow** | Pending → Approved / Rejected; balance deducted only on approval |

---

## 🚀 Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/Abantikagithub/leave-management-system.git
cd leave-management-system
```

### 2. Create and activate a virtual environment

```bash
# Windows
conda create -p venv python=3.11 -y
conda activate venv/
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the server

```bash
uvicorn main:app --reload
```

The API will be live at **http://127.0.0.1:8000**

---

## 📖 Interactive Documentation

| URL | Description |
|---|---|
| `http://127.0.0.1:8000/docs` | **Swagger UI** — try every endpoint in your browser |
| `http://127.0.0.1:8000/redoc` | ReDoc — clean reference documentation |
| `http://127.0.0.1:8000/openapi.json` | Raw OpenAPI 3.x specification |

---

## 📁 Project Structure

```
leave-management-api/
├── main.py           # FastAPI application — all routes, schemas, helpers
├── database.json     # Flat-file data store (5 employees, 15 balance records)
├── requirements.txt  # Python dependencies
└── README.md         # You are here
```

---

## 🔌 API Reference

All responses follow this wrapper:

```json
{
  "success": true,
  "message": "Human-readable action message",
  "data": { }
}
```

### Employees

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/employees` | List all employees. Optional `?department=` filter. |
| `GET` | `/api/employees/{id}` | Get a single employee by ID. |
| `POST` | `/api/employees` | Create a new employee. |
| `PUT` | `/api/employees/{id}` | Update an existing employee. |

**Create employee — request body:**
```json
{
  "firstName": "Ananya",
  "lastName": "Das",
  "email": "ananya.das@company.com",
  "department": "Legal",
  "joinDate": "2025-01-20"
}
```

---

### Leave Requests

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/leaves` | List all requests. Filter by `?status=` and/or `?employeeId=`. |
| `GET` | `/api/leaves/employee/{id}` | All requests for one employee. |
| `GET` | `/api/leaves/{leaveId}` | Get a single leave request. |
| `POST` | `/api/leaves` | Submit a new leave request. |
| `PATCH` | `/api/leaves/{leaveId}/status` | Approve or reject a request. |

**Submit leave — request body:**
```json
{
  "employeeId": 1,
  "startDate": "2025-09-01",
  "endDate": "2025-09-05",
  "leaveType": "Annual",
  "reason": "Family vacation"
}
```

> `totalDays` is calculated automatically. `status` defaults to `"Pending"`.

**Update status — request body:**
```json
{ "status": "Approved" }
```

> Balance is deducted from the employee's record **only on Approval**.

---

### Leave Balances

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/leavebalances/employee/{id}/year/{year}` | All balances for an employee/year. |
| `GET` | `/api/leavebalances/employee/{id}/year/{year}/check` | Check if balance is sufficient. |
| `POST` | `/api/leavebalances` | Create a new balance record. |

**Check balance — query params:**
```
GET /api/leavebalances/employee/1/year/2025/check?leaveType=Annual&days=10
```

---

## 📦 Sample Data (database.json)

The repository ships with:
- **5 employees** across Engineering, HR, Finance, and Marketing.
- **15 leave balance records** (Annual / Sick / Casual for each employee, year 2025).
- An empty `leaves` array ready for new submissions.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| Framework | FastAPI 0.115 |
| Server | Uvicorn (ASGI) |
| Validation | Pydantic v2 |
| Persistence | Flat-file JSON + `threading.Lock` |

---

## 🔮 Future Enhancements

- **Database** — Migrate from JSON to PostgreSQL via SQLAlchemy.
- **Auth** — JWT-based authentication and RBAC.
- **Notifications** — Automated email alerts on status changes.
- **Holiday Calendar** — Skip weekends/public holidays in day calculations.
- **Docker** — Containerise with a `Dockerfile` and `docker-compose.yml`.

---
