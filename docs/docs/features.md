---
id: features
title: Features
sidebar_label: Features
---

This is a non-exhaustive list of Kodiak's features.

If you have any questions about Kodiak, some good places to look are this page, the [configuration reference](configuration-reference.md), our [Kodiak recipes](recipes.md), and the [the GitHub repository](https://github.com/chdsbd/kodiak).

As always, feel free to email us at support@kodiakhq.com with any question or concern.

## General Rule

Kodiak acts like a GitHub user. Any feature that works for a GitHub user likely works for Kodiak. Give it a go!

## GitHub Branch Protection
Kodiak's behavior is largely driven by GitHub Branch Protection. If a PR is blocked from merging by a missing required status check, missing approval, merge conflict, etc., Kodiak will not merge the PR.

## Updating Pull Requests
To have Kodiak update branches you must enable the "Require branches to be up to date before merging" GitHub Branch Protection setting.

![todo-replace-with-our-own-image](https://help.github.com/assets/images/help/repository/protecting-branch-loose-status.png)
<!-- https://help.github.com/en/github/administering-a-repository/enabling-required-status-checks -->

When merging a pull request, Kodiak will update the PR if out of date with the target branch.

To have Kodiak immediately update any PR that is out-of-date, enable [`update.always`](https://kodiakhq.com/docs/config-reference#updatealways).

If you use Kodiak with a dependancy update bot, you should disable auto updates for the bot via [`update.blacklist_usernames`](configuration-reference.md#updateblacklist_usernames). See [Automated dependency updates with Dependabot](recipes.md#automated-dependency-updates-with-dependabot) for more information.


## Merging Pull Requests
When the automerge label (configurable via [`merge.automerge_label`](https://kodiakhq.com/docs/config-reference#mergeautomerge_label)) is applied to a PR, Kodiak will attempt to merge the PR. Assuming all GitHub Branch Protection requirements are met (status checks, reviews, etc.), Kodiak will merge the PR.

You can disable the `merge.automerge_label` requirement by disabling `merge.require_automerge_label`. This means that as soon as your pull request meets the GitHub Branch Protection requirements, Kodiak will merge the pull request.


Some required GitHub status checks may remain pending indefinitely. This is common for status checks that require manual approval or GitHub apps like the [WIP GitHub App](https://github.com/wip/app), which sets a pending status check until the PR title is updated.
To prevent these status checks from blocking Kodiak's merge queue you must add them to `merge.dont_wait_on_status_checks`.

<!-- TODO: Link up all these config references -->

### Merge Methods
Like the GitHub UI, Kodiak supports merging via "squash", "rebase", and "merge" commits. This is configurable via [`merge.method`](https://kodiakhq.com/docs/config-reference#mergemethod).

Kodiak also supports the "Require signed commits" branch protection setting for "squash" and "merge" commit methods. The "rebase" method is not compatible due to GitHub limitations.

<!-- add require signed commits screenshot -->

### Merge Message
The commit title and body of a comment can be controlled via ...
The merge commit can be customized via the `merge.message` configuration options.

- `merge.message.body` – use GitHub default body, the pull request, or none
- `merge.message.include_pr_number` – add the pull request number to the title like the GitHub UI
- `merge.message.body_type` – when using the pull request body, use the markdown, plain text, or html render of the pull request for the pull request body 
- `merge.message.strip_html_comments` – remove HTML comments from the pull request body
- `merge.message.include_pull_request_author` – add the pull request author as a `Co-authored-by: ...` trailer (rarely used)
- `merge.message.include_pull_request_url` – include the pull request URL at the bottom of the commit message

### Preventing Merge

With GitHub Branch Protection, required status checks will prevent a pull request from merging until tests have passed. Draft pull requests will also not be merged.

Kodiak has some internal features to disable merging as well:

- `merge.blacklist_title_regex` – disable Kodiak merging based on a regex matching to the pull request title.
- `merge.blacklist_labels` – disable Kodiak merging based on labels applied to the PR
- `merge.do_not_merge` – completely disable Kodiak from merging any PR


### Efficient Merging

With default settings, Kodiak will conserve continuous integration (CI) resources and only update a PR when necessary prior to merge. This can be altered with `update.always` at a cost of more CI load.

By default Kodiak's internal merge queue acts on a first-come, first-served basis. The first pull request that enters the queue will be merge before any other pull request, even if another pull request requires fewer branch updates.

If `merge.prioritize_ready_to_merge` is enabled, if a PR is able to be merged without any branch updates, Kodiak will merge it, ignoring any pull requests in the queue.

If a pull request is out of date when Kodiak starts merging it, Kodiak will not wait for pending status checks to update the pull request. This improves merge performance at the cost of potential extra CI jobs. You can disable this behavior by turning off `merge.optimistic_updates`.

### Branch cleanup

Kodiak can delete branches on merge when `merge.delete_branch_on_merge` is enabled. GitHub now has this feature, but Kodiak had it first! 😊

### Merge Conflicts

By default, if a pull request encounters a merge conflict with the `merge.automerge_label` applied, Kodiak will comment on the PR about the merge conflict and remove the automerge label. This can be disabled with `merge.notify_on_conflict`.


## Approving Pull Requests
Kodiak can approve PRs with `approve.auto_approve_usernames`.

This is useful when the "Require pull request reviews before merging" Branch Protection setting is enabled and you want to automate dependency updates for services like dependabot.

If dependabot opens a PR, Kodiak can automatically approve the PR so it passes GitHub Branch Protection settings.

 See [Automated dependency updates with Dependabot](recipes.md#automated-dependency-updates-with-dependabot) for more information.
