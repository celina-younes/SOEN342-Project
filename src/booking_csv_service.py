import csv
from datetime import datetime
from typing import List, TypedDict
from models import (
    Appointment,
    AvailabilitySlot,
    HealthcareProfessional,
    Patient,
)
from repositories import AvailabilityRepository, AppointmentRepository

class ImportResult(TypedDict):
    imported: int
    duplicates_skipped: int
    invalid_rows: int
    errors: List[str]


class BookingAndCsvService:
    def __init__(
        self,
        slots: List[AvailabilitySlot],
        appointments: List[Appointment],
        availability_repository: AvailabilityRepository,
        appointment_repository: AppointmentRepository,
    ):
        self.slots = slots
        self.appointments = appointments
        self.availability_repository = availability_repository
        self.appointment_repository = appointment_repository

    def import_availabilities_from_csv(self, file_path: str) -> ImportResult:
        result: ImportResult = {
            "imported": 0,
            "duplicates_skipped": 0,
            "invalid_rows": 0,
            "errors": [],
        }
        headers = [
            "First Name",
            "Last Name",
            "Title",
            "Specialty",
            "Date",
            "Start",
            "End",
        ]
        errors = result["errors"]
        professional_by_key = {
            (
                slot.professional.first_name,
                slot.professional.last_name,
                slot.professional.title,
                slot.professional.specialty,
            ): slot.professional
            for slot in self.slots
        }
        existing_slots = {
            (
                slot.professional.first_name,
                slot.professional.last_name,
                slot.professional.title,
                slot.professional.specialty,
                slot.slot_date,
                slot.start_time,
                slot.end_time,
            )
            for slot in self.slots
        }

        try:
            with open(file_path, mode="r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f, strict=True)
                if reader.fieldnames != headers:
                    errors.append(
                        f"CSV headers must be exactly {headers}; found {reader.fieldnames}."
                    )
                    return result

                for row_number, row in enumerate(reader, start=2):
                    try:
                        if None in row:
                            raise ValueError("Row contains more columns than the header.")

                        values = {}
                        for header in headers:
                            value = row.get(header)
                            if value is None or not value.strip():
                                raise ValueError(f"Missing value for '{header}'.")
                            values[header] = value.strip()

                        slot_date = datetime.strptime(
                            values["Date"], "%Y-%m-%d"
                        ).date()
                        if slot_date.strftime("%Y-%m-%d") != values["Date"]:
                            raise ValueError("Date must use YYYY-MM-DD.")
                        start_time = datetime.strptime(
                            values["Start"], "%H:%M"
                        ).time()
                        if start_time.strftime("%H:%M") != values["Start"]:
                            raise ValueError("Start time must use HH:MM.")
                        end_time = datetime.strptime(
                            values["End"], "%H:%M"
                        ).time()
                        if end_time.strftime("%H:%M") != values["End"]:
                            raise ValueError("End time must use HH:MM.")
                        if end_time <= start_time:
                            raise ValueError("End time must be later than start time.")

                        professional_key = (
                            values["First Name"],
                            values["Last Name"],
                            values["Title"],
                            values["Specialty"],
                        )
                        slot_key = professional_key + (
                            slot_date,
                            start_time,
                            end_time,
                        )
                        if slot_key in existing_slots:
                            result["duplicates_skipped"] += 1
                            continue

                        professional = professional_by_key.get(professional_key)
                        if professional is None:
                            professional = HealthcareProfessional(*professional_key)
                            professional_by_key[professional_key] = professional

                        new_slot = AvailabilitySlot(
                            professional=professional,
                            slot_date=slot_date,
                            start_time=start_time,
                            end_time=end_time,
                        )

                        if self.availability_repository.save(new_slot):
                            self.slots.append(new_slot)
                            existing_slots.add(slot_key)
                            result["imported"] += 1
                        else:
                            result["duplicates_skipped"] += 1
                    except (TypeError, ValueError) as error:
                        result["invalid_rows"] += 1
                        errors.append(f"Row {row_number}: {error}")
        except csv.Error as error:
            result["invalid_rows"] += 1
            errors.append(f"Malformed CSV file '{file_path}': {error}")
        except (OSError, UnicodeError) as error:
            errors.append(f"Unable to read CSV file '{file_path}': {error}")

        return result

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
        booking_channel = booking_channel.strip().upper()

        if booking_channel not in ("WALK-IN", "PHONE"):
            raise ValueError("Invalid booking channel.")

        appointment = Appointment(
            patient=patient,
            slot=target_slot,
            booking_channel=booking_channel.upper(),
        )
        self.appointment_repository.save(appointment)
        self.appointments.append(appointment)
        return appointment
    def close_appointment(
        self,
        appointment_id: str,
        additional_notes: str = "",
    ) -> Appointment:

        appointment = next(
            (
                a for a in self.appointments
                if a.appointment_id == appointment_id
            ),
            None
        )

        if appointment is None:
            raise ValueError("Appointment not found.")

        previous_status = appointment.appointment_status
        previous_notes = appointment.additional_notes

        appointment.close(additional_notes)

        try:
            self.appointment_repository.update(appointment)
        except Exception:
            appointment.appointment_status = previous_status
            appointment.additional_notes = previous_notes
            raise

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