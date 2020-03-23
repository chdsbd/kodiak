---
id: prior-art-and-alternatives
title: Prior Art / Alternatives
sidebar_label: Prior Art / Alternatives
---

If Kodiak doesn't suit your current needs, there are plenty of
implementations of pull request (PR) automation and efficent branch updating and merging.

| Name                                                                                                                 | Works With Branch Protection | Auto Merging | Auto Update Branches | Update Branches Efficiently | Open Source | Practice [Dogfooding](https://en.wikipedia.org/wiki/Eating_your_own_dog_food) | Language   |
| -------------------------------------------------------------------------------------------------------------------- | ---------------------------- | ------------ | -------------------- | --------------------------- | ----------- | ----------------------------------------------------------------------------- | ---------- |
| <!-- 2019-04-18 --> [Kodiak](https://github.com/chdsbd/kodiak)                                                       | ✅                           | ✅           | ✅                   | ✅                          | ✅          | ✅                                                                            | Python     |
| <!-- 2013-02-01 --> <a rel="nofollow" href="https://github.com/graydon/bors">Bors</a>                                | ❌                           | ✅           | ✅                   | ✅                          | ✅          | ❌                                                                            | Python     |
| <!-- 2014-12-18 --> <a rel="nofollow" href="https://github.com/barosl/homu">Homu</a>                                 | ❌                           | ✅           | ✅                   | ✅                          | ✅          | ❌                                                                            | Python     |
| <!-- 2014-02-26 --> <a rel="nofollow" href="https://github.com/Shopify/shipit-engine">Shipit</a>                     | ❌                           | ✅           | ✅                   | ❌                          | ✅          | ❌                                                                            | Ruby       |
| <!-- 2016-08-06 --> <a rel="nofollow" href="https://github.com/gullintanni/gullintanni">Gullintanni</a>              | ❌                           | ✅           | ✅                   | ✅                          | ✅          | ❌                                                                            | Elixir     |
| <!-- 2016-10-27 --> <a rel="nofollow" href="https://github.com/voyagegroup/popuko">Popuko</a>                        | ❌                           | ✅           | ✅                   | ✅                          | ✅          | ✅                                                                            | Go         |
| <!-- 2016-12-13 --> <a rel="nofollow" href="https://bors.tech">Bors-ng</a>                                           | ❌                           | ✅           | ✅                   | ✅                          | ✅          | ✅                                                                            | Elixir     |
| <!-- 2017-01-18 --> <a rel="nofollow" href="https://github.com/smarkets/marge-bot">Marge-bot</a>                     | ❌                           | ✅           | ✅                   | ✅                          | ✅          | ❌                                                                            | Python     |
| <!-- 2017-09-17 --> <a rel="nofollow" href="https://github.com/palantir/bulldozer">Bulldozer</a>                     | ✅                           | ✅           | ✅                   | ❌                          | ✅          | ❌                                                                            | Go         |
| <!-- 2018-04-18 --> <a rel="nofollow" href="https://github.com/Mergifyio/mergify-engine">Mergify</a>                 | ❌                           | ✅           | ✅                   | ❌                          | ✅          | ✅                                                                            | Python     |
| <!-- 2018-07-05 --> <a rel="nofollow" href="https://github.com/tibdex/autorebase">Autorebase</a>                     | ✅                           | ✅           | ✅                   | ❌                          | ✅          | ✅                                                                            | TypeScript |
| <!-- 2018-09-21 --> <a rel="nofollow" href="https://github.com/SvanBoxel/auto-merge">Auto Merge</a>                  | ❌                           | ✅           | ❌                   | ❌                          | ✅          | ❌                                                                            | JavaScript |
| <!-- 2018-10-21 --> <a rel="nofollow" href="https://github.com/phstc/probot-merge-when-green">Merge when green</a>   | ❌                           | ✅           | ❌                   | ❌                          | ✅          | ✅                                                                            | JavaScript |
| <!-- Unknown    --> <a rel="nofollow" href="https://github.com/marketplace/always-be-closing">Always Be Closing</a > | 🤷‍                          | ✅           | ✅                   | 🤷‍                         | ❌          | 🤷‍                                                                           | 🤷‍        |
| <!-- Unknown    --> <a rel="nofollow" href="https://github.com/marketplace/auto-merge">Auto Merge</a>                | 🤷‍                          | ✅           | 🤷‍                  | 🤷‍                         | ❌          | 🤷‍                                                                           | 🤷‍        |
| <!-- Unknown --> <a rel="nofollow" href="https://reporanger.com">Ranger</a>                                          | ✅ ‍                         | ✅           | ❌ ‍                 | ❌ ‍                        | ❌          | 🤷‍                                                                           | 🤷‍        |

## Explanations

### Works With Branch Protection

- PR mergeability is determined by GitHub Branch Protection settings and app configuration
- doesn't require changing continuous integration (CI) tools
- doesn't create separate test branches for merging that would circumvent the GitHub PR workflow

### Auto Merging

- automatically merges PR once up to date with master and all required statuses and checks pass

### Auto Update Branches

- ensures branches are automatically updated to the latest version of master

### Update Branches Efficiently

- an improvement upon [Auto Update Branches](#auto-update-branches) where branches are only updated when necessary, as opposed to updating all branches any time their target branch (usually master) updates
