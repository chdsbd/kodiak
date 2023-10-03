FROM python:3.7-slim

RUN apt update && \
  apt-get install --no-install-recommends -y \
    supervisor \
    git && \
  python -m pip install --upgrade pip && \
  pip install \
    --no-cache-dir \
    --root-user-action=ignore \
    cryptography===37.0.4 \
    poetry===1.1.15 && \
  poetry config virtualenvs.in-project true && \
  groupadd kodiak && \
  useradd --uid 1000 --gid kodiak kodiak && \
  mkdir -p /var/app && \
  chown -R kodiak:kodiak /var/app

WORKDIR /var/app

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

COPY --chown=kodiak pyproject.toml poetry.lock /var/app

# install deps
RUN poetry install

COPY --chown=kodiak . /var/app

USER kodiak

CMD ["/usr/bin/supervisord"]
