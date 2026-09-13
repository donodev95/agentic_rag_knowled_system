import asyncio

from backend.app.core.config import get_settings
from backend.app.mcp.client import authenticated_mcp_session


async def main() -> None:
    settings = get_settings()

    token = settings.google_drive_access_token.get_secret_value()

    headers = {
        "x-goog-user-project": settings.google_drive_quota_project,
    }

    async with authenticated_mcp_session(
        settings.google_drive_mcp_url,
        token,
        additional_headers=headers,
    ) as session:

        tools = await session.list_tools()

        for tool in tools.tools:
            if tool.name == "search_files":
                print("NAME:")
                print(tool.name)

                print("\nDESCRIPTION:")
                print(tool.description)

                print("\nINPUT SCHEMA:")
                print(tool.input_schema)


if __name__ == "__main__":
    asyncio.run(main())