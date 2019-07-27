FORKS_CANNOT_BE_UPDATED = """\
The [Github merging API](https://developer.github.com/v3/repos/merging/) only supports updating branches within a repository, not across forks. While Kodiak can still merge pull requests created from forked repositories, it cannot automatically update them.

Please see [kodiak#104](https://github.com/chdsbd/kodiak/issues/104) for the most recent information on this limitation.

"""
