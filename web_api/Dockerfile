FROM python:3.7@sha256:6eaf19442c358afc24834a6b17a3728a45c129de7703d8583392a138ecbdb092

RUN set -ex && mkdir -p /var/app

# use cryptography version for poetry that doesn't require Rust
RUN python3 -m pip install cryptography===37.0.4
RUN python3 -m pip install poetry===1.1.8

RUN poetry config virtualenvs.in-project true

WORKDIR /var/app

COPY pyproject.toml poetry.lock /var/app/

# install deps
RUN poetry install

COPY . /var/app

CMD ["/var/app/.venv/bin/gunicorn", "--bind", "0.0.0.0:5000", "--access-logfile", "-",  "--error-logfile",  "-", "--capture-output",  "--enable-stdio-inheritance", "--access-logformat",  "'request=\"%(r)s\" request_time=%(L)s remote_addr=\"%(h)s\" request_id=%({X-Request-Id}i)s response_id=%({X-Response-Id}i)s method=%(m)s protocol=%(H)s status_code=%(s)s response_length=%(b)s referer=\"%(f)s\" process_id=%(p)s user_agent=\"%(a)s\"'", "web_api.wsgi"]
