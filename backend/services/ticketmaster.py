import httpx

from backend import config
from backend.errors import (
    EventNotFound,
    TicketmasterAuthError,
    TicketmasterRateLimited,
    TicketmasterUnavailable,
)
from backend.models.schemas import Event

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

    def _normalize_event(self, raw: dict) -> Event:
        dates = raw.get("dates", {})
        start = dates.get("start", {})
        status = dates.get("status", {})

        venues = raw.get("_embedded", {}).get("venues", [])
        venue = venues[0] if venues else {}

        price_ranges = raw.get("priceRanges", [])
        price = price_ranges[0].get("min") if price_ranges else None

        return Event(
            id=raw["id"],
            name=raw["name"],
            url=raw["url"],
            date=start.get("localDate"),
            time=start.get("localTime"),
            status=status.get("code"),
            price=price,
            city=venue.get("city", {}).get("name"),
            country=venue.get("country", {}).get("name"),
        )

    async def search_events(
        self, keyword: str | None = None, city: str | None = None, size: int = 20
    ) -> list[Event]:
        params: dict = {"size": min(size, 20), "sort": "date,asc"}
        if keyword:
            params["keyword"] = keyword
        if city:
            params["city"] = city

        data = await self._get("/events.json", params)
        raw_events = data.get("_embedded", {}).get("events", [])
        return [self._normalize_event(e) for e in raw_events]

    async def get_event(self, event_id: str) -> Event:
        data = await self._get(f"/events/{event_id}.json", {})
        return self._normalize_event(data)
