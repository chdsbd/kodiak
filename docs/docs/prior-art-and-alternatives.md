---
id: prior-art-and-alternatives
title: Prior Art / Alternatives
sidebar_label: Prior Art / Alternatives
---

If Kodiak doesn't suit your current needs, there are plenty of
implementations of pull request (PR) automation and efficent branch updating and merging.

| Name                                                                                                                                               | Auto Merging | Auto Update Branches | Update Branches Efficiently | Works With Branch Protection | Works with Forks | Simple Configuration | Open Source | Hosted SaaS | Free for public and personal repositories | Language   |
| -------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | -------------------- | --------------------------- | ---------------------------- | ---------------- | -------------------- | ----------- | ----------- | ----------------------------------------- | ---------- |
| <!-- 2019-04-18 --> [Kodiak](https://github.com/chdsbd/kodiak)                                                                                     | ✅           | ✅                   | ✅                          | ✅                           | ✅               | ✅                   | ✅          | ✅          | ✅                                        | Python     |
| <!-- 2013-02-01 --> <a rel="nofollow" href="https://github.com/graydon/bors">Bors</a>                                                              | ✅           | ✅                   | ✅                          | ❌                           | ❌               | ❌                   | ✅          | ❌          | ❌                                        | Python     |
| <!-- 2014-12-18 --> <a rel="nofollow" href="https://github.com/barosl/homu">Homu</a>                                                               | ✅           | ✅                   | ✅                          | ❌                           | ❌               | ❌                   | ✅          | ❌          | ❌                                        | Python     |
| <!-- 2014-02-26 --> <a rel="nofollow" href="https://github.com/Shopify/shipit-engine">Shipit</a>                                                   | ✅           | ✅                   | ❌                          | ❌                           | ❌               | ❌                   | ✅          | ❌          | ❌                                        | Ruby       |
| <!-- 2016-08-06 --> <a rel="nofollow" href="https://github.com/gullintanni/gullintanni">Gullintanni</a>                                            | ✅           | ✅                   | ✅                          | ❌                           | ❌               | ❌                   | ✅          | ❌          | ❌                                        | Elixir     |
| <!-- 2016-10-27 --> <a rel="nofollow" href="https://github.com/voyagegroup/popuko">Popuko</a>                                                      | ✅           | ✅                   | ✅                          | ❌                           | ❌               | ❌                   | ✅          | ❌          | ❌                                        | Go         |
| <!-- 2016-12-13 --> <a rel="nofollow" href="https://bors.tech">Bors-ng</a>                                                                         | ✅           | ✅                   | ✅                          | ❌                           | ❌               | ❌                   | ✅          | ❌          | ❌                                        | Elixir     |
| <!-- 2017-01-18 --> <a rel="nofollow" href="https://github.com/smarkets/marge-bot">Marge-bot</a>                                                   | ✅           | ✅                   | ✅                          | ❌                           | ❌               | ❌                   | ✅          | ❌          | ❌                                        | Python     |
| <!-- 2017-09-17 --> <a rel="nofollow" href="https://github.com/palantir/bulldozer">Bulldozer</a>                                                   | ✅           | ✅                   | ❌                          | ✅                           | ❌               | ❌                   | ✅          | ❌          | ❌                                        | Go         |
| <!-- 2018-04-18 --> <a rel="nofollow" href="https://github.com/Mergifyio/mergify-engine">Mergify</a>                                               | ✅           | ✅                   | ❌                          | ❌                           | ❌               | ❌                   | ❌          | ✅          | ❌                                        | Python     |
| <!-- 2018-07-05 --> <a rel="nofollow" href="https://github.com/tibdex/autorebase">Autorebase</a>                                                   | ✅           | ✅                   | ❌                          | ✅                           | ❌               | ❌                   | ✅          | ❌          | ❌                                        | TypeScript |
| <!-- 2018-09-21 --> <a rel="nofollow" href="https://github.com/SvanBoxel/auto-merge">Auto Merge</a>                                                | ✅           | ❌                   | ❌                          | ❌                           | ❌               | ❌                   | ✅          | ❌          | ❌                                        | JavaScript |
| <!-- 2018-10-21 --> <a rel="nofollow" href="https://github.com/phstc/probot-merge-when-green">Merge when green</a>                                 | ✅           | ❌                   | ❌                          | ❌                           | ❌               | ❌                   | ✅          | ❌          | ❌                                        | JavaScript |
| <!-- 2020-12-16 --> <a rel="nofollow" href="https://github.blog/changelog/2020-12-16-pull-request-auto-merge-public-beta/">GitHub's auto-merge</a> | ✅           | ❌                   | ❌                          | ✅                           | ✅               | ✅                   | ❌          | ✅          | ✅                                        | 🤷‍        |
| <!-- 2021-08-28 --> <a rel="nofollow" href="https://https://mergequeue.com">MergeQueue</a>                                                         | ✅           | ✅                   | ✅                          | ✅                           | ❌               | ❌                   | ❌          | ✅          | ❌                                        | 🤷‍        |
| <!-- Unknown --> <a rel="nofollow" href="https://reporanger.com">Ranger</a> ‍                                                                      | ✅           | ❌ ‍                 | ❌ ‍                        | ✅                           | ❌               | ❌                   | ❌          | ✅          | ❌                                        | 🤷‍        |

## Explanations

### Auto Merging

- automatically merges PR once up to date with master and all required statuses and checks pass

### Auto Update Branches

- ensures branches are automatically updated to the latest version of master

### Update Branches Efficiently

- an improvement upon [Auto Update Branches](#auto-update-branches) where branches are only updated when necessary, as opposed to updating all branches any time their target branch (usually master) updates

### Works With Branch Protection

- PR mergeability is determined by GitHub Branch Protection settings and app configuration
- doesn't require changing continuous integration (CI) tools
- doesn't create separate test branches for merging that would circumvent the GitHub PR workflow

### Works with Forks

- will update and merge pull requests made from repositories forks. This is a necessary for an open source project to accept changes from external contributors.

### Simple Configuration

- configuration has sane defaults and requires minimal effort from the user. Kodiak's configuration is a simple TOML file with only one required configuration option.

```toml
# .kodiak.toml
version = 1
```

### Open Source

- documentation and resources necessary to self host the application are publically available.

### Hosted SaaS

- a publically hosted version of the application is available for users to install.

### Free for public and personal repositories

- hosted version is free for all public repositories and Personal repositories. Kodiak only charges for use with private Organization repositories.

## Resources

- For a list of Kodiak's features see the ["Features" page](features.md).
- Check out the ["Recipes" page](recipes.md) for configuration examples.
