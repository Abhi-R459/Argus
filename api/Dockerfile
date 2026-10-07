FROM python:3.11-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install python dependencies
COPY api/requirements.lock ./requirements.lock
RUN python -m pip install --no-cache-dir --disable-pip-version-check --require-hashes -r requirements.lock

# The API imports shared database utilities from the repository-level db package.
RUN useradd --create-home --uid 10001 argus \
    && mkdir -p /app/anchor \
    && chown argus:argus /app/anchor
COPY --chown=argus:argus api/ ./api/
COPY --chown=argus:argus db/ ./db/
COPY --chown=argus:argus alembic.ini ./alembic.ini

USER argus

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
