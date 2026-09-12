"""Central configuration.

Everything league-specific lives here so nothing is hard-coded across modules.
League size is read from data, never assumed, so that future seasons or a
different league size need no code changes.
"""

from pathlib import Path

# --- League -----------------------------------------------------------------

LEAGUE_ID = 683383
LEAGUE_NAME = "Almost all Americans"
SEASON_NAME = "2026/27"

# Expected membership. Treated as a HINT for cross-checking Phase 2 output,
# never as truth. Live data wins; mismatches get reported, not reconciled.
EXPECTED_TEAM_COUNT = 18
OWNER_DISPLAY_NAME = "Luel Waktola"
OWNER_TEAM_NAME = "Midtable Crisis"

EXPECTED_MEMBERS = [
    ("Rock ‘n’ Iraola", "Andrew Romani"),
    ("CMazz", "Chris Mazzatta"),
    ("Erik's Team", "Erik Baxter"),
    ("Blue Bloods", "Jordan Fernholz"),
    ("Game of Throw-In", "Craig Allen"),
    ("Bruno's Bros", "Joe Gannitello"),
    ("#GOAT", "Isaac Sotelo"),
    ("Big Cannon Energy", "Ryan Smith"),
    ("Hoevoeloe", "Yorick Stoepker"),
    ("millers minions", "Chris Miller"),
    ("Kick'in the balls", "Brian Moran"),
    ("Ophelia Balls", "Danilo Arroyo"),
    ("Championship side", "Brady Baxter"),
    ("Toffee Machine", "Kirk Baxter"),
    ("Keiner Bobby Dazzler", "Reggie Mazz"),
    ("Midtable Crisis", "Luel Waktola"),
    ("OliveOilMoneh", "Harry Daskalopoulos"),
    ("FOGGING ESTANDARDS", "Iain Abshier"),
]

# --- HTTP -------------------------------------------------------------------

BASE_URL = "https://fantasy.premierleague.com/api"

# Identify ourselves honestly. If the API rejects this, Phase 1 will say so
# clearly rather than us quietly impersonating a browser.
USER_AGENT = (
    "aaa-league-intelligence/0.1 (private FPL league analytics; "
    "single daily request cycle)"
)

REQUEST_DELAY_SECONDS = 1.0   # polite spacing between sequential requests
REQUEST_TIMEOUT_SECONDS = 20
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 2.0    # 2s, 4s, 8s

# --- Analytics gates --------------------------------------------------------
# Minimum completed gameweeks before a metric family may be surfaced.

GATE_LUCK_METRICS = 10
GATE_POWER_RANKINGS = 10
GATE_PROJECTIONS = 15
TRANSFER_ROI_HORIZON_GWS = 5

# --- Paths ------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "db" / "league.sqlite"
PHASE1_OUTPUT = REPO_ROOT / "phase1_output"
PHASE1_PAYLOADS = PHASE1_OUTPUT / "payloads"
REPORTS_DIR = REPO_ROOT / "reports"
DIGEST_DIR = REPO_ROOT / "digest"
