from typing import Dict


def get_default_settings() -> Dict[str, str]:
    return {
        "ENV": "local",
        "LOG_LEVEL": "info",
    }
