"""Getunte Schwellwerte für Sensor-Stopbedingungen (nicht auto-generiert)."""

# Reflectance-Wahrscheinlichkeit für Linien-/Farb-Stopbedingungen
# (on_black / on_white / over_line).
#
# Von 0.70 (raccoon-Default) auf 0.90 angehoben nach Run 12.07.2026:
# Die Kalibrierung von Lichtsensor 1 (Port 1, rear_left) war kollabiert
# (blackThreshold=2219, separation=1244 statt ~3800/~2700), wodurch der
# blanke Boden bereits p_black=0.73 ergab und `on_black` in M010 sofort
# im Stand ausgelöst hat. Höhere Schwelle = deutlich weniger Fehltrigger.
LINE_THRESHOLD = 0.70
