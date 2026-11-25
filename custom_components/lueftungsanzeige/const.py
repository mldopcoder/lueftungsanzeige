"""Konstanten für die Lüftungsanzeige."""

from datetime import timedelta

DOMAIN = "lueftungsanzeige"

CONF_MODE = "mode"
CONF_SENSOR = "sensor"
CONF_OUTDOOR_SENSOR = "outdoor_sensor"
CONF_OUTDOOR_CO2 = "outdoor_co2"
CONF_TARGET = "target"
CONF_TOLERANCE = "tolerance"
CONF_RECOMMEND = "recommend"
CONF_ROOM_TEMP = "room_temp"
CONF_OUTDOOR_TEMP = "outdoor_temp"
CONF_WINDOW = "window"
CONF_DELAY = "delay"  # Minuten, um die der Sensor hinterherhinkt (Netatmo: ~5)

DEFAULT_DELAY = 0.0

MODE_CO2 = "co2"
MODE_HUMIDITY = "humidity"

# Felder, die im Optionsdialog geleert werden dürfen
OPTIONAL_KEYS = (CONF_OUTDOOR_SENSOR, CONF_ROOM_TEMP, CONF_OUTDOOR_TEMP, CONF_WINDOW)

DEFAULT_TARGET_CO2 = 800.0  # ppm
DEFAULT_OUTDOOR_CO2 = 420.0  # ppm
DEFAULT_TOLERANCE = 0.5  # g/m³ über Ausgangswert vor dem Duschen
DEFAULT_RECOMMEND = {
    MODE_CO2: 1000.0,  # ppm, ab hier "Lüften empfohlen"
    MODE_HUMIDITY: 1.5,  # g/m³ über dem Tiefstwert der letzten 3 h
}

# Startwert der Luftwechselrate k (1/min), bis gelernt wurde
DEFAULT_K = {MODE_CO2: 0.15, MODE_HUMIDITY: 0.08}
K_MIN = 0.005
K_MAX = 2.0

# Anstieg nach dem Tiefpunkt -> Fenster wohl zu -> Sitzung automatisch beenden
RISE = {MODE_CO2: 60.0, MODE_HUMIDITY: 0.4}
# Mindestabfall, damit eine Sitzung als echtes Lüften zählt und gelernt wird
MIN_DROP = {MODE_CO2: 80.0, MODE_HUMIDITY: 0.5}

PRIOR_WEIGHT = 2.0  # Gelerntes zählt so viel wie 2 Messwerte der laufenden Sitzung
DEFAULT_PRIOR_WEIGHT = 0.5  # Startwert zählt wie eine halbe gelernte Lüftung
DT_SCALE = 5.0  # K – wie stark ähnliche Temperaturdifferenzen bevorzugt werden
HOUR_SCALE = 2.5  # h – Lüftungen zu ähnlicher Tageszeit zählen mehr
AGE_DECAY = 0.95  # ältere Lüftungen zählen etwas weniger

HISTORY_WINDOW = 3 * 3600  # s – für den Ausgangswert im Bad
MAX_DURATION = 90 * 60  # s – danach wird eine Sitzung automatisch beendet
MIN_LEARN_DURATION = 2 * 60  # s
MAX_LEARN_DURATION = 30 * 60  # s – länger ist kein Stoßlüften (z. B. Fenster gekippt)
# Nach dem Ende noch so lange (plus Messverzögerung) auf verspätete Werte warten
FOLLOW_UP = 30 * 60  # s – Nachlauf: so lange nach dem Schließen den Tiefstwert suchen
# Fenster innerhalb dieser Zeit wieder auf -> gleiche Lüftung fortsetzen (Prellen)
REOPEN_GRACE = 60  # s
MAX_SESSIONS = 50
TICK = timedelta(seconds=30)

STORAGE_VERSION = 1

EVENT_TARGET_REACHED = f"{DOMAIN}_ziel_erreicht"
EVENT_ENDED = f"{DOMAIN}_beendet"
