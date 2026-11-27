from datetime import datetime
from models import Appointment, AvailabilitySlot, HealthcareProfessional, Patient
from availability_service import AvailabilityService
from booking_csv_service import BookingAndCsvService
from database import Database
from repositories import (
    AvailabilityRepository,
    AppointmentRepository,
)

def parse_date(prompt: str):
    val = input(prompt).strip()
    return datetime.strptime(val, "%Y-%m-%d").date() if val else None


def parse_time(prompt: str):
    val = input(prompt).strip()
    return datetime.strptime(val, "%H:%M").time()


def main():
    database = Database()

    try:
        database.initialize()
        run_application(database)
    finally:
        database.close()


def run_application(database: Database):
    availability_repository = AvailabilityRepository(database)
    appointment_repository = AppointmentRepository(database)

    slots = availability_repository.get_all()
    appointments = appointment_repository.get_all(slots)

    avail_service = AvailabilityService(
        slots,
        availability_repository
    )

    booking_csv_service = BookingAndCsvService(
        slots,
        appointments,
        availability_repository,
        appointment_repository
    )
    while True:
        print("\n === Appointment Tracking System ===")
        print("1. Make Availability for Healthcare Professional")
        print("2. Search for Availability")
        print("3. Book an Appointment")
        print("4. Export Availabilities to CSV")
        print("5. View Booked Appointments")
        print("6. Import Professional Availability from CSV")
        print("7. Close an Appointment")
        print("0. Exit")

        choice = input("Select an option: ").strip()

        try:
            if choice == "1":
                fname = input("First Name: ").strip()
                lname = input("Last Name: ").strip()
                title = input("Title: ").strip()
                spec = input("Specialty: ").strip()
                prof = HealthcareProfessional(fname, lname, title, spec)

                s_date = parse_date("Start Date (YYYY-MM-DD): ")
                e_date = parse_date("End Date (YYYY-MM-DD): ")
                pattern = input("Pattern (WEEKLY / MONTHLY): ").strip().upper()

                days_of_week = None
                day_of_month = None
                if pattern == "WEEKLY":
                    raw_days = input("Days of week (0=Mon..6=Sun, comma-separated, e.g. 0,2): ")
                    days_of_week = [int(d.strip()) for d in raw_days.split(",")]
                elif pattern == "MONTHLY":
                    day_of_month = int(input("Day of month (1-31): ").strip())

                s_time = parse_time("Start Time (HH:MM): ")
                e_time = parse_time("End Time (HH:MM): ")

                created = avail_service.create_availability(
                    prof, s_date, e_date, pattern, s_time, e_time, days_of_week, day_of_month
                )
                print(f"Created {len(created)} availability slot(s).")
                
            elif choice == "2":
                spec = input("Filter by Specialty (Enter to skip): ").strip() or None
                name = input("Filter by Professional Name (Enter to skip): ").strip() or None
                s_date = parse_date("From Date YYYY-MM-DD (Enter to skip): ")
                e_date = parse_date("To Date YYYY-MM-DD (Enter to skip): ")

                matches = avail_service.search_availability(spec, name, s_date, e_date)
                if not matches:
                    print("No available slots found.")
                else:
                    for s in matches:
                        print(s)

            elif choice == "3":
                slot_id = input("Enter Slot ID to book: ").strip()
                patient_id = input(
                    "Existing Patient ID (Enter for new patient): "
                ).strip()
                if patient_id:
                    patient = appointment_repository.get_patient(
                        patient_id
                    )

                    if patient is None:
                        raise ValueError("Patient ID not found.")

                else:
                    p_name = input(
                        "Patient Full Name: "
                    ).strip()

                    p_phone = input(
                        "Patient Telephone: "
                    ).strip()

                    p_ramq = input(
                        "RAMQ No. (Enter if uninsured): "
                    ).strip() or None

                    if not p_name or not p_phone:
                        raise ValueError(
                            "Patient name and telephone are required."
                        )
                    has_ref = input("Does patient have a referral? (y/n): ").strip().lower() == "y"
                    patient = Patient(p_name, p_phone, p_ramq, has_ref)

                req_ref = input("Does this service require a referral? (y/n): ").strip().lower() == "y"
                channel = input("Booking channel (WALK-IN / PHONE): ").strip().upper() or "WALK-IN"
                appt = booking_csv_service.book_appointment(slot_id, patient, channel, req_ref)
                slot = appt.slot
                professional = slot.professional
                print("\nAppointment booked successfully:")
                print(f"Appointment ID: {appt.appointment_id}")
                print(f"  Patient ID: {appt.patient.patient_id}")
                print(
                    f"  Patient: {appt.patient.full_name} "
                    f"({appt.patient.telephone})"
                )
                print(
                    f"  Professional: {professional.title} "
                    f"{professional.full_name}"
                )
                print(f"  Specialty: {professional.specialty}")
                print(f"  Date: {slot.slot_date:%Y-%m-%d}")
                print(
                    f"  Time: {slot.start_time:%H:%M} - "
                    f"{slot.end_time:%H:%M}"
                )
                print(f"  Booking channel: {appt.booking_channel}")
                print(f"  Slot ID: {slot.slot_id}")

            elif choice == "4":
                path = input("Output CSV filename (default: availabilities_export.csv): ").strip()
                path = path or "availabilities_export.csv"
                count = booking_csv_service.export_availabilities_to_csv(path)
                print(f"Exported {count} availability record(s) to '{path}'.")

            elif choice == "5":
                if not appointments:
                    print("No appointments booked yet.")
                else:
                    print("\nBooked Appointments:")
                    for appointment in appointments:
                        slot = appointment.slot
                        professional = slot.professional
                        print(f"\nAppointment ID: {appointment.appointment_id}")
                        print(f"  Patient ID: {appointment.patient.patient_id}")
                        print(f"  Status: {appointment.appointment_status}")
                        print(f"  Additional notes: {appointment.additional_notes}")
                        print(
                            f"  Patient: {appointment.patient.full_name} "
                            f"({appointment.patient.telephone})"
                        )
                        print(
                            f"  Professional: {professional.title} "
                            f"{professional.full_name}"
                        )
                        print(f"  Specialty: {professional.specialty}")
                        print(f"  Date: {slot.slot_date:%Y-%m-%d}")
                        print(
                            f"  Time: {slot.start_time:%H:%M} - "
                            f"{slot.end_time:%H:%M}"
                        )
                        print(f"  Booking channel: {appointment.booking_channel}")
                        print(f"  Slot ID: {slot.slot_id}")
                input("\nPress Enter to return to the menu...")

            elif choice == "6":
                path = input("Input CSV filename: ").strip()
                result = booking_csv_service.import_availabilities_from_csv(path)
                print(f"Successfully imported slots: {result['imported']}")
                print(f"Duplicate slots skipped: {result['duplicates_skipped']}")
                print(f"Invalid rows rejected: {result['invalid_rows']}")
                if result["errors"]:
                    print("Import errors:")
                    for error in result["errors"]:
                        print(f"- {error}")
            elif choice == "7":
                appointment_id = input(
                    "Enter Appointment ID: "
                ).strip()

                additional_notes = input(
                    "Additional notes (Enter to skip): "
                ).strip()

                appointment = booking_csv_service.close_appointment(
                    appointment_id,
                    additional_notes
                )

                print("\nAppointment closed successfully.")
                print(f"Appointment ID: {appointment.appointment_id}")
                print(f"Status: {appointment.appointment_status}")
                print(f"Additional notes: {appointment.additional_notes}")
            elif choice == "0":
                break
            else:
                print("Invalid option.")

        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
