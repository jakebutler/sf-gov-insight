from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel


class MeetingItem(BaseModel):
    itemIndex: Optional[int] = None
    fileNumber: Optional[str] = None
    ver: Optional[str] = None
    agendaNumber: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    title: Optional[str] = None
    details: Optional[str] = None


class MeetingSchema(BaseModel):
    meetingName: Optional[str] = None
    meetingDate: Optional[str] = None
    meetingLocation: Optional[str] = None
    meetingItems: List[MeetingItem] = []
    agenda_text: Optional[str] = None
    minutes_text: Optional[str] = None
    transcript_text: Optional[str] = None
