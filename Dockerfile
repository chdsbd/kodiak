FROM python:3.7

RUN set -ex && mkdir -p /var/app

RUN pip install poetry
WORKDIR /var/app
COPY . /var/app

RUN poetry config settings.virtualenvs.in-project true
RUN poetry install


CMD poetry run uvicorn kodiak.main:app --host 0.0.0.0 --port $PORT
