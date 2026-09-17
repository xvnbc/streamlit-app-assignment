# EV Car-Sharing Operations Dashboard

A Streamlit dashboard analysing one year of anonymised events from an urban electric car-sharing service (mobility sector). Each event is either a customer rental or a service operation, where an agent charges a car or moves it off a charging station.

The dashboard answers two questions:

1. How are the vehicles used by customers, and how do agents charge and relocate them?
2. While a car is charging, it may be rented before it is full. Above which battery level is this unlikely enough to send an agent to move it and avoid idle-at-full fees?

## Quick start with Docker

```bash
docker run --rm -p 8501:8501 yuqixin/assignment-streamlit-app:latest
```

Then open http://localhost:8501.

Image on DockerHub: https://hub.docker.com/r/<dockerhub-username>/assignment-streamlit-app

## Run locally

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/xvnbc/streamlit-app-assignment.git
cd streamlit-app-assignment
uv sync
uv run streamlit run app/streamlit_app.py
```

Without uv:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e . --no-deps
streamlit run app/streamlit_app.py
```

The app reads `data/rentals.csv` by default. Set the `DATA_PATH` environment variable to use another file.

## Project structure

```
├── app/streamlit_app.py          Streamlit dashboard
├── data/                         Input data
├── src/assignment_streamlit_app/
│   ├── config.py                 Column names, event types, defaults
│   ├── loading.py                CSV reading, column and type normalisation
│   ├── cleaning.py               Deduplication, event labelling, battery imputation
│   ├── filters.py                Date, event type and vehicle filters
│   ├── metrics.py                KPIs, demand patterns, battery distributions
│   └── threshold.py              Rental probability by battery level
├── tests/                        pytest suite
├── Dockerfile
└── .github/workflows/ci.yml      Lint and tests on every push and pull request
```

## Data preparation

`cleaning.build_rental_dataset` turns the raw file into an analysis-ready table:

- removes duplicated rows, keeping one event per vehicle and start time;
- drops rows with missing values that cannot be reconstructed;
- labels each event as `customer_rental`, `agent_charge` or `agent_move`;
- rebuilds the battery level at the start of agent events from the vehicle's previous event, and the outcome of each charging session from its next event.

## Development

```bash
uv run ruff check .
uv run pytest --cov
```

Both checks run in GitHub Actions on every push and pull request.

Dependencies are locked in `uv.lock`. After changing them, refresh the pip files:

```bash
uv export --no-dev --no-hashes --no-emit-project -o requirements.txt
uv export --no-hashes --no-emit-project -o requirements-dev.txt
```

Build the image yourself:

```bash
docker build -t assignment-streamlit-app .
docker run --rm -p 8501:8501 assignment-streamlit-app
```
