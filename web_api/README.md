# web_api

The web API for the Kodiak dashboard.

## dev

```console
# install dependencies
poetry install

# copy & modify example .env file
cp example.env .env

s/dev

s/test

s/lint

s/build


# run production app server
.venv/bin/gunicorn --bind 0.0.0.0:$PORT web_api.wsgi

# ingest events for analysis (run continuously)
.venv/bin/python core/event_ingestor.py

# aggregate events into chartable data (run on cron)
.venv/bin/python  core/analytics_aggregator.py

# aggregate user activity (run on cron)
.venv/bin/python core/user_activity_aggregator.py
```
