from typing import Any, cast

import pytest
import responses

from core.models import Account, AccountMembership, SyncAccountsError, User


@pytest.fixture
def user() -> User:
    return cast(
        User,
        User.objects.create(
            github_id=10137,
            github_login="ghost",
            github_access_token="33149942-C986-42F8-9A45-AD83D5077776",
        ),
    )


@pytest.fixture
def mocked_responses() -> Any:
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
def failing_installation_response(mocked_responses: Any) -> None:
    mocked_responses.add(
        responses.GET,
        "https://api.github.com/user/installations",
        json={
            "message": "Bad credentials",
            "documentation_url": "https://developer.github.com/v3",
        },
        status=401,
    )


@pytest.fixture
def successful_installation_response(mocked_responses: Any) -> None:
    mocked_responses.add(
        responses.GET,
        "https://api.github.com/user/installations",
        json={
            "total_count": 1,
            "installations": [
                {
                    "id": 1066615,
                    "account": {
                        "login": "chdsbd",
                        "id": 1929960,
                        "node_id": "MDQ6VXNlcjE5Mjk5NjA=",
                        "avatar_url": "https://avatars2.githubusercontent.com/u/1929960?v=4",
                        "gravatar_id": "",
                        "url": "https://api.github.com/users/chdsbd",
                        "html_url": "https://github.com/chdsbd",
                        "followers_url": "https://api.github.com/users/chdsbd/followers",
                        "following_url": "https://api.github.com/users/chdsbd/following{/other_user}",
                        "gists_url": "https://api.github.com/users/chdsbd/gists{/gist_id}",
                        "starred_url": "https://api.github.com/users/chdsbd/starred{/owner}{/repo}",
                        "subscriptions_url": "https://api.github.com/users/chdsbd/subscriptions",
                        "organizations_url": "https://api.github.com/users/chdsbd/orgs",
                        "repos_url": "https://api.github.com/users/chdsbd/repos",
                        "events_url": "https://api.github.com/users/chdsbd/events{/privacy}",
                        "received_events_url": "https://api.github.com/users/chdsbd/received_events",
                        "type": "User",
                        "site_admin": False,
                    },
                    "repository_selection": "selected",
                    "access_tokens_url": "https://api.github.com/app/installations/1066615/access_tokens",
                    "repositories_url": "https://api.github.com/installation/repositories",
                    "html_url": "https://github.com/settings/installations/1066615",
                    "app_id": 31500,
                    "app_slug": "kodiak-local-dev",
                    "target_id": 1929960,
                    "target_type": "User",
                    "permissions": {
                        "administration": "read",
                        "checks": "write",
                        "contents": "write",
                        "issues": "read",
                        "metadata": "read",
                        "pull_requests": "write",
                        "statuses": "read",
                    },
                    "events": [
                        "check_run",
                        "issue_comment",
                        "pull_request",
                        "pull_request_review",
                        "pull_request_review_comment",
                        "push",
                        "status",
                    ],
                    "created_at": "2019-05-26T23:47:57.000-04:00",
                    "updated_at": "2020-02-09T18:39:43.000-05:00",
                    "single_file_name": None,
                },
                {
                    "id": 81843,
                    "account": {
                        "login": "recipeyak",
                        "id": 57954,
                        "node_id": "MDQ6T3JnYW5pemF0aW9uNTc5NTQ=",
                        "avatar_url": "https://avatars2.githubusercontent.com/u/57954?v=4",
                        "gravatar_id": "",
                        "url": "https://api.github.com/users/recipeyak",
                        "html_url": "https://github.com/recipeyak",
                        "followers_url": "https://api.github.com/users/recipeyak/followers",
                        "following_url": "https://api.github.com/users/recipeyak/following{/other_user}",
                        "gists_url": "https://api.github.com/users/recipeyak/gists{/gist_id}",
                        "starred_url": "https://api.github.com/users/recipeyak/starred{/owner}{/repo}",
                        "subscriptions_url": "https://api.github.com/users/recipeyak/subscriptions",
                        "organizations_url": "https://api.github.com/users/recipeyak/orgs",
                        "repos_url": "https://api.github.com/users/recipeyak/repos",
                        "events_url": "https://api.github.com/users/recipeyak/events{/privacy}",
                        "received_events_url": "https://api.github.com/users/recipeyak/received_events",
                        "type": "Organization",
                        "site_admin": False,
                    },
                    "repository_selection": "selected",
                    "access_tokens_url": "https://api.github.com/app/installations/81843/access_tokens",
                    "repositories_url": "https://api.github.com/installation/repositories",
                    "html_url": "https://github.com/settings/installations/81843",
                    "app_id": 31500,
                    "app_slug": "kodiak-local-dev",
                    "target_id": 1929960,
                    "target_type": "User",
                    "permissions": {
                        "administration": "read",
                        "checks": "write",
                        "contents": "write",
                        "issues": "read",
                        "metadata": "read",
                        "pull_requests": "write",
                        "statuses": "read",
                    },
                    "events": [
                        "check_run",
                        "issue_comment",
                        "pull_request",
                        "pull_request_review",
                        "pull_request_review_comment",
                        "push",
                        "status",
                    ],
                    "created_at": "2019-06-12T16:21:22.000-04:00",
                    "updated_at": "2020-03-11T13:11:25.000-05:00",
                    "single_file_name": None,
                },
            ],
        },
    )


@pytest.mark.django_db
def test_sync_accounts_failing_api_request(
    user: User, failing_installation_response: object
) -> None:
    with pytest.raises(SyncAccountsError):
        user.sync_accounts()


@pytest.mark.django_db
def test_sync_accounts_new_and_existing_accounts(
    user: User, successful_installation_response: object
) -> None:
    user_account = Account.objects.create(
        github_id=1066615,
        github_account_login=user.github_login,
        github_account_id=1929960,
        github_account_type="User",
    )
    AccountMembership.objects.create(user=user, account=user_account)

    # the user should get removed from this account when we sync. This tests
    # that our membership removal of installations a user no longer has access
    # to works.
    acme_corp_account = Account.objects.create(
        github_id=79233,
        github_account_login="acme-corp",
        github_account_id=33803,
        github_account_type="Organization",
    )
    AccountMembership.objects.create(user=user, account=acme_corp_account)

    assert Account.objects.count() == 2
    assert AccountMembership.objects.filter(user=user).count() == 2
    user.sync_accounts()

    assert (
        Account.objects.count() == 3
    ), "we should have a new account for recipeyak, brining the total to three."
    assert (
        AccountMembership.objects.filter(user=user).count() == 2
    ), "we should be added to recipeyak, but removed from acme-corp."

    assert (
        AccountMembership.objects.filter(user=user, account=acme_corp_account).exists()
        is False
    ), "the user should no longer be a member of the organization if is no longer returned from `/user/installations` endpoint."
    assert (
        Account.objects.filter(id=acme_corp_account.id).exists() is True
    ), "account that we are no longer a member of should not be deleted."
