from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.logger import get_logger

logger = get_logger("excel_writer")

# ── Colours ───────────────────────────────────────────────────────────────────
_HDR_BG = "1F3864"   # dark navy — title row
_HDR_FG = "FFFFFF"
_EMP_BG = "2E75B6"   # blue — employee header row
_EMP_FG = "FFFFFF"
_DATE_BG = "1F3864"  # dark navy — date column
_DATE_FG = "FFFFFF"
_ROW_A   = "EBF3FB"  # light blue alternating row
_ROW_B   = "FFFFFF"

_THIN   = Side(style="thin", color="B0BEC5")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def _fill(hex_color: str) -> PatternFill:
    return PatternFill("solid", fgColor=hex_color)


def _font(bold=False, color="000000", size=10) -> Font:
    return Font(bold=bold, color=color, size=size, name="Calibri")


def _normalize_day(raw_date: str) -> str:
    """Return YYYY-MM-DD from any reasonable date string."""
    raw = str(raw_date).strip()
    if " " in raw:
        raw = raw.split(" ")[0]
    if "T" in raw:
        raw = raw.split("T")[0]
    day = raw[:10]
    parts = day.split("-")
    # DD-MM-YYYY → YYYY-MM-DD
    if len(parts) == 3 and len(parts[0]) == 2 and len(parts[2]) == 4:
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return day


def _day_label(iso: str) -> str:
    """YYYY-MM-DD → '08 Sep 2026'"""
    try:
        return date.fromisoformat(iso).strftime("%d %b %Y")
    except Exception:
        return iso


class ExcelWriter:
    def __init__(self, file_path: str) -> None:
        self.file_path = Path(file_path).expanduser()
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Public entry point ────────────────────────────────────────────────────
    def write_tasks(self, rows: list[dict]) -> None:
        if not rows:
            logger.info("No task rows to write to Excel.")
            return

        # Structure: { "YYYY-MM-DD": { "Employee": ["task1", "task2", ...] } }
        data: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

        for r in rows:
            day      = _normalize_day(r.get("date") or r.get("created_at") or date.today().isoformat())
            assignee = str(r.get("assignee") or "Unknown").strip()
            task     = str(r.get("task") or "").strip()

            for line in task.splitlines():
                line = line.strip().lstrip("•").strip()
                if line:
                    data[day][assignee].append(line)

        target = self.file_path
        temp   = target.with_suffix(".tmp.xlsx")

        wb = load_workbook(target) if target.exists() else Workbook()
        if "Sheet" in wb.sheetnames:
            del wb["Sheet"]

        # Remove old summary sheet so we rebuild it fresh
        if "Task Summary" in wb.sheetnames:
            del wb["Task Summary"]

        ws = wb.create_sheet(title="Task Summary", index=0)
        self._write_summary_sheet(ws, data)

        wb.active = wb["Task Summary"]

        wb.save(temp)
        temp.replace(target)
        logger.info("Excel workbook updated: %s", target)

    # ── Sheet builder ─────────────────────────────────────────────────────────
    def _write_summary_sheet(
        self,
        ws,
        data: dict[str, dict[str, list[str]]],
    ) -> None:
        """
        Layout:
          Row 1  : Title (merged across all columns)
          Row 2  : "Date" | Employee1 | Employee2 | ...
          Row 3+ : <date label> | tasks for emp1 | tasks for emp2 | ...
        """
        # Sorted dates and employees
        sorted_dates     = sorted(data.keys())
        all_employees    = sorted({emp for day in data.values() for emp in day})
        n_emp            = len(all_employees)
        total_cols       = 1 + n_emp           # date col + one per employee

        # ── Row 1: Title ──────────────────────────────────────────────────────
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_cols)
        title_cell = ws.cell(row=1, column=1, value="TenBit Daily Task Report")
        title_cell.fill      = _fill(_HDR_BG)
        title_cell.font      = _font(bold=True, color=_HDR_FG, size=14)
        title_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 30

        # ── Row 2: Headers (Date + employees) ────────────────────────────────
        date_hdr = ws.cell(row=2, column=1, value="Date")
        date_hdr.fill      = _fill(_DATE_BG)
        date_hdr.font      = _font(bold=True, color=_DATE_FG, size=10)
        date_hdr.alignment = Alignment(horizontal="center", vertical="center")
        date_hdr.border    = _BORDER

        for col_idx, emp in enumerate(all_employees, start=2):
            c = ws.cell(row=2, column=col_idx, value=emp)
            c.fill      = _fill(_EMP_BG)
            c.font      = _font(bold=True, color=_EMP_FG, size=10)
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            c.border    = _BORDER

        ws.row_dimensions[2].height = 20

        # ── Date column width & employee column width ─────────────────────────
        ws.column_dimensions["A"].width = 14
        for col_idx in range(2, total_cols + 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = 28

        # ── Data rows ─────────────────────────────────────────────────────────
        for row_idx, day in enumerate(sorted_dates, start=3):
            bg = _ROW_A if row_idx % 2 == 0 else _ROW_B

            # Date cell
            c = ws.cell(row=row_idx, column=1, value=_day_label(day))
            c.fill      = _fill(_DATE_BG)
            c.font      = _font(bold=True, color=_DATE_FG, size=10)
            c.alignment = Alignment(horizontal="center", vertical="top")
            c.border    = _BORDER

            max_lines = 1
            for col_idx, emp in enumerate(all_employees, start=2):
                tasks = data[day].get(emp, [])
                cell_text = "\n".join(f"• {t}" for t in tasks) if tasks else ""
                max_lines = max(max_lines, len(tasks))

                c = ws.cell(row=row_idx, column=col_idx, value=cell_text)
                c.fill      = _fill(bg)
                c.font      = _font(size=10)
                c.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
                c.border    = _BORDER

            # Row height based on busiest employee that day
            ws.row_dimensions[row_idx].height = max(18, min(max_lines * 16, 250))

        ws.freeze_panes = "B3"   # freeze date column + header rows
