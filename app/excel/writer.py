from __future__ import annotations

from datetime import date
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.logger import get_logger

logger = get_logger("excel_writer")

# ── Colours ───────────────────────────────────────────────────────────────────
_HDR_BG   = "1F3864"
_HDR_FG   = "FFFFFF"
_COL_BG   = "2E75B6"
_COL_FG   = "FFFFFF"
_ROW_A    = "EBF3FB"
_ROW_B    = "FFFFFF"

_STATUS_CLR = {
    "completed":   ("C6EFCE", "375623"),
    "in_progress": ("FFEB9C", "9C5700"),
    "open":        ("DDEBF7", "1F3864"),
    "blocked":     ("FFC7CE", "9C0006"),
    "review":      ("E2EFDA", "375623"),
}
_PRIORITY_CLR = {
    "urgent": ("FF0000", "FFFFFF"),
    "high":   ("FF9900", "FFFFFF"),
    "medium": ("4472C4", "FFFFFF"),
    "low":    ("70AD47", "FFFFFF"),
}

_THIN   = Side(style="thin", color="B0BEC5")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def _fill(hex_color: str) -> PatternFill:
    return PatternFill("solid", fgColor=hex_color)


def _font(bold=False, color="000000", size=10) -> Font:
    return Font(bold=bold, color=color, size=size, name="Calibri")


class ExcelWriter:
    def __init__(self, file_path: str) -> None:
        self.file_path = Path(file_path).expanduser()
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def write_tasks(self, rows: list[dict]) -> None:
        if not rows:
            logger.info("No task rows to write to Excel.")
            return

        # Group by date → then by assignee, merging all tasks into one cell
        from collections import defaultdict
        by_date: dict[str, dict[str, dict]] = defaultdict(dict)

        for r in rows:
            raw_date = str(r.get("date") or r.get("created_at") or date.today().isoformat())
            # Extract just date part — ignore time portion
            raw_date = raw_date.strip()
            if " " in raw_date:
                raw_date = raw_date.split(" ")[0]
            if "T" in raw_date:
                raw_date = raw_date.split("T")[0]
            day = raw_date[:10]
            # Handle DD-MM-YYYY format → convert to YYYY-MM-DD
            parts = day.split("-")
            if len(parts) == 3 and len(parts[0]) == 2 and len(parts[2]) == 4:
                day = f"{parts[2]}-{parts[1]}-{parts[0]}"

            assignee = str(r.get("assignee") or "Unknown").strip()
            task_text = str(r.get("task") or "").strip()
            status = str(r.get("status") or "open").lower()
            priority = str(r.get("priority") or "medium").lower()
            deadline = str(r.get("deadline") or "")

            if assignee not in by_date[day]:
                by_date[day][assignee] = {
                    "tasks": [],
                    "status": status,
                    "priority": priority,
                    "deadline": deadline,
                }

            # Append each task as a bullet
            for line in task_text.splitlines():
                line = line.strip().lstrip("•").strip()
                if line:
                    by_date[day][assignee]["tasks"].append(line)

            # Take "highest" status across tasks
            order = ["completed", "in_progress", "review", "open", "blocked"]
            cur_s = by_date[day][assignee]["status"]
            if order.index(status) < order.index(cur_s) if status in order and cur_s in order else False:
                by_date[day][assignee]["status"] = status

        target = self.file_path
        temp   = target.with_suffix(".tmp.xlsx")

        wb = load_workbook(target) if target.exists() else Workbook()
        if "Sheet" in wb.sheetnames:
            del wb["Sheet"]

        for day_str in sorted(by_date.keys()):
            try:
                sheet_name = date.fromisoformat(day_str).strftime("%d %b %Y")
            except Exception:
                # Try DD-MM-YYYY format
                try:
                    parts = day_str[:10].split("-")
                    if len(parts) == 3 and len(parts[0]) == 2:
                        iso = f"{parts[2]}-{parts[1]}-{parts[0]}"
                        sheet_name = date.fromisoformat(iso).strftime("%d %b %Y")
                    else:
                        sheet_name = day_str[:10]
                except Exception:
                    sheet_name = day_str[:10]

            if sheet_name in wb.sheetnames:
                del wb[sheet_name]

            ws = wb.create_sheet(title=sheet_name)
            self._write_sheet(ws, sheet_name, by_date[day_str])

        if wb.sheetnames:
            wb.active = wb[wb.sheetnames[-1]]

        wb.save(temp)
        temp.replace(target)
        logger.info("Excel workbook updated successfully: %s", target)

    def _write_sheet(self, ws, date_label: str, by_person: dict) -> None:
        # Column widths: Name | Tasks | Status | Priority | Deadline
        for col, w in [(1, 22), (2, 70), (3, 14), (4, 12), (5, 14)]:
            ws.column_dimensions[get_column_letter(col)].width = w

        # Title row
        ws.merge_cells("A1:E1")
        c = ws["A1"]
        c.value = f"Daily Task Report — {date_label}"
        c.fill  = _fill(_HDR_BG)
        c.font  = _font(bold=True, color=_HDR_FG, size=13)
        c.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 28

        # Column headers
        for col, hdr in enumerate(["Team Member", "Tasks", "Status", "Priority", "Deadline"], 1):
            c = ws.cell(row=2, column=col, value=hdr)
            c.fill = _fill(_COL_BG)
            c.font = _font(bold=True, color=_COL_FG, size=10)
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = _BORDER
        ws.row_dimensions[2].height = 18

        row = 3
        for i, person in enumerate(sorted(by_person.keys())):
            data   = by_person[person]
            tasks  = data["tasks"]
            status = data["status"]
            priority = data["priority"]
            deadline = data["deadline"]
            bg = _ROW_A if i % 2 == 0 else _ROW_B

            # Build task text — bullet points
            task_cell_value = "\n".join(f"• {t}" for t in tasks) if tasks else ""

            # Estimate row height based on number of lines
            n_lines = max(len(tasks), 1)
            ws.row_dimensions[row].height = max(18, min(n_lines * 15, 200))

            # A: Team Member
            c = ws.cell(row=row, column=1, value=person)
            c.fill = _fill(bg)
            c.font = _font(bold=True, size=10)
            c.alignment = Alignment(horizontal="left", vertical="top", wrap_text=False)
            c.border = _BORDER

            # B: Tasks
            c = ws.cell(row=row, column=2, value=task_cell_value)
            c.fill = _fill(bg)
            c.font = _font(size=10)
            c.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
            c.border = _BORDER

            # C: Status badge
            s_bg, s_fg = _STATUS_CLR.get(status, ("E0E0E0", "333333"))
            c = ws.cell(row=row, column=3, value=status.replace("_", " ").title())
            c.fill = _fill(s_bg)
            c.font = _font(bold=True, color=s_fg, size=9)
            c.alignment = Alignment(horizontal="center", vertical="top")
            c.border = _BORDER

            # D: Priority badge
            p_bg, p_fg = _PRIORITY_CLR.get(priority, ("E0E0E0", "333333"))
            c = ws.cell(row=row, column=4, value=priority.title())
            c.fill = _fill(p_bg)
            c.font = _font(bold=True, color=p_fg, size=9)
            c.alignment = Alignment(horizontal="center", vertical="top")
            c.border = _BORDER

            # E: Deadline
            c = ws.cell(row=row, column=5, value=deadline)
            c.fill = _fill(bg)
            c.font = _font(size=10)
            c.alignment = Alignment(horizontal="center", vertical="top")
            c.border = _BORDER

            row += 1

        ws.freeze_panes = "A3"
