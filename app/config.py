import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self):
        self.whatsapp_group_name = os.getenv("WHATSAPP_GROUP_NAME", "")
        self.whatsapp_url = os.getenv("WHATSAPP_URL", "https://web.whatsapp.com")
        self.whatsapp_profile_path = os.getenv("WHATSAPP_PROFILE_PATH", "")
        self.llm_api_key = os.getenv("LLM_API_KEY", "") or os.getenv("MISTRAL_API_KEY", "")
        self.llm_model = os.getenv("LLM_MODEL", os.getenv("MISTRAL_MODEL", "mistral-small-latest"))
        self.mistral_api_key = os.getenv("MISTRAL_API_KEY", "")
        self.mistral_model = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
        # NVIDIA NIM (OpenAI-compatible) — preferred over Mistral if key is set
        self.nvidia_api_key = os.getenv("NVIDIA_API_KEY", "")
        self.nvidia_base_url = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
        self.nvidia_model = os.getenv("NVIDIA_MODEL", "mistralai/mistral-large-2-instruct")
        # OpenAI
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        # LLM provider selection: nvidia | mistral | openai
        self.llm_provider = os.getenv("LLM_PROVIDER", "nvidia").lower()
        # Custom system prompt override — if set, replaces default prompt
        self.custom_system_prompt = os.getenv("CUSTOM_SYSTEM_PROMPT", "").strip()
        self.target_window_days = int(os.getenv("TARGET_WINDOW_DAYS", "7"))
        self.dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
        self.excel_output_path = os.getenv("EXCEL_OUTPUT_PATH", "./data/tasks.xlsx")
        self.db_path = os.getenv("DB_PATH", "./data/tasks.db")
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.max_messages_per_run = int(os.getenv("MAX_MESSAGES_PER_RUN", "200"))
        self.max_group_search_wait_seconds = int(os.getenv("MAX_GROUP_SEARCH_WAIT_SECONDS", "60"))

        # Sender name mapping: "92xxxxxxxxxx=Real Name,92yyyyy=Other Name"
        # or JSON: {"92xxxxxxxxxx": "Real Name"}
        self.sender_name_map: dict[str, str] = self._parse_sender_map(
            os.getenv("SENDER_NAME_MAP", "")
        )

    @staticmethod
    def _parse_sender_map(raw: str) -> dict[str, str]:
        """Parse SENDER_NAME_MAP from env — supports both JSON and key=value,key=value formats."""
        raw = raw.strip()
        if not raw:
            return {}
        # Try JSON first
        if raw.startswith("{"):
            try:
                return json.loads(raw)
            except Exception:
                return {}
        # key=value pairs separated by comma or semicolon
        result = {}
        for pair in raw.replace(";", ",").split(","):
            pair = pair.strip()
            if "=" in pair:
                k, _, v = pair.partition("=")
                k = k.strip().lstrip("+")
                v = v.strip()
                if k and v:
                    result[k] = v
        return result

    def resolve_sender_name(self, raw_name: str) -> str:
        """Return mapped real name if phone number or exact key found in raw_name, else return raw_name."""
        if not self.sender_name_map:
            return raw_name
        # Check exact match first (e.g. AT=Ayan)
        stripped = raw_name.strip()
        if stripped in self.sender_name_map:
            return self.sender_name_map[stripped]
        # Match phone digits embedded in raw_name
        digits_only = "".join(c for c in raw_name if c.isdigit())
        for key, real_name in self.sender_name_map.items():
            key_digits = "".join(c for c in key if c.isdigit())
            if key_digits and key_digits in digits_only:
                return real_name
        return raw_name

    def resolved_excel_path(self) -> Path:
        return Path(self.excel_output_path).expanduser().resolve()

    def resolved_db_path(self) -> Path:
        return Path(self.db_path).expanduser().resolve()


def settings() -> Settings:
    return Settings()
