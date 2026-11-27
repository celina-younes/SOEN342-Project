
from datetime import date, datetime

from models import Appointment
from ical_gateway import ICalendarGateway, CalendarEvent


class CalendarExportService:

    def __init__(
        self,
        appointments: list[Appointment],
        gateway: ICalendarGateway,
    ):
        self.appointments = appointments
        self.gateway = gateway

    def export_appointments(
        self,
        filter_type: str,
        filter_value: str,
        file_path: str,
        start_date: date | None = None,
    ) -> int:

        filter_type = filter_type.strip().lower()
        filter_value = filter_value.strip()

        if filter_type not in (
            "professional",
            "patient",
            "referral"
        ):
            raise ValueError("Invalid calendar filter.")

        if not filter_value:
            raise ValueError("Calendar filter value is required.")

        if start_date is None:
            start_date = date.today()

        matches = []

        for appointment in self.appointments:

            if appointment.appointment_status == "Cancelled":
                continue

            if appointment.slot.slot_date < start_date:
                continue

            if filter_type == "professional":
                matches_filter = (
                    appointment.slot.professional.professional_id
                    == filter_value
                )

            elif filter_type == "patient":
                matches_filter = (
                    appointment.patient.patient_id
                    == filter_value
                )

            else:
                matches_filter = (
                    appointment.referral_type is not None
                    and appointment.referral_type.strip().casefold()
                        == filter_value.casefold()
                )

            if matches_filter:
                matches.append(appointment)

        matches.sort(
            key=lambda appointment: (
                appointment.slot.slot_date,
                appointment.slot.start_time,
            )
        )

        events = []

        for appointment in matches:
            slot = appointment.slot

            start = datetime.combine(
                slot.slot_date,
                slot.start_time
            )

            end = datetime.combine(
                slot.slot_date,
                slot.end_time
            )

            if filter_type == "patient":
                summary = (
                    f"Appointment with "
                    f"{slot.professional.title} "
                    f"{slot.professional.full_name}"
                )
            else:
                summary = "Clinic appointment"

            events.append(
                CalendarEvent(
                    event_id=appointment.appointment_id,
                    start=start,
                    end=end,
                    summary=summary,
                )
            )

        return self.gateway.export(events, file_path)
