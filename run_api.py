from __future__ import annotations

import uvicorn

from mayabu.core.config import get_app_settings


if __name__ == "__main__":
    settings = get_app_settings()
    development = settings.environment == "development"

    uvicorn.run(
        "mayabu.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=development,
        workers=1 if development else settings.api_workers,
    )