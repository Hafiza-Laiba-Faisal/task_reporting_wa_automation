"""
Google Sheets Writer
====================
Mirrors ExcelWriter interface — takes the same list[dict] of task rows
and writes them to a Google Spreadsheet using the same layout:

    Row 1 : Title  (merged)
    Row 2 : Date | ← Ayan → | ← Farah → | …
    Row 3 : sub-headers: Tasks | Status per employee
    Row 4+: data rows — sorted by date

Dependencies:  gspread>=6.0.0  google-auth>=2.0.0
Install:       pip install gspread google-auth
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from app.logger import get_logger

logger = get_logger("google_sheets_writer")

# ── Palette (Google Sheets uses RGB dicts) ────────────────────────────────────
def _rgb(hex_color: str) -> dict:
    h = hex_color.lstrip("#")
    return {
        "red":   int(h[0:2], 16) / 255,
        "green": int(h[2:4], 16) / 255,
        "blue":  int(h[4:6], 16) / 255,
    }

_HDR_BG  = "1F3864"  # dark navy
_EMP_BG  = "2E75B6"  # blue — employee header
_SUB_BG  = "4472C4"  # mid-blue — sub-headers
_DATE_BG = "1F3864"  # date cell
_ROW_A   = "EBF3FB"  # light blue alternating
_ROW_B   = "FFFFFF"

_STATUS_CLR = {
    "completed":   ("C6EFCE", "375623"),
    "in_progress": ("FFEB9C", "9C5700"),
    "open":        ("DDEBF7", "1F3864"),
    "blocked":     ("FFC7CE", "9C0006"),
    "review":      ("E2EFDA", "375623"),
}

_STATUS_LABEL = {
    "completed":   "✅ Completed",
    "in_progress": "🔄 In Progress",
    "open":        "📋 Open",
    "blocked":     "🚫 Blocked",
    "review":      "🔍 Review",
}

_STATUS_ORDER = ["in_progress", "open", "review", "blocked", "completed"]


def _dominant_status(statuses: list[str]) -> str:
    for s in _STATUS_ORDER:
        if s in statuses:
            return s
    return statuses[0] if statuses else "open"


def _normalize_day(raw_date: str) -> str:
    raw = str(raw_date).strip()
    if " " in raw:
        raw = raw.split(" ")[0]
    if "T" in raw:
        raw = raw.split("T")[0]
    day = raw[:10]
    parts = day.split("-")
    if len(parts) == 3 and len(parts[0]) == 2 and len(parts[2]) == 4:
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return day


def _day_label(iso: str) -> str:
    try:
        return date.fromisoformat(iso).strftime("%d %b %Y")
    except Exception:
        return iso


# ── Helper: cell format request builders ─────────────────────────────────────

def _bg_fmt(hex_color: str, bold: bool = False, fg: str = "FFFFFF", font_size: int = 10) -> dict:
    return {
        "backgroundColor": _rgb(hex_color),
        "textFormat": {
            "bold": bold,
            "foregroundColor": _rgb(fg),
            "fontSize": font_size,
        },
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
        "wrapStrategy": "WRAP",
    }


def _data_fmt(hex_bg: str, hex_fg: str = "000000", bold: bool = False, align: str = "LEFT") -> dict:
    return {
        "backgroundColor": _rgb(hex_bg),
        "textFormat": {
            "bold": bold,
            "foregroundColor": _rgb(hex_fg),
            "fontSize": 10,
        },
        "horizontalAlignment": align,
        "verticalAlignment": "TOP",
        "wrapStrategy": "WRAP",
    }


def _cell_range(sheet_id: int, r0: int, c0: int, r1: int, c1: int) -> dict:
    """0-indexed row/col range."""
    return {
        "sheetId": sheet_id,
        "startRowIndex": r0, "endRowIndex": r1,
        "startColumnIndex": c0, "endColumnIndex": c1,
    }


# ── Main writer class ─────────────────────────────────────────────────────────

class GoogleSheetsWriter:
    """
    Writes task data to a Google Spreadsheet.

    Usage:
        writer = GoogleSheetsWriter(
            spreadsheet_id="1abc...",
            credentials_path="./credentials.json",   # service account JSON
            sheet_name="Task Summary",
        )
        writer.write_tasks(rows)  # same rows as ExcelWriter.write_tasks()
    """

    def __init__(
        self,
        spreadsheet_id: str,
        credentials_path: str,
        sheet_name: str = "Task Summary",
    ) -> None:
        self.spreadsheet_id = spreadsheet_id
        self.credentials_path = str(Path(credentials_path).expanduser())
        self.sheet_name = sheet_name
        self._gc = None   # gspread client (lazy-init)
        self._service = None  # sheets API service (lazy-init)

    # ── Auth ──────────────────────────────────────────────────────────────────
    def _get_client(self):
        if self._gc:
            return self._gc
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(self.credentials_path, scopes=scopes)
        self._gc = gspread.authorize(creds)
        return self._gc

    def _get_service(self):
        """Raw googleapiclient service for batchUpdate (formatting)."""
        if self._service:
            return self._service
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(self.credentials_path, scopes=scopes)
        self._service = build("sheets", "v4", credentials=creds)
        return self._service

    # ── Public entry point ────────────────────────────────────────────────────
    def write_tasks(self, rows: list[dict]) -> str:
        """
        Write tasks to Google Sheet and return the sheet URL.
        rows: same format as ExcelWriter.write_tasks()
        Returns: URL of the spreadsheet
        """
        if not rows:
            logger.info("No task rows to write to Google Sheets.")
            return ""

        # ── 1. Build data structure ───────────────────────────────────────────
        data: dict[str, dict[str, dict]] = defaultdict(
            lambda: defaultdict(lambda: {"tasks": [], "statuses": []})
        )
        for r in rows:
            day      = _normalize_day(r.get("date") or r.get("created_at") or date.today().isoformat())
            assignee = str(r.get("assignee") or "Unknown").strip()
            task     = str(r.get("task") or "").strip()
            status   = str(r.get("status") or "open").lower().strip()
            for line in task.splitlines():
                line = line.strip().lstrip("•").strip()
                if line:
                    data[day][assignee]["tasks"].append(line)
            if status:
                data[day][assignee]["statuses"].append(status)

        sorted_dates  = sorted(data.keys())
        all_employees = sorted({emp for day in data.values() for emp in day})
        n_emp         = len(all_employees)
        total_cols    = 1 + n_emp * 2

        # ── 2. Get or create the worksheet ───────────────────────────────────
        gc = self._get_client()
        try:
            sh = gc.open_by_key(self.spreadsheet_id)
        except Exception as e:
            raise RuntimeError(f"Cannot open spreadsheet '{self.spreadsheet_id}': {e}") from e

        try:
            ws = sh.worksheet(self.sheet_name)
            ws.clear()
        except Exception:
            ws = sh.add_worksheet(title=self.sheet_name, rows=500, cols=total_cols + 5)

        sheet_id = ws.id

        # ── 3. Build values grid ──────────────────────────────────────────────
        all_values: list[list[str]] = []

        # Row 0 (idx): title row
        title_row = ["TenBit Daily Task Report"] + [""] * (total_cols - 1)
        all_values.append(title_row)

        # Row 1: employee headers
        emp_row = ["Date"]
        for emp in all_employees:
            emp_row.append(emp)
            emp_row.append("")   # placeholder for merged col
        all_values.append(emp_row)

        # Row 2: sub-headers
        sub_row = [""]
        for _ in all_employees:
            sub_row.append("Tasks")
            sub_row.append("Status")
        all_values.append(sub_row)

        # Rows 3+: data
        for day in sorted_dates:
            row_vals = [_day_label(day)]
            for emp in all_employees:
                emp_data = data[day].get(emp, {"tasks": [], "statuses": []})
                tasks_list = emp_data["tasks"]
                statuses   = emp_data["statuses"]
                cell_text  = "\n".join(f"• {t}" for t in tasks_list) if tasks_list else ""
                if tasks_list:
                    status_key = _dominant_status(statuses) if statuses else "open"
                    s_label    = _STATUS_LABEL.get(status_key, status_key.title())
                else:
                    s_label = "—"
                row_vals.append(cell_text)
                row_vals.append(s_label)
            all_values.append(row_vals)

        # ── 4. Write values to sheet ──────────────────────────────────────────
        ws.update(range_name="A1", values=all_values)
        logger.info("Google Sheets: wrote %d rows x %d cols", len(all_values), total_cols)

        # ── 5. Apply formatting via batchUpdate ───────────────────────────────
        svc = self._get_service()
        requests = self._build_format_requests(
            sheet_id, data, sorted_dates, all_employees, total_cols
        )
        if requests:
            svc.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"requests": requests},
            ).execute()
            logger.info("Google Sheets: applied %d format requests", len(requests))

        url = f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit"
        logger.info("Google Sheets updated: %s", url)
        return url

    # ── Formatting helpers ────────────────────────────────────────────────────
    def _build_format_requests(
        self,
        sheet_id: int,
        data: dict,
        sorted_dates: list[str],
        all_employees: list[str],
        total_cols: int,
    ) -> list[dict]:
        reqs = []
        n_emp = len(all_employees)

        # ── Title row (row 0): merge + format ────────────────────────────────
        reqs.append({"mergeCells": {
            "range": _cell_range(sheet_id, 0, 0, 1, total_cols),
            "mergeType": "MERGE_ALL",
        }})
        reqs.append({"repeatCell": {
            "range": _cell_range(sheet_id, 0, 0, 1, total_cols),
            "cell": {"userEnteredFormat": _bg_fmt(_HDR_BG, bold=True, fg="FFFFFF", font_size=14)},
            "fields": "userEnteredFormat",
        }})

        # ── Date header (rows 1-2, col 0): merge ─────────────────────────────
        reqs.append({"mergeCells": {
            "range": _cell_range(sheet_id, 1, 0, 3, 1),
            "mergeType": "MERGE_ALL",
        }})
        reqs.append({"repeatCell": {
            "range": _cell_range(sheet_id, 1, 0, 3, 1),
            "cell": {"userEnteredFormat": _bg_fmt(_DATE_BG, bold=True, fg="FFFFFF", font_size=11)},
            "fields": "userEnteredFormat",
        }})

        # ── Employee headers (row 1): merge each pair ────────────────────────
        for i in range(n_emp):
            tasks_col  = 1 + i * 2
            status_col = tasks_col + 1
            reqs.append({"mergeCells": {
                "range": _cell_range(sheet_id, 1, tasks_col, 2, status_col + 1),
                "mergeType": "MERGE_ALL",
            }})
            reqs.append({"repeatCell": {
                "range": _cell_range(sheet_id, 1, tasks_col, 2, status_col + 1),
                "cell": {"userEnteredFormat": _bg_fmt(_EMP_BG, bold=True, fg="FFFFFF", font_size=10)},
                "fields": "userEnteredFormat",
            }})
            # Sub-headers row 2
            reqs.append({"repeatCell": {
                "range": _cell_range(sheet_id, 2, tasks_col, 3, status_col + 1),
                "cell": {"userEnteredFormat": _bg_fmt(_SUB_BG, bold=True, fg="FFFFFF", font_size=9)},
                "fields": "userEnteredFormat",
            }})

        # ── Data rows (rows 3+) ───────────────────────────────────────────────
        for row_offset, day in enumerate(sorted_dates):
            row_idx = 3 + row_offset
            bg = _ROW_A if row_offset % 2 == 0 else _ROW_B

            # Date cell col 0
            reqs.append({"repeatCell": {
                "range": _cell_range(sheet_id, row_idx, 0, row_idx + 1, 1),
                "cell": {"userEnteredFormat": _bg_fmt(_DATE_BG, bold=True, fg="FFFFFF", font_size=10)},
                "fields": "userEnteredFormat",
            }})

            for i, emp in enumerate(all_employees):
                tasks_col  = 1 + i * 2
                status_col = tasks_col + 1
                emp_data   = (data[day].get(emp) or {})
                tasks_list = emp_data.get("tasks", [])
                statuses   = emp_data.get("statuses", [])

                # Tasks cell
                reqs.append({"repeatCell": {
                    "range": _cell_range(sheet_id, row_idx, tasks_col, row_idx + 1, tasks_col + 1),
                    "cell": {"userEnteredFormat": _data_fmt(bg, "000000", False, "LEFT")},
                    "fields": "userEnteredFormat",
                }})

                # Status cell coloring
                if tasks_list:
                    status_key   = _dominant_status(statuses) if statuses else "open"
                    s_bg, s_fg   = _STATUS_CLR.get(status_key, ("E0E0E0", "333333"))
                    status_format = _data_fmt(s_bg, s_fg, bold=True, align="CENTER")
                else:
                    status_format = _data_fmt("F5F5F5", "AAAAAA", bold=False, align="CENTER")

                reqs.append({"repeatCell": {
                    "range": _cell_range(sheet_id, row_idx, status_col, row_idx + 1, status_col + 1),
                    "cell": {"userEnteredFormat": status_format},
                    "fields": "userEnteredFormat",
                }})

        # ── Column widths ─────────────────────────────────────────────────────
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                      "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 110},
            "fields": "pixelSize",
        }})
        for i in range(n_emp):
            tasks_col  = 1 + i * 2
            status_col = tasks_col + 1
            reqs.append({"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                          "startIndex": tasks_col, "endIndex": tasks_col + 1},
                "properties": {"pixelSize": 260},
                "fields": "pixelSize",
            }})
            reqs.append({"updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                          "startIndex": status_col, "endIndex": status_col + 1},
                "properties": {"pixelSize": 130},
                "fields": "pixelSize",
            }})

        # ── Row height title ──────────────────────────────────────────────────
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "ROWS",
                      "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 40},
            "fields": "pixelSize",
        }})

        # ── Freeze header rows and date column ────────────────────────────────
        reqs.append({"updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": {"frozenRowCount": 3, "frozenColumnCount": 1},
            },
            "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
        }})

        return reqs

    # ── Sharing ───────────────────────────────────────────────────────────────
    def share_with_team(self, emails: list[str]) -> None:
        """Share the spreadsheet with a list of emails (editor access)."""
        if not emails:
            return
        try:
            import gspread
            from google.oauth2.service_account import Credentials

            scopes = ["https://www.googleapis.com/auth/drive"]
            creds  = Credentials.from_service_account_file(self.credentials_path, scopes=scopes)
            gc     = gspread.authorize(creds)
            sh     = gc.open_by_key(self.spreadsheet_id)
            for email in emails:
                sh.share(email, perm_type="user", role="writer", notify=True)
                logger.info("Shared spreadsheet with: %s", email)
        except Exception as e:
            logger.warning("Failed to share spreadsheet: %s", e)
