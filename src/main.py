from datetime import datetime
from models import Appointment, AvailabilitySlot, HealthcareProfessional
from availability_service import AvailabilityService


def parse_date(prompt: str):
    val = input(prompt).strip()
    return datetime.strptime(val, "%Y-%m-%d").date() if val else None


def parse_time(prompt: str):
    val = input(prompt).strip()
    return datetime.strptime(val, "%H:%M").time()


def main():
    slots: list[AvailabilitySlot] = []
    appointments: list[Appointment] = []

    avail_service = AvailabilityService(slots)

    while True:
        print("\n Appointment Tracking System")
        print("1. Make Availability for Healthcare Professional")
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

            elif choice == "0":
                break
            else:
                print("Invalid option.")

        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
