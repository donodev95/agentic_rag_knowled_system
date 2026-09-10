from typing import Annotated

from fastapi import Depends, Request

from backend.app.core.config import Settings


def get_request_settings(request: Request) -> Settings:
    """Return settings loaded during application startup."""
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(get_request_settings)] # Tell FastAPI to inject the settings into the endpoint function.