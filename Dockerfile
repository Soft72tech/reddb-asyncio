
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT=/project-cache/venv

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev

RUN apt update && apt install -y --no-install-recommends procps net-tools netcat-traditional libfbclient2 && rm -rf /var/lib/apt/lists/*


ENV PATH="/project-cache/venv/bin:${PATH}"
ENV PYTHONPATH="/project:${PYTHONPATH}"

WORKDIR /project
