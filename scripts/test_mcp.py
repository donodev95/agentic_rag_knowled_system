import asyncio

from backend.app.core.config import get_settings
from backend.app.mcp.client import authenticated_mcp_session


async def test_query(session, query: str) -> None:
    print(f"\nQUERY: {query}")

    result = await session.call_tool(
        "get_file_metadata",
        arguments={
            "fileId": "1cOjVp9M6ooEw6JMRP8l8PiXElL-G5HAE",
        },
    )

    print("METADATA ERROR:", result.is_error)
    print("METADATA STRUCTURED:", result.structured_content)
    print("METADATA CONTENT:", result.content)
    
    


async def main() -> None:
    

    settings = get_settings()
    token = settings.google_drive_access_token.get_secret_value()

    print("PYTHON TOKEN PREFIX:", token[:20])
    print("PYTHON TOKEN LENGTH:", len(token))

    if settings.google_drive_access_token is None:
        raise RuntimeError("GOOGLE_DRIVE_ACCESS_TOKEN is not configured")

    token = settings.google_drive_access_token.get_secret_value()

    headers = {
        "x-goog-user-project": settings.google_drive_quota_project,
    }

    async with authenticated_mcp_session(
        settings.google_drive_mcp_url,
        token,
        additional_headers=headers,
    ) as session:

        await test_query(
            session,
            "owner = 'me'",
        )

        await test_query(
            session,
            "parentId = 'root'",
        )

        await test_query(
            session,
            f"parentId = '{settings.google_drive_folder_id}'",
        )


if __name__ == "__main__":
    asyncio.run(main())