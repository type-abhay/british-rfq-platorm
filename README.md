# British Auction in RFQ System — Full-Stack Deliverable

A complete full-stack implementation of a British Auction Request for Quotation (RFQ) system with automatic anti-sniping bid extensions, configurable trigger rules (`BID_RECEIVED`, `ANY_RANK_CHANGE`, `L1_CHANGE`), hard forced-close capping, row-level concurrency locking, and a minimal React + TypeScript frontend.

## Deliverables Included
1. **High-Level Design & Architecture Diagram**: `docs/HLD_and_Schema_Design.md` (and PDF deliverable)
2. **Database Schema Design & Migrations**: `app/models.py`, `alembic/versions/0001_initial_schema.py`, and `docs/HLD_and_Schema_Design.md`
3. **Backend Code (FastAPI + SQLAlchemy 2.0 + PostgreSQL)**: `app/`, `tests/`, `seed.py`
4. **Frontend Code (React + TypeScript + Vite)**: `frontend/` (styled with `#fefae0` background, `#283618` accent, `#606c38` hover)

---

## Quick Start (Windows Command Prompt / PowerShell)

### 1. Start the PostgreSQL Docker Container (on port 5433)
If your `rfq-db` container from earlier is already created, ensure it is running:
```cmd
docker start rfq-db
```
*(If you ever need to create it fresh: `docker run --name rfq-db -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=british_auction_rfq -p 5433:5432 -d postgres:16`)*

### 2. Run the FastAPI Backend (Terminal 1)
From the `british_auction_rfq` root directory:
```cmd
venv\Scripts\activate
pip install -r requirements.txt
pytest tests/ -v
python seed.py
uvicorn app.main:app --reload
```
*Note: `.env` is pre-configured to connect to `postgresql+psycopg2://postgres:postgres@127.0.0.1:5433/british_auction_rfq` automatically, and `app/main.py` automatically creates any missing tables on startup.*

### 3. Run the React Frontend (Terminal 2)
Open a second terminal, navigate to `british_auction_rfq/frontend`, and run:
```cmd
cd frontend
npm install
npm run dev
```
Open **`http://localhost:5173`** in your browser.
