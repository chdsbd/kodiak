<p align=center><img src="https://github.com/chdsbd/kodiak/raw/master/assets/logo.png" alt="" width="200" height="200"></p>

# kodiak [![CircleCI](https://circleci.com/gh/chdsbd/kodiak.svg?style=svg&circle-token=4879604a0cca6fa815c4d22936350f5bdf455905)](https://circleci.com/gh/chdsbd/kodiak)

A bot to automatically merge GitHub PRs

[![install](https://3c7446e0-cd7f-4e98-a123-1875fcbf3182.s3.amazonaws.com/button-small.svg?v=123)](https://github.com/apps/kodiakhq/installations/new)

## Why?

Enabling the "require branches be up to date" feature on GitHub repositories is
great because, when coupled with CI, master will always be green.

However, as the number of collaborators on a GitHub repo increases, a
repetitive behavior emerges where contributors are updating their branches
manually hoping to merge their branch before others.

Kodiak fixes this wasteful behavior by automatically updating
and merging branches. Contributors simply mark their
PR with a configurable label that indicates the PR is ready to merge and Kodiak
will do the rest, handling branch updates and merging, using the _minimal_
number of branch updates to land the code on master.

This means that contributors don't have to worry about keeping their PRs up
to date with the latest on master or even pressing the merge button. Kodiak
does this for them.

### Minimal updates

Kodiak ensures that branches are always updated before merging, but does so
efficiently by only updating a PR when it's being prepared to merge. This
prevents spurious CI jobs from being created as they would if all PRs were
updated when their targets were updated.

## How does it work?

1. Kodiak receives a webhook event from GitHub and adds it to a queue for processing
2. Kodiak processes these webhook events and extracts the associated pull
   requests for further processing
3. The following pull request information is requested:

   - the `.kodiak.toml` configuration file is fetched from default repository branch
   - branch protection rules are found for the target branch
   - reviews, status checks and labels are located for the pull request

4. Pull request mergeability is evaluated using PR data

   - configuration automerge_label, blacklist_title_regex, and blacklist_labels are checked
   - configuration merge method is checked against enabled repo merge methods
   - pull request merge states are evaluated
   - the branch is updated if necessary and this process restarts
   - branch protection rules are evaluated

5. The pull request is merged 🎉

## Known issues
- Kodiak intentionally requires branch protection to be enabled to function,
  Kodiak won't merge PRs if branch protection is disabled.
- Due to a limitation with the GitHub API, Kodiak doesn't support [requiring
  signed commits](https://help.github.com/en/articles/about-required-commit-signing).
  ([kodiak#89](https://github.com/chdsbd/kodiak/issues/89))
- Kodiak doesn't display config parsing errors at the moment. Please see [README#setup](https://github.com/chdsbd/kodiak#setup) and [kodiak/test/fixtures/config](https://github.com/chdsbd/kodiak/tree/master/kodiak/test/fixtures/config) for examples.  ([kodiak#102](https://github.com/chdsbd/kodiak/issues/102))
- Kodiak doesn't handling updating forks of branches. ([kodiak#104](https://github.com/chdsbd/kodiak/issues/104))
- Github [closing issue keywords](https://help.github.com/en/articles/closing-issues-using-keywords) do not work. This seems to be a bug with Github and bot users.

## Setup

1. Create a `.kodiak.toml` file in the root of your repository on the default
   branch with the following contents (see [`kodiak/test/fixtures/config`](kodiak/test/fixtures/config) for more examples):

   ```toml
   # version is the only required field
   version = 1

   # the following settings can be omitted since they have defaults

   [merge]
   automerge_label = "automerge" # default: "automerge"
   blacklist_title_regex = "^WIP.*" # default: "^WIP.*"
   blacklist_labels = [] # default: []
   method = "squash" # default: "merge", options: "merge", "squash", "rebase"
   delete_branch_on_merge = true # default: false
   block_on_reviews_requested = false # default: false
   notify_on_conflict = true # default: true
   optimistic_updates = true # default: true

   [merge.message]
   title = "pull_request_title" # default: "github_default"
   body = "pull_request_body" # default: "github_default"
   include_pr_number = false # default: true
   body_type = "markdown" # default: "markdown"
   ```

2. Setup Kodiak

   Kodiak can be run either through the GitHub App or by self hosting.
   In order to merge pull requests (PRs) Kodiak needs read write access to
   PRs as well as additional permissions to the repository. This means that Kodiak
   can see **all** the code in your repository.

   The current [permissions](https://developer.github.com/v3/apps/permissions/) that are required to use the GitHub App are:

   | name                      | level      | reason                            |
   | ------------------------- | ---------- | --------------------------------- |
   | repository administration | read-only  | branch protection info            |
   | checks                    | read/write | PR mergeability and status report |
   | repository contents       | read/write | update PRs, read configuration    |
   | pull requests             | read/write | PR mergeability, merge PR         |
   | commit statuses           | read-only  | PR mergeability                   |

   The necessary event subscriptions are:

   | event name                  |
   | --------------------------- |
   | check run                   |
   | pull request                |
   | pull request review         |
   | pull request review comment |

   **Via GitHub App**

   Follow the steps at: <https://github.com/apps/kodiakhq>

   **Self Hosted**

   You can run the `Dockerfile` provided in the repo on your platform of choice
   or you could use the Heroku app configuration below. Redis >=5 is required
   for operation.

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

## Prior Art

| Name                                                                                      | Works With GitHub Integrations | Auto Merging | Auto Update Branches | Update Branches Efficiently | Open Source | Practice [Dogfooding](https://en.wikipedia.org/wiki/Eating_your_own_dog_food) | Language   |
| ----------------------------------------------------------------------------------------- | ------------------------------ | ------------ | -------------------- | --------------------------- | ----------- | ----------------------------------------------------------------------------- | ---------- |
| <!-- 2019-04-18 --> [Kodiak](https://github.com/chdsbd/kodiak)                            | ✅                             | ✅           | ✅                   | ✅                          | ✅          | ✅                                                                            | Python     |
| <!-- 2013-02-01 --> [Bors](https://github.com/graydon/bors)                               | ❌                             | ✅           | ✅                   | ✅                          | ✅          | ❌                                                                            | Python     |
| <!-- 2014-12-18 --> [Homu](https://github.com/barosl/homu)                                | ❌                             | ✅           | ✅                   | ✅                          | ✅          | ❌                                                                            | Python     |
| <!-- 2016-08-06 --> [Gullintanni](https://github.com/gullintanni/gullintanni)             | ❌                             | ✅           | ✅                   | ✅                          | ✅          | ❌                                                                            | Elixir     |
| <!-- 2016-10-27 --> [Popuko](https://github.com/voyagegroup/popuko)                       | ❌                             | ✅           | ✅                   | ✅                          | ✅          | ✅                                                                            | Go         |
| <!-- 2016-12-13 --> [Bors-ng](https://bors.tech)                                          | ❌                             | ✅           | ✅                   | ✅                          | ✅          | ✅                                                                            | Elixir     |
| <!-- 2017-01-18 --> [Marge-bot](https://github.com/smarkets/marge-bot)                    | ❌                             | ✅           | ✅                   | ✅                          | ✅          | ❌                                                                            | Python     |
| <!-- 2017-09-17 --> [Bulldozer](https://github.com/palantir/bulldozer)                    | ✅                             | ✅           | ✅                   | ❌                          | ✅          | ❌                                                                            | Go         |
| <!-- 2018-04-18 --> [Mergify](https://github.com/Mergifyio/mergify-engine)                | ❌                             | ✅           | ✅                   | ❌                          | ✅          | ✅                                                                            | Python     |
| <!-- 2018-07-05 --> [Autorebase](https://github.com/tibdex/autorebase)                    | ✅                             | ✅           | ✅                   | ❌                          | ✅          | ✅                                                                            | TypeScript |
| <!-- 2018-09-21 --> [Auto Merge](https://github.com/SvanBoxel/auto-merge)                 | ❌                             | ✅           | ❌                   | ❌                          | ✅          | ❌                                                                            | JavaScript |
| <!-- Unknown    --> [Always Be Closing](https://github.com/marketplace/always-be-closing) | 🤷‍                            | ✅           | ✅                   | 🤷‍                         | ❌          | 🤷‍                                                                           | 🤷‍        |

Works With GitHub Integration:

- doesn't require changing CI
- follows commit statuses & GitHub checks
- works with PRs — some services create separate test branches for merging
  that circumvent the simpler PR workflow

Auto Merging:

- automatically merges PR once up to date with master and all required statuses and checks pass.

Auto Update Branches:

- ensures branches are automatically updated to the latest version of master

Update Branches Efficiently:

- a improvement of Auto Update Branches where branches are only updated when necessary, as opposed to updating all branches any time their target branch (usually master) updates.

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

1. Configure the permissions as described in the setup instructions above.
2. Add a homepage URL (anything works)
3. Setup the webhook URL

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

4. Now install the GitHub App

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

5. Setup secrets

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
