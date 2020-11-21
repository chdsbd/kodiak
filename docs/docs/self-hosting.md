---
id: self-hosting
title: Self Hosting
sidebar_label: Self Hosting
---

If you don't want to use the [GitHub App](https://github.com/marketplace/kodiakhq#pricing-and-setup), you can run Kodiak on your own infrastructure.

> We recommend [watching the Kodiak repo for releases](https://docs.github.com/en/enterprise-server@2.20/github/receiving-notifications-about-activity-on-github/watching-and-unwatching-releases-for-a-repository#watching-releases-for-a-repository), so that you can get bug fixes and avoid issues with GitHub API changes.

## Heroku

These instructions describe setting up Kodiak on Heroku using a Docker container, but you should be able to adapt this for other container platforms.

1.  Create a new GitHub app via https://github.com/settings/apps/new with the permissions described in the [Permissions](/docs/permissions) sections of this document and with the event subscriptions specified below

    More information on creating a GitHub app can be found at: https://developer.github.com/apps/building-github-apps/creating-a-github-app/

    The necessary event subscriptions are:

    | event name                  |
    | --------------------------- |
    | check run                   |
    | pull request                |
    | pull request review         |
    | pull request review comment |
    | push                        |
    | status                      |

    - For the homepage URL any link should work.
    - A GitHub App secret is required for Kodiak to run.
    - Download your private key for later and copy your GitHub app ID and secret key for later.
    - Use your Heroku app hostname for the webhook URL with `/api/github/hook` appended. Something like `https://my-kodiak-app.herokuapp.com/api/github/hook`.

2.  Setup container on Heroku

    Kodiak depends on Redis v5 for persistence.

    ```shell
    # a unique name for the heroku app
    export APP_NAME='kodiak-prod'

    # create app with container stack
    heroku apps:create $APP_NAME
    heroku stack:set container -a $APP_NAME

    # login to registry
    heroku container:login

    # download latest release from docker hub and tag for push to heroku
    docker pull cdignam/kodiak
    docker tag cdignam/kodiak registry.heroku.com/$APP_NAME/web

    # push tagged image to Heroku
    docker push registry.heroku.com/$APP_NAME/web

    # create gihub app at https://developer.github.com/apps/building-github-apps/creating-a-github-app/
    # The APP_ID and PRIVATE_KEY are needed to run the app. You must also set a SECRET_KEY to pass to the app.

    # configure app environment (this can also be done through the Heroku web ui)
    heroku config:set -a $APP_NAME GITHUB_APP_ID='<GH_APP_ID>' SECRET_KEY='<GH_APP_SECRET>' GITHUB_PRIVATE_KEY="$(cat github_private_key.pem)" GITHUB_APP_NAME='<GH_APP_NAME>'

    # (optional) configure your Sentry DSN to report any errors Kodiak encounters
    heroku config:set -a $APP_NAME SENTRY_DSN='<SENTRY_DSN>'

    # (optional) GitHub Enterprise users should set their v3 and v4 GitHub API URLs
    #
    # GITHUB_V3_API_ROOT
    #   http(s)://[hostname]/api/v3, instead of https://api.github.com.
    #
    # GITHUB_V4_API_URL
    #   http(s)://[hostname]/api/graphql, instead of https://api.github.com/graphql.
    heroku config:set -a $APP_NAME GITHUB_V3_API_ROOT="https://github.acme-corp.intern/api/v3"
    heroku config:set -a $APP_NAME GITHUB_V4_API_URL="https://github.acme-corp.intern/api/graphql"


    # Redis v5 is required and provided by RedisCloud
    heroku addons:create -a $APP_NAME rediscloud:30 --wait

    # release app
    heroku container:release web -a $APP_NAME
    ```
