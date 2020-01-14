import hashlib
import hmac
from typing import Optional

from fastapi import HTTPException
from starlette import status

from kodiak import app_config


async def extract_github_event(
    body: bytes, x_github_event: Optional[str], x_hub_signature: Optional[str]
) -> str:
    """
    Validate GitHub event and get the event name.
    """
    expected_sha = hmac.new(
        key=app_config.SECRET_KEY.encode(), msg=body, digestmod=hashlib.sha1
    ).hexdigest()
    if x_github_event is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required header: X-Github-Event",
        )
    if x_hub_signature is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required signature: X-Hub-Signature",
        )
    sha = x_hub_signature.replace("sha1=", "")
    if not hmac.compare_digest(sha, expected_sha):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature: X-Hub-Signature",
        )
    return x_github_event
