import secrets

from fastapi import Header, HTTPException


def verify_dashboard_token(
    provided_token: str | None,
    expected_token: str,
) -> bool:

    if not provided_token:
        return False

    return secrets.compare_digest(
        provided_token,
        expected_token,
    )


def verify_webhook_secret(
    provided_secret: str | None,
    expected_secret: str,
) -> bool:

    if not provided_secret:
        return False

    return secrets.compare_digest(
        provided_secret,
        expected_secret,
    )


def require_dashboard_token(
    token: str | None,
    expected_token: str,
):
    if not verify_dashboard_token(
        token,
        expected_token,
    ):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
        )