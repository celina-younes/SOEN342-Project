from datetime import date, time, timedelta
from typing import List, Optional
from models import AvailabilitySlot, HealthcareProfessional


class AvailabilityService:
    def __init__(self, slots: List[AvailabilitySlot]):
        self.slots = slots

    def create_availability(
        self,
        professional: HealthcareProfessional,
        start_date: date,
        end_date: date,
        pattern: str,
        start_time: time,
        end_time: time,
        days_of_week: Optional[List[int]] = None,
        day_of_month: Optional[int] = None,
    ) -> List[AvailabilitySlot]:
        created_slots: List[AvailabilitySlot] = []
        current = start_date

        while current <= end_date:
            match = False
            if pattern.upper() == "WEEKLY" and days_of_week is not None:
                if current.weekday() in days_of_week:
                    match = True
            elif pattern.upper() == "MONTHLY" and day_of_month is not None:
                if current.day == day_of_month:
                    match = True

            if match:
                new_slot = AvailabilitySlot(
                    professional=professional,
                    slot_date=current,
                    start_time=start_time,
                    end_time=end_time,
                )
                self.slots.append(new_slot)
                created_slots.append(new_slot)

            current += timedelta(days=1)

        return created_slots

    def search_availability(
        self,
        specialty: Optional[str] = None,
        professional_name: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[AvailabilitySlot]:
        results = [s for s in self.slots if not s.is_booked]

        if specialty:
            results = [
                s for s in results
                if specialty.lower() in s.professional.specialty.lower()
            ]
        if professional_name:
            results = [
                s for s in results
                if professional_name.lower() in s.professional.full_name.lower()
            ]
        if start_date:
            results = [s for s in results if s.slot_date >= start_date]
        if end_date:
            results = [s for s in results if s.slot_date <= end_date]

        return sorted(results, key=lambda s: (s.slot_date, s.start_time))