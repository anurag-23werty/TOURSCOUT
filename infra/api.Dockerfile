# TourScout API + MCP server in one container. Build from the repo root:
#   docker build -f infra/api.Dockerfile -t tourscout-api .
#
# Two stages: `build` resolves dependencies with uv; the final image gets only the virtualenv, the code and the data,
# copied in already owned by the non-root user (a `chown -R` layer would duplicate every file and double the image).

FROM python:3.12-slim AS build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /usr/local/bin/uv
WORKDIR /app

# Dependencies first (cached layer): the MCP package is a local path dependency of the API.
COPY packages/tourscout_mcp packages/tourscout_mcp
COPY apps/api/pyproject.toml apps/api/uv.lock apps/api/README.md apps/api/
RUN cd apps/api && uv sync --frozen --no-dev --no-install-project
COPY apps/api apps/api
RUN cd apps/api && uv sync --frozen --no-dev

# GeoNames cities (CC BY 4.0) baked in so cold starts don't download them.
COPY data/download_geonames.py data/
RUN python data/download_geonames.py && rm -f data/raw/*.zip


FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 app
WORKDIR /app

COPY --from=build --chown=app /app/packages packages
COPY --from=build --chown=app /app/apps/api apps/api
COPY --from=build --chown=app /app/data/raw data/raw
COPY --chown=app evals/personas evals/personas
USER app

ENV PATH="/app/apps/api/.venv/bin:$PATH" \
    GEONAMES_FILE=/app/data/raw/cities15000.txt \
    TOURSCOUT_ENV=production \
    TRUST_PROXY=true \
    PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health', timeout=4)"

# Render / Railway set $PORT. --proxy-headers so client IPs (rate limits) come from the platform's proxy.
CMD ["sh", "-c", "uvicorn tourscout_api.api.app:create_app --factory --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
