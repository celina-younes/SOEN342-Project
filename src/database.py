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

    def close(self):
        self.connection.close()