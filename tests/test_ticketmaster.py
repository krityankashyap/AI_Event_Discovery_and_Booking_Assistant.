import httpx
import pytest
import respx

from backend.errors import (
    EventNotFound,
    TicketmasterAuthError,
    TicketmasterRateLimited,
    TicketmasterUnavailable,
)
from backend.services.ticketmaster import BASE_URL, TicketmasterService


def _event_json(**overrides: object) -> dict:
    """Build one raw Ticketmaster event dict, with optional field overrides."""
    event = {
        "id": "abc",
        "name": "Coldplay",
        "url": "https://tm.com/abc",
        "dates": {
            "start": {"localDate": "2026-09-27", "localTime": "19:30:00"},
            "status": {"code": "onsale"},
        },
        "priceRanges": [{"min": 45.0, "max": 150.0, "currency": "GBP"}],
        "_embedded": {
            "venues": [
                {"name": "Wembley", "city": {"name": "London"}, "country": {"name": "GB"}}
            ]
        },
    }
    event.update(overrides)
    return event


@respx.mock
async def test_search_events_happy_path():
    respx.get(f"{BASE_URL}/events.json").mock(
        return_value=httpx.Response(200, json={"_embedded": {"events": [_event_json()]}})
    )
    async with httpx.AsyncClient() as client:
        events = await TicketmasterService(client).search_events(city="London")

    assert len(events) == 1
    e = events[0]
    assert e.id == "abc"
    assert e.name == "Coldplay"
    assert e.url == "https://tm.com/abc"
    assert e.date == "2026-09-27"
    assert e.time == "19:30:00"
    assert e.status == "onsale"
    assert e.price == 45.0
    assert e.city == "London"
    assert e.country == "GB"


@respx.mock
async def test_search_events_empty_results():
    # No "_embedded" key at all -> Ticketmaster's shape when nothing matches.
    respx.get(f"{BASE_URL}/events.json").mock(return_value=httpx.Response(200, json={}))
    async with httpx.AsyncClient() as client:
        events = await TicketmasterService(client).search_events(city="Atlantis")

    assert events == []


@respx.mock
async def test_search_events_missing_prices_stay_none():
    # priceRanges omitted entirely -> price must be None, never invented.
    event = _event_json()
    del event["priceRanges"]
    respx.get(f"{BASE_URL}/events.json").mock(
        return_value=httpx.Response(200, json={"_embedded": {"events": [event]}})
    )
    async with httpx.AsyncClient() as client:
        events = await TicketmasterService(client).search_events(city="London")

    assert events[0].price is None


@respx.mock
async def test_get_event_happy_path():
    respx.get(f"{BASE_URL}/events/abc.json").mock(
        return_value=httpx.Response(200, json=_event_json())
    )
    async with httpx.AsyncClient() as client:
        event = await TicketmasterService(client).get_event("abc")

    assert event.id == "abc"
    assert event.name == "Coldplay"


@respx.mock
async def test_get_event_404_maps_to_event_not_found():
    respx.get(f"{BASE_URL}/events/xyz.json").mock(return_value=httpx.Response(404))
    async with httpx.AsyncClient() as client:
        with pytest.raises(EventNotFound):
            await TicketmasterService(client).get_event("xyz")


@respx.mock
async def test_401_maps_to_auth_error():
    respx.get(f"{BASE_URL}/events.json").mock(return_value=httpx.Response(401))
    async with httpx.AsyncClient() as client:
        with pytest.raises(TicketmasterAuthError):
            await TicketmasterService(client).search_events(city="London")


@respx.mock
async def test_429_maps_to_rate_limited():
    respx.get(f"{BASE_URL}/events.json").mock(return_value=httpx.Response(429))
    async with httpx.AsyncClient() as client:
        with pytest.raises(TicketmasterRateLimited):
            await TicketmasterService(client).search_events(city="London")


@respx.mock
async def test_500_maps_to_unavailable():
    respx.get(f"{BASE_URL}/events.json").mock(return_value=httpx.Response(500))
    async with httpx.AsyncClient() as client:
        with pytest.raises(TicketmasterUnavailable):
            await TicketmasterService(client).search_events(city="London")


@respx.mock
async def test_timeout_maps_to_unavailable():
    respx.get(f"{BASE_URL}/events.json").mock(side_effect=httpx.TimeoutException("slow"))
    async with httpx.AsyncClient() as client:
        with pytest.raises(TicketmasterUnavailable):
            await TicketmasterService(client).search_events(city="London")
