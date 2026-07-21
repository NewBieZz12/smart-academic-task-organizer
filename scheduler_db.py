# scheduler_db.py Greedy, GA, Resource Leveling

import sqlite3
import os
import json
import random
import copy
import time
from datetime import datetime, timedelta, time as datetime_time
from dateutil import parser


# ==============================================================================
# ENGINE LAYER 1: HYBRID OPTIMIZATION PIPELINE SCHEDULER
# ==============================================================================
class GenericScheduler:
    def __init__(self):
        """
        Calculates optimized deadline milestones using a hybrid pipeline:
        1. Greedy heuristic seed generation
        2. Genetic algorithm optimization
        3. Post-processing workload balancing / resource leveling
        """
        self.population_size = 100
        self.crossover_rate = 0.80
        self.mutation_rate = 0.15
        self.max_generations = 150
        self.tournament_size = 5
        self.block_duration_hours = 2

    def _get_daily_capacity(self, date_str: str) -> float:
        """
        Every day is limited to 4 study hours.
        Since each milestone block is 2 hours, maximum 2 task blocks are allowed per day.
        """
        return 4.0

    def _is_overlapping(self, slot_start: datetime, slot_end: datetime, constraints: list) -> bool:
        for c_start, c_end in constraints:
            if max(slot_start, c_start) < min(slot_end, c_end):
                return True
        return False

    def _get_valid_slots_matrix(
        self,
        deadline_iso: str,
        timetable_constraints: list,
        existing_daily_workload: dict = None
    ) -> list:
        """
        Generates valid candidate slots.

        Updated:
        - Excludes slots that overlap timetable or existing task intervals.
        - Excludes dates that already reached 4 hours of saved task workload.
        """
        existing_daily_workload = existing_daily_workload or {}

        try:
            start_date = datetime.now().date()
            end_date = parser.parse(deadline_iso).date()
        except Exception:
            start_date = datetime.now().date()
            end_date = start_date + timedelta(days=14)

        if (end_date - start_date).days < 5:
            end_date = start_date + timedelta(days=6)

        valid_slots = []
        current = start_date

        while current <= end_date:
            current_date_str = current.strftime("%Y-%m-%d")

            already_allocated_hours = existing_daily_workload.get(current_date_str, 0.0)
            allowed_max = self._get_daily_capacity(current_date_str)

            # If the date is already full, do not generate any slot for this day.
            if already_allocated_hours >= allowed_max:
                current += timedelta(days=1)
                continue

            for hour in [9, 11, 14, 16]:
                proposed_start = datetime.combine(current, datetime_time(hour, 0))
                proposed_end = proposed_start + timedelta(hours=self.block_duration_hours)

                if proposed_start < datetime.now():
                    continue

                # Make sure adding this block will not exceed daily 4-hour capacity.
                if already_allocated_hours + self.block_duration_hours > allowed_max:
                    continue

                if not self._is_overlapping(proposed_start, proposed_end, timetable_constraints):
                    valid_slots.append(f"{current_date_str} {hour:02d}:00")

            current += timedelta(days=1)

        return valid_slots

    def _calculate_fitness_with_telemetry(
        self,
        chromosome: list,
        existing_daily_workload: dict = None
    ) -> tuple:
        """
        Calculates GA fitness.

        Updated:
        - Includes existing saved task workload when calculating daily overload penalties.
        """
        if not chromosome:
            return 0.0, 0.0, 0.0

        existing_daily_workload = existing_daily_workload or {}

        daily_distribution = {}
        assignment_date_registry = set()
        time_slot_distribution = {}

        deadline_penalties = 0.0
        spacing_penalties = 0.0
        chronology_penalties = 0.0
        identity_clash_penalties = 0.0
        time_repetition_penalties = 0.0

        previous_datetime = None

        for gene in chromosome:
            slot = gene["assigned_slot"]
            meta = gene["meta"]
            project_identity = meta["project"]

            date_part, time_part = slot.split(" ")

            daily_distribution[date_part] = daily_distribution.get(date_part, 0) + 1
            time_slot_distribution[time_part] = time_slot_distribution.get(time_part, 0) + 1

            tracking_pair = (date_part, project_identity)
            if tracking_pair in assignment_date_registry:
                identity_clash_penalties += 1500.0
            assignment_date_registry.add(tracking_pair)

            try:
                current_dt = datetime.strptime(slot, "%Y-%m-%d %H:%M")
                deadline_dt = parser.parse(meta["deadline_iso"])

                if current_dt > deadline_dt:
                    deadline_penalties += 1000.0

                if previous_datetime and current_dt <= previous_datetime:
                    chronology_penalties += 800.0

                previous_datetime = current_dt
            except Exception:
                pass

        for date_str, count in daily_distribution.items():
            new_allocated_hours = count * self.block_duration_hours
            existing_hours = existing_daily_workload.get(date_str, 0.0)
            total_allocated_hours = existing_hours + new_allocated_hours

            allowed_max = self._get_daily_capacity(date_str)

            if total_allocated_hours > allowed_max:
                spacing_penalties += (total_allocated_hours - allowed_max) * 500.0

        for _, count in time_slot_distribution.items():
            if count > 1:
                time_repetition_penalties += (count - 1) * 120.0

        total_penalties = (
            deadline_penalties
            + spacing_penalties
            + chronology_penalties
            + identity_clash_penalties
            + time_repetition_penalties
        )

        base_score = 10000.0 / (1.0 + total_penalties)
        diversity_bonus = len(time_slot_distribution.keys()) * 20.0

        return base_score + diversity_bonus, deadline_penalties, spacing_penalties

    def split_task_into_milestones(
        self,
        title: str,
        project: str,
        deadline_iso: str,
        priority: str,
        timetable_constraints: list = None,
        existing_daily_workload: dict = None
    ) -> list:
        constraints_list = timetable_constraints if timetable_constraints else []
        existing_daily_workload = existing_daily_workload or {}

        phases = [
            {"title": f" Phase 1: {title}"},
            {"title": f" Phase 2: {title}"},
            {"title": f" Phase 3: {title}"}
        ]

        print(f"\n{'=' * 80}")
        print("[BACKEND TELEMETRY ENGINE] INITIALIZING HYBRID SCHEDULING PIPELINE")
        print(f"{'=' * 80}")

        start_pipeline_time = time.time()

        valid_slots = self._get_valid_slots_matrix(
            deadline_iso=deadline_iso,
            timetable_constraints=constraints_list,
            existing_daily_workload=existing_daily_workload
        )

        print(f"🧩 Constraint intervals received by scheduler: {len(constraints_list)}")
        print(f"🧩 Existing daily workload map: {existing_daily_workload}")
        print(f"🧩 Valid candidate slots generated before fallback: {len(valid_slots)}")
        print("🧩 First 20 valid candidate slots before fallback:")
        for s in valid_slots[:20]:
            print(f"   - {s}")

        if not valid_slots:
            fallback_start = datetime.now() + timedelta(days=1)
            valid_slots = []

            # Fallback now also respects existing daily workload.
            for i in range(14):
                candidate_date = fallback_start + timedelta(days=i)
                candidate_date_str = candidate_date.strftime("%Y-%m-%d")
                already_allocated_hours = existing_daily_workload.get(candidate_date_str, 0.0)

                if already_allocated_hours + self.block_duration_hours <= self._get_daily_capacity(candidate_date_str):
                    valid_slots.append(f"{candidate_date_str} 09:00")

                if len(valid_slots) >= 3:
                    break

            if not valid_slots:
                raise ValueError("No valid slots available. All candidate days are full or blocked by constraints.")

            print("⚠️ No valid slots found. Capacity-aware fallback slots activated:")
            for s in valid_slots:
                print(f"   - {s}")

        # MODULE 1: GREEDY SEED GENERATION
        start_greedy_time = time.time()
        greedy_chromosome = []
        allocated_slots_tracker = set()
        generated_daily_workload = copy.deepcopy(existing_daily_workload)

        for phase in phases:
            assigned = False

            for slot in valid_slots:
                date_part = slot.split(" ")[0]

                existing_for_day = generated_daily_workload.get(date_part, 0.0)
                allowed_max = self._get_daily_capacity(date_part)

                if (
                    slot not in allocated_slots_tracker
                    and existing_for_day + self.block_duration_hours <= allowed_max
                ):
                    allocated_slots_tracker.add(slot)
                    generated_daily_workload[date_part] = existing_for_day + self.block_duration_hours

                    greedy_chromosome.append({
                        "assigned_slot": slot,
                        "meta": {
                            "title": phase["title"],
                            "project": project,
                            "priority": priority,
                            "deadline_iso": deadline_iso
                        }
                    })

                    assigned = True
                    break

            if not assigned:
                # Last resort: find any slot with capacity.
                fallback_slot = None

                for slot in valid_slots:
                    date_part = slot.split(" ")[0]
                    existing_for_day = generated_daily_workload.get(date_part, 0.0)

                    if existing_for_day + self.block_duration_hours <= self._get_daily_capacity(date_part):
                        fallback_slot = slot
                        generated_daily_workload[date_part] = existing_for_day + self.block_duration_hours
                        break

                if not fallback_slot:
                    raise ValueError(
                        "Unable to assign all milestones without exceeding the 4-hour daily workload limit."
                    )

                greedy_chromosome.append({
                    "assigned_slot": fallback_slot,
                    "meta": {
                        "title": phase["title"],
                        "project": project,
                        "priority": priority,
                        "deadline_iso": deadline_iso
                    }
                })

        greedy_duration_ms = (time.time() - start_greedy_time) * 1000.0
        print(f"⏱️ [MODULE 1] Greedy Heuristic initialization completed in: {greedy_duration_ms:.4f} ms")

        # MODULE 2 & 3: GENETIC OPTIMIZATION
        start_ga_time = time.time()
        population = [copy.deepcopy(greedy_chromosome)]

        while len(population) < self.population_size:
            mutated_ind = copy.deepcopy(greedy_chromosome)

            for gene in mutated_ind:
                if random.random() < 0.40:
                    gene["assigned_slot"] = random.choice(valid_slots)

            population.append(mutated_ind)

        best_fitness = -1.0
        best_individual = greedy_chromosome
        consecutive_no_improvement = 0

        for generation in range(self.max_generations):
            pop_metrics = []

            for ind in population:
                fit, _, _ = self._calculate_fitness_with_telemetry(
                    chromosome=ind,
                    existing_daily_workload=existing_daily_workload
                )
                pop_metrics.append((fit, ind))

            pop_metrics.sort(key=lambda x: x[0], reverse=True)
            current_best_fit = pop_metrics[0][0]
            current_best_ind = pop_metrics[0][1]

            if current_best_fit > best_fitness:
                if best_fitness > 0 and (current_best_fit - best_fitness) / best_fitness < 0.0001:
                    consecutive_no_improvement += 1
                else:
                    consecutive_no_improvement = 0

                best_fitness = current_best_fit
                best_individual = current_best_ind
            else:
                consecutive_no_improvement += 1

            if consecutive_no_improvement >= 30:
                break

            next_generation = [copy.deepcopy(best_individual)]

            while len(next_generation) < self.population_size:
                parents = []

                for _ in range(2):
                    sampled = random.sample(pop_metrics, self.tournament_size)
                    sampled.sort(key=lambda x: x[0], reverse=True)
                    parents.append(sampled[0][1])

                p1, p2 = parents[0], parents[1]
                child = copy.deepcopy(p1)

                if random.random() < self.crossover_rate:
                    cut_point = random.randint(1, len(child) - 1) if len(child) > 1 else 0
                    child[cut_point:] = copy.deepcopy(p2[cut_point:])

                if random.random() < self.mutation_rate:
                    target_gene = random.choice(child)
                    target_gene["assigned_slot"] = random.choice(valid_slots)

                next_generation.append(child)

            population = next_generation

        ga_duration_ms = (time.time() - start_ga_time) * 1000.0
        print(f"⏱️ [MODULE 2 + 3] Genetic Engine run optimized in: {ga_duration_ms:.4f} ms (Fitness: {best_fitness:.2f})")

        # MODULE 4: RESOURCE LEVELING
        start_level_time = time.time()
        leveled_chromosome = copy.deepcopy(best_individual)
        leveled_chromosome.sort(key=lambda x: datetime.strptime(x["assigned_slot"], "%Y-%m-%d %H:%M"))

        # Important:
        # Start from existing saved workload, not empty workload.
        daily_workload_registry = copy.deepcopy(existing_daily_workload)
        used_slots_on_pass = set()

        for gene in leveled_chromosome:
            original_slot = gene["assigned_slot"]
            date_part, _ = original_slot.split(" ")

            allowed_max = self._get_daily_capacity(date_part)
            current_day_hours = daily_workload_registry.get(date_part, 0.0)

            if (
                current_day_hours + self.block_duration_hours <= allowed_max
                and original_slot not in used_slots_on_pass
            ):
                daily_workload_registry[date_part] = current_day_hours + self.block_duration_hours
                used_slots_on_pass.add(original_slot)
                continue

            moved = False

            for alternative_slot in valid_slots:
                alt_date = alternative_slot.split(" ")[0]
                alt_max = self._get_daily_capacity(alt_date)
                alt_current_hours = daily_workload_registry.get(alt_date, 0.0)

                if (
                    alternative_slot not in used_slots_on_pass
                    and alt_current_hours + self.block_duration_hours <= alt_max
                    and alternative_slot >= original_slot
                ):
                    gene["assigned_slot"] = alternative_slot
                    daily_workload_registry[alt_date] = alt_current_hours + self.block_duration_hours
                    used_slots_on_pass.add(alternative_slot)
                    moved = True
                    break

            if not moved:
                raise ValueError(
                    "Resource Leveling failed: unable to place milestone without exceeding 4-hour daily limit."
                )

        milestones_output = []

        for index, gene in enumerate(leveled_chromosome):
            dt_part, tm_part = gene["assigned_slot"].split(" ")
            start_dt = datetime.strptime(gene["assigned_slot"], "%Y-%m-%d %H:%M")
            end_dt = start_dt + timedelta(hours=self.block_duration_hours)

            milestones_output.append({
                "milestone_id": 1000 + index,
                "project": gene["meta"]["project"],
                "title": gene["meta"]["title"],
                "planned_date": dt_part,
                "time_slot": tm_part,
                "start_iso": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "end_iso": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "priority": gene["meta"]["priority"],
                "deadline_iso": gene["meta"]["deadline_iso"]
            })

        leveling_duration_ms = (time.time() - start_level_time) * 1000.0
        total_pipeline_ms = (time.time() - start_pipeline_time) * 1000.0

        print(f"⏱️ [MODULE 4] Resource Leveling processing engine resolved in: {leveling_duration_ms:.4f} ms")
        print(f"🏆 Total Optimization Pipeline processing execution time: {total_pipeline_ms:.4f} ms")
        print(f"📊 Final daily workload after leveling: {daily_workload_registry}")
        print(f"{'=' * 80}\n")

        print("📦 Final selected milestone schedule:")
        for m in milestones_output:
            print(
                f"   - {m['title']} | {m['planned_date']} {m['time_slot']} "
                f"to {m['end_iso']} | project={m['project']}"
            )

        print("🔍 Conflict validation against constraints:")
        for m in milestones_output:
            task_start = parser.parse(m["start_iso"])
            task_end = parser.parse(m["end_iso"])
            has_conflict = False

            for c_start, c_end in constraints_list:
                if max(task_start, c_start) < min(task_end, c_end):
                    has_conflict = True
                    print(
                        f"   ❌ CONFLICT: {m['title']} "
                        f"{task_start} - {task_end} overlaps {c_start} - {c_end}"
                    )

            if not has_conflict:
                print(f"   ✅ OK: {m['title']} has no timetable/task conflict.")

        return milestones_output


