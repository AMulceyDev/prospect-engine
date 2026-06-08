FROM python:3.12-slim

WORKDIR /app

# installer uv
RUN pip install uv

# copier dépendances
COPY pyproject.toml uv.lock* /app/

# installer deps via uv
RUN uv sync

# copier code
COPY . /app

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]