"""Shared constants: column names, event types and analysis defaults."""

# Canonical column names used everywhere after loading
VEHICLE_ID = "vehicle_id"
MODEL_ID = "model_id"
STARTED_TIME = "started_time"
FINISHED_TIME = "finished_time"
CHARGE_START = "chargelevelstart"
CHARGE_END = "chargelevelend"
CHARGED = "charged"
SERVICE_RENTAL = "servicerental"

RAW_COLUMNS = [
    VEHICLE_ID,
    MODEL_ID,
    STARTED_TIME,
    FINISHED_TIME,
    CHARGE_START,
    CHARGE_END,
    CHARGED,
    SERVICE_RENTAL,
]

COLUMN_ALIASES = {
    "startedtime": STARTED_TIME,
    "finishedtime": FINISHED_TIME,
    "charge_level_start": CHARGE_START,
    "charge_level_end": CHARGE_END,
    "service_rental": SERVICE_RENTAL,
}

# Event types
CUSTOMER_RENTAL = "customer_rental"
AGENT_CHARGE = "agent_charge"
AGENT_MOVE = "agent_move"
RENTAL_TYPES = [CUSTOMER_RENTAL, AGENT_CHARGE, AGENT_MOVE]

# Analysis defaults
DEFAULT_WINDOW_MINUTES = 60
DEFAULT_SOC_BIN_WIDTH = 5
