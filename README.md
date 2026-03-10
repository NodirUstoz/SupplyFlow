# SupplyFlow - Supply Chain Management Platform

A comprehensive, production-grade supply chain management platform built with Django REST Framework and React. SupplyFlow provides end-to-end supply chain visibility with supplier management, procurement workflows, shipment tracking, demand forecasting, quality inspections, and advanced analytics.

## Features

- **Supplier Management** - Maintain a complete supplier registry with contacts, ratings, contract tracking, and performance scoring.
- **Procurement Workflows** - Create purchase requisitions, convert them to purchase orders, and route through configurable multi-level approval workflows.
- **Shipment Tracking** - Track shipments in real-time with carrier integration, status updates, and geographic visualization.
- **Inventory Management** - Monitor stock levels across multiple warehouses with reorder point alerts and movement history.
- **Quality Inspections** - Record inspections against received goods, track defect reports, and enforce quality gates before inventory acceptance.
- **Demand Forecasting** - Leverage historical data with weighted moving-average and linear-regression models to predict future demand.
- **Supply Chain Analytics** - Dashboards covering spend analysis, supplier lead-time trends, on-time delivery rates, and procurement cycle metrics.
- **Role-Based Access Control** - Organization-scoped multi-tenancy with granular permissions (Admin, Manager, Buyer, Viewer).

## Tech Stack

| Layer          | Technology                                  |
|----------------|---------------------------------------------|
| Backend        | Python 3.11, Django 4.2, Django REST Framework 3.14 |
| Frontend       | React 18, Redux Toolkit, Recharts, Leaflet  |
| Database       | PostgreSQL 15                               |
| Cache / Broker | Redis 7                                     |
| Task Queue     | Celery 5                                    |
| Reverse Proxy  | Nginx                                       |
| Containerization | Docker, Docker Compose                    |

## Architecture

```
Client (React SPA)
    |
  Nginx (reverse proxy, static files)
    |
  Django / Gunicorn  <-->  PostgreSQL
    |                        |
  Celery Workers  <-->  Redis (broker + cache)
```

## Getting Started

### Prerequisites

- Docker and Docker Compose v2+
- Git

### Quick Start

```bash
# Clone the repository
git clone https://github.com/your-org/supplyflow.git
cd supplyflow

# Copy environment file and adjust values
cp .env.example .env

# Build and start all services
docker compose up --build -d

# Run database migrations
docker compose exec backend python manage.py migrate

# Create a superuser
docker compose exec backend python manage.py createsuperuser

# Load sample data (optional)
docker compose exec backend python manage.py loaddata sample_data

# The application is now available:
#   Frontend:  http://localhost
#   API:       http://localhost/api/
#   Admin:     http://localhost/api/admin/
```

### Local Development (without Docker)

#### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set environment variables or use .env
export DJANGO_SETTINGS_MODULE=config.settings.development
export DATABASE_URL=postgres://supplyflow:supplyflow@localhost:5432/supplyflow
export REDIS_URL=redis://localhost:6379/0

python manage.py migrate
python manage.py runserver
```

#### Frontend

```bash
cd frontend
npm install
npm start          # Runs on http://localhost:3000
```

#### Celery Worker

```bash
cd backend
celery -A config.celery worker -l info
celery -A config.celery beat -l info
```

## Project Structure

```
supplyflow/
├── backend/
│   ├── apps/
│   │   ├── accounts/       # Users, organizations, authentication
│   │   ├── suppliers/      # Supplier registry, contacts, ratings, contracts
│   │   ├── procurement/    # Requisitions, purchase orders, approval workflows
│   │   ├── shipments/      # Shipments, tracking, carrier management
│   │   ├── inventory/      # Warehouses, stock levels, inventory items
│   │   ├── quality/        # Inspections, defect reports
│   │   ├── forecasting/    # Demand forecasting models
│   │   └── analytics/      # Dashboards and reporting
│   ├── config/             # Django settings, URLs, WSGI, Celery
│   ├── utils/              # Shared utilities, pagination, exception handling
│   └── manage.py
├── frontend/
│   ├── public/
│   └── src/
│       ├── api/            # Axios API clients
│       ├── components/     # Reusable UI components
│       ├── pages/          # Page-level route components
│       ├── store/          # Redux store and slices
│       ├── hooks/          # Custom React hooks
│       └── styles/         # Global CSS
├── nginx/
│   └── nginx.conf
├── docker-compose.yml
├── .env.example
└── .gitignore
```

## API Documentation

Once the server is running, interactive API documentation is available at:

- **Swagger UI**: `http://localhost/api/docs/`
- **ReDoc**: `http://localhost/api/redoc/`

### Key Endpoints

| Resource               | Endpoint                        | Methods                    |
|------------------------|---------------------------------|----------------------------|
| Authentication         | `/api/auth/login/`              | POST                       |
| Users                  | `/api/accounts/users/`          | GET, POST                  |
| Suppliers              | `/api/suppliers/`               | GET, POST, PUT, DELETE     |
| Supplier Ratings       | `/api/suppliers/{id}/ratings/`  | GET, POST                  |
| Purchase Requisitions  | `/api/procurement/requisitions/`| GET, POST, PUT             |
| Purchase Orders        | `/api/procurement/orders/`      | GET, POST, PUT             |
| Approval Actions       | `/api/procurement/approvals/`   | GET, POST                  |
| Shipments              | `/api/shipments/`               | GET, POST, PUT             |
| Shipment Tracking      | `/api/shipments/{id}/tracking/` | GET, POST                  |
| Inventory Items        | `/api/inventory/items/`         | GET, POST, PUT             |
| Stock Levels           | `/api/inventory/stock/`         | GET                        |
| Quality Inspections    | `/api/quality/inspections/`     | GET, POST, PUT             |
| Demand Forecasts       | `/api/forecasting/`             | GET, POST                  |
| Analytics - Spend      | `/api/analytics/spend/`         | GET                        |
| Analytics - Lead Time  | `/api/analytics/lead-time/`     | GET                        |

## Environment Variables

See `.env.example` for all configurable variables. Key settings:

| Variable                | Description                          | Default                |
|-------------------------|--------------------------------------|------------------------|
| `DJANGO_SECRET_KEY`     | Django secret key                    | (required)             |
| `DJANGO_DEBUG`          | Enable debug mode                    | `False`                |
| `DATABASE_URL`          | PostgreSQL connection string         | (required)             |
| `REDIS_URL`             | Redis connection string              | `redis://redis:6379/0` |
| `ALLOWED_HOSTS`         | Comma-separated allowed hosts        | `localhost`            |
| `CORS_ALLOWED_ORIGINS`  | Comma-separated CORS origins         | `http://localhost:3000`|

## Testing

```bash
# Backend tests
docker compose exec backend python manage.py test

# Frontend tests
docker compose exec frontend npm test
```

## Deployment

For production deployment:

1. Update `.env` with production secrets and `DJANGO_DEBUG=False`.
2. Set `DJANGO_SETTINGS_MODULE=config.settings.production`.
3. Configure a proper SSL certificate in Nginx.
4. Use a managed PostgreSQL and Redis instance.
5. Run `python manage.py collectstatic` during the build.

## License

This project is proprietary software. All rights reserved.
