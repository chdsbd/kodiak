---
id: config-reference
title: Configuration Reference
---

Below is a Kodiak configuration with all options set and commented.

The Kodiak `.kodiak.toml` configuration file can be placed at the repository root or at `.github/.kodiak.toml`.

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
blacklist_title_regex = "" # default: "^WIP:.*", options: "" (disables regex), a regex string (e.g. ".*DONT\s*MERGE.*")

# if these labels are set Kodiak will not merge the PR
blacklist_labels = [] # default: [], options: list of label names (e.g. ["wip"])

# choose a merge method. If the configured merge method is disabled for a
# repository, Kodiak will report an error in a status message.
method = "merge" # default: "merge", options: "merge", "squash", "rebase"

# once a PR is merged into master, delete the branch
delete_branch_on_merge = false # default: false

# DEPRECATED
# Due to limitations with the GitHub API this feature is
# fundamentally broken and cannot be fixed. Please use the GitHub branch
# protection "required reviewers" setting instead. See this issue/comment
# for more information about why this feature is not fixable
# see: https://github.com/chdsbd/kodiak/issues/153#issuecomment-523057332.
#
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

# DEPRECATED
# This setting only updates PRs that are passing passing all requirements or
# waiting for status checks to pass. `update.always = True` will deliver
# better behavior in many use cases.
#
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

# if a PR is passing all checks and is able to be merged, merge it without
# placing it in the queue. This will introduce some unfairness where those
# waiting in the queue the longest will not be served first.
prioritize_ready_to_merge = false # default: false

# never merge a PR. This can be used with merge.update_branch_immediately to
# automatically update a PR without merging.
do_not_merge = false # default: false

[merge.message]
# by default, github uses the first commit title for the PR of a merge.
# "pull_request_title" uses the PR title.
title = "github_default" # default: "github_default", options: "github_default", "pull_request_title"

# by default, GitHub combines the titles of a PR's commits to create the body
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

[update]
# update PR whenever out of date with the base branch. PR will be
# updated regardless of failing requirements for merge (e.g. failing status
# checks, missing reviews, blacklist labels).
#
# Kodiak will only update the PR if the automerge label is enabled or
# `update.require_automerge_label` is false.
always = false # default: false
# enable updating PRs missing automerge label. automerge label is defined by `merge.automerge_label`.
require_automerge_label = true # default: true
```

See [`kodiak/test/fixtures/config`](https://github.com/chdsbd/kodiak/tree/master/kodiak/test/fixtures/config) for more examples and [`kodiak/config.py`](https://github.com/chdsbd/kodiak/blob/master/kodiak/config.py) for the Python models.
