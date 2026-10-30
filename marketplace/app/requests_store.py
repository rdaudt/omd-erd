from datetime import datetime

from pydantic import BaseModel

PERSONA = "John Analyst Doe"


class AccessRequest(BaseModel):
    number: str
    user: str
    product_name: str
    product_title: str
    entra_group: str | None
    justification: str
    duration: str
    opened_at: datetime


class AccessRequestStore:
    def __init__(self):
        self._items: dict[str, AccessRequest] = {}

    def create(self, product_name: str, product_title: str, justification: str, duration: str,
               entra_group: str | None) -> AccessRequest:
        number = f"REQ{10000 + len(self._items) + 1:07d}"
        request = AccessRequest(
            number=number, user=PERSONA, product_name=product_name, product_title=product_title,
            entra_group=entra_group, justification=justification, duration=duration,
            opened_at=datetime.now(),
        )
        self._items[number] = request
        return request

    def get(self, number: str) -> AccessRequest | None:
        return self._items.get(number)
