import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)

# Dedicated logger for call payloads (observability requirement: log at minimum the
# final collected data payload for every call).
call_logger = logging.getLogger("voice_agent.calls")
api_logger = logging.getLogger("voice_agent.api")
