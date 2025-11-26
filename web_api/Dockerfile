FROM python:3.8.20

RUN set -ex && mkdir -p /var/app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.9.11 /uv /uvx /bin/

WORKDIR /var/app

# Copy dependency files
COPY pyproject.toml uv.lock /var/app/

COPY . /var/app

# Install the application and dependencies
RUN uv sync --frozen

CMD ["/var/app/.venv/bin/gunicorn", "--bind", "0.0.0.0:5000", "--access-logfile", "-",  "--error-logfile",  "-", "--capture-output",  "--enable-stdio-inheritance", "--access-logformat",  "'request=\"%(r)s\" request_time=%(L)s remote_addr=\"%(h)s\" request_id=%({X-Request-Id}i)s response_id=%({X-Response-Id}i)s method=%(m)s protocol=%(H)s status_code=%(s)s response_length=%(b)s referer=\"%(f)s\" process_id=%(p)s user_agent=\"%(a)s\"'", "web_api.wsgi"]
