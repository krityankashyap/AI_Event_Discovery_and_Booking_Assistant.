from pydantic import BaseModel


class Event(BaseModel):
    id: str
    name: str
    url: str
    date: str | None = None
    time: str | None = None
    status: str | None = None
    price: float | None = None
    city: str | None = None
    country: str | None = None


class Venue(BaseModel):
    id: str
    name: str
    city: str | None = None
    country: str | None = None
    address: str | None = None
    url: str | None = None
