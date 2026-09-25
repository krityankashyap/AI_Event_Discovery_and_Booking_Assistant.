import json

from backend.errors import EventNotFound
from backend.main import handle_app_error


async def test_app_error_shape():
    response = await handle_app_error(request=None, exc=EventNotFound("Event abc not found"))
    assert response.status_code == 404
    body = json.loads(response.body)
    assert body == {"error": {"code": "event_not_found", "message": "Event abc not found"}}
