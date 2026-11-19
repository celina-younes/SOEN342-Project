from dataclasses import dataclass, field
from datetime import date, time
from typing import Optional
import uuid


@dataclass
class HealthcareProfessional:
    first_name: str
    last_name: str
    title: str
    specialty: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


@dataclass
class Patient:
    full_name: str
    telephone: str
    ramq_no: Optional[str] = None
    has_referral: bool = False
    patient_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class AvailabilitySlot:
    professional: HealthcareProfessional
    slot_date: date
    start_time: time
    end_time: time
    is_booked: bool = False
    slot_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def __str__(self) -> str:
        status = "BOOKED" if self.is_booked else "AVAILABLE"
        return (
            f"[{self.slot_id}] {self.slot_date} | "
            f"{self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')} | "
            f"{self.professional.title} {self.professional.full_name} "
            f"({self.professional.specialty}) [{status}]"
        )


@dataclass
class Appointment:
    patient: Patient
    slot: AvailabilitySlot
    booking_channel: str  # "WALK-IN" or "PHONE"
    appointment_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    appointment_status: str = "Confirmed"

    def str(self) -> str:
        return (
            f"Appt #{self.appointment_id} ({self.booking_channel}) -> "
            f"Patient: {self.patient.full_name} ({self.patient.telephone}) | "
            f"Prof: {self.slot.professional.full_name} on {self.slot.slot_date} "
            f"at {self.slot.start_time.strftime('%H:%M')}"
        )