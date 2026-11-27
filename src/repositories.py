from datetime import date, time

from database import Database
from models import (
    HealthcareProfessional,
    Patient,
    AvailabilitySlot,
    Appointment,
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
                    additional_notes
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                appointment.appointment_id,
                patient.patient_id,
                appointment.slot.slot_id,
                appointment.booking_channel,
                appointment.appointment_status,
                appointment.additional_notes,
            ))

            for resource in appointment.resources:
                self.connection.execute("""
                    INSERT INTO resources (
                        resource_id,
                        name,
                        resource_type
                    )
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(resource_id) DO NOTHING
                """, (
                    resource.resource_id,
                    resource.name,
                    resource.resource_type,
                ))

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
            )
            for row in rows
        ]