import re


def normalize_message_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "")
    cleaned = cleaned.strip()
    return cleaned


def extract_sender_and_text(text: str) -> tuple[str | None, str | None]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None, None

    sender = None
    body: list[str] = []
    for line in lines:
        if sender is None and re.match(r"^[A-Za-z0-9 _.-]{1,30}$", line):
            sender = line
            continue
        body.append(line)

    final_text = " ".join(body).strip()
    if not final_text:
        return None, None
    return sender or "unknown", normalize_message_text(final_text)
