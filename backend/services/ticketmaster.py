import httpx

from backend import config
from backend.errors import (
    EventNotFound,
    TicketmasterAuthError,
    TicketmasterRateLimited,
    TicketmasterUnavailable,
)

BASE_URL = "https://app.ticketmaster.com/discovery/v2"


class TicketmasterService:
    def __init__(self, client: httpx.AsyncClient):
        self._client = client
        self._api_key = config.TICKETMASTER_API_KEY

    async def _get(self, path: str, params: dict) -> dict:
        params = {**params, "apikey": self._api_key}
        try:
            response = await self._client.get(f"{BASE_URL}{path}", params=params)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise TicketmasterUnavailable("Ticketmaster is unreachable.") from exc

        status = response.status_code
        if status in (401, 403):
            raise TicketmasterAuthError("Ticketmaster rejected our API key.")
        if status == 404:
            raise EventNotFound("The requested Ticketmaster resource was not found.")
        if status == 429:
            raise TicketmasterRateLimited("Ticketmaster rate limit hit. Try again shortly.")
        if status >= 500:
            raise TicketmasterUnavailable("Ticketmaster is having problems. Try again later.")
        return response.json()
