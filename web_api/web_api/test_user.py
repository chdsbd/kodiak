from typing import Any

import pytest
import responses

from web_api.models import Account, AccountMembership, SyncAccountsError, User


@pytest.fixture
def user() -> User:
    return User.objects.create(
        github_id=10137,
        github_login="ghost",
        github_access_token="33149942-C986-42F8-9A45-AD83D5077776",
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
                        "login": "ghost",
                        "id": 10137,
                        "node_id": "MDQ6VXNlcjE5Mjk5NjA=",
                        "avatar_url": "https://avatars2.githubusercontent.com/u/10137?v=4",
                        "gravatar_id": "",
                        "url": "https://api.github.com/users/ghost",
                        "html_url": "https://github.com/ghost",
                        "followers_url": "https://api.github.com/users/ghost/followers",
                        "following_url": "https://api.github.com/users/ghost/following{/other_user}",
                        "gists_url": "https://api.github.com/users/ghost/gists{/gist_id}",
                        "starred_url": "https://api.github.com/users/ghost/starred{/owner}{/repo}",
                        "subscriptions_url": "https://api.github.com/users/ghost/subscriptions",
                        "organizations_url": "https://api.github.com/users/ghost/orgs",
                        "repos_url": "https://api.github.com/users/ghost/repos",
                        "events_url": "https://api.github.com/users/ghost/events{/privacy}",
                        "received_events_url": "https://api.github.com/users/ghost/received_events",
                        "type": "User",
                        "site_admin": False,
                    },
                    "repository_selection": "selected",
                    "access_tokens_url": "https://api.github.com/app/installations/136746/access_tokens",
                    "repositories_url": "https://api.github.com/installation/repositories",
                    "html_url": "https://github.com/settings/installations/136746",
                    "app_id": 31500,
                    "app_slug": "kodiak-local-dev",
                    "target_id": 10137,
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
                    "id": 136746,
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
    mocked_responses.add(
        responses.GET,
        "https://api.github.com/orgs/recipeyak/memberships/ghost",
        json={
            "organization": {
                "avatar_url": "https://avatars2.githubusercontent.com/u/57954?v=4",
                "description": None,
                "events_url": "https://api.github.com/orgs/recipeyak/events",
                "hooks_url": "https://api.github.com/orgs/recipeyak/hooks",
                "id": 57954,
                "issues_url": "https://api.github.com/orgs/recipeyak/issues",
                "login": "recipeyak",
                "members_url": "https://api.github.com/orgs/recipeyak/members{/member}",
                "node_id": "MDQ6T3JnYW5pemF0aW9uNTc5NTQ=",
                "public_members_url": "https://api.github.com/orgs/recipeyak/public_members{/member}",
                "repos_url": "https://api.github.com/orgs/recipeyak/repos",
                "url": "https://api.github.com/orgs/recipeyak",
            },
            "organization_url": "https://api.github.com/orgs/recipeyak",
            "role": "admin",
            "state": "active",
            "url": "https://api.github.com/orgs/recipeyak/memberships/ghost",
            "user": {
                "avatar_url": "https://avatars2.githubusercontent.com/u/1929960?v=4",
                "events_url": "https://api.github.com/users/ghost/events{/privacy}",
                "followers_url": "https://api.github.com/users/ghost/followers",
                "following_url": "https://api.github.com/users/ghost/following{/other_user}",
                "gists_url": "https://api.github.com/users/ghost/gists{/gist_id}",
                "gravatar_id": "",
                "html_url": "https://github.com/ghost",
                "id": 10137,
                "login": "ghost",
                "node_id": "MDQ6VXNlcjEwMTM3Cg=",
                "organizations_url": "https://api.github.com/users/ghost/orgs",
                "received_events_url": "https://api.github.com/users/ghost/received_events",
                "repos_url": "https://api.github.com/users/ghost/repos",
                "site_admin": False,
                "starred_url": "https://api.github.com/users/ghost/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/ghost/subscriptions",
                "type": "User",
                "url": "https://api.github.com/users/ghost",
            },
        },
    )


@pytest.fixture
def failing_installation_response_membership_check(mocked_responses: Any) -> None:
    mocked_responses.add(
        responses.GET,
        "https://api.github.com/user/installations",
        json={
            "total_count": 1,
            "installations": [
                {
                    "id": 1066615,
                    "account": {
                        "login": "ghost",
                        "id": 10137,
                        "node_id": "MDQ6VXNlcjE5Mjk5NjA=",
                        "avatar_url": "https://avatars2.githubusercontent.com/u/10137?v=4",
                        "gravatar_id": "",
                        "url": "https://api.github.com/users/ghost",
                        "html_url": "https://github.com/ghost",
                        "followers_url": "https://api.github.com/users/ghost/followers",
                        "following_url": "https://api.github.com/users/ghost/following{/other_user}",
                        "gists_url": "https://api.github.com/users/ghost/gists{/gist_id}",
                        "starred_url": "https://api.github.com/users/ghost/starred{/owner}{/repo}",
                        "subscriptions_url": "https://api.github.com/users/ghost/subscriptions",
                        "organizations_url": "https://api.github.com/users/ghost/orgs",
                        "repos_url": "https://api.github.com/users/ghost/repos",
                        "events_url": "https://api.github.com/users/ghost/events{/privacy}",
                        "received_events_url": "https://api.github.com/users/ghost/received_events",
                        "type": "User",
                        "site_admin": False,
                    },
                    "repository_selection": "selected",
                    "access_tokens_url": "https://api.github.com/app/installations/136746/access_tokens",
                    "repositories_url": "https://api.github.com/installation/repositories",
                    "html_url": "https://github.com/settings/installations/136746",
                    "app_id": 31500,
                    "app_slug": "kodiak-local-dev",
                    "target_id": 10137,
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
                    "id": 136746,
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
                {
                    "id": 65490234,
                    "account": {
                        "login": "acme-corp",
                        "id": 23452345,
                        "node_id": "MDQ6T3JnYW5pemF0aW9uNjU0OTAyMzQK",
                        "avatar_url": "https://avatars2.githubusercontent.com/u/57954?v=4",
                        "gravatar_id": "",
                        "url": "https://api.github.com/users/acme-corp",
                        "html_url": "https://github.com/acme-corp",
                        "followers_url": "https://api.github.com/users/acme-corp/followers",
                        "following_url": "https://api.github.com/users/acme-corp/following{/other_user}",
                        "gists_url": "https://api.github.com/users/acme-corp/gists{/gist_id}",
                        "starred_url": "https://api.github.com/users/acme-corp/starred{/owner}{/repo}",
                        "subscriptions_url": "https://api.github.com/users/acme-corp/subscriptions",
                        "organizations_url": "https://api.github.com/users/acme-corp/orgs",
                        "repos_url": "https://api.github.com/users/acme-corp/repos",
                        "events_url": "https://api.github.com/users/acme-corp/events{/privacy}",
                        "received_events_url": "https://api.github.com/users/acme-corp/received_events",
                        "type": "Organization",
                        "site_admin": False,
                    },
                    "repository_selection": "selected",
                    "access_tokens_url": "https://api.github.com/app/installations/65490234/access_tokens",
                    "repositories_url": "https://api.github.com/installation/repositories",
                    "html_url": "https://github.com/settings/installations/65490234",
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
    mocked_responses.add(
        responses.GET,
        "https://api.github.com/orgs/recipeyak/memberships/ghost",
        json={
            "organization": {
                "avatar_url": "https://avatars2.githubusercontent.com/u/57954?v=4",
                "description": None,
                "events_url": "https://api.github.com/orgs/recipeyak/events",
                "hooks_url": "https://api.github.com/orgs/recipeyak/hooks",
                "id": 57954,
                "issues_url": "https://api.github.com/orgs/recipeyak/issues",
                "login": "recipeyak",
                "members_url": "https://api.github.com/orgs/recipeyak/members{/member}",
                "node_id": "MDQ6T3JnYW5pemF0aW9uNTc5NTQ=",
                "public_members_url": "https://api.github.com/orgs/recipeyak/public_members{/member}",
                "repos_url": "https://api.github.com/orgs/recipeyak/repos",
                "url": "https://api.github.com/orgs/recipeyak",
            },
            "organization_url": "https://api.github.com/orgs/recipeyak",
            "role": "admin",
            "state": "active",
            "url": "https://api.github.com/orgs/recipeyak/memberships/ghost",
            "user": {
                "avatar_url": "https://avatars2.githubusercontent.com/u/1929960?v=4",
                "events_url": "https://api.github.com/users/ghost/events{/privacy}",
                "followers_url": "https://api.github.com/users/ghost/followers",
                "following_url": "https://api.github.com/users/ghost/following{/other_user}",
                "gists_url": "https://api.github.com/users/ghost/gists{/gist_id}",
                "gravatar_id": "",
                "html_url": "https://github.com/ghost",
                "id": 10137,
                "login": "ghost",
                "node_id": "MDQ6VXNlcjEwMTM3Cg=",
                "organizations_url": "https://api.github.com/users/ghost/orgs",
                "received_events_url": "https://api.github.com/users/ghost/received_events",
                "repos_url": "https://api.github.com/users/ghost/repos",
                "site_admin": False,
                "starred_url": "https://api.github.com/users/ghost/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/ghost/subscriptions",
                "type": "User",
                "url": "https://api.github.com/users/ghost",
            },
        },
    )
    mocked_responses.add(
        responses.GET,
        "https://api.github.com/orgs/acme-corp/memberships/ghost",
        status=403,
        json={
            "message": "You must be a member of acme-corp to see membership information for ghost.",
            "documentation_url": "https://developer.github.com/v3/orgs/members/#get-organization-membership",
        },
    )


@pytest.mark.django_db
def test_sync_accounts_failing_api_request(
    user: User, failing_installation_response: object
) -> None:
    with pytest.raises(SyncAccountsError):
        user.sync_accounts()


@pytest.mark.django_db
def test_sync_accounts_failing_api_request_collaborator(
    user: User, failing_installation_response_membership_check: object
) -> None:
    """
    If the user is a collaborator of an organization they will get an API error
    when testing membership. We should ignore the error and not add them to that organization.
    """
    assert Account.objects.count() == 0
    assert AccountMembership.objects.count() == 0
    assert User.objects.count() == 1
    user.sync_accounts()

    assert (
        Account.objects.filter(
            github_account_login__in=["ghost", "chdsbd", "recipeyak"]
        ).count()
        == Account.objects.count()
        == 3
    )
    assert AccountMembership.objects.count() == 3
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_sync_accounts_new_and_existing_accounts(
    user: User, successful_installation_response: object
) -> None:
    user_account = Account.objects.create(
        github_installation_id=1066615,
        github_account_login=user.github_login,
        github_account_id=user.github_id,
        github_account_type="User",
    )
    AccountMembership.objects.create(user=user, account=user_account, role="member")

    # the user should get removed from this account when we sync. This tests
    # that our membership removal of installations a user no longer has access
    # to works.
    acme_corp_account = Account.objects.create(
        github_installation_id=79233,
        github_account_login="acme-corp",
        github_account_id=33803,
        github_account_type="Organization",
    )
    AccountMembership.objects.create(
        user=user, account=acme_corp_account, role="member"
    )

    assert Account.objects.count() == 2
    assert AccountMembership.objects.filter(user=user).count() == 2
    user.sync_accounts()

    assert Account.objects.filter(
        github_account_login__in=["recipeyak", "chdsbd", "ghost", "acme-corp"]
    )
    assert Account.objects.count() == 4, (
        "we should have a new account for recipeyak and chdsbd."
    )
    assert (
        AccountMembership.objects.filter(user=user)
        .exclude(account__github_account_login__in=["recipeyak", "chdsbd", "ghost"])
        .count()
        == 0
    ), "we should have removed acme-corp."
    assert (
        AccountMembership.objects.filter(
            user=user, role="member", account__github_account_login="chdsbd"
        ).count()
        == 1
    )
    assert (
        AccountMembership.objects.filter(
            user=user, role="admin", account__github_account_login="recipeyak"
        ).count()
        == 1
    )

    assert (
        AccountMembership.objects.filter(user=user, account=acme_corp_account).exists()
        is False
    ), (
        "the user should no longer be a member of the organization if is no longer returned from `/user/installations` endpoint."
    )
    assert Account.objects.filter(id=acme_corp_account.id).exists() is True, (
        "account that we are no longer a member of should not be deleted."
    )
