import asyncio
import json
import os

from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

SUPERVISOR_WEBSOCKET = "ws://supervisor/core/websocket"
ADMIN_GROUP = "system-admin"


async def verify_ingress_admin(user_id: str) -> bool:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return False

    try:
        async with asyncio.timeout(5):
            async with connect(SUPERVISOR_WEBSOCKET, proxy=None, close_timeout=1) as websocket:
                greeting = json.loads(await websocket.recv())
                if not isinstance(greeting, dict) or greeting.get("type") != "auth_required":
                    return False

                await websocket.send(json.dumps({"type": "auth", "access_token": token}))
                authentication = json.loads(await websocket.recv())
                if not isinstance(authentication, dict) or authentication.get("type") != "auth_ok":
                    return False

                await websocket.send(json.dumps({"id": 1, "type": "config/auth/list"}))
                response = json.loads(await websocket.recv())
    except (OSError, TimeoutError, WebSocketException, ValueError, TypeError):
        return False

    if (
        not isinstance(response, dict)
        or response.get("id") != 1
        or response.get("type") != "result"
        or response.get("success") is not True
        or not isinstance(response.get("result"), list)
    ):
        return False

    matches = [user for user in response["result"] if isinstance(user, dict) and user.get("id") == user_id]
    if len(matches) != 1:
        return False
    user = matches[0]
    groups = user.get("group_ids")
    return user.get("is_active") is True and (
        user.get("is_owner") is True or (isinstance(groups, list) and ADMIN_GROUP in groups)
    )