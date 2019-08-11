<p align=center><img src="https://github.com/chdsbd/kodiak/raw/master/assets/logo.png" alt="" width="200" height="200"></p>

# kodiak [![CircleCI](https://circleci.com/gh/chdsbd/kodiak.svg?style=svg&circle-token=4879604a0cca6fa815c4d22936350f5bdf455905)](https://circleci.com/gh/chdsbd/kodiak)

A bot to automatically merge GitHub PRs

[![install](https://3c7446e0-cd7f-4e98-a123-1875fcbf3182.s3.amazonaws.com/button-small.svg?v=123)](https://github.com/apps/kodiakhq/installations/new)

## Why?

Enabling the "require branches be up to date" feature on GitHub repositories is
great because, when coupled with CI, _master will always be green_.

However, as the number of collaborators on a GitHub repo increases, a
repetitive behavior emerges where contributors are updating their branches
manually hoping to merge their branch before others.

Kodiak fixes this wasteful behavior by _automatically updating
and merging branches_. Contributors simply mark their
PR with a (configurable) label to indicate the PR is ready to merge and Kodiak
will do the rest; handling branch updates and merging using the _minimal
number of branch updates_ to land the code on master.

This means that contributors don't have to worry about keeping their PRs up
to date with the latest on master or even pressing the merge button. Kodiak
does this for them! 🎉

### Minimal updates

Kodiak _efficiently updates pull requests_ by only updating a PR when it's ready to merge. This
_prevents spurious CI jobs_ from being created as they would if all PRs were
updated when their targets were updated.

## How does it work?

1.  Kodiak receives a webhook event from GitHub and adds it to a per-installation queue for processing
2.  Kodiak processes these webhook events and extracts the associated pull
    requests for further processing

3.  Pull request mergeability is evaluated using PR data

    - kodiak configurations are checked
    - pull request merge states are evaluated
    - branch protection rules are checked
    - the branch is updated if necessary

4.  If the PR is mergeable it's queued in a per-repo merge queue

5.  A task works serially over the merge queue to update a PR and merge it

6.  The pull request is merged 🎉

## Known issues

- Kodiak intentionally requires branch protection to be enabled to function,
  Kodiak won't merge PRs if branch protection is disabled.
- Due to a limitation with the GitHub API, Kodiak doesn't support [requiring
  signed commits](https://help.github.com/en/articles/about-required-commit-signing).
  ([kodiak#89](https://github.com/chdsbd/kodiak/issues/89))
- Due to permission limitations for GitHub Apps, Kodiak doesn't support updating forks of branches. ([kodiak#104](https://github.com/chdsbd/kodiak/issues/104))
- GitHub CODEOWNERS are not supported. Kodiak will prematurely update PRs that still require a review from a Code Owner. However, Kodiak will be able to merge the PR once all checks pass. ([kodiak#87](https://github.com/chdsbd/kodiak/issues/87))

## Setup

1.  Install the GitHub app

    [![install](https://3c7446e0-cd7f-4e98-a123-1875fcbf3182.s3.amazonaws.com/button-small.svg?v=123)](https://github.com/apps/kodiakhq/installations/new)

2.  Create a `.kodiak.toml` file in the root of your repository with the following contents:

    Here are a few examples to pick from and modify.

    ### minimal config

    ```toml
    # .kodiak.toml
    # Minimal config. version is the only required field.
    version = 1
    ```

    ### opinionated config

    ```toml
    # .kodiak.toml
    version = 1

    [merge]
    method = "squash"
    delete_branch_on_merge = true
    dont_wait_on_status_checks = ["WIP"] # handle github.com/apps/wip

    [merge.message]
    title = "pull_request_title"
    body = "pull_request_body"
    include_pr_number = true
    body_type = "markdown"
    strip_html_comments = true # remove html comments to auto remove PR templates
    ```

    ### config with comments and all options set

    ```toml
    # .kodiak.toml
    # version is the only required setting in a kodiak config.
    # it must be set to 1
    version = 1

    [merge]
    # label to use to enable Kodiak to merge a PR
    automerge_label = "automerge" # default: "automerge"

    # require that the automerge label be set for Kodiak to merge a PR. if you
    # disable this Kodiak will immediately attempt to merge every PR you create
    require_automerge_label = true

    # if this title regex matches, Kodiak will not merge the PR. this is useful
    # to prevent merging work in progress PRs
    blacklist_title_regex = "" # default: "^WIP.*", options: "" (disables regex), a regex string (e.g. ".*DONT\s*MERGE.*")

    # if these labels are set Kodiak will not merge the PR
    blacklist_labels = [] # default: [], options: list of label names (e.g. ["wip"])

    # choose a merge method. If the configured merge method is disabled for a
    # repository, Kodiak will report an error in a status message.
    method = "merge" # default: "merge", options: "merge", "squash", "rebase"

    # once a PR is merged into master, delete the branch
    delete_branch_on_merge = false # default: false

    # if you request review from a user, don't merge until that user provides a
    # review, even if the PR is passing all checks
    block_on_reviews_requested = false # default: false

    # if there is a merge conflict, make a comment on the PR and remove the
    # automerge label. this is disabled when require_automerge_label is enabled
    notify_on_conflict = true # default: true

    # if there are running status checks on a PR when it's up for merge, don't
    # wait for those to finish before updating the branch
    optimistic_updates = false # default: true

    # use this for status checks that run indefinitely, like deploy jobs or the
    # WIP GitHub App
    dont_wait_on_status_checks = [] # default: [], options: list of check names (e.g. ["ci/circleci: lint_api"])

    # immediately update a PR whenever the target updates. If enabled, Kodiak will
    # not be able to efficiently update PRs. Any time the target of a PR updates,
    # the PR will update.
    #
    # If you have multiple PRs against a target like "master", any time a commit
    # is added to "master" _all_ of those PRs against "master" will update.
    #
    # For N PRs against a target you will potentially see N(N-1)/2 updates. If
    # this configuration option was disabled you would only see N-1 updates.
    #
    # If you have continuous integration (CI) run on every commit, enabling this
    # configuration option will likely increase your CI costs if you pay per
    # minute. If you pay per build host, this will likely increase job queueing.
    update_branch_immediately = false # default: false


    [merge.message]
    # by default, github uses the first commit title for the PR of a merge.
    # "pull_request_title" uses the PR title.
    title = "github_default" # default: "github_default", options: "github_default", "pull_request_title"

    # by default, GithHub combines the titles a PR's commits to create the body
    # text of a merge. "pull_request_body" uses the content of the PR to generate
    # the body content while "empty" simple gives an empty string.
    body = "github_default" # default: "github_default", options: "github_default", "pull_request_body", "empty"

    # GitHub adds the PR number to the title of merges created through the UI.
    # This setting replicates that feature.
    include_pr_number = true # default: true

    # markdown is the normal format for GitHub merges
    body_type = "markdown" # default: "markdown", options: "plain_text", "markdown", "html"

    # useful for stripping HTML comments created by PR templates when the `markdown` `body_type` is used.
    strip_html_comments = false # default: false
    ```

    See [`kodiak/test/fixtures/config`](kodiak/test/fixtures/config) for more examples and [`kodiak/config.py`](kodiak/config.py) for the Python models.

3.  Configure branch protection

    Branch protection must configured on your target branch (typically master) for Kodiak to enable itself. See the excellent GitHub docs for a quick guide to enabling branch protection: https://help.github.com/en/articles/configuring-protected-branches

4.  Create an automerge label

    The default label is "automerge" and is configured via the `merge.automerge_label` config.
    If you have disabled `merge.require_automerge_label`, you can skip this step.

5.  Start auto merging PRs with Kodiak! 🎉

    Label your PRs with your automerge label and let Kodiak do the rest!

    If you have any questions please [open a ticket](https://github.com/chdsbd/kodiak/issues/new/choose).

## Prior Art

| Name                                                                                      | Works With Branch Protection | Auto Merging | Auto Update Branches | Update Branches Efficiently | Open Source | Practice [Dogfooding](https://en.wikipedia.org/wiki/Eating_your_own_dog_food) | Language   |
| ----------------------------------------------------------------------------------------- | ---------------------------- | ------------ | -------------------- | --------------------------- | ----------- | ----------------------------------------------------------------------------- | ---------- |
| <!-- 2019-04-18 --> [Kodiak](https://github.com/chdsbd/kodiak)                            | ✅                           | ✅           | ✅                   | ✅                          | ✅          | ✅                                                                            | Python     |
| <!-- 2013-02-01 --> [Bors](https://github.com/graydon/bors)                               | ❌                           | ✅           | ✅                   | ✅                          | ✅          | ❌                                                                            | Python     |
| <!-- 2014-12-18 --> [Homu](https://github.com/barosl/homu)                                | ❌                           | ✅           | ✅                   | ✅                          | ✅          | ❌                                                                            | Python     |
| <!-- 2016-08-06 --> [Gullintanni](https://github.com/gullintanni/gullintanni)             | ❌                           | ✅           | ✅                   | ✅                          | ✅          | ❌                                                                            | Elixir     |
| <!-- 2016-10-27 --> [Popuko](https://github.com/voyagegroup/popuko)                       | ❌                           | ✅           | ✅                   | ✅                          | ✅          | ✅                                                                            | Go         |
| <!-- 2016-12-13 --> [Bors-ng](https://bors.tech)                                          | ❌                           | ✅           | ✅                   | ✅                          | ✅          | ✅                                                                            | Elixir     |
| <!-- 2017-01-18 --> [Marge-bot](https://github.com/smarkets/marge-bot)                    | ❌                           | ✅           | ✅                   | ✅                          | ✅          | ❌                                                                            | Python     |
| <!-- 2017-09-17 --> [Bulldozer](https://github.com/palantir/bulldozer)                    | ✅                           | ✅           | ✅                   | ❌                          | ✅          | ❌                                                                            | Go         |
| <!-- 2018-04-18 --> [Mergify](https://github.com/Mergifyio/mergify-engine)                | ❌                           | ✅           | ✅                   | ❌                          | ✅          | ✅                                                                            | Python     |
| <!-- 2018-07-05 --> [Autorebase](https://github.com/tibdex/autorebase)                    | ✅                           | ✅           | ✅                   | ❌                          | ✅          | ✅                                                                            | TypeScript |
| <!-- 2018-09-21 --> [Auto Merge](https://github.com/SvanBoxel/auto-merge)                 | ❌                           | ✅           | ❌                   | ❌                          | ✅          | ❌                                                                            | JavaScript |
| <!-- 2018-10-21 --> [Merge when green](https://github.com/phstc/probot-merge-when-green)  | ❌                           | ✅           | ❌                   | ❌                          | ✅          | ✅                                                                            | JavaScript |
| <!-- Unknown    --> [Always Be Closing](https://github.com/marketplace/always-be-closing) | 🤷‍                          | ✅           | ✅                   | 🤷‍                         | ❌          | 🤷‍                                                                           | 🤷‍        |
| <!-- Unknown    --> [Auto Merge](https://github.com/marketplace/auto-merge)               | 🤷‍                          | ✅           | 🤷‍                  | 🤷‍                         | ❌          | 🤷‍                                                                           | 🤷‍        |

### explanations

#### Works With GitHub Integration:

- doesn't require changing CI
- follows commit statuses & GitHub checks
- works with PRs — some services create separate test branches for merging
  that circumvent the simpler GitHub PR workflow

#### Auto Merging:

- automatically merges PR once up to date with master and all required statuses and checks pass

#### Auto Update Branches:

- ensures branches are automatically updated to the latest version of master

#### Update Branches Efficiently:

- an improvement upon [Auto Update Branches](#auto-update-branches) where branches are only updated when necessary, as opposed to updating all branches any time their target branch (usually master) updates

## Permissions

Kodiak needs read/write access to PRs as well as your repository to update and merge PRs. This means that Kodiak
can see **all** the code in your repository. Below is a table of all the required permissions and the reasons they are necessary.

| name                      | level      | reason                                                                 |
| ------------------------- | ---------- | ---------------------------------------------------------------------- |
| repository administration | read-only  | branch protection info                                                 |
| checks                    | read/write | PR mergeability and status report                                      |
| repository contents       | read/write | update PRs, read configuration                                         |
| issues                    | read/write | support [closing issues using keywords][issue-keywords]                |
| pull requests             | read/write | PR mergeability, merge PR                                              |
| commit statuses           | read-only  | PR mergeability                                                        |
| organization members      | read-only  | view review requests for users/teams of a PR to calculate mergeability |

[issue-keywords]: https://help.github.com/en/articles/closing-issues-using-keywords

## Self-hosting setup on Heroku

If you don't want to use the [GitHub App](https://github.com/apps/kodiakhq/installations/new) you can run Kodiak on your own infrastructure. These instructions describe setting up Kodiak on Heroku using a Docker container, but you should be able to adapt this for other container platforms.

1.  Create a new GitHub app via https://github.com/settings/apps/new with the permissions described in the [Permissions](#permissions) sections of this document and with the event subscriptions specified below

    More information on creating a GitHub app can be found at: https://developer.github.com/apps/building-github-apps/creating-a-github-app/

    The necessary event subscriptions are:

    | event name                  |
    | --------------------------- |
    | check run                   |
    | pull request                |
    | pull request review         |
    | pull request review comment |

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
    heroku config:set -a $APP_NAME GITHUB_APP_ID='<GH_APP_ID>' SECRET_KEY='<GH_APP_SECRET>' GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\nsome/private/key\nbits\n-----END RSA PRIVATE KEY-----\n"

    # Redis v5 is required and provided by RedisCloud
    heroku addons:create -a $APP_NAME rediscloud:30 --wait

    # release app
    heroku container:release web -a $APP_NAME
    ```

## Development

```shell
# install dependencies
poetry install

# start dev server
poetry run uvicorn kodiak.main:app --reload

# type check and lint
s/lint

# format code
s/fmt

# test code
s/test
```

### Testing on a Live Repo

Due to the nature of a GitHub bot, testing relies largely on mocks.
For testing to see if a given feature will work it is recommended to create a
GitHub App and a testing GitHub repo.

#### Create a GitHub App via <https://github.com/settings/apps/new>

1.  Configure the app as described in the [heroku setup instructions](#self-hosting-setup-on-heroku) above.
2.  Setup the webhook URL

    You probably want to use something like [`ngrok`](https://ngrok.com) for
    this. If you do use `ngrok`, you may also want to signup for an account
    via the [`ngrok` website](https://ngrok.com) so that your `ngrok` url
    for the webhook doesn't expire.

    With `ngrok` installed, we can run it with the Kodiak's dev port.

    ```
    ngrok http 8000
    ```

    Now we can copy the **Forwarding** url into the GitHub app form.
    Don't forget to append the path: `/api/github/hook` and sure to copy the
    `https`.

    Then hit create.

3.  Now install the GitHub App

    Use the **Install** option in the sidebar for the GitHub App.

    You will want to create a testing GitHub repo with a Kodiak config file
    with the `app_id` option set to your GitHub app's id.

    You will also need to setup branch protection in `settings > branches`.
    Make sure the **Branch name pattern** matches `master`. Then check
    **Require status checks to pass before merging** and the sub-option
    **Require branches to be up to date before merging**.

    This allows for the production version of Kodiak to be setup on all repos,
    while allowing the testing version to run on the configured repo. If the
    production version of Kodiak finds a non-matching app_id, it will ignore
    the repository, leaving your local version to handle it.

4.  Setup secrets

    After creating we need to add a **Webhook secret**. The field is labeled **(optional)** but it is necessary for Kodiak to work.

    You can fill it in with a UUID -- be sure to hold onto it, we'll need it
    later.

    Now you need to generate a private key via the generate private key button under the **Private keys** section.

    Move the secret key to directory where you are running Kodiak.

#### Run the dev server

Note: you need to replace the `$SHARE_SECRET`, `$GH_PRIVATE_KEY_PATH` and `$GITHUB_APP_ID` with your own values.

The GitHub App ID can be found in the **About** sections of your GitHub App.

```
SECRET_KEY=$SHARED_SECRET GITHUB_PRIVATE_KEY_PATH=$GH_PRIVATE_KEY_PATH GITHUB_APP_ID=$GITHUB_APP_ID poetry run uvicorn kodiak.main:app
```

You can create a test PR via the following shell function.

Note: you need to have [`hub`](https://github.com/github/hub) installed.

```sh
create_mock_pr() {
  git pull &&
  uuidgen >> "$(uuidgen).txt" &&
  git checkout -b $(uuidgen) &&
  git add . &&
  git commit -am $(uuidgen) &&
  git push --set-upstream origin $(git symbolic-ref --short HEAD) &&
  hub pull-request -l automerge -m "$(uuidgen)" &&
  git checkout master
}
```

### Releasing a new version

```bash
GIT_SHA='62fcc1870b609f43b95de41b8be41a2858eb56bd'
APP_NAME='kodiak-prod'
docker pull cdignam/kodiak:$GIT_SHA
docker tag cdignam/kodiak:$GIT_SHA registry.heroku.com/$APP_NAME/web
docker push registry.heroku.com/$APP_NAME/web
heroku container:release -a $APP_NAME web
```
