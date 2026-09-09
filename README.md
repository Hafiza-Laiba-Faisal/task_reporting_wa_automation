# WhatsApp Task Extraction Automation

This project automates the extraction of actionable tasks from one configured WhatsApp group and stores them in an Excel workbook.

## Goals

- Read only one configured WhatsApp group.
- Verify that the correct group is open before collecting messages.
- Normalize and classify messages.
- Extract actionable tasks with an LLM-style extractor and Pydantic validation.
- Deduplicate messages and tasks in SQLite.
- Update Excel automatically.
- Log all runs and failures.

## Key constraints

- No n8n, no Zapier, no Make, no official WhatsApp API.
- Custom Python automation only.
- Playwright-based WhatsApp Web automation.
- SQLite for state, openpyxl for Excel.
- Pydantic validation for structured output.
- modular design to allow replacement of browser, database, or extraction providers later.

## Project structure

- app/config.py: application settings from environment and .env.
- app/whatsapp/browser.py: browser/session management.
- app/whatsapp/group_finder.py: exact group search and verification.
- app/whatsapp/message_collector.py: message extraction and deduplication.
- app/database/repository.py: SQLite state.
- app/ai/extractor.py: task extraction layer.
- app/ai/schemas.py: Pydantic model validation.
- app/excel/writer.py: workbook writing.
- app/pipeline/processor.py: orchestration pipeline.
- tests/: regression and validation tests.

## Setup

1. Create a Python virtual environment.
2. Install dependencies:
   pip install -r requirements.txt
3. Copy .env.example to .env and set your values.
4. Ensure Chrome/Chromium is installed for Playwright.
5. Log into WhatsApp Web once in the configured browser profile if required.

## Run via terminal

python main.py

## Run the local frontend

uvicorn app.frontend:app --reload --host 0.0.0.0 --port 8000

Then open:
http://localhost:8000/

## Mistral setup

Set one of these in .env:

MISTRAL_API_KEY=your_key_here
MISTRAL_MODEL=mistral-small-latest

Or keep using the generic LLM_API_KEY/LLM_MODEL variables.

## Dry run

Set DRY_RUN=true in .env to analyze messages without writing to Excel or updating task records.

## Testing

pytest -q

## Important safety notes

The automation does not guess when group name matching is ambiguous. It will stop and request manual intervention rather than process the wrong group.

This is a controlled internal/demo automation pattern and is not a guaranteed official integration path for WhatsApp.
