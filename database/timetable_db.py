#timtable_db.py
import sqlite3
import os
from datetime import datetime


class TimetableDatabaseManager:
    def __init__(self, db_name="timetable.db"):
        self.db_path = db_name
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def _normalize_project_id(self, project_id: str = None) -> str:
        cleaned = str(project_id or "").strip()
        return cleaned if cleaned else "project-1"

    def _ensure_column(self, cursor, table_name: str, column_name: str, column_sql: str):
        cursor.execute(f"PRAGMA table_info({table_name})")
        existing_columns = [row[1] for row in cursor.fetchall()]

        if column_name not in existing_columns:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")

    def init_db(self):
        """
        Creates and migrates the timetable table.

        project_id allows one SQLite database to store multiple independent
        timetable profiles/workspaces without data bleeding between them.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS timetable (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL DEFAULT 'project-1',
                    course_code TEXT NOT NULL,
                    course_name TEXT NOT NULL,
                    course_venue TEXT,
                    class_day TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            # Migration support for existing timetable databases created before project_id.
            self._ensure_column(
                cursor=cursor,
                table_name="timetable",
                column_name="project_id",
                column_sql="project_id TEXT NOT NULL DEFAULT 'project-1'"
            )

            conn.commit()

        print(f"📁 Isolated Timetable DB Engaged at: {os.path.abspath(self.db_path)}")

    def clear_timetable_records(self, project_id: str = "project-1"):
        """
        Clears timetable records only for the selected workspace.
        This prevents Timetable 2 from deleting Timetable 1 data.
        """
        active_project_id = self._normalize_project_id(project_id)

        query = "DELETE FROM timetable WHERE project_id = ?"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (active_project_id,))
            conn.commit()

        print(f"🧹 Timetable records evicted for project_id={active_project_id}.")

    def clear_all_timetable_records(self):
        """
        Optional full wipe utility. Use only for development reset.
        Normal app routes should use clear_timetable_records(project_id).
        """
        query = "DELETE FROM timetable"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            conn.commit()

        print("🧹 All timetable records evicted from storage.")

    def insert_batch_timetable_slots(self, extracted_courses, project_id: str = "project-1"):
        """
        Inserts parsed timetable slots into the selected workspace.
        """
        active_project_id = self._normalize_project_id(project_id)

        query = """
            INSERT INTO timetable (
                project_id,
                course_code,
                course_name,
                course_venue,
                class_day,
                start_time,
                end_time,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self.get_connection() as conn:
            cursor = conn.cursor()

            for course in extracted_courses:
                cursor.execute(query, (
                    active_project_id,
                    str(course.get("course_code", "UNKNOWN")).strip().upper(),
                    str(course.get("course_name", "Unnamed Course")).strip(),
                    str(course.get("course_venue", "Venue TBC")).strip(),
                    str(course.get("class_day", "")).strip(),
                    str(course.get("start_time", "")).strip(),
                    str(course.get("end_time", "")).strip(),
                    timestamp
                ))

            conn.commit()

        print(f"🚀 Ingested {len(extracted_courses)} class blocks for project_id={active_project_id}.")

    def get_all_timetable_slots(self, project_id: str = None):
        """
        Fetches timetable slots.

        If project_id is supplied, only returns rows for that workspace.
        If project_id is None, returns all rows for backward compatibility.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if project_id is None:
                query = """
                    SELECT course_code, course_name, course_venue, class_day, start_time, end_time
                    FROM timetable
                    ORDER BY class_day ASC, start_time ASC
                """
                cursor.execute(query)
            else:
                active_project_id = self._normalize_project_id(project_id)
                query = """
                    SELECT course_code, course_name, course_venue, class_day, start_time, end_time
                    FROM timetable
                    WHERE project_id = ?
                    ORDER BY class_day ASC, start_time ASC
                """
                cursor.execute(query, (active_project_id,))

            return cursor.fetchall()

    def get_all_timetable_slots_by_project(self, project_id: str = "project-1"):
        """
        Explicit project-scoped alias for router compatibility.
        """
        return self.get_all_timetable_slots(project_id=project_id)

    def clear_timetable_records_by_project(self, project_id: str = "project-1"):
        """
        Explicit project-scoped alias for router compatibility.
        """
        return self.clear_timetable_records(project_id=project_id)

    def insert_batch_timetable_slots_by_project(self, project_id: str, extracted_courses):
        """
        Explicit project-scoped alias for router compatibility.
        """
        return self.insert_batch_timetable_slots(
            extracted_courses=extracted_courses,
            project_id=project_id
        )

    def has_timetable(self, project_id: str = "project-1") -> bool:
        """
        Returns whether the selected workspace already has timetable records.
        """
        active_project_id = self._normalize_project_id(project_id)

        query = "SELECT COUNT(*) FROM timetable WHERE project_id = ?"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (active_project_id,))
            count = cursor.fetchone()[0]

        return count > 0

    def count_timetable_slots(self, project_id: str = "project-1") -> int:
        """
        Counts timetable slots for the selected workspace.
        """
        active_project_id = self._normalize_project_id(project_id)

        query = "SELECT COUNT(*) FROM timetable WHERE project_id = ?"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (active_project_id,))
            count = cursor.fetchone()[0]

        return int(count)
