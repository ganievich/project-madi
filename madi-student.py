import csv
import json
import os
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
from typing import Any


class DataManagerError(Exception):
    """Деректерді өңдеу, тексеру немесе файлмен жұмыс кезіндегі қате."""


class StudentDataManager:
    """1-нұсқа: Студенттердің үлгерімін талдау деректер моделі және файл менеджері."""

    ALLOWED_EXTENSIONS = (".json", ".csv")
    CSV_FIELDS = [
        "id",
        "full_name",
        "group_name",
        "grade1",
        "grade2",
        "grade3",
        "attendance",
        "avg_grade",
        "risk_status",
        "updated_at",
    ]

    def __init__(self, filepath: str = "students_data.json") -> None:
        self.filepath = filepath
        self.records: list[dict[str, Any]] = []

    @staticmethod
    def calculate_average(g1: float, g2: float, g3: float) -> float:
        return round((g1 + g2 + g3) / 3.0, 2)

    @staticmethod
    def determine_risk(avg_grade: float, attendance: float) -> str:
        if avg_grade < 50.0 or attendance < 70.0:
            return "Тәуекел тобы"
        return "Қалыпты"

    def validate_record(
        self,
        student_id: str,
        full_name: str,
        group_name: str,
        g1_raw: str,
        g2_raw: str,
        g3_raw: str,
        attendance_raw: str,
        editing_original_id: str | None = None,
    ) -> dict[str, Any]:
        sid = student_id.strip()
        name = " ".join(full_name.strip().split())
        group = group_name.strip().upper()

        if not sid:
            raise ValueError("ID өрісі бос болмауы керек.")
        if len(sid) < 2 or len(sid) > 20:
            raise ValueError("ID ұзындығы 2-ден 20 таңбаға дейін болуы тиіс.")

        if not name or len(name) < 3:
            raise ValueError("Аты-жөні кемінде 3 таңбадан тұруы керек.")

        if not group or len(group) < 2:
            raise ValueError("Топ атауы енгізілуі керек (мысалы: ИП-24-1К2).")

        existing_ids = {
            str(r["id"]).strip()
            for r in self.records
            if editing_original_id is None or str(r["id"]).strip() != editing_original_id
        }
        if sid in existing_ids:
            raise ValueError(f"'{sid}' ID-і бар жазба тізімде бар. Бірегей ID енгізіңіз.")

        def parse_score(raw: str, label: str, min_val: float, max_val: float) -> float:
            cleaned = raw.strip().replace(",", ".")
            if not cleaned:
                raise ValueError(f"'{label}' өрісі толтырылуы керек.")
            try:
                val = float(cleaned)
            except ValueError as exc:
                raise ValueError(f"'{label}' өрісіне сан енгізіңіз.") from exc
            if val < min_val or val > max_val:
                raise ValueError(
                    f"'{label}' мәні {min_val:g} мен {max_val:g} аралығында болуы керек."
                )
            return round(val, 2)

        g1 = parse_score(g1_raw, "1-бақылау бағасы", 0.0, 100.0)
        g2 = parse_score(g2_raw, "2-бақылау бағасы", 0.0, 100.0)
        g3 = parse_score(g3_raw, "3-бақылау бағасы", 0.0, 100.0)
        attendance = parse_score(attendance_raw, "Қатысу пайызы (%)", 0.0, 100.0)

        avg_grade = self.calculate_average(g1, g2, g3)
        risk_status = self.determine_risk(avg_grade, attendance)

        return {
            "id": sid,
            "full_name": name,
            "group_name": group,
            "grade1": g1,
            "grade2": g2,
            "grade3": g3,
            "attendance": attendance,
            "avg_grade": avg_grade,
            "risk_status": risk_status,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

    def add_record(self, record: dict[str, Any]) -> None:
        self.records.append(record)

    def update_record(self, original_id: str, updated: dict[str, Any]) -> None:
        for idx, item in enumerate(self.records):
            if str(item["id"]).strip() == original_id:
                self.records[idx] = updated
                return
        raise DataManagerError(f"'{original_id}' ID-і бар жазба табылмады.")

    def delete_record(self, student_id: str) -> None:
        sid = str(student_id).strip()
        before = len(self.records)
        self.records = [r for r in self.records if str(r["id"]).strip() != sid]
        if len(self.records) == before:
            raise DataManagerError(f"'{sid}' ID-і бар жазба жойылмады.")

    def get_groups(self) -> list[str]:
        groups = sorted({str(r["group_name"]) for r in self.records if r.get("group_name")})
        return ["Барлығы"] + groups

    def search_and_filter(
        self,
        query: str = "",
        group_filter: str = "Барлығы",
        min_avg: float | None = None,
        max_avg: float | None = None,
        risk_only: bool = False,
    ) -> list[dict[str, Any]]:
        q = query.strip().lower()
        result: list[dict[str, Any]] = []

        for r in self.records:
            if q:
                haystack = (
                    f"{r.get('id', '')} {r.get('full_name', '')} {r.get('group_name', '')}"
                ).lower()
                if q not in haystack:
                    continue

            if group_filter and group_filter != "Барлығы":
                if str(r.get("group_name", "")) != group_filter:
                    continue

            avg_val = float(r.get("avg_grade", 0.0))
            if min_avg is not None and avg_val < min_avg:
                continue
            if max_avg is not None and avg_val > max_avg:
                continue

            if risk_only and r.get("risk_status") != "Тәуекел тобы":
                continue

            result.append(r)

        return result

    def sort_records(
        self, records: list[dict[str, Any]], key: str, descending: bool = False
    ) -> list[dict[str, Any]]:
        numeric_keys = {"grade1", "grade2", "grade3", "attendance", "avg_grade"}

        def sort_key(item: dict[str, Any]) -> Any:
            val = item.get(key, "")
            if key in numeric_keys:
                try:
                    return float(val)
                except (TypeError, ValueError):
                    return 0.0
            return str(val).lower()

        return sorted(records, key=sort_key, reverse=descending)

    def get_top_students(self, limit: int = 3) -> list[dict[str, Any]]:
        sorted_by_avg = sorted(
            self.records,
            key=lambda r: (float(r.get("avg_grade", 0.0)), float(r.get("attendance", 0.0))),
            reverse=True,
        )
        return sorted_by_avg[:limit]

    def get_statistics(self) -> dict[str, Any]:
        total = len(self.records)
        if total == 0:
            return {
                "total": 0,
                "overall_avg": 0.0,
                "avg_attendance": 0.0,
                "risk_count": 0,
                "risk_percent": 0.0,
                "passed_count": 0,
                "group_stats": [],
            }

        avgs = [float(r.get("avg_grade", 0.0)) for r in self.records]
        atts = [float(r.get("attendance", 0.0)) for r in self.records]
        risk_count = sum(1 for r in self.records if r.get("risk_status") == "Тәуекел тобы")
        passed_count = total - risk_count

        group_map: dict[str, list[float]] = {}
        for r in self.records:
            grp = str(r.get("group_name", "Белгісіз"))
            group_map.setdefault(grp, []).append(float(r.get("avg_grade", 0.0)))

        group_stats = [
            {
                "group": grp,
                "count": len(scores),
                "avg": round(sum(scores) / len(scores), 2),
            }
            for grp, scores in sorted(group_map.items())
        ]

        return {
            "total": total,
            "overall_avg": round(sum(avgs) / total, 2),
            "avg_attendance": round(sum(atts) / total, 2),
            "risk_count": risk_count,
            "risk_percent": round((risk_count / total) * 100.0, 1),
            "passed_count": passed_count,
            "group_stats": group_stats,
        }

    def generate_seed_data(self, count: int = 26) -> list[dict[str, Any]]:
        """Кемінде 25 тест жазбасын қалыптастыру."""
        seed_specs = [
            ("ST-1001", "Ахметов Әлихан Маратұлы", "ИП-24-1К2", 92, 88, 95, 96),
            ("ST-1002", "Серікова Аружан Ерланқызы", "ИП-24-1К2", 85, 90, 87, 92),
            ("ST-1003", "Нұрланов Диас Болатұлы", "ИП-24-1К2", 42, 48, 51, 78),
            ("ST-1004", "Төлеген Мәдина Серікқызы", "ИП-24-2К2", 78, 82, 80, 65),
            ("ST-1005", "Қасымов Темірлан Талғатұлы", "ИП-24-2К2", 94, 96, 91, 98),
            ("ST-1006", "Омарова Айзере Бақытқызы", "ИП-24-2К2", 64, 70, 68, 84),
            ("ST-1007", "Жұмағалиев Санжар Ғаниұлы", "ИТ-24-1К", 55, 52, 49, 72),
            ("ST-1008", "Әбдіқадырова Дана Нұрланқызы", "ИТ-24-1К", 89, 86, 90, 94),
            ("ST-1009", "Сәдуақасов Арман Қайратұлы", "ИТ-24-1К", 38, 44, 40, 58),
            ("ST-1010", "Кенжебаева Інжу Мұратқызы", "ИТ-24-2К", 81, 79, 84, 88),
            ("ST-1011", "Мұхамедов Нұрсұлтан Әділұлы", "ИТ-24-2К", 73, 76, 71, 68),
            ("ST-1012", "Ермекова Томирис Русланқызы", "ИТ-24-2К", 97, 93, 95, 99),
            ("ST-1013", "Байзақов Мирас Ержанұлы", "КБ-24-1К", 60, 62, 58, 80),
            ("ST-1014", "Тұрсынова Камила Асқарқызы", "КБ-24-1К", 88, 84, 86, 91),
            ("ST-1015", "Дүйсенов Рамазан Саматұлы", "КБ-24-1К", 45, 39, 47, 62),
            ("ST-1016", "Құрманғалиева Амина Дарханқызы", "КБ-24-1К", 77, 74, 79, 85),
            ("ST-1017", "Сағындықов Әділет Берікұлы", "ИП-24-1К2", 82, 85, 80, 90),
            ("ST-1018", "Уәлиева Жансая Мақсатқызы", "ИП-24-1К2", 91, 89, 92, 95),
            ("ST-1019", "Халилов Ернар Қанатұлы", "ИП-24-2К2", 49, 53, 46, 74),
            ("ST-1020", "Шәріпова Альбина Мейрамқызы", "ИП-24-2К2", 86, 88, 84, 93),
            ("ST-1021", "Ғабдуллин Әлишер Рахатұлы", "ИТ-24-1К", 67, 65, 70, 76),
            ("ST-1022", "Ибрагимова Назерке Сәбитқызы", "ИТ-24-1К", 90, 92, 89, 97),
            ("ST-1023", "Полатов Дамир Ғалымұлы", "ИТ-24-2К", 58, 61, 56, 66),
            ("ST-1024", "Смағұлова Әсел Ерболатқызы", "ИТ-24-2К", 84, 81, 83, 89),
            ("ST-1025", "Тілеубергенов Ғазиз Қуанышұлы", "КБ-24-1К", 75, 72, 74, 82),
            ("ST-1026", "Маратова Ақбота Жандосқызы", "КБ-24-1К", 93, 91, 94, 96),
        ]

        generated: list[dict[str, Any]] = []
        for sid, name, grp, g1, g2, g3, att in seed_specs[: max(count, 25)]:
            avg_val = self.calculate_average(float(g1), float(g2), float(g3))
            risk_val = self.determine_risk(avg_val, float(att))
            generated.append(
                {
                    "id": sid,
                    "full_name": name,
                    "group_name": grp,
                    "grade1": float(g1),
                    "grade2": float(g2),
                    "grade3": float(g3),
                    "attendance": float(att),
                    "avg_grade": avg_val,
                    "risk_status": risk_val,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
            )
        return generated

    def _normalize_loaded_item(self, raw_item: Any) -> dict[str, Any]:
        if not isinstance(raw_item, dict):
            raise DataManagerError("Файлдағы жазба объектісінің форматы қате.")

        required_keys = ["id", "full_name", "group_name", "grade1", "grade2", "grade3", "attendance"]
        for key in required_keys:
            if key not in raw_item:
                raise DataManagerError(f"Жазбада '{key}' өрісі жетіспейді.")

        return self.validate_record(
            student_id=str(raw_item["id"]),
            full_name=str(raw_item["full_name"]),
            group_name=str(raw_item["group_name"]),
            g1_raw=str(raw_item["grade1"]),
            g2_raw=str(raw_item["grade2"]),
            g3_raw=str(raw_item["grade3"]),
            attendance_raw=str(raw_item["attendance"]),
        )

    def load_from_file(self, filepath: str | None = None) -> tuple[list[dict[str, Any]], str | None]:
        target = filepath or self.filepath
        self.filepath = target
        warning: str | None = None

        if not os.path.exists(target):
            self.records = self.generate_seed_data(26)
            try:
                self.save_to_file(target)
                warning = f"'{target}' файлы табылмады. 26 тест жазбасымен жаңа файл құрылды."
            except DataManagerError:
                warning = f"'{target}' файлы табылмады. Жадыға 26 тест жазбасы жүктелді."
            return self.records, warning

        ext = os.path.splitext(target)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise DataManagerError(f"Қолдау көрсетілмейтін файл кеңейтімі: '{ext}'.")

        try:
            with open(target, "r", encoding="utf-8-sig") as f:
                if ext == ".json":
                    data = json.load(f)
                    if not isinstance(data, list):
                        raise DataManagerError("JSON түбірлік элементі тізім болуы керек.")
                    raw_items = data
                else:
                    reader = csv.DictReader(f)
                    if not reader.fieldnames:
                        raise DataManagerError("CSV файлында баған тақырыптары жоқ.")
                    raw_items = list(reader)
        except json.JSONDecodeError as exc:
            raise DataManagerError(f"JSON құрылымы бүлінген: {exc}") from exc
        except OSError as exc:
            raise DataManagerError(f"Файлды оқу кезінде жүйелік қате: {exc}") from exc

        valid_records: list[dict[str, Any]] = []
        skipped_count = 0
        seen_ids: set[str] = set()

        for item in raw_items:
            try:
                normalized = self._normalize_loaded_item(item)
                sid = normalized["id"]
                if sid in seen_ids:
                    skipped_count += 1
                    continue
                seen_ids.add(sid)
                valid_records.append(normalized)
            except (ValueError, DataManagerError):
                skipped_count += 1

        if skipped_count > 0:
            warning = (
                f"Файлдан {len(valid_records)} жарамды жазба оқылды, "
                f"{skipped_count} қате немесе қайталанған жол өткізілді."
            )

        self.records = valid_records
        return self.records, warning

    def save_to_file(self, filepath: str | None = None) -> str:
        target = filepath or self.filepath
        self.filepath = target
        ext = os.path.splitext(target)[1].lower()

        if ext not in self.ALLOWED_EXTENSIONS:
            raise DataManagerError("Файлды .json немесе .csv кеңейтімімен сақтаңыз.")

        parent_dir = os.path.dirname(os.path.abspath(target))
        if parent_dir and not os.path.exists(parent_dir):
            try:
                os.makedirs(parent_dir, exist_ok=True)
            except OSError as exc:
                raise DataManagerError(f"Каталог құру мүмкін болмады: {exc}") from exc

        try:
            if ext == ".json":
                with open(target, "w", encoding="utf-8") as f:
                    json.dump(self.records, f, ensure_ascii=False, indent=2)
            else:
                with open(target, "w", encoding="utf-8-sig", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=self.CSV_FIELDS, extrasaction="ignore")
                    writer.writeheader()
                    writer.writerows(self.records)
        except OSError as exc:
            raise DataManagerError(f"Файлға жазу кезінде қате: {exc}") from exc

        return target


class StudentAppUI:
    """Студенттердің үлгерімін талдау жүйесінің Tkinter интерфейсі."""

    COLUMNS = (
        ("id", "ID", 95, "center"),
        ("full_name", "Аты-жөні", 210, "w"),
        ("group_name", "Тобы", 105, "center"),
        ("grade1", "1-бақ.", 75, "e"),
        ("grade2", "2-бақ.", 75, "e"),
        ("grade3", "3-бақ.", 75, "e"),
        ("attendance", "Қатысу %", 90, "e"),
        ("avg_grade", "Орташа балл", 105, "e"),
        ("risk_status", "Мәртебесі", 125, "center"),
    )

    def __init__(self, root: tk.Tk, manager: StudentDataManager) -> None:
        self.root = root
        self.manager = manager
        self.root.title("Студенттердің үлгерімін талдау жүйесі (1-нұсқа)")
        self.root.geometry("1220x740")
        self.root.minsize(1020, 620)

        self.selected_original_id: str | None = None
        self.sort_column: str = "id"
        self.sort_descending: bool = False
        self.current_view_records: list[dict[str, Any]] = []

        self._configure_styles()
        self._build_menu()
        self._build_layout()
        self._bind_shortcuts()

        self._initial_load()

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("Section.TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", rowheight=26, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Ашу (JSON / CSV)...", accelerator="Ctrl+O", command=self.open_file_dialog)
        file_menu.add_command(label="Сақтау", accelerator="Ctrl+S", command=self.save_data)
        file_menu.add_command(label="Басқаша сақтау...", command=self.save_as_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="26 тест жазбасын қалпына келтіру", command=self.restore_seed_data)
        file_menu.add_separator()
        file_menu.add_command(label="Шығу", command=self.on_close)
        menubar.add_cascade(label="Файл", menu=file_menu)

        analytics_menu = tk.Menu(menubar, tearoff=0)
        analytics_menu.add_command(label="Статистика терезесі", accelerator="Ctrl+T", command=self.open_statistics_window)
        analytics_menu.add_command(label="Үздік 3 студент", command=self.open_top_students_window)
        menubar.add_cascade(label="Талдау", menu=analytics_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Пернетақта тіркесімдері", command=self.show_shortcuts_help)
        menubar.add_cascade(label="Анықтама", menu=help_menu)

        self.root.config(menu=menubar)

    def _build_layout(self) -> None:
        top_bar = ttk.Frame(self.root, padding=(12, 8, 12, 4))
        top_bar.pack(fill=tk.X)

        ttk.Label(
            top_bar,
            text="Студенттердің үлгерімін талдау жүйесі (1-нұсқа)",
            style="Title.TLabel",
        ).pack(side=tk.LEFT)

        ttk.Button(top_bar, text="Статистика терезесі", command=self.open_statistics_window).pack(
            side=tk.RIGHT, padx=(6, 0)
        )
        ttk.Button(top_bar, text="Үздік 3 студент", command=self.open_top_students_window).pack(
            side=tk.RIGHT, padx=(6, 0)
        )
        ttk.Button(top_bar, text="Файлға сақтау", command=self.save_data).pack(side=tk.RIGHT)

        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        left_frame = ttk.Labelframe(
            main_pane, text="Студент деректерін енгізу / өңдеу", style="Section.TLabelframe", padding=10
        )
        right_frame = ttk.Frame(main_pane)

        main_pane.add(left_frame, weight=1)
        main_pane.add(right_frame, weight=3)

        self._build_form(left_frame)
        self._build_filter_bar(right_frame)
        self._build_table(right_frame)
        self._build_summary_strip(right_frame)

        self.status_var = tk.StringVar(value="Дайын.")
        status_bar = ttk.Frame(self.root, relief=tk.SUNKEN, padding=(10, 4))
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Label(status_bar, textvariable=self.status_var).pack(side=tk.LEFT)

    def _build_form(self, parent: ttk.Labelframe) -> None:
        self.vars: dict[str, tk.StringVar] = {
            "id": tk.StringVar(),
            "full_name": tk.StringVar(),
            "group_name": tk.StringVar(),
            "grade1": tk.StringVar(),
            "grade2": tk.StringVar(),
            "grade3": tk.StringVar(),
            "attendance": tk.StringVar(),
        }

        fields = [
            ("ID:", "id"),
            ("Аты-жөні:", "full_name"),
            ("Тобы:", "group_name"),
            ("1-бақылау (0-100):", "grade1"),
            ("2-бақылау (0-100):", "grade2"),
            ("3-бақылау (0-100):", "grade3"),
            ("Қатысу % (0-100):", "attendance"),
        ]

        for row_idx, (label_text, key) in enumerate(fields):
            ttk.Label(parent, text=label_text).grid(row=row_idx, column=0, sticky=tk.W, pady=5, padx=(0, 6))
            entry = ttk.Entry(parent, textvariable=self.vars[key], width=24)
            entry.grid(row=row_idx, column=1, sticky=tk.EW, pady=5)
            if key == "id":
                self.id_entry = entry
            for score_key in ("grade1", "grade2", "grade3", "attendance"):
                self.vars[score_key].trace_add("write", lambda *_: self._update_live_preview())

        parent.columnconfigure(1, weight=1)

        preview_box = ttk.Labelframe(parent, text="Автоматты есептеу", padding=8)
        preview_box.grid(row=len(fields), column=0, columnspan=2, sticky=tk.EW, pady=(10, 8))

        self.preview_avg_var = tk.StringVar(value="Орташа балл: —")
        self.preview_risk_var = tk.StringVar(value="Мәртебесі: —")

        ttk.Label(preview_box, textvariable=self.preview_avg_var, font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        ttk.Label(preview_box, textvariable=self.preview_risk_var, font=("Segoe UI", 9, "bold")).pack(
            anchor=tk.W, pady=(2, 0)
        )

        btn_row1 = ttk.Frame(parent)
        btn_row1.grid(row=len(fields) + 1, column=0, columnspan=2, sticky=tk.EW, pady=(4, 4))
        btn_row1.columnconfigure((0, 1), weight=1)

        ttk.Button(btn_row1, text="Қосу (Ctrl+N)", command=self.add_student).grid(
            row=0, column=0, sticky=tk.EW, padx=(0, 3)
        )
        ttk.Button(btn_row1, text="Өзгерту", command=self.update_student).grid(
            row=0, column=1, sticky=tk.EW, padx=(3, 0)
        )

        btn_row2 = ttk.Frame(parent)
        btn_row2.grid(row=len(fields) + 2, column=0, columnspan=2, sticky=tk.EW, pady=(0, 6))
        btn_row2.columnconfigure((0, 1), weight=1)

        ttk.Button(btn_row2, text="Жою (Del)", command=self.delete_student).grid(
            row=0, column=0, sticky=tk.EW, padx=(0, 3)
        )
        ttk.Button(btn_row2, text="Тазарту (Esc)", command=self.clear_form).grid(
            row=0, column=1, sticky=tk.EW, padx=(3, 0)
        )

        hint = (
            "Шарттар:\n"
            "• Орташа балл = (1-бақ + 2-бақ + 3-бақ) / 3\n"
            "• Тәуекел тобы: орташа < 50 немесе қатысу < 70%"
        )
        ttk.Label(parent, text=hint, foreground="#444444", font=("Segoe UI", 8)).grid(
            row=len(fields) + 3, column=0, columnspan=2, sticky=tk.W, pady=(6, 0)
        )

    def _build_filter_bar(self, parent: ttk.Frame) -> None:
        filter_box = ttk.Labelframe(
            parent, text="Іздеу және сүзгілеу (ID, Аты-жөні, Тобы, Баға диапазоны)", padding=8
        )
        filter_box.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(filter_box, text="Іздеу:").grid(row=0, column=0, sticky=tk.W, padx=(0, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_table())
        ttk.Entry(filter_box, textvariable=self.search_var, width=22).grid(row=0, column=1, padx=(0, 10))

        ttk.Label(filter_box, text="Топ:").grid(row=0, column=2, sticky=tk.W, padx=(0, 4))
        self.group_filter_var = tk.StringVar(value="Барлығы")
        self.group_combo = ttk.Combobox(
            filter_box, textvariable=self.group_filter_var, values=["Барлығы"], state="readonly", width=13
        )
        self.group_combo.grid(row=0, column=3, padx=(0, 10))
        self.group_combo.bind("<<ComboboxSelected>>", lambda *_: self.refresh_table())

        ttk.Label(filter_box, text="Орташа балл:").grid(row=0, column=4, sticky=tk.W, padx=(0, 4))
        self.min_avg_var = tk.StringVar()
        self.max_avg_var = tk.StringVar()
        self.min_avg_var.trace_add("write", lambda *_: self.refresh_table())
        self.max_avg_var.trace_add("write", lambda *_: self.refresh_table())

        ttk.Entry(filter_box, textvariable=self.min_avg_var, width=6).grid(row=0, column=5)
        ttk.Label(filter_box, text="–").grid(row=0, column=6, padx=2)
        ttk.Entry(filter_box, textvariable=self.max_avg_var, width=6).grid(row=0, column=7, padx=(0, 10))

        self.risk_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            filter_box,
            text="Тек тәуекел тобы",
            variable=self.risk_only_var,
            command=self.refresh_table,
        ).grid(row=0, column=8, padx=(0, 8))

        ttk.Button(filter_box, text="Сүзгіні тазарту", command=self.reset_filters).grid(row=0, column=9)

    def _build_table(self, parent: ttk.Frame) -> None:
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill=tk.BOTH, expand=True)

        col_ids = [c[0] for c in self.COLUMNS]
        self.tree = ttk.Treeview(table_frame, columns=col_ids, show="headings", selectmode="browse")

        for col_id, heading_text, width, anchor in self.COLUMNS:
            self.tree.heading(
                col_id,
                text=heading_text,
                command=lambda c=col_id: self.on_sort_column(c),
            )
            self.tree.column(col_id, width=width, minwidth=65, anchor=anchor)

        self.tree.tag_configure("risk", background="#fdecea", foreground="#991b1b")
        self.tree.tag_configure("normal", background="#ffffff", foreground="#111827")

        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky=tk.NSEW)
        vsb.grid(row=0, column=1, sticky=tk.NS)
        hsb.grid(row=1, column=0, sticky=tk.EW)

        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)

    def _build_summary_strip(self, parent: ttk.Frame) -> None:
        strip = ttk.Labelframe(parent, text="Жалпы көрсеткіштер (қорытынды)", padding=8)
        strip.pack(fill=tk.X, pady=(6, 0))

        self.summary_var = tk.StringVar(value="Жазба саны: 0")
        ttk.Label(strip, textvariable=self.summary_var, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-n>", lambda _e: self.add_student())
        self.root.bind("<Control-N>", lambda _e: self.add_student())
        self.root.bind("<Control-s>", lambda _e: self.save_data())
        self.root.bind("<Control-S>", lambda _e: self.save_data())
        self.root.bind("<Control-o>", lambda _e: self.open_file_dialog())
        self.root.bind("<Control-O>", lambda _e: self.open_file_dialog())
        self.root.bind("<Control-t>", lambda _e: self.open_statistics_window())
        self.root.bind("<Control-T>", lambda _e: self.open_statistics_window())
        self.root.bind("<Escape>", lambda _e: self.clear_form())
        self.tree.bind("<Delete>", lambda _e: self.delete_student())

    def _initial_load(self) -> None:
        try:
            _, warning = self.manager.load_from_file()
            self._update_group_filter_values()
            self.refresh_table()
            if warning:
                self.set_status(warning)
                messagebox.showwarning("Файл ескертуі", warning)
            else:
                self.set_status(f"'{self.manager.filepath}' файлынан {len(self.manager.records)} жазба жүктелді.")
        except DataManagerError as exc:
            self.manager.records = self.manager.generate_seed_data(26)
            self._update_group_filter_values()
            self.refresh_table()
            msg = f"Файлды оқу кезінде қате шықты: {exc}\n26 тест жазбасы жадыға жүктелді."
            self.set_status(msg.splitlines()[0])
            messagebox.showerror("Файл қатесі", msg)

    def set_status(self, message: str) -> None:
        self.status_var.set(message)

    def _update_group_filter_values(self) -> None:
        current = self.group_filter_var.get()
        groups = self.manager.get_groups()
        self.group_combo["values"] = groups
        if current not in groups:
            self.group_filter_var.set("Барлығы")

    def _update_live_preview(self) -> None:
        def try_float(s: str) -> float | None:
            txt = s.strip().replace(",", ".")
            if not txt:
                return None
            try:
                return float(txt)
            except ValueError:
                return None

        g1 = try_float(self.vars["grade1"].get())
        g2 = try_float(self.vars["grade2"].get())
        g3 = try_float(self.vars["grade3"].get())
        att = try_float(self.vars["attendance"].get())

        if g1 is not None and g2 is not None and g3 is not None:
            avg_val = self.manager.calculate_average(g1, g2, g3)
            self.preview_avg_var.set(f"Орташа балл: {avg_val:.2f}")
            if att is not None:
                risk = self.manager.determine_risk(avg_val, att)
                self.preview_risk_var.set(f"Мәртебесі: {risk}")
            else:
                self.preview_risk_var.set("Мәртебесі: қатысу % енгізіңіз")
        else:
            self.preview_avg_var.set("Орташа балл: —")
            self.preview_risk_var.set("Мәртебесі: —")

    def _parse_bound(self, raw: str, label: str) -> float | None:
        txt = raw.strip().replace(",", ".")
        if not txt:
            return None
        try:
            val = float(txt)
        except ValueError as exc:
            raise ValueError(f"'{label}' сүзгісіне дұрыс сан енгізіңіз.") from exc
        if val < 0 or val > 100:
            raise ValueError(f"'{label}' сүзгісі 0 мен 100 аралығында болуы керек.")
        return val

    def refresh_table(self) -> None:
        try:
            min_avg = self._parse_bound(self.min_avg_var.get(), "Төменгі орташа балл")
            max_avg = self._parse_bound(self.max_avg_var.get(), "Жоғарғы орташа балл")
        except ValueError as exc:
            self.set_status(str(exc))
            return

        filtered = self.manager.search_and_filter(
            query=self.search_var.get(),
            group_filter=self.group_filter_var.get(),
            min_avg=min_avg,
            max_avg=max_avg,
            risk_only=self.risk_only_var.get(),
        )
        sorted_list = self.manager.sort_records(
            filtered, key=self.sort_column, descending=self.sort_descending
        )
        self.current_view_records = sorted_list

        for row_id in self.tree.get_children():
            self.tree.delete(row_id)

        for rec in sorted_list:
            tag = "risk" if rec["risk_status"] == "Тәуекел тобы" else "normal"
            values = (
                rec["id"],
                rec["full_name"],
                rec["group_name"],
                f"{rec['grade1']:.1f}",
                f"{rec['grade2']:.1f}",
                f"{rec['grade3']:.1f}",
                f"{rec['attendance']:.1f}%",
                f"{rec['avg_grade']:.2f}",
                rec["risk_status"],
            )
            self.tree.insert("", tk.END, iid=str(rec["id"]), values=values, tags=(tag,))

        stats = self.manager.get_statistics()
        self.summary_var.set(
            f"Жалпы жазба: {stats['total']}  |  Көрсетілгені: {len(sorted_list)}  |  "
            f"Жалпы орташа балл: {stats['overall_avg']:.2f}  |  "
            f"Тәуекел тобы: {stats['risk_count']} ({stats['risk_percent']:.1f}%)"
        )

    def on_sort_column(self, col_id: str) -> None:
        if self.sort_column == col_id:
            self.sort_descending = not self.sort_descending
        else:
            self.sort_column = col_id
            self.sort_descending = False

        for cid, heading_text, _, _ in self.COLUMNS:
            arrow = ""
            if cid == self.sort_column:
                arrow = " ↓" if self.sort_descending else " ↑"
            self.tree.heading(cid, text=f"{heading_text}{arrow}")

        self.refresh_table()
        direction_label = "кему" if self.sort_descending else "өсу"
        self.set_status(f"'{col_id}' бағаны бойынша {direction_label} ретімен сұрыпталды.")

    def on_row_select(self, _event: Any = None) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        sid = selected[0]
        rec = next((r for r in self.manager.records if str(r["id"]) == sid), None)
        if rec is None:
            return

        self.selected_original_id = str(rec["id"])
        self.vars["id"].set(str(rec["id"]))
        self.vars["full_name"].set(str(rec["full_name"]))
        self.vars["group_name"].set(str(rec["group_name"]))
        self.vars["grade1"].set(str(rec["grade1"]))
        self.vars["grade2"].set(str(rec["grade2"]))
        self.vars["grade3"].set(str(rec["grade3"]))
        self.vars["attendance"].set(str(rec["attendance"]))
        self._update_live_preview()
        self.set_status(f"'{rec['full_name']}' ({rec['id']}) жазбасы таңдалды.")

    def clear_form(self) -> None:
        self.selected_original_id = None
        for var in self.vars.values():
            var.set("")
        self.tree.selection_remove(self.tree.selection())
        self.id_entry.focus_set()
        self._update_live_preview()
        self.set_status("Форма өрістері тазартылды.")

    def reset_filters(self) -> None:
        self.search_var.set("")
        self.group_filter_var.set("Барлығы")
        self.min_avg_var.set("")
        self.max_avg_var.set("")
        self.risk_only_var.set(False)
        self.refresh_table()
        self.set_status("Іздеу және сүзгі параметрлері тазартылды.")

    def add_student(self) -> None:
        try:
            record = self.manager.validate_record(
                student_id=self.vars["id"].get(),
                full_name=self.vars["full_name"].get(),
                group_name=self.vars["group_name"].get(),
                g1_raw=self.vars["grade1"].get(),
                g2_raw=self.vars["grade2"].get(),
                g3_raw=self.vars["grade3"].get(),
                attendance_raw=self.vars["attendance"].get(),
                editing_original_id=None,
            )
            self.manager.add_record(record)
            self._update_group_filter_values()
            self.refresh_table()
            self.clear_form()
            msg = f"Жаңа студент қосылды: {record['full_name']} (Орташа: {record['avg_grade']:.2f})"
            self.set_status(msg)
        except ValueError as exc:
            messagebox.showwarning("Валидация қатесі", str(exc))
            self.set_status(f"Қате: {exc}")

    def update_student(self) -> None:
        if not self.selected_original_id:
            messagebox.showinfo("Ақпарат", "Өзгерту үшін кестеден студент жазбасын таңдаңыз.")
            return

        try:
            updated = self.manager.validate_record(
                student_id=self.vars["id"].get(),
                full_name=self.vars["full_name"].get(),
                group_name=self.vars["group_name"].get(),
                g1_raw=self.vars["grade1"].get(),
                g2_raw=self.vars["grade2"].get(),
                g3_raw=self.vars["grade3"].get(),
                attendance_raw=self.vars["attendance"].get(),
                editing_original_id=self.selected_original_id,
            )
            self.manager.update_record(self.selected_original_id, updated)
            self._update_group_filter_values()
            self.refresh_table()
            self.selected_original_id = updated["id"]
            msg = f"'{updated['full_name']}' жазбасы жаңартылды."
            self.set_status(msg)
            messagebox.showinfo("Сәтті", msg)
        except (ValueError, DataManagerError) as exc:
            messagebox.showwarning("Өзгерту қатесі", str(exc))
            self.set_status(f"Қате: {exc}")

    def delete_student(self) -> None:
        selected = self.tree.selection()
        target_id = selected[0] if selected else self.selected_original_id
        if not target_id:
            messagebox.showinfo("Ақпарат", "Жою үшін кестеден жазба таңдаңыз.")
            return

        rec = next((r for r in self.manager.records if str(r["id"]) == target_id), None)
        display_name = f"{rec['full_name']} ({target_id})" if rec else target_id

        confirmed = messagebox.askyesno(
            "Жоюды растау",
            f"'{display_name}' жазбасын шынымен жойғыңыз келе ме?",
        )
        if not confirmed:
            return

        try:
            self.manager.delete_record(target_id)
            self._update_group_filter_values()
            self.refresh_table()
            if self.selected_original_id == target_id:
                self.clear_form()
            msg = f"'{display_name}' жазбасы жойылды."
            self.set_status(msg)
        except DataManagerError as exc:
            messagebox.showerror("Жою қатесі", str(exc))

    def save_data(self) -> None:
        try:
            saved_path = self.manager.save_to_file()
            msg = f"Деректер '{saved_path}' файлына сақталды ({len(self.manager.records)} жазба)."
            self.set_status(msg)
            messagebox.showinfo("Сақталды", msg)
        except DataManagerError as exc:
            self.set_status(f"Сақтау қатесі: {exc}")
            messagebox.showerror("Сақтау қатесі", str(exc))

    def save_as_dialog(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Деректерді сақтау",
            defaultextension=".json",
            filetypes=[("JSON файлы", "*.json"), ("CSV файлы", "*.csv")],
        )
        if not path:
            return
        try:
            saved_path = self.manager.save_to_file(path)
            msg = f"Деректер '{saved_path}' файлына сақталды."
            self.set_status(msg)
            messagebox.showinfo("Сақталды", msg)
        except DataManagerError as exc:
            self.set_status(f"Сақтау қатесі: {exc}")
            messagebox.showerror("Сақтау қатесі", str(exc))

    def open_file_dialog(self) -> None:
        path = filedialog.askopenfilename(
            title="Деректер файлын ашу",
            filetypes=[("JSON және CSV файлдары", "*.json *.csv"), ("JSON", "*.json"), ("CSV", "*.csv")],
        )
        if not path:
            return
        try:
            _, warning = self.manager.load_from_file(path)
            self._update_group_filter_values()
            self.refresh_table()
            self.clear_form()
            if warning:
                self.set_status(warning)
                messagebox.showwarning("Файл ескертуі", warning)
            else:
                msg = f"'{path}' файлынан {len(self.manager.records)} жазба жүктелді."
                self.set_status(msg)
                messagebox.showinfo("Жүктелді", msg)
        except DataManagerError as exc:
            self.set_status(f"Ашу қатесі: {exc}")
            messagebox.showerror("Файлды ашу қатесі", str(exc))

    def restore_seed_data(self) -> None:
        if not messagebox.askyesno(
            "Тест деректері",
            "Ағымдағы тізімді 26 дайын тест жазбасымен алмастырғыңыз келе ме?",
        ):
            return
        self.manager.records = self.manager.generate_seed_data(26)
        self._update_group_filter_values()
        self.refresh_table()
        self.clear_form()
        self.set_status("26 тест жазбасы жүктелді.")

    def open_statistics_window(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Үлгерім және тәуекел статистикасы")
        win.geometry("560x420")
        win.transient(self.root)
        win.grab_set()

        stats = self.manager.get_statistics()

        frame = ttk.Frame(win, padding=14)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Жалпы статистикалық көрсеткіштер", font=("Segoe UI", 12, "bold")).pack(
            anchor=tk.W, pady=(0, 10)
        )

        metrics_lines = [
            f"Студенттердің жалпы саны: {stats['total']}",
            f"Жалпы орташа балл: {stats['overall_avg']:.2f}",
            f"Орташа қатысу пайызы: {stats['avg_attendance']:.1f}%",
            f"Тәуекел тобындағы студенттер: {stats['risk_count']} ({stats['risk_percent']:.1f}%)",
            f"Қалыпты үлгерімдегі студенттер: {stats['passed_count']}",
        ]
        for line in metrics_lines:
            ttk.Label(frame, text=line, font=("Segoe UI", 10)).pack(anchor=tk.W, pady=2)

        ttk.Label(frame, text="Топтар бойынша орташа балл:", font=("Segoe UI", 10, "bold")).pack(
            anchor=tk.W, pady=(12, 4)
        )

        grp_tree = ttk.Treeview(frame, columns=("group", "count", "avg"), show="headings", height=7)
        grp_tree.heading("group", text="Топ")
        grp_tree.heading("count", text="Студент саны")
        grp_tree.heading("avg", text="Орташа балл")
        grp_tree.column("group", width=150, anchor="center")
        grp_tree.column("count", width=130, anchor="center")
        grp_tree.column("avg", width=140, anchor="e")
        grp_tree.pack(fill=tk.BOTH, expand=True)

        for g in stats["group_stats"]:
            grp_tree.insert("", tk.END, values=(g["group"], g["count"], f"{g['avg']:.2f}"))

        ttk.Button(frame, text="Жабу", command=win.destroy).pack(anchor=tk.E, pady=(10, 0))

    def open_top_students_window(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Үздік 3 студент")
        win.geometry("620x280")
        win.transient(self.root)
        win.grab_set()

        frame = ttk.Frame(win, padding=14)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text="Орташа баллы ең жоғары үздік 3 студент",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor=tk.W, pady=(0, 10))

        top_list = self.manager.get_top_students(3)
        top_tree = ttk.Treeview(
            frame,
            columns=("rank", "id", "name", "group", "avg", "att"),
            show="headings",
            height=4,
        )
        headers = [
            ("rank", "Орын", 70, "center"),
            ("id", "ID", 95, "center"),
            ("name", "Аты-жөні", 210, "w"),
            ("group", "Тобы", 100, "center"),
            ("avg", "Орташа балл", 100, "e"),
            ("att", "Қатысу %", 90, "e"),
        ]
        for cid, htext, w, anc in headers:
            top_tree.heading(cid, text=htext)
            top_tree.column(cid, width=w, anchor=anc)
        top_tree.pack(fill=tk.BOTH, expand=True)

        for idx, st in enumerate(top_list, start=1):
            top_tree.insert(
                "",
                tk.END,
                values=(
                    f"#{idx}",
                    st["id"],
                    st["full_name"],
                    st["group_name"],
                    f"{st['avg_grade']:.2f}",
                    f"{st['attendance']:.1f}%",
                ),
            )

        ttk.Button(frame, text="Жабу", command=win.destroy).pack(anchor=tk.E, pady=(10, 0))

    def show_shortcuts_help(self) -> None:
        info = (
            "Пернетақта тіркесімдері:\n"
            "• Ctrl+N — Жаңа студент жазбасын қосу\n"
            "• Ctrl+S — Деректерді файлға сақтау\n"
            "• Ctrl+O — JSON / CSV файлын ашу\n"
            "• Ctrl+T — Статистика терезесін ашу\n"
            "• Delete — Таңдалған жолды жою\n"
            "• Esc — Форма өрістерін тазарту"
        )
        messagebox.showinfo("Пернетақта тіркесімдері", info)

    def on_close(self) -> None:
        try:
            self.manager.save_to_file()
        except DataManagerError as exc:
            if not messagebox.askyesno(
                "Сақтау қатесі",
                f"Шығар алдында сақтау сәтсіз аяқталды:\n{exc}\n\nБағдарламаны бәрібір жабу керек пе?",
            ):
                return
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    manager = StudentDataManager(filepath="students_data.json")
    app = StudentAppUI(root, manager)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
