from datetime import date, time

from database import Database
from models import (
    HealthcareProfessional,
    Patient,
    AvailabilitySlot,
    Appointment,
    Referral,
    Resource,
)


class ProfessionalRepository:
    def __init__(self, database: Database):
        self.connection = database.connection

    def save(self, professional: HealthcareProfessional):
        self.connection.execute("""
            INSERT INTO professionals (
                professional_id,
                first_name,
                last_name,
                title,
                specialty
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(professional_id) DO UPDATE SET
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                title = excluded.title,
                specialty = excluded.specialty
        """, (
            professional.professional_id,
            professional.first_name,
            professional.last_name,
            professional.title,
            professional.specialty,
        ))

    def get_all(self) -> dict[str, HealthcareProfessional]:
        rows = self.connection.execute(
            "SELECT * FROM professionals"
        ).fetchall()

        return {
            row["professional_id"]: HealthcareProfessional(
                first_name=row["first_name"],
                last_name=row["last_name"],
                title=row["title"],
                specialty=row["specialty"],
                professional_id=row["professional_id"],
            )
            for row in rows
        }

    def get_or_create(
        self,
        professional: HealthcareProfessional
    ) -> HealthcareProfessional:

        professionals = self.get_all()

        if professional.professional_id in professionals:
            return professionals[professional.professional_id]

        def identity(p):
            return (
                p.first_name.strip().casefold(),
                p.last_name.strip().casefold(),
                p.title.strip().casefold(),
                p.specialty.strip().casefold(),
            )

        matches = [
            existing
            for existing in professionals.values()
            if identity(existing) == identity(professional)
        ]

        if len(matches) > 1:
            raise ValueError("Multiple matching professionals found.")

        if matches:
            return matches[0]

        self.save(professional)
        return professional


class AvailabilityRepository:
    def __init__(self, database: Database):
        self.connection = database.connection
        self.professional_repository = ProfessionalRepository(database)

    def save(self, slot: AvailabilitySlot) -> bool:
        return bool(self.save_many([slot]))

    def save_many(
        self,
        slots: list[AvailabilitySlot]
    ) -> list[AvailabilitySlot]:

        saved_slots = []

        with self.connection:
            for slot in slots:
                professional = (
                    self.professional_repository.get_or_create(
                        slot.professional
                    )
                )

                result = self.connection.execute("""
                    INSERT INTO availability_slots (
                        slot_id,
                        professional_id,
                        slot_date,
                        start_time,
                        end_time,
                        is_booked
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT (
                        professional_id,
                        slot_date,
                        start_time,
                        end_time
                    ) DO NOTHING
                """, (
                    slot.slot_id,
                    professional.professional_id,
                    slot.slot_date.isoformat(),
                    slot.start_time.isoformat(),
                    slot.end_time.isoformat(),
                    int(slot.is_booked),
                ))

                if result.rowcount == 1:
                    saved_slots.append((slot, professional))

        for slot, professional in saved_slots:
            slot.professional = professional

        return [slot for slot, _ in saved_slots]

    def get_all(self) -> list[AvailabilitySlot]:
        professionals = self.professional_repository.get_all()

        rows = self.connection.execute(
            "SELECT * FROM availability_slots"
        ).fetchall()

        return [
            AvailabilitySlot(
                professional=professionals[row["professional_id"]],
                slot_date=date.fromisoformat(row["slot_date"]),
                start_time=time.fromisoformat(row["start_time"]),
                end_time=time.fromisoformat(row["end_time"]),
                is_booked=bool(row["is_booked"]),
                slot_id=row["slot_id"],
            )
            for row in rows
        ]


class ResourceRepository:
    def __init__(self, database: Database):
        self.connection = database.connection

    def get_all(self) -> list[Resource]:
        rows = self.connection.execute("""
            SELECT *
            FROM resources
            ORDER BY resource_id
        """).fetchall()

        return [
            Resource(
                name=row["name"],
                resource_type=row["resource_type"],
                resource_id=row["resource_id"],
            )
            for row in rows
        ]


