---
id: quickstart
title: Quick Start
sidebar_label: Quick Start
---

1.  Install [the GitHub app](https://github.com/marketplace/kodiakhq#pricing-and-setup)

2.  Create a `.kodiak.toml` file in the root of your repository with the following contents

    ```toml
    # .kodiak.toml
    # Minimal config. version is the only required field.
    version = 1
    ```

3.  Configure [GitHub branch protection](https://help.github.com/en/articles/configuring-protected-branches). Setup [required status checks](https://docs.github.com/en/github/administering-a-repository/enabling-required-status-checks) to prevent failing PRs from being merged.

4.  Create an automerge label (default: "automerge")

5.  Start auto merging PRs with Kodiak

    Label your PRs with your `automerge` label and let Kodiak do the rest! 🎉

If you have any questions please review [our help page](/help).
