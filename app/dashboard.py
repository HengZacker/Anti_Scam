import secrets

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Request,
)

from .config import settings


router = APIRouter(

    prefix="/dashboard",

    tags=["Dashboard"],
)


def verify_token(
    authorization: str | None,
    x_dashboard_token: str | None,
):

    token = None


    if (
        authorization
        and authorization.lower().startswith(
            "bearer "
        )
    ):

        token = (
            authorization[7:]
            .strip()
        )


    elif x_dashboard_token:

        token = (
            x_dashboard_token
            .strip()
        )


    if (
        not token
        or not secrets.compare_digest(
            token,
            settings.dashboard_token,
        )
    ):

        raise HTTPException(

            status_code=401,

            detail="Unauthorized",
        )


@router.get("")
async def dashboard(

    request: Request,

    authorization: str | None = Header(
        default=None
    ),

    x_dashboard_token: str | None = Header(
        default=None
    ),
):

    verify_token(
        authorization,
        x_dashboard_token,
    )


    database = (
        request
        .app
        .state
        .database
    )


    stats = (
        await database.get_stats()
    )


    top_extensions = (
        await database
        .get_top_extensions(10)
    )


    recent_events = (
        await database
        .get_recent_events(50)
    )


    return {

        "name":
            "Telegram File Guard",

        "version":
            "4.0.0",

        "environment":
            settings.environment,

        "delete_enabled":
            settings.delete_enabled,

        "dry_run":
            settings.dry_run,

        "blocked_extension_count":
            len(
                settings.blocked_extensions
            ),

        "blocked_extensions":
            sorted(
                settings.blocked_extensions
            ),

        "stats":
            stats,

        "top_extensions":
            top_extensions,

        "recent_events":
            recent_events,
    }