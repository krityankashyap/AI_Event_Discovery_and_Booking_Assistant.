from langchain_core.tools import tool

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
        events = await service.search_events(keyword=keyword, city=city)
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

    return [search_events]
