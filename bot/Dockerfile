FROM python:3.7@sha256:6eaf19442c358afc24834a6b17a3728a45c129de7703d8583392a138ecbdb092

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

COPY --chown=kodiak pyproject.toml poetry.lock ./

# install deps
RUN poetry install && ls .venv/bin

COPY --chown=kodiak . ./

USER kodiak

CMD ["/usr/bin/supervisord"]
