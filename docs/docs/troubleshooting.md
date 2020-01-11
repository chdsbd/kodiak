---
id: troubleshooting
title: Troubleshooting
sidebar_label: Troubleshooting
---

If Kodiak isn't working as expected, feel free to file an [GitHub Issue](https://github.com/chdsbd/kodiak/issues/new/choose).

## Known Issues

- Kodiak intentionally requires branch protection to be enabled to function,
  Kodiak won't merge PRs if branch protection is disabled.
- Due to a limitation with the GitHub API, Kodiak doesn't support [requiring
  signed commits](https://help.github.com/en/articles/about-required-commit-signing).
  ([kodiak#89](https://github.com/chdsbd/kodiak/issues/89))
- GitHub CODEOWNERS are not supported. Kodiak will prematurely update PRs that still require a review from a Code Owner. However, Kodiak will be able to merge the PR once all checks pass. ([kodiak#87](https://github.com/chdsbd/kodiak/issues/87))
- Using `merge.block_on_reviews_requested` is not recommended. If a PR is blocked by this rule a reviewer's comment will allow the PR to be merged, not just a positive approval. This is a limitation of the GitHub API. Please try GitHub's required approvals branch protection setting instead. ([kodiak#153](https://github.com/chdsbd/kodiak/issues/153))
