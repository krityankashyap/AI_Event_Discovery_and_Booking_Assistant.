from langchain_core.tools import tool

from backend.errors import AppError
from backend.services.ticketmaster import TicketmasterService


def create_event_tools(service: TicketmasterService) -> list:
    @tool(response_format="content_and_artifact")
    async def search_events(keyword: str | None = None, city: str | None = None):
        """Search for real events happening in a city.

        Use this whenever the user asks to find events, concerts, shows, or gigs.
        Args:
            keyword: what to search for, e.g. "concert", "Coldplay", "comedy".
            city: the city to search in, e.g. "London".
        """
        try:
            events = await service.search_events(keyword=keyword, city=city)
        except AppError as exc:
            return exc.message, []

        if not events:
            return "No events found.", []

        # content: numbered text WITH ids, for the LLM to reason over
        lines = []
        for i, e in enumerate(events, start=1):
            price = e.price if e.price is not None else "price not listed"
            lines.append(f"{i}. [id={e.id}] {e.name} | {e.date} {e.time} | {e.city} | {price}")
        content = "\n".join(lines)

        # artifact: structured dicts, for the UI (LLM never reads this)
        artifact = [e.model_dump() for e in events]

        return content, artifact

    @tool(response_format="content_and_artifact")
    async def get_event_details(event_id: str):
        """Get detailed information about one specific event, by its id.

        Use this when the user asks for more details about an event they've seen.
        Args:
            event_id: the event's id, taken from a previous search result.
        """
        try:
            event = await service.get_event(event_id)
        except AppError as exc:
            return exc.message, []

        price = event.price if event.price is not None else "price not listed"
        content = (
            f"[id={event.id}] {event.name} | {event.date} {event.time} | {event.city} | {price}"
        )
        return content, [event.model_dump()]

    @tool(response_format="content_and_artifact")
    async def request_booking(event_id: str):
        """Request to book a specific event. Returns the official booking URL.

        Only call this when the user has clearly chosen a specific event to book
        (e.g. "book number 1", "I want tickets to the Coldplay show").
        Args:
            event_id: the id of the event the user wants to book.
        """
        try:
            # Re-fetch so the booking URL comes from the API, never the model.
            event = await service.get_event(event_id)
        except AppError as exc:
            return exc.message, []

        content = f"Booking confirmed for {event.name}. Official link: {event.url}"
        artifact = {"event_id": event.id, "name": event.name, "url": event.url}
        return content, artifact

    return [search_events, get_event_details, request_booking]
