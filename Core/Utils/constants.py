import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Timeout Constants (in milliseconds)
NAVIGATION_TIMEOUT = 180000  # 3 minutes for page navigation
WAIT_FOR_LOAD_STATE_TIMEOUT = 90000  # 1.5 minutes for load state operations
STANDINGS_LOAD_TIMEOUT = 20000  # 20 seconds for standings (supplementary data)

# Financial Settings
DEFAULT_STAKE = float(os.getenv("DEFAULT_STAKE", 1.0))
CURRENCY_SYMBOL = os.getenv("CURRENCY_SYMBOL", "$")

# Concurrency Control
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", 1))

