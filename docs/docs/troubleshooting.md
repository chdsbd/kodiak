---
id: troubleshooting
title: Troubleshooting
sidebar_label: Troubleshooting
---

If Kodiak isn't working as expected, feel free to file a [GitHub Issue](https://github.com/chdsbd/kodiak/issues/new/choose) or email us at support@kodiakhq.com.

## Workarounds

Editing a pull request (changing title, editing labels, etc.) will trigger Kodiak to evaluate the pull request for mergeability. If you think Kodiak's status check is stuck, editing a pull request may help.

### Kodiak isn't running on one of my repositories

Verify you have granted Kodiak access to that repository for your installation.

1. Visit https://github.com/settings/installations and click "Configure" on your kodiakhq installation
2. Verify you have granted repository access to "All repositories" or have selected your specific repository if you chose "Only select repositories"

### Kodiak isn't working on any of my repositories

If all else fails, you can reinstall the Kodiak GitHub App. After reinstalling, follow the "workarounds" section above to trigger Kodiak to evaluate your exiting pull requests.

If you need to do this, please also contact support@github.com.

## Known issues

### Branch protection requirement

Kodiak intentionally requires branch protection to be enabled to function,
Kodiak won't activate if branch protection is disabled.

### Commit signature support

Kodiak is able to [create signatures](https://help.github.com/en/articles/about-required-commit-signing) for merge and squash commits, but not rebase merges due to GitHub API limitations. ([kodiak#89](https://github.com/chdsbd/kodiak/issues/89))

### Restricting pushes

If you use the "Restrict who can push to matching branches" branch protection setting you must add Kodiak as an allowed user, like the following screenshot.
![Restrict who can push to matching branches](/img/restrict-who-can-push-to-matching-branches.png) Kodiak will not be able to merge pull requests without this and you will receive a mysterious "Merging blocked by GitHub requirements" status check.

### Kodiak "Merging blocked by GitHub requirements" status check

If you see Kodiak providing a status check of "Merging blocked by GitHub requirements", this likely means there is a branch protection setting that conflicts with Kodiak. If you see this issue persistently please contact us at support@kodiakhq.com.

### Merge Errors

It is dangerous to retry merging a pull request when GitHub returns an internal server error (HTTP status code 500) because the merge can partially succeed in a way that will leave the pull request open, but the branch merged.

This state where the branch has been merged but the pull request remains open would trigger Kodiak to erroneously merge in the pull request multiple times, as we've seen in [#397](https://github.com/chdsbd/kodiak/issues/397). To prevent this behavior Kodiak will disable itself on a pull request if it encounters an internal server error when merging a pull request.

If Kodiak set the `disable_bot_label` label (default "kodiak:disabled") on your pull request you can remove the label to re-enable Kodiak. GitHub API instability is usually brief.

Related issues: [#398](https://github.com/chdsbd/kodiak/pull/398), [#397](https://github.com/chdsbd/kodiak/issues/397)

### GitHub Enterprise IP allow list

GitHub Enterprise [allows limiting access by IP address](https://docs.github.com/en/organizations/keeping-your-organization-secure/managing-allowed-ip-addresses-for-your-organization). To allow Kodiak to run when the IP allow list is enabled, you must add Kodiak's outgoing IP addresses to your allow list.

Here's the list of outgoing IP addresses Kodiak uses.

```
174.138.118.176
165.227.248.81
```
