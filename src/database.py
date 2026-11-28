import sqlite3
from pathlib import Path


class Database:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = (
                Path(__file__).resolve().parent.parent
                / "data"
                / "appointments.db"
            )

        self.connection = sqlite3.connect(db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    def initialize(self):
        with self.connection:
            self.connection.executescript("""
                CREATE TABLE IF NOT EXISTS professionals (
                    professional_id TEXT PRIMARY KEY,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    specialty TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS patients (
                    patient_id TEXT PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    telephone TEXT NOT NULL,
                    ramq_no TEXT,
                    has_referral INTEGER NOT NULL DEFAULT 0
                        CHECK (has_referral IN (0, 1))
                );

                CREATE TABLE IF NOT EXISTS referrals (
                    referral_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    referring_professional_id TEXT NOT NULL,
                    referring_professional_first_name TEXT NOT NULL,
                    referring_professional_last_name TEXT NOT NULL,
                    referring_professional_title TEXT NOT NULL,
                    referring_professional_specialty TEXT NOT NULL,
                    requested_specialty TEXT,
                    requested_professional_id TEXT,
                    requested_professional_first_name TEXT,
                    requested_professional_last_name TEXT,
                    requested_professional_title TEXT,
                    requested_professional_specialty TEXT,
                    referral_type TEXT NOT NULL
                        CHECK (length(trim(referral_type)) > 0),
                    clinical_reason TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Pending',

                    FOREIGN KEY (patient_id)
                        REFERENCES patients(patient_id),

                    CHECK (
                        (
                            requested_specialty IS NOT NULL
                            AND length(trim(requested_specialty)) > 0
                        )
                        OR requested_professional_id IS NOT NULL
                    ),

                    CHECK (
                        (
                            requested_professional_id IS NULL
                            AND requested_professional_first_name IS NULL
                            AND requested_professional_last_name IS NULL
                            AND requested_professional_title IS NULL
                            AND requested_professional_specialty IS NULL
                        )
                        OR
                        (
                            requested_professional_id IS NOT NULL
                            AND requested_professional_first_name IS NOT NULL
                            AND requested_professional_last_name IS NOT NULL
                            AND requested_professional_title IS NOT NULL
                            AND requested_professional_specialty IS NOT NULL
                        )
                    )
                );

                CREATE TABLE IF NOT EXISTS availability_slots (
                    slot_id TEXT PRIMARY KEY,
                    professional_id TEXT NOT NULL,
                    slot_date TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    is_booked INTEGER NOT NULL DEFAULT 0
                        CHECK (is_booked IN (0, 1)),

                    CHECK (start_time < end_time),

                    FOREIGN KEY (professional_id)
                        REFERENCES professionals(professional_id),

                    UNIQUE (
                        professional_id,
                        slot_date,
                        start_time,
                        end_time
                    )
                );

                CREATE TABLE IF NOT EXISTS appointments (
                    appointment_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    slot_id TEXT NOT NULL,
                    booking_channel TEXT NOT NULL
                        CHECK (booking_channel IN ('WALK-IN', 'PHONE')),
                    appointment_status TEXT NOT NULL
                        DEFAULT 'Confirmed',
                    additional_notes TEXT NOT NULL DEFAULT '',
                    referral_type TEXT,

                    FOREIGN KEY (patient_id)
                        REFERENCES patients(patient_id),

                    FOREIGN KEY (slot_id)
                        REFERENCES availability_slots(slot_id)
                );

                CREATE TABLE IF NOT EXISTS resources (
                    resource_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    resource_type TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS appointment_resources (
                    appointment_id TEXT NOT NULL,
                    resource_id TEXT NOT NULL,

                    PRIMARY KEY (appointment_id, resource_id),

                    FOREIGN KEY (appointment_id)
                        REFERENCES appointments(appointment_id),

                    FOREIGN KEY (resource_id)
                        REFERENCES resources(resource_id)
                );
            """)

            columns = {
                row["name"]
                for row in self.connection.execute(
                    "PRAGMA table_info(appointments)"
                )
            }

            if "referral_type" not in columns:
                self.connection.execute("""
                    ALTER TABLE appointments
                    ADD COLUMN referral_type TEXT
                """)

            self.connection.executemany("""
                INSERT INTO resources (
                    resource_id,
                    name,
                    resource_type
                )
                VALUES (?, ?, ?)
                ON CONFLICT(resource_id) DO NOTHING
            """, [
                ("R001", "Examination Room 1", "ROOM"),
                ("R002", "Examination Room 2", "ROOM"),
                ("R003", "Ultrasound Machine", "EQUIPMENT"),
                ("R004", "Assisting Nurse", "HUMAN"),
            ])

    def close(self):
        self.connection.close()