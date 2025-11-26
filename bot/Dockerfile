FROM python:3.8.20

RUN set -ex && mkdir -p /var/app

RUN apt-get update && apt-get install -y supervisor

RUN mkdir -p /var/log/supervisor

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.9.11 /uv /uvx /bin/

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

WORKDIR /var/app

# Copy dependency files
COPY pyproject.toml uv.lock /var/app/

COPY . /var/app

# Install the application and dependencies
RUN uv sync --frozen

CMD ["/usr/bin/supervisord"]
