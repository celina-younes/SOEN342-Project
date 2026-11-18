import csv
from typing import List
from models import (
    Appointment,
    AvailabilitySlot,
    Patient,
)


class BookingAndCsvService:
    def __init__(
        self,
        slots: List[AvailabilitySlot],
        appointments: List[Appointment],
    ):
        self.slots = slots
        self.appointments = appointments

    def book_appointment(
        self,
        slot_id: str,
        patient: Patient,
        booking_channel: str = "WALK-IN",
        requires_referral: bool = False,
    ) -> Appointment:
        target_slot = next((s for s in self.slots if s.slot_id == slot_id), None)

        if not target_slot:
            raise ValueError(f"Slot ID '{slot_id}' not found.")
        if target_slot.is_booked:
            raise ValueError("Selected time slot is already booked.")
        if requires_referral and not patient.has_referral:
            raise ValueError(
                f"Specialty '{target_slot.professional.specialty}' requires a medical referral."
            )

        target_slot.is_booked = True
        appointment = Appointment(
            patient=patient,
            slot=target_slot,
            booking_channel=booking_channel.upper(),
        )
        self.appointments.append(appointment)
        return appointment

    def export_availabilities_to_csv(self, file_path: str) -> int:
        headers = [
            "First Name",
            "Last Name",
            "Title",
            "Specialty",
            "Date",
            "Start",
            "End",
        ]
        with open(file_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for slot in self.slots:
                writer.writerow([
                    slot.professional.first_name,
                    slot.professional.last_name,
                    slot.professional.title,
                    slot.professional.specialty,
                    slot.slot_date.strftime("%Y-%m-%d"),
                    slot.start_time.strftime("%H:%M"),
                    slot.end_time.strftime("%H:%M"),
                ])
        return len(self.slots)