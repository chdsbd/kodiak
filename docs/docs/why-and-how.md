---
id: why-and-how
title: Why and How
---

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

Additionally this introduces fairness to the PR merge process as ready to
merge PRs in the merge queue are merged on a first come, first served basis.

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
