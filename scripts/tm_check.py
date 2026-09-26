import asyncio

import httpx

from backend.services.ticketmaster import TicketmasterService


async def main() -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        service = TicketmasterService(client)
        events = await service.search_events(keyword="concert", city="London", size=5)

        print(f"Got {len(events)} events\n")
        for i, event in enumerate(events, start=1):
            price = event.price if event.price is not None else "not listed"
            print(f"{i}. {event.name} | {event.date} {event.time} | {event.city} | price: {price}")
            print(f"   {event.url}")


if __name__ == "__main__":
    asyncio.run(main())