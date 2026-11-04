# ORBIT Analytics Agent

**A natural-language analytics platform for querying business data and generating interactive insights.**

ORBIT Analytics Agent is a full-stack analytics application that enables users to ask business questions in natural language and receive structured results, visualizations, and generated SQL queries.

Instead of manually writing SQL queries, users can explore business data through a conversational analytics interface.

---

## Overview

ORBIT simplifies data analysis by connecting a React-based dashboard with a FastAPI backend and a SQLite demo warehouse.

Users can ask questions such as:

- Show monthly revenue for 2024.
- Show revenue by region.
- Which are the top 5 products by revenue?
- How many orders are there by status?

The application processes supported questions, identifies the relevant analytics operation, generates an approved SQL query, executes it against the database, and displays the results.

## Features

- **Natural Language Analytics** – Ask business questions using everyday language.
- **Automated SQL Generation** – Generate SQL queries for supported analytics questions.
- **Interactive Visualizations** – Explore results through charts and graphs.
- **KPI Metrics** – Display important business metrics.
- **Data Source Explorer** – Inspect database tables and schema information.
- **SQL Explorer** – View and copy generated SQL queries.
- **Query History** – Access previous analytics requests.
- **CSV Export** – Export query results.
- **SQL Validation** – Apply read-only query validation before execution.
- **Agent Execution Trace** – View the workflow used to process a query.

## Tech Stack

| Layer | Technologies |
|---|---|
| Frontend | React.js, TypeScript, Vite |
| Styling | CSS |
| Charts | Recharts |
| Icons | Lucide React |
| Backend | Python, FastAPI |
| Database | SQLite |
| API | REST API |
| Server | Uvicorn |
| Containerization | Docker, Docker Compose |

## Architecture

```text
                  USER
                    |
                    v
           React Analytics UI
                    |
                    v
               FastAPI API
                    |
                    v
           Analytics Workflow
                    |
          +---------+---------+
          |         |         |
          v         v         v
       Planner  SQL Safety  Executor
          |         |         |
          +---------+---------+
                    |
                    v
             SQLite Database
                    |
                    v
         Results & Visualizations
                    |
                    v
             React Dashboard
```

## Project Structure

```text
orbit-analytics-agent/
│
├── .github/
│   └── workflows/
│
├── backend/
│
├── frontend/
│
├── docs/
│
├── .env.example
├── .gitignore
├── docker-compose.yml
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 20+
- npm
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/Nithish464/orbit-analytics-agent.git
cd orbit-analytics-agent
```

### 2. Start the Backend

Open a terminal:

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows CMD:

```cmd
.venv\Scripts\activate.bat
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the FastAPI server:

```bash
python -m uvicorn app.main:app --reload
```

Backend URL:

```text
http://127.0.0.1:8000
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

Health endpoint:

```text
http://127.0.0.1:8000/api/health
```

### 3. Start the Frontend

Open another terminal from the project root:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

Frontend URL:

```text
http://localhost:5173
```

## Example Analytics Queries

Try these questions in the ORBIT analytics interface:

| Query | Expected Analysis |
|---|---|
| Show monthly revenue for 2024 | Monthly revenue breakdown |
| Show revenue by region | Regional revenue comparison |
| Which are the top 5 products by revenue? | Top-performing products |
| How many orders are there by status? | Order status distribution |

## Database Schema

The demo warehouse contains four tables:

| Table | Description |
|---|---|
| customers | Customer information |
| products | Product details |
| orders | Order transactions |
| order_items | Individual items within orders |

## Security

ORBIT includes an application-level read-only SQL validation layer designed to reduce unsafe query execution.

Current safeguards include:

- SELECT-only query validation.
- Blocking potentially destructive SQL operations.
- Schema table allowlisting.
- Query comment and multiple-statement checks.
- Query result limits.

**Note:** These safeguards are designed for the demonstration project and do not guarantee production-grade SQL security. Production deployments should additionally use database-level read-only permissions and robust SQL parsing.

## Current Implementation

The current version uses a deterministic analytics workflow with predefined query-planning logic and approved SQL patterns.

It demonstrates a natural-language analytics experience but is not yet a fully autonomous LLM-powered analytics agent.

## Future Improvements

- Integrate an LLM-powered query planning system.
- Support additional database connectors.
- Add authentication and role-based access control.
- Improve SQL parsing and database-level security.
- Add advanced analytics and forecasting.
- Deploy with production monitoring.
- Add automated frontend and API integration tests.

## Author

**Nithishkumar K**

- GitHub: [Nithish464](https://github.com/Nithish464)
- Repository: [ORBIT Analytics Agent](https://github.com/Nithish464/orbit-analytics-agent)

---

## License

This project is developed for learning, demonstration, and portfolio purposes.