# ==============================================================================
# ENGINE LAYER 2: PERSISTENCE SQLITE DATA WAREHOUSE
# ==============================================================================
class TasksDatabaseManager:
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scheduler.db")
        self.engine_scheduler = GenericScheduler()
        self.initialize_warehouse()

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

    def initialize_warehouse(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL DEFAULT 'project-1',
                    title TEXT NOT NULL,
                    project TEXT NOT NULL,
                    planned_date TEXT NOT NULL,
                    planned_time TEXT NOT NULL,
                    deadline_iso TEXT NOT NULL,
                    priority TEXT DEFAULT 'Normal',
                    sorting_score INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS timetable_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL DEFAULT 'project-1',
                    course_code TEXT NOT NULL,
                    course_name TEXT,
                    course_venue TEXT,
                    start_iso TEXT NOT NULL,
                    end_iso TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)

            self._ensure_column(cursor, "tasks", "project_id", "project_id TEXT NOT NULL DEFAULT 'project-1'")
            self._ensure_column(cursor, "timetable_events", "project_id", "project_id TEXT NOT NULL DEFAULT 'project-1'")
            self._ensure_column(cursor, "timetable_events", "course_name", "course_name TEXT")
            self._ensure_column(cursor, "timetable_events", "course_venue", "course_venue TEXT")
            self._ensure_column(cursor, "timetable_events", "created_at", "created_at TEXT DEFAULT CURRENT_TIMESTAMP")

            conn.commit()

    def insert_timetable_event(
        self,
        project_id: str,
        course_code: str,
        start_iso: str,
        end_iso: str,
        course_name: str = "",
        course_venue: str = ""
    ):
        active_project_id = self._normalize_project_id(project_id)

        query = """
            INSERT INTO timetable_events (
                project_id,
                course_code,
                course_name,
                course_venue,
                start_iso,
                end_iso
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                active_project_id,
                str(course_code or "").upper().strip(),
                str(course_name or "").strip(),
                str(course_venue or "").strip(),
                start_iso,
                end_iso
            ))
            conn.commit()

    def clear_timetable_events(self, project_id: str):
        active_project_id = self._normalize_project_id(project_id)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM timetable_events WHERE project_id = ?", (active_project_id,))
            conn.commit()

    def get_timetable_intervals(self, project_id: str) -> list:
        active_project_id = self._normalize_project_id(project_id)
        intervals = []

        query = """
            SELECT start_iso, end_iso
            FROM timetable_events
            WHERE project_id = ?
        """

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (active_project_id,))

            for start_str, end_str in cursor.fetchall():
                try:
                    intervals.append((parser.parse(start_str), parser.parse(end_str)))
                except Exception as e:
                    print(f"⚠️ Dropped invalid timetable interval: {start_str} - {end_str}. Reason: {e}")

        return intervals

    def get_existing_task_intervals(self, project_id: str) -> list:
        active_project_id = self._normalize_project_id(project_id)
        intervals = []

        query = """
            SELECT planned_date, planned_time
            FROM tasks
            WHERE project_id = ?
        """

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (active_project_id,))

            for planned_date, planned_time in cursor.fetchall():
                try:
                    clean_time = str(planned_time or "12:00").strip()
                    if len(clean_time) == 5:
                        clean_time += ":00"

                    start_dt = datetime.strptime(f"{planned_date} {clean_time}", "%Y-%m-%d %H:%M:%S")
                    end_dt = start_dt + timedelta(hours=self.engine_scheduler.block_duration_hours)
                    intervals.append((start_dt, end_dt))
                except Exception as e:
                    print(f"⚠️ Dropped invalid existing task interval: {planned_date} {planned_time}. Reason: {e}")

        return intervals

    def get_existing_daily_workload(self, project_id: str) -> dict:
        """
        Returns existing saved task workload by date.

        Example:
        {
            "2026-07-08": 4.0,
            "2026-07-09": 2.0
        }

        Each saved task phase is treated as 2 hours.
        """
        active_project_id = self._normalize_project_id(project_id)
        daily_workload = {}

        query = """
            SELECT planned_date
            FROM tasks
            WHERE project_id = ?
        """

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (active_project_id,))

            for row in cursor.fetchall():
                planned_date = str(row[0] or "").strip()

                if not planned_date:
                    continue

                daily_workload[planned_date] = (
                    daily_workload.get(planned_date, 0.0)
                    + self.engine_scheduler.block_duration_hours
                )

        return daily_workload

    def generate_and_save_split_task(self, project_id: str, title: str, project: str, deadline_iso: str, priority: str):
        active_project_id = self._normalize_project_id(project_id)

        timetable_constraints = self.get_timetable_intervals(active_project_id)
        existing_task_constraints = self.get_existing_task_intervals(active_project_id)
        existing_daily_workload = self.get_existing_daily_workload(active_project_id)

        combined_constraints = timetable_constraints + existing_task_constraints

        print(f"📌 Fixed timetable constraints loaded: {len(timetable_constraints)}")
        print(f"📌 Existing task constraints loaded: {len(existing_task_constraints)}")
        print(f"📌 Existing daily workload loaded: {existing_daily_workload}")
        print(f"📌 Total scheduling constraints loaded: {len(combined_constraints)}")

        optimized_milestones = self.engine_scheduler.split_task_into_milestones(
            title=title,
            project=project,
            deadline_iso=deadline_iso,
            priority=priority,
            timetable_constraints=combined_constraints,
            existing_daily_workload=existing_daily_workload
        )

        if optimized_milestones:
            self.insert_bulk_milestones(optimized_milestones, active_project_id)

        return optimized_milestones

    def propose_split_task(self, project_id: str, title: str, project: str, deadline_iso: str, priority: str):
        """
        Proposal-only version used by /api/schedule/propose.

        It does not save to database.
        It still considers:
        - timetable constraints
        - existing task time intervals
        - existing daily workload capacity
        """
        active_project_id = self._normalize_project_id(project_id)

        timetable_constraints = self.get_timetable_intervals(active_project_id)
        existing_task_constraints = self.get_existing_task_intervals(active_project_id)
        existing_daily_workload = self.get_existing_daily_workload(active_project_id)

        combined_constraints = timetable_constraints + existing_task_constraints

        print(f"📌 Proposal fixed timetable constraints loaded: {len(timetable_constraints)}")
        print(f"📌 Proposal existing task constraints loaded: {len(existing_task_constraints)}")
        print(f"📌 Proposal existing daily workload loaded: {existing_daily_workload}")
        print(f"📌 Proposal total constraints loaded: {len(combined_constraints)}")

        return self.engine_scheduler.split_task_into_milestones(
            title=title,
            project=project,
            deadline_iso=deadline_iso,
            priority=priority,
            timetable_constraints=combined_constraints,
            existing_daily_workload=existing_daily_workload
        )

    def insert_assignment_direct(
        self,
        project_id: str = "project-1",
        title: str = None,
        project: str = None,
        deadline_iso: str = None,
        priority: str = "Normal",
        payload=None,
        **kwargs
    ):
        try:
            data = {}

            if payload is not None:
                data = payload.dict() if hasattr(payload, "dict") else payload

                if not isinstance(data, dict):
                    data = {}

                title = data.get("title", title)
                project = data.get("project", project)
                deadline_iso = data.get("deadline_iso", deadline_iso)
                priority = data.get("priority", priority or "Normal")
                project_id = data.get("project_id", project_id)

            active_project_id = self._normalize_project_id(project_id)
            user_selected_date = kwargs.get("planned_date") or data.get("planned_date")
            user_selected_time = (
                kwargs.get("planned_time")
                or kwargs.get("time_slot")
                or data.get("planned_time")
                or data.get("time_slot")
            )

            if not title or not project or not deadline_iso:
                raise ValueError("Missing critical fields: title, project, or deadline_iso are required.")

            current_timestamp = datetime.now()
            current_time_str = current_timestamp.strftime("%Y-%m-%d %H:%M:%S")

            try:
                parsed_deadline = parser.isoparse(deadline_iso)
            except Exception:
                try:
                    parsed_deadline = parser.parse(deadline_iso)
                except Exception:
                    parsed_deadline = current_timestamp

            final_planned_date = str(user_selected_date).strip() if user_selected_date else parsed_deadline.strftime("%Y-%m-%d")
            final_planned_time = str(user_selected_time).strip() if user_selected_time else "12:00"

            query = """
                INSERT INTO tasks (
                    project_id,
                    title,
                    project,
                    planned_date,
                    planned_time,
                    deadline_iso,
                    priority,
                    sorting_score,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
            """

            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (
                    active_project_id,
                    str(title).strip(),
                    str(project).strip().upper(),
                    final_planned_date,
                    final_planned_time,
                    str(deadline_iso).strip(),
                    str(priority),
                    current_time_str
                ))
                conn.commit()
                return cursor.lastrowid

        except Exception as e:
            print(f"❌ Failed inside database entry creation layer: {str(e)}")
            raise e

    def insert_bulk_milestones(self, milestones_list: list, project_id: str):
        try:
            active_project_id = self._normalize_project_id(project_id)
            current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            query = """
                INSERT INTO tasks (
                    project_id,
                    title,
                    project,
                    planned_date,
                    planned_time,
                    deadline_iso,
                    priority,
                    sorting_score,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
            """

            with self.get_connection() as conn:
                cursor = conn.cursor()

                for block in milestones_list:
                    title = block.get("title", "Unnamed Milestone Block")
                    project = str(block.get("project", "UNKNOWN")).strip().upper()
                    planned_date = block.get("planned_date")
                    planned_time = block.get("time_slot") or block.get("planned_time", "12:00")
                    deadline_iso = block.get("deadline_iso")
                    priority = block.get("priority", "Normal")

                    cursor.execute(query, (
                        active_project_id,
                        str(title).strip(),
                        project,
                        str(planned_date).strip(),
                        str(planned_time).strip(),
                        str(deadline_iso).strip(),
                        str(priority),
                        current_time_str
                    ))

                conn.commit()
                return True

        except Exception as e:
            print(f"❌ Failed inside bulk database processing arrays: {str(e)}")
            raise e

    def get_all_tasks(self, project_id: str):
        active_project_id = self._normalize_project_id(project_id)

        query = """
            SELECT id, title, project, planned_date, planned_time, deadline_iso, priority
            FROM tasks
            WHERE project_id = ?
            ORDER BY planned_date ASC, planned_time ASC
        """

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (active_project_id,))
            return cursor.fetchall()

    def get_tasks_in_range(self, start_date: str, end_date: str, project_id: str) -> list:
        active_project_id = self._normalize_project_id(project_id)

        query = """
            SELECT id, title, project, planned_date, planned_time, deadline_iso, priority
            FROM tasks
            WHERE project_id = ? AND (planned_date BETWEEN ? AND ?)
            ORDER BY planned_date ASC, planned_time ASC
        """

        results = []

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (active_project_id, start_date, end_date))

            for row in cursor.fetchall():
                try:
                    clean_time = str(row[4] or "12:00").strip()
                    if len(clean_time) == 5:
                        clean_time += ":00"

                    start_dt = datetime.strptime(f"{row[3]} {clean_time}", "%Y-%m-%d %H:%M:%S")
                except Exception:
                    start_dt = datetime.strptime(f"{row[3]} 12:00:00", "%Y-%m-%d %H:%M:%S")

                end_dt = start_dt + timedelta(hours=self.engine_scheduler.block_duration_hours)

                results.append({
                    "id": row[0],
                    "type": "TASK_PHASE",
                    "is_fixed_class": False,
                    "title": row[1],
                    "project": row[2],
                    "planned_date": row[3],
                    "planned_time": start_dt.strftime("%H:%M"),
                    "time_slot": start_dt.strftime("%H:%M"),
                    "end_time": end_dt.strftime("%H:%M"),
                    "start_iso": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "end_iso": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "deadline_iso": row[5],
                    "priority": row[6]
                })

        return results

    def get_timetable_events_in_range(self, start_date: str, end_date: str, project_id: str) -> list:
        active_project_id = self._normalize_project_id(project_id)

        query = """
            SELECT id, course_code, course_name, course_venue, start_iso, end_iso
            FROM timetable_events
            WHERE project_id = ? AND (substr(start_iso, 1, 10) BETWEEN ? AND ?)
            ORDER BY start_iso ASC
        """

        results = []

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (active_project_id, start_date, end_date))

            for row in cursor.fetchall():
                try:
                    event_id = row[0]
                    course_code = row[1]
                    course_name = row[2] or f"Lecture: {course_code}"
                    course_venue = row[3] or ""
                    start_iso = row[4]
                    end_iso = row[5]

                    start_dt = parser.parse(start_iso)
                    end_dt = parser.parse(end_iso)

                    results.append({
                        "id": f"class-{event_id}",
                        "type": "CLASS",
                        "is_fixed_class": True,
                        "title": course_name,
                        "course_code": course_code,
                        "project": course_code,
                        "venue": course_venue,
                        "planned_date": start_dt.strftime("%Y-%m-%d"),
                        "planned_time": start_dt.strftime("%H:%M"),
                        "time_slot": start_dt.strftime("%H:%M"),
                        "end_time": end_dt.strftime("%H:%M"),
                        "start_iso": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "end_iso": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "deadline_iso": "",
                        "priority": "High"
                    })

                except Exception as e:
                    print(f"⚠️ Dropped invalid timetable event row {row}: {e}")
                    continue

        return results

    def get_weekly_view_payload(self, target_date_str: str, project_id: str) -> dict:
        active_project_id = self._normalize_project_id(project_id)

        try:
            parsed_target = parser.parse(target_date_str).date()
        except Exception:
            parsed_target = datetime.now().date()

        current_weekday_idx = parsed_target.weekday()
        start_of_week = parsed_target - timedelta(days=current_weekday_idx)
        end_of_week = start_of_week + timedelta(days=6)

        start_str = start_of_week.strftime("%Y-%m-%d")
        end_str = end_of_week.strftime("%Y-%m-%d")

        tasks = self.get_tasks_in_range(start_str, end_str, active_project_id)
        classes = self.get_timetable_events_in_range(start_str, end_str, active_project_id)

        unified_events = tasks + classes
        unified_events.sort(key=lambda x: x["start_iso"])

        return {
            "requested_target_date": target_date_str,
            "project_id": active_project_id,
            "week_start": start_str,
            "week_end": end_str,
            "total_events_count": len(unified_events),
            "events": unified_events
        }


def get_db():
    return TasksDatabaseManager()
