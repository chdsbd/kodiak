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
.venv/bin/gunicorn --bind 0.0.0.0:$PORT core.wsgi

# ingest events for analysis (run continuously)
./manage.py ingest_events

# aggregate events into chartable data (run on cron)
./manage.py aggregate_pull_request_activity

# aggregate user activity (run on cron)
./manage.py aggregate_user_pull_request_activity
```
