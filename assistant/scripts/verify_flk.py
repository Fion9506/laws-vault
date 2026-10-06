"""flk-mcp 可用性验证脚本。用法：python scripts/verify_flk.py

经验（2026-09-26）：系统代理会拦截 127.0.0.1 请求导致 502 Bad Gateway，
必须在 httpx 发起请求前设置 NO_PROXY 绕过代理。
"""
import os
os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"

import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = "http://127.0.0.1:18062/mcp"


async def main():
    async with streamablehttp_client(URL) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = [t.name for t in (await s.list_tools()).tools]
            print(f"flk-mcp OK ({len(tools)} tools): {', '.join(tools)}")


asyncio.run(main())
