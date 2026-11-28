from datetime import datetime
from models import (
    Appointment,
    AvailabilitySlot,
    HealthcareProfessional,
    Patient,
    Referral,
)
from availability_service import AvailabilityService
from booking_csv_service import BookingAndCsvService
from database import Database
from repositories import (
    AvailabilityRepository,
    AppointmentRepository,
    ProfessionalRepository,
    ReferralRepository,
    ResourceRepository,
)
from ical_gateway import ICalendarGateway
from calendar_export_service import CalendarExportService

def parse_date(prompt: str):
    val = input(prompt).strip()
    return datetime.strptime(val, "%Y-%m-%d").date() if val else None


def parse_time(prompt: str):
    val = input(prompt).strip()
    return datetime.strptime(val, "%H:%M").time()


class ReferralInputCancelled(Exception):
    pass


def prompt_referral_input(prompt: str) -> str:
    try:
        value = input(f"{prompt} (type 'cancel' to return to the menu): ").strip()
    except (EOFError, KeyboardInterrupt):
        raise ReferralInputCancelled from None

    if value.casefold() == "cancel":
        raise ReferralInputCancelled
    if not value:
        raise ValueError(f"{prompt} is required.")

    return value


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
    professional_repository = ProfessionalRepository(database)
    referral_repository = ReferralRepository(database)
    resource_repository = ResourceRepository(database)

    slots = availability_repository.get_all()
    appointments = appointment_repository.get_all(slots)

    avail_service = AvailabilityService(
        slots,
        availability_repository,
        appointments
    )

    booking_csv_service = BookingAndCsvService(
        slots,
        appointments,
        availability_repository,
        appointment_repository
    )

    calendar_gateway = ICalendarGateway()

    calendar_service = CalendarExportService(
        appointments,
        calendar_gateway
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
        print("8. Export Appointments to iCalendar")
        print("9. Process Medical Referral")
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

                
                req_ref = input(
                    "Does this service require a referral? (y/n): "
                ).strip().lower() == "y"

                referral_type = None

                if patient.has_referral:
                    referral_type = input(
                        "Referral type (Enter to skip): "
                    ).strip() or None

                channel = input(
                    "Booking channel (WALK-IN / PHONE): "
                ).strip().upper() or "WALK-IN"

                available_resources = resource_repository.get_all()

                print("\nResource Catalog:")

                for resource in available_resources:
                    print(
                        f"{resource.resource_id}: "
                        f"{resource.name} "
                        f"({resource.resource_type})"
                    )

                raw_resources = input(
                    "Required resource IDs "
                    "(comma-separated, Enter for none): "
                ).strip()

                resources_by_id = {
                    resource.resource_id: resource
                    for resource in available_resources
                }

                selected_resources = []

                if raw_resources:
                    resource_ids = [
                        value.strip().upper()
                        for value in raw_resources.split(",")
                    ]

                    for resource_id in resource_ids:

                        if resource_id not in resources_by_id:
                            raise ValueError(
                                f"Unknown resource ID: {resource_id}"
                            )

                        selected_resources.append(
                            resources_by_id[resource_id]
                        )

                appt = booking_csv_service.book_appointment(
                    slot_id,
                    patient,
                    channel,
                    req_ref,
                    resources=selected_resources,
                    referral_type=referral_type
                )

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
                if appt.resources:
                    print("  Resources:")

                    for resource in appt.resources:
                        print(f"    - {resource.name}")

                if appt.referral_type:
                    print(f"  Referral type: {appt.referral_type}")

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
                        if appointment.resources:
                            print("  Resources:")

                            for resource in appointment.resources:
                                print(f"    - {resource.name}")

                        if appointment.referral_type:
                            print(
                                f"  Referral type: "
                                f"{appointment.referral_type}"
                            )
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

           
            elif choice == "8":

                print("\nExport appointments by:")
                print("1. Healthcare Professional")
                print("2. Patient")
                print("3. Referral Type")

                export_choice = input(
                    "Select filter: "
                ).strip()

                if export_choice == "1":
                    filter_type = "professional"

                    professionals = professional_repository.get_all()

                    print("\nHealthcare Professionals:")

                    for professional in professionals.values():
                        print(
                            f"{professional.professional_id}: "
                            f"{professional.title} "
                            f"{professional.full_name}"
                        )

                    filter_value = input(
                        "Enter Professional ID: "
                    ).strip()

                    if filter_value not in professionals:
                        raise ValueError("Professional not found.")

                elif export_choice == "2":
                    filter_type = "patient"

                    patients = {
                        appointment.patient.patient_id:
                            appointment.patient
                        for appointment in appointments
                    }

                    print("\nPatients:")

                    for patient in patients.values():
                        print(
                            f"{patient.patient_id}: "
                            f"{patient.full_name}"
                        )

                    filter_value = input(
                        "Enter Patient ID: "
                    ).strip()

                    if filter_value not in patients:
                        raise ValueError("Patient not found.")

                elif export_choice == "3":
                    filter_type = "referral"

                    referral_types = sorted({
                        appointment.referral_type
                        for appointment in appointments
                        if appointment.referral_type
                    })

                    print("\nReferral types:")

                    for referral_type in referral_types:
                        print(referral_type)

                    filter_value = input(
                        "Enter Referral Type: "
                    ).strip()

                else:
                    raise ValueError("Invalid export filter.")

                start_date = parse_date(
                    "Start Date YYYY-MM-DD (Enter for today): "
                )

                file_path = input(
                    "Output filename "
                    "(default: appointments.ics): "
                ).strip() or "appointments.ics"

                count = calendar_service.export_appointments(
                    filter_type,
                    filter_value,
                    file_path,
                    start_date
                )

                print(
                    f"Exported {count} appointment(s) "
                    f"to '{file_path}'."
                )

            elif choice == "9":
                try:
                    patient_rows = database.connection.execute("""
                        SELECT patient_id, full_name, telephone
                        FROM patients
                        ORDER BY full_name, patient_id
                    """).fetchall()

                    if not patient_rows:
                        raise ValueError(
                            "No existing patients are available. "
                            "Create a patient through the booking workflow first."
                        )

                    print("\nPatients:")
                    for row in patient_rows:
                        print(
                            f"{row['patient_id']}: {row['full_name']} "
                            f"({row['telephone']})"
                        )

                    patient_id = prompt_referral_input("Patient ID")
                    patient = appointment_repository.get_patient(patient_id)
                    if patient is None:
                        raise ValueError("Patient ID not found.")

                    professionals = professional_repository.get_all()
                    if professionals:
                        print("\nLocal Healthcare Professionals:")
                        for professional in professionals.values():
                            print(
                                f"{professional.professional_id}: "
                                f"{professional.title} "
                                f"{professional.full_name} "
                                f"({professional.specialty})"
                            )
                    else:
                        print(
                            "\nNo local healthcare professionals found. "
                            "You can enter an external referring professional."
                        )

                    referrer_type = prompt_referral_input(
                        "Referring professional: 1 for local, 2 for external"
                    )
                    if referrer_type == "1":
                        if not professionals:
                            raise ValueError(
                                "No local healthcare professionals are available."
                            )

                        referrer_id = prompt_referral_input(
                            "Referring professional ID"
                        )
                        referring_professional = professionals.get(referrer_id)
                        if referring_professional is None:
                            raise ValueError(
                                "Referring professional ID not found."
                            )
                    elif referrer_type == "2":
                        first_name = prompt_referral_input(
                            "External professional first name"
                        )
                        last_name = prompt_referral_input(
                            "External professional last name"
                        )
                        title = prompt_referral_input(
                            "External professional title"
                        )
                        specialty = prompt_referral_input(
                            "External professional specialty"
                        )
                        referring_professional = HealthcareProfessional(
                            first_name,
                            last_name,
                            title,
                            specialty,
                        )
                    else:
                        raise ValueError(
                            "Choose 1 for a local or 2 for an external professional."
                        )

                    target_type = prompt_referral_input(
                        "Requested target: 1 for specialty, "
                        "2 for professional, 3 for both"
                    )
                    requested_specialty = None
                    requested_professional = None

                    if target_type in ("1", "3"):
                        requested_specialty = prompt_referral_input(
                            "Requested specialty"
                        )

                    if target_type in ("2", "3"):
                        if not professionals:
                            raise ValueError(
                                "No local healthcare professionals are available "
                                "to select as the requested professional."
                            )

                        print("\nRequested Professionals:")
                        for professional in professionals.values():
                            print(
                                f"{professional.professional_id}: "
                                f"{professional.title} "
                                f"{professional.full_name} "
                                f"({professional.specialty})"
                            )

                        requested_professional_id = prompt_referral_input(
                            "Requested professional ID"
                        )
                        requested_professional = professionals.get(
                            requested_professional_id
                        )
                        if requested_professional is None:
                            raise ValueError(
                                "Requested professional ID not found."
                            )
                    elif target_type != "1":
                        raise ValueError(
                            "Choose 1 for specialty, 2 for professional, "
                            "or 3 for both."
                        )

                    referral_type = prompt_referral_input("Referral type")
                    clinical_reason = prompt_referral_input("Clinical reason")
                    priority = prompt_referral_input("Priority")

                    referral = Referral(
                        patient=patient,
                        referring_professional=referring_professional,
                        requested_specialty=requested_specialty,
                        requested_professional=requested_professional,
                        referral_type=referral_type,
                        clinical_reason=clinical_reason,
                        priority=priority,
                        status="Pending",
                    )
                    referral_repository.save(referral)

                    print("\nReferral created successfully.")
                    print(f"Referral ID: {referral.referral_id}")
                    print(f"Status: {referral.status}")
                except ReferralInputCancelled:
                    print("Referral entry cancelled; no referral was saved.")
 
            elif choice == "0":
                break
            else:
                print("Invalid option.")

        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
