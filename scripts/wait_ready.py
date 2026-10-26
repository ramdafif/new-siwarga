import os
import time
from urllib.error import URLError
from urllib.request import urlopen

base = os.getenv("APP_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
for attempt in range(60):
    try:
        with urlopen(base + "/health/ready", timeout=2) as response:
            if response.status == 200:
                break
    except (URLError, TimeoutError):
        time.sleep(1)
else:
    raise SystemExit("Application readiness timed out")
