from fastapi import (
    APIRouter,
    Header,
    Query,
)

from fastapi.responses import HTMLResponse, JSONResponse

from .config import settings
from .database import Database
from .security import require_dashboard_token
from .templates import dashboard_html


router = APIRouter()


def get_database(request):
    return request.app.state.database


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def dashboard(
    request,
    token: str | None = Query(
        default=None
    ),
    authorization: str | None = Header(
        default=None
    ),
):

    provided_token = token

    if authorization and authorization.startswith(
        "Bearer "
    ):
        provided_token = authorization[7:]

    require_dashboard_token(
        provided_token,
        settings.dashboard_token,
    )

    database: Database = get_database(
        request
    )

    stats = await database.get_stats()

    events = await database.get_recent_events(
        limit=100
    )

    return HTMLResponse(
        dashboard_html(
            stats,
            events,
        )
    )


@router.get("/api/stats")
async def api_stats(
    request,
    token: str | None = Query(
        default=None
    ),
    authorization: str | None = Header(
        default=None
    ),
):

    provided_token = token

    if authorization and authorization.startswith(
        "Bearer "
    ):
        provided_token = authorization[7:]

    require_dashboard_token(
        provided_token,
        settings.dashboard_token,
    )

    database: Database = get_database(
        request
    )

    stats = await database.get_stats()

    return JSONResponse(stats)