class AppointmentRepository:
    def __init__(self, database: Database):
        self.connection = database.connection

    def get_patient(self, patient_id: str) -> Patient | None:
        row = self.connection.execute("""
            SELECT *
            FROM patients
            WHERE patient_id = ?
        """, (patient_id,)).fetchone()

        if row is None:
            return None

        return Patient(
            full_name=row["full_name"],
            telephone=row["telephone"],
            ramq_no=row["ramq_no"],
            has_referral=bool(row["has_referral"]),
            patient_id=row["patient_id"],
        )

    def resolve_patient(self, patient: Patient) -> Patient:
        existing = self.get_patient(patient.patient_id)

        if existing is not None:
            return patient

        if patient.ramq_no:
            ramq_no = patient.ramq_no.replace(" ", "").upper()

            rows = self.connection.execute("""
                SELECT patient_id, full_name
                FROM patients
                WHERE UPPER(REPLACE(ramq_no, ' ', '')) = ?
            """, (ramq_no,)).fetchall()

            if len(rows) > 1:
                raise ValueError(
                    "Multiple patients have the same RAMQ number."
                )

            if rows:
                row = rows[0]

                if (
                    row["full_name"].strip().casefold()
                    != patient.full_name.strip().casefold()
                ):
                    raise ValueError(
                        "RAMQ number belongs to another patient."
                    )

                return Patient(
                    full_name=patient.full_name,
                    telephone=patient.telephone,
                    ramq_no=ramq_no,
                    has_referral=patient.has_referral,
                    patient_id=row["patient_id"],
                )

            patient.ramq_no = ramq_no

        return patient

    def save(self, appointment: Appointment):
        with self.connection:

            self.connection.execute("BEGIN IMMEDIATE")

            self.validate_booking(appointment)
        
            patient = self.resolve_patient(appointment.patient)

            self.connection.execute("""
                INSERT INTO patients (
                    patient_id,
                    full_name,
                    telephone,
                    ramq_no,
                    has_referral
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(patient_id) DO UPDATE SET
                    full_name = excluded.full_name,
                    telephone = excluded.telephone,
                    ramq_no = excluded.ramq_no,
                    has_referral = excluded.has_referral
            """, (
                patient.patient_id,
                patient.full_name,
                patient.telephone,
                patient.ramq_no,
                int(patient.has_referral),
            ))

            result = self.connection.execute("""
                UPDATE availability_slots
                SET is_booked = 1
                WHERE slot_id = ? AND is_booked = 0
            """, (appointment.slot.slot_id,))

            if result.rowcount != 1:
                raise ValueError(
                    "Selected slot does not exist or is already booked."
                )

            self.connection.execute("""
                INSERT INTO appointments (
                    appointment_id,
                    patient_id,
                    slot_id,
                    booking_channel,
                    appointment_status,
                    additional_notes,
                    referral_type
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                appointment.appointment_id,
                patient.patient_id,
                appointment.slot.slot_id,
                appointment.booking_channel,
                appointment.appointment_status,
                appointment.additional_notes,
                appointment.referral_type,
            ))

            for resource in appointment.resources:
                

                self.connection.execute("""
                    INSERT INTO appointment_resources (
                        appointment_id,
                        resource_id
                    )
                    VALUES (?, ?)
                """, (
                    appointment.appointment_id,
                    resource.resource_id,
                ))

        appointment.patient = patient
        appointment.slot.is_booked = True


    
    def validate_booking(self, appointment: Appointment):
        slot = appointment.slot

        stored_slot = self.connection.execute("""
            SELECT *
            FROM availability_slots
            WHERE slot_id = ?
        """, (slot.slot_id,)).fetchone()

        if stored_slot is None:
            raise ValueError("Availability slot not found.")

        if (
            stored_slot["professional_id"]
                != slot.professional.professional_id
            or stored_slot["slot_date"]
                != slot.slot_date.isoformat()
            or stored_slot["start_time"]
                != slot.start_time.isoformat()
            or stored_slot["end_time"]
                != slot.end_time.isoformat()
        ):
            raise ValueError("Appointment does not match availability.")

        if slot.start_time >= slot.end_time:
            raise ValueError(
                "Start time must be earlier than end time."
            )

        if stored_slot["is_booked"]:
            raise ValueError("Selected time slot is already booked.")

        professional_conflict = self.connection.execute("""
            SELECT a.appointment_id
            FROM appointments a
            JOIN availability_slots s
                ON a.slot_id = s.slot_id
            WHERE s.professional_id = ?
              AND s.slot_date = ?
              AND a.appointment_status != 'Cancelled'
              AND s.start_time < ?
              AND s.end_time > ?
        """, (
            slot.professional.professional_id,
            slot.slot_date.isoformat(),
            slot.end_time.isoformat(),
            slot.start_time.isoformat(),
        )).fetchone()

        if professional_conflict:
            raise ValueError(
                "Healthcare professional is already booked "
                "during this time."
            )

        resource_ids = set()

        for resource in appointment.resources:

            if resource.resource_id in resource_ids:
                raise ValueError("Duplicate resource selected.")

            resource_ids.add(resource.resource_id)

            existing_resource = self.connection.execute("""
                SELECT resource_id
                FROM resources
                WHERE resource_id = ?
            """, (resource.resource_id,)).fetchone()

            if existing_resource is None:
                raise ValueError("Selected resource does not exist.")

            resource_conflict = self.connection.execute("""
                SELECT a.appointment_id
                FROM appointment_resources ar
                JOIN appointments a
                    ON ar.appointment_id = a.appointment_id
                JOIN availability_slots s
                    ON a.slot_id = s.slot_id
                WHERE ar.resource_id = ?
                  AND s.slot_date = ?
                  AND a.appointment_status != 'Cancelled'
                  AND s.start_time < ?
                  AND s.end_time > ?
            """, (
                resource.resource_id,
                slot.slot_date.isoformat(),
                slot.end_time.isoformat(),
                slot.start_time.isoformat(),
            )).fetchone()

            if resource_conflict:
                raise ValueError(
                    f"Resource '{resource.name}' is already booked "
                    "during this time."
                )

    def update(self, appointment: Appointment):
        with self.connection:
            result = self.connection.execute("""
                UPDATE appointments
                SET appointment_status = ?,
                    additional_notes = ?
                WHERE appointment_id = ?
            """, (
                appointment.appointment_status,
                appointment.additional_notes,
                appointment.appointment_id,
            ))

            if result.rowcount != 1:
                raise ValueError("Appointment not found in database.")
    def get_all(
        self,
        slots: list[AvailabilitySlot]
    ) -> list[Appointment]:

        slots_by_id = {
            slot.slot_id: slot for slot in slots
        }

        patient_rows = self.connection.execute(
            "SELECT * FROM patients"
        ).fetchall()

        patients = {
            row["patient_id"]: Patient(
                full_name=row["full_name"],
                telephone=row["telephone"],
                ramq_no=row["ramq_no"],
                has_referral=bool(row["has_referral"]),
                patient_id=row["patient_id"],
            )
            for row in patient_rows
        }

        resource_rows = self.connection.execute("""
            SELECT ar.appointment_id,
                   r.resource_id,
                   r.name,
                   r.resource_type
            FROM appointment_resources ar
            JOIN resources r
                ON ar.resource_id = r.resource_id
        """).fetchall()

        resources_by_appointment = {}

        for row in resource_rows:
            resource = Resource(
                name=row["name"],
                resource_type=row["resource_type"],
                resource_id=row["resource_id"],
            )

            resources_by_appointment.setdefault(
                row["appointment_id"], []
            ).append(resource)

        rows = self.connection.execute(
            "SELECT * FROM appointments"
        ).fetchall()

        return [
            Appointment(
                patient=patients[row["patient_id"]],
                slot=slots_by_id[row["slot_id"]],
                booking_channel=row["booking_channel"],
                appointment_id=row["appointment_id"],
                appointment_status=row["appointment_status"],
                additional_notes=row["additional_notes"],
                resources=resources_by_appointment.get(
                    row["appointment_id"], []
                ),
                referral_type=row["referral_type"],
            )
            for row in rows
        ]


class ReferralRepository:
    def __init__(self, database: Database):
        self.connection = database.connection

    def save(self, referral: Referral):
        referring_professional = referral.referring_professional
        requested_professional = referral.requested_professional

        if referring_professional is None:
            raise ValueError("A referring professional is required.")

        with self.connection:
            patient = self.connection.execute("""
                SELECT patient_id
                FROM patients
                WHERE patient_id = ?
            """, (referral.patient.patient_id,)).fetchone()

            if patient is None:
                raise ValueError(
                    "Patient must be saved before its referral."
                )

            self.connection.execute("""
                INSERT INTO referrals (
                    referral_id,
                    patient_id,
                    referring_professional_id,
                    referring_professional_first_name,
                    referring_professional_last_name,
                    referring_professional_title,
                    referring_professional_specialty,
                    requested_specialty,
                    requested_professional_id,
                    requested_professional_first_name,
                    requested_professional_last_name,
                    requested_professional_title,
                    requested_professional_specialty,
                    referral_type,
                    clinical_reason,
                    priority,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                referral.referral_id,
                referral.patient.patient_id,
                referring_professional.professional_id,
                referring_professional.first_name,
                referring_professional.last_name,
                referring_professional.title,
                referring_professional.specialty,
                referral.requested_specialty,
                (
                    requested_professional.professional_id
                    if requested_professional is not None else None
                ),
                (
                    requested_professional.first_name
                    if requested_professional is not None else None
                ),
                (
                    requested_professional.last_name
                    if requested_professional is not None else None
                ),
                (
                    requested_professional.title
                    if requested_professional is not None else None
                ),
                (
                    requested_professional.specialty
                    if requested_professional is not None else None
                ),
                referral.referral_type,
                referral.clinical_reason,
                referral.priority,
                referral.status,
            ))

    @staticmethod
    def _from_row(row) -> Referral:
        referring_professional = HealthcareProfessional(
            first_name=row["referring_professional_first_name"],
            last_name=row["referring_professional_last_name"],
            title=row["referring_professional_title"],
            specialty=row["referring_professional_specialty"],
            professional_id=row["referring_professional_id"],
        )

        requested_professional = None
        if row["requested_professional_id"] is not None:
            requested_professional = HealthcareProfessional(
                first_name=row["requested_professional_first_name"],
                last_name=row["requested_professional_last_name"],
                title=row["requested_professional_title"],
                specialty=row["requested_professional_specialty"],
                professional_id=row["requested_professional_id"],
            )

        patient = Patient(
            full_name=row["patient_full_name"],
            telephone=row["patient_telephone"],
            ramq_no=row["patient_ramq_no"],
            has_referral=bool(row["patient_has_referral"]),
            patient_id=row["patient_id"],
        )

        return Referral(
            patient=patient,
            clinical_reason=row["clinical_reason"],
            priority=row["priority"],
            status=row["status"],
            referring_professional=referring_professional,
            requested_specialty=row["requested_specialty"],
            requested_professional=requested_professional,
            referral_id=row["referral_id"],
            referral_type=row["referral_type"],
        )

    def get_by_id(self, referral_id: str) -> Referral | None:
        row = self.connection.execute("""
            SELECT r.*,
                   p.full_name AS patient_full_name,
                   p.telephone AS patient_telephone,
                   p.ramq_no AS patient_ramq_no,
                   p.has_referral AS patient_has_referral
            FROM referrals r
            JOIN patients p
                ON p.patient_id = r.patient_id
            WHERE r.referral_id = ?
        """, (referral_id,)).fetchone()

        return self._from_row(row) if row is not None else None

    def get_all(self) -> list[Referral]:
        rows = self.connection.execute("""
            SELECT r.*,
                   p.full_name AS patient_full_name,
                   p.telephone AS patient_telephone,
                   p.ramq_no AS patient_ramq_no,
                   p.has_referral AS patient_has_referral
            FROM referrals r
            JOIN patients p
                ON p.patient_id = r.patient_id
            ORDER BY r.referral_id
        """).fetchall()

        return [self._from_row(row) for row in rows]