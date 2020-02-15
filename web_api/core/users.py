import logging
from typing import List, Optional

import requests

from core.models import Installation, InstallationMembership, User

logger = logging.getLogger(__name__)


class SyncError(Exception):
    pass


def sync_installations(user: User) -> None:
    """

    - create any missing installations
    - add memberships of user for installations
    - remove memberships of installations that aren't included
    """
    user_installations_res = requests.get(
        "https://api.github.com/user/installations",
        headers=dict(
            authorization=f"Bearer {user.github_access_token}",
            Accept="application/vnd.github.machine-man-preview+json",
        ),
    )
    try:
        user_installations_res.raise_for_status()
    except requests.HTTPError:
        logging.warning("sync_installation failed", exc_info=True)
        raise SyncError

    # TODO(chdsbd): Handle multiple pages of installations
    try:
        if user_installations_res.links["next"]:
            logging.warning("user has multiple pages")
    except KeyError:
        pass

    installations_data = user_installations_res.json()
    installations = installations_data["installations"]

    installs: List[Installation] = []

    for installation in installations:
        installation_id = installation["id"]
        installation_account_id = installation["account"]["id"]
        installation_account_login = installation["account"]["login"]
        installation_account_type = installation["account"]["type"]

        existing_install: Optional[Installation] = Installation.objects.filter(
            github_account_id=installation_account_id
        ).first()
        if existing_install is None:
            install = Installation.objects.create(
                github_id=installation_id,
                github_account_id=installation_account_id,
                github_account_login=installation_account_login,
                github_account_type=installation_account_type,
                payload=installation,
            )
        else:
            install = existing_install
            install.github_id = installation_id
            install.github_account_id = installation_account_id
            install.github_account_login = installation_account_login
            install.github_account_type = installation_account_type
            install.payload = installation
            install.save()

        try:
            InstallationMembership.objects.get(installation=install, user=user)
        except InstallationMembership.DoesNotExist:
            InstallationMembership.objects.create(installation=install, user=user)

        installs.append(install)

    # remove installations to which the user no longer has access.
    InstallationMembership.objects.exclude(installation__in=installs).filter(
        user=user
    ).delete()
