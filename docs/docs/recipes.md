---
id: recipes
title: Recipes
sidebar_label: Recipes
---

## Sync with Master

A config to keep every PR up-to-date with master. Whenever the target branch of a PR updates, the PR will update.

```toml
# .kodiak.toml
version = 1

[update]
always = true # default: false
require_automerge_label = false # default: true
```

## Automated dependency updates with Dependabot

Kodiak can automerge Dependabot PRs without human intervention by configuring Dependabot to open pull requests with our [`merge.automerge_label`](/docs/config-reference#mergeautomerge_label) label.

### Configuring Dependabot with the automerge label

1. Install Kodiak following the [quick start guide](/docs/quickstart).

2. Configure dependabot to open PRs with your [`merge.automerge_label`](/docs/config-reference#mergeautomerge_label) label. See the [Dependabot labels documentation](https://help.github.com/en/github/administering-a-repository/configuration-options-for-dependency-updates#labels) for more information.

```yaml
# dependabot.yml
# Specify labels for pull requests

version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "daily"
    labels:
      - "dependencies"
      # Add default Kodiak `merge.automerge_label`
      - "automerge"
```

3. Success! Dependabot PRs will now include your automerge label, triggering Kodiak to automatically merge them. 🎉

### Adding pull request approvals to Dependabot pull requests

When "Required approving reviews" is configured via GitHub Branch Protection, every pull request needs an approving review before it can be merged.

Kodiak can add an approval to pull requests via [`approve.auto_approve_usernames`](/docs/config-reference#approveauto_approve_usernames), enabling Dependabot PRs to be merged without human intervention.

> **NOTE:** Remove the `[bot]` suffix from GitHub Bot usernames. Instead of `"dependabot[bot]"` use `"dependabot"`.

```toml
# .kodiak.toml
version = 1

[approve]
# note: remove the "[bot]" suffix from GitHub Bot usernames.
# Instead of "dependabot[bot]" use "dependabot".
auto_approve_usernames = ["dependabot"]

# if using `update.always`, add dependabot to the blacklist to allow
# dependabot to update and close stale dependency upgrades.
[update]
ignored_usernames = ["dependabot"]
```

If you use Kodiak with [`update.always`](/docs/config-reference#updatealways) enabled, add Dependabot to the [`update.ignored_usernames`](/docs/config-reference#updateignored_usernames) list. If a PR by Dependabot is updated by another user, Dependabot will not update or close the PR when stale. This setting prevents Kodiak from breaking Dependabot PRs.

## The Favourite

This is the config used by the [Kodiak repository](https://github.com/chdsbd/kodiak/blob/master/.kodiak.toml).

We squash all PR commits and use the PR title and body for the merge commit. Once merged, we delete the PR's branch.

```
# .kodiak.toml
version = 1

[merge]
method = "squash" # default: "merge"
delete_branch_on_merge = true # default: false

[merge.message]
title = "pull_request_title" # default: "github_default"
body = "pull_request_body" # default: "github_default"
```

<span id="efficiency-and-speed"/> <!-- handle old links -->

## Efficient Merges

By default, Kodiak will efficiently merge pull requests.

When ["Require branches to be up to date before merging"](features.md#updating-pull-requests) is enabled via GitHub Branch Protection settings, a pull request's branch must be up-to-date with the target branch before merge. In this case Kodiak will update a pull request just before merge.

If we had multiple PRs waiting to be merged, each PR would only be updated (if required) just before to merge.

```toml
# .kodiak.toml
# Kodiak is efficient by default
version = 1
```

See ["Efficient Merging"](features.md#efficient-merging) for more information about efficiency.

## Speedy Merges

By default, pull requests are merged on a first-come-first-served policy for the merge queue. Enabling [`merge.prioritize_ready_to_merge`](config-reference.md#mergeprioritize_ready_to_merge) bypasses the queue for any PR that can be merged without updates.

Assuming ["Require branches to be up to date before merging"](features.md#updating-pull-requests) is enabled via GitHub Branch Protection settings, when [`update.always`](config-reference.md#updatealways) is enabled, a pull request's branch will be updated when the target branch updates. This option may improve merge speeds but wastes resources.

```toml
# .kodiak.toml
version = 1

[merge]
# if a PR is ready, merge it, don't place it in the merge queue.
prioritize_ready_to_merge = true # default: false

[update]
# immediately update a pull request's branch when outdated.
always = true # default: false
```

## Better Merge Messages

GitHub's default merge commits are _ugly_. GitHub uses the title of the first commit for the merge title and combines all of the other commit titles and bodies for the merge body.

Using the pull request title and body give a cleaner, more useful merge commit.

This config uses the PR title and body, along with the PR number to create a nice merge commit. Additionally we strip HTML comments from the PR markdown body which can be useful if your GitHub repo has PR templates.

```toml
# .kodiak.toml
version = 1

[merge.message]
# use title of PR for merge commit.
title = "pull_request_title" # default: "github_default"

# use body of PR for merge commit.
body = "pull_request_body" # default: "github_default"

# add the PR number to the merge commit title, like GitHub.
include_pr_number = true # default: true

# use the default markdown content of the PR for the merge commit.
body_type = "markdown" # default: "markdown"

# remove html comments to auto remove PR templates.
strip_html_comments = true # default: false
```
