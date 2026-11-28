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
    professional_id: str = field(
        default_factory=lambda: str(uuid.uuid4())
    )

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

8
@dataclass
class Referral:
    patient: Patient
    clinical_reason: str
    priority: str
    status: str = "Pending"
    referring_professional: Optional[HealthcareProfessional] = None
    requested_specialty: Optional[str] = None
    requested_professional: Optional[HealthcareProfessional] = None
    referral_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    referral_type: str = field(kw_only=True)

    def __post_init__(self):
        if not isinstance(self.referral_type, str) or not self.referral_type.strip():
            raise ValueError("A referral type is required.")

        if self.referring_professional is None:
            raise ValueError("A referring professional is required.")

        if (
            self.requested_professional is None
            and not (
                self.requested_specialty
                and self.requested_specialty.strip()
            )
        ):
            raise ValueError(
                "A requested specialty or requested professional is required."
            )


@dataclass
class AvailabilitySlot:
    professional: HealthcareProfessional
    slot_date: date
    start_time: time
    end_time: time
    is_booked: bool = False
    slot_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def overlaps(self, other: "AvailabilitySlot") -> bool:
        return (
            self.slot_date == other.slot_date
            and self.start_time < other.end_time
            and other.start_time < self.end_time
        )

    def __str__(self) -> str:
        status = "BOOKED" if self.is_booked else "AVAILABLE"
        return (
            f"[{self.slot_id}] {self.slot_date} | "
            f"{self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')} | "
            f"{self.professional.title} {self.professional.full_name} "
            f"({self.professional.specialty}) [{status}]"
        )

@dataclass
class Resource:
    name: str
    resource_type: str
    resource_id: str = field(
        default_factory=lambda: str(uuid.uuid4())
    )
    
@dataclass
class Appointment:
    patient: Patient
    slot: AvailabilitySlot
    booking_channel: str  # "WALK-IN" or "PHONE"
    appointment_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    appointment_status: str = "Confirmed"
    additional_notes: str = ""
    resources: list[Resource] = field(default_factory=list)
    referral_type: Optional[str] = None

    def close(self, additional_notes: str = ""):
            if self.appointment_status == "Completed":
                raise ValueError("Appointment is already closed.")

            if self.appointment_status == "Cancelled":
                raise ValueError("Cannot close a cancelled appointment.")

            self.additional_notes = additional_notes.strip()
            self.appointment_status = "Completed"
            
    def __str__(self) -> str:
        return (
            f"Appt #{self.appointment_id} ({self.booking_channel}) -> "
            f"Patient: {self.patient.full_name} ({self.patient.telephone}) | "
            f"Prof: {self.slot.professional.full_name} on {self.slot.slot_date} "
            f"at {self.slot.start_time.strftime('%H:%M')}"
        )
