from __future__ import annotations

from datetime import date
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.logger import get_logger

logger = get_logger("excel_writer")

# ── Colour palette ────────────────────────────────────────────────────────────
_HEADER_BG   = "1F3864"   # dark blue
_HEADER_FG   = "FFFFFF"
_DATE_BG     = "2E75B6"   # mid blue  (date section header)
_DATE_FG     = "FFFFFF"
_NAME_BG     = "D6E4F0"   # light blue (person row)
_ALT_BG      = "F2F8FF"   # very light blue alternating task row
_WHITE       = "FFFFFF"

_STATUS_COLORS = {
    "completed":   ("C6EFCE", "375623"),   # green
    "in_progress": ("FFEB9C", "9C5700"),   # amber
    "open":        ("DDEBF7", "1F3864"),   # blue
    "blocked":     ("FFC7CE", "9C0006"),   # red
    "review":      ("E2EFDA", "375623"),   # light green
}

_PRIORITY_COLORS = {
    "urgent": ("FF0000", "FFFFFF"),
    "high":   ("FF9900", "FFFFFF"),
    "medium": ("4472C4", "FFFFFF"),
    "low":    ("70AD47", "FFFFFF"),
}

_THIN = Side(style="thin", color="B0BEC5")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def _fill(hex_color: str) -> PatternFill:
    return PatternFill("solid", fgColor=hex_color)


def _font(bold=False, color="000000", size=10) -> Font:
    return Font(bold=bold, color=color, size=size, name="Calibri")


def _badge_cell(ws, row: int, col: int, value: str, colors: dict) -> None:
    bg, fg = colors.get(str(value).lower(), ("E0E0E0", "333333"))
    cell = ws.cell(row=row, column=col, value=str(value).replace("_", " ").title())
    cell.fill = _fill(bg)
    cell.font = _font(bold=True, color=fg, size=9)
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border = _BORDER


class ExcelWriter:
    def __init__(self, file_path: str) -> None:
        self.file_path = Path(file_path).expanduser()
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def write_tasks(self, rows: list[dict]) -> None:
        if not rows:
            logger.info("No task rows to write to Excel.")
            return

        # Group rows by date then by assignee
        from collections import defaultdict
        by_date: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
        for r in rows:
            day = str(r.get("date") or r.get("message_timestamp") or date.today().isoformat())[:10]
            # Use just the date part if it's a datetime string
            if "T" in day:
                day = day[:10]
            assignee = str(r.get("assignee") or "Unknown")
            by_date[day][assignee].append(r)

        target = self.file_path
        temp = target.with_suffix(".tmp.xlsx")

        # Use existing workbook or create new
        if target.exists():
            wb = load_workbook(target)
        else:
            wb = Workbook()
            # Remove default sheet
            if "Sheet" in wb.sheetnames:
                del wb["Sheet"]

        # One sheet per date — named by date e.g. "09-Sep-2026"
        for day_str in sorted(by_date.keys()):
            try:
                sheet_name = date.fromisoformat(day_str).strftime("%d-%b-%Y")
            except Exception:
                sheet_name = day_str[:10]

            # Remove existing sheet for this date to rebuild clean
            if sheet_name in wb.sheetnames:
                del wb[sheet_name]

            ws = wb.create_sheet(title=sheet_name)
            self._write_day_sheet(ws, sheet_name, by_date[day_str])

        # Make newest date the active sheet
        if wb.sheetnames:
            wb.active = wb[wb.sheetnames[-1]]

        wb.save(temp)
        temp.replace(target)
        logger.info("Excel workbook updated successfully: %s", target)

    def _write_day_sheet(self, ws, date_label: str, by_person: dict[str, list[dict]]) -> None:
        """Write one day's tasks — grouped by person."""

        # ── Column widths ────────────────────────────────────────────────────
        col_widths = {1: 22, 2: 55, 3: 14, 4: 12, 5: 14}
        for col, width in col_widths.items():
            ws.column_dimensions[get_column_letter(col)].width = width

        # ── Main header row ──────────────────────────────────────────────────
        ws.merge_cells("A1:E1")
        title_cell = ws["A1"]
        title_cell.value = f"Daily Task Report — {date_label}"
        title_cell.fill = _fill(_HEADER_BG)
        title_cell.font = _font(bold=True, color=_HEADER_FG, size=13)
        title_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 28

        # ── Column labels ────────────────────────────────────────────────────
        headers = ["Team Member", "Task", "Status", "Priority", "Deadline"]
        for col, hdr in enumerate(headers, 1):
            cell = ws.cell(row=2, column=col, value=hdr)
            cell.fill = _fill(_DATE_BG)
            cell.font = _font(bold=True, color=_DATE_FG, size=10)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = _BORDER
        ws.row_dimensions[2].height = 18

        current_row = 3
        alt = False

        for person in sorted(by_person.keys()):
            tasks = by_person[person]

            # Person name spans all their task rows in column A
            name_start = current_row
            for i, task in enumerate(tasks):
                bg = _ALT_BG if alt else _WHITE
                alt = not alt

                # Col A: person name — only fill on first row, merge later
                ws.cell(row=current_row, column=1, value=person if i == 0 else "")
                ws.cell(row=current_row, column=1).fill = _fill(_NAME_BG)
                ws.cell(row=current_row, column=1).font = _font(bold=(i == 0), size=10)
                ws.cell(row=current_row, column=1).alignment = Alignment(
                    horizontal="left", vertical="center", wrap_text=False
                )
                ws.cell(row=current_row, column=1).border = _BORDER

                # Col B: task description
                task_text = str(task.get("task", ""))
                cell_b = ws.cell(row=current_row, column=2, value=task_text)
                cell_b.fill = _fill(bg)
                cell_b.font = _font(size=10)
                cell_b.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                cell_b.border = _BORDER
                ws.row_dimensions[current_row].height = max(15, min(len(task_text) // 4, 60))

                # Col C: status badge
                _badge_cell(ws, current_row, 3,
                            task.get("status", "open"), _STATUS_COLORS)

                # Col D: priority badge
                _badge_cell(ws, current_row, 4,
                            task.get("priority", "medium"), _PRIORITY_COLORS)

                # Col E: deadline
                deadline = task.get("deadline") or ""
                cell_e = ws.cell(row=current_row, column=5, value=deadline)
                cell_e.fill = _fill(bg)
                cell_e.font = _font(size=10)
                cell_e.alignment = Alignment(horizontal="center", vertical="center")
                cell_e.border = _BORDER

                current_row += 1

            # Merge person name column for all their rows
            if len(tasks) > 1:
                ws.merge_cells(
                    start_row=name_start, start_column=1,
                    end_row=current_row - 1, end_column=1
                )
                ws.cell(row=name_start, column=1).alignment = Alignment(
                    horizontal="left", vertical="center", wrap_text=False
                )

            # Thin separator row between people
            for col in range(1, 6):
                sep = ws.cell(row=current_row, column=col, value="")
                sep.fill = _fill("E8F0F7")
                sep.border = _BORDER
            ws.row_dimensions[current_row].height = 5
            current_row += 1

        # Freeze top 2 rows
        ws.freeze_panes = "A3"
