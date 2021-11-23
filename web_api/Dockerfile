FROM python:3.8@sha256:cb03bb011e5dca2d0d48f842187fd789062e234e829e96f417542e7ffcaf41cf

RUN set -ex && mkdir -p /var/app

RUN python3 -m pip install poetry===1.1.8

RUN poetry config virtualenvs.in-project true

WORKDIR /var/app

COPY pyproject.toml poetry.lock /var/app/

# install deps
RUN poetry install

COPY . /var/app

CMD ["/var/app/.venv/bin/gunicorn", "--bind", "0.0.0.0:5000", "--access-logfile", "-",  "--error-logfile",  "-", "--capture-output",  "--enable-stdio-inheritance", "--access-logformat",  "'request=\"%(r)s\" request_time=%(L)s remote_addr=\"%(h)s\" request_id=%({X-Request-Id}i)s response_id=%({X-Response-Id}i)s method=%(m)s protocol=%(H)s status_code=%(s)s response_length=%(b)s referer=\"%(f)s\" process_id=%(p)s user_agent=\"%(a)s\"'", "web_api.wsgi"]
