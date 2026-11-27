
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class CalendarEvent:
    event_id: str
    start: datetime
    end: datetime
    summary: str


class ICalendarGateway:

    @staticmethod
    def escape_text(value: str) -> str:
        return (
            value.replace("\\", "\\\\")
            .replace("\r\n", "\\n")
            .replace("\r", "\\n")
            .replace("\n", "\\n")
            .replace(";", "\\;")
            .replace(",", "\\,")
        )

    @staticmethod
    def fold_line(line: str) -> str:
        parts = []
        current = ""

        for character in line:
            candidate = current + character

            if len(candidate.encode("utf-8")) > 75:
                parts.append(current)
                current = " " + character
            else:
                current = candidate

        parts.append(current)

        return "\r\n".join(parts)

    def export(
        self,
        events: list[CalendarEvent],
        file_path: str
    ) -> int:

        path = Path(file_path)

        if path.suffix.lower() != ".ics":
            raise ValueError(
                "Calendar file must use the .ics extension."
            )

        timestamp = datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ"
        )

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//SOEN342//Appointment Tracking System//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
        ]

        for event in events:
            if event.start >= event.end:
                raise ValueError("Invalid calendar event interval.")

            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{event.event_id}@soen342",
                f"DTSTAMP:{timestamp}",
                f"DTSTART:{event.start:%Y%m%dT%H%M%S}",
                f"DTEND:{event.end:%Y%m%dT%H%M%S}",
                f"SUMMARY:{self.escape_text(event.summary)}",
                "END:VEVENT",
            ])

        lines.append("END:VCALENDAR")

        content = "\r\n".join(
            self.fold_line(line) for line in lines
        ) + "\r\n"

        path.write_bytes(content.encode("utf-8"))

        return len(events)
