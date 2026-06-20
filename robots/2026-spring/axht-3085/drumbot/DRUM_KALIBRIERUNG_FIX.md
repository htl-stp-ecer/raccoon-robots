# Drum-Kalibrierung — Änderungen & Verifikationsplan

Kontext: Auf dem Review-Screen der Drum-Kalibrierung reagierten *Retry* und *Confirm*
scheinbar nicht, und die Kalibrierung lief endlos ins Leere. Ursache war **nicht** die
Auswerte-Logik, sondern dass der **Drum-Motor während des Sampling nicht drehte**
(`ticks=0`, flaches Lichtsignal 3059–3063). Dieses Dokument hält fest, was geändert
wurde, warum — und was am realen Robot noch geprüft werden muss.

Stand: 2026-06-20. Betroffene Dateien siehe unten.

---

## 1. Root-Cause (aus dem Log abgeleitet)

Log-Symptome während `sample()`:

```
Collected 470 samples — min=3059, max=3063, avg=3062, ticks=0
Cluster: pocket=3060, blocked=3062, spread=2
Drum calibration needs review: stripe spacing not uniform (deviation 100.0%)
```

- `ticks=0` (`drum_motor_calibration_mixin.py`, `abs(end_encoder - start_encoder)`):
  Der Encoder stand über die kompletten 5 s still → die Trommel hat sich nicht bewegt.
- Flaches Lichtsignal (Spannweite 4) bestätigt das: der Sensor starrt auf einen festen
  Punkt, statt über die Streifen zu streichen.
- Folge: 2-Means clustert nur Rauschen (`pocket=3060 / blocked=3062`, delta=2),
  Streifen-Analyse findet keine echten Streifen → "stripe spacing not uniform".

Die Buttons **funktionierten tatsächlich** (das Log beweist es: Retry → `Sampling…`,
Confirm → `REJECTED delta=2 < 750`). Sie *fühlten* sich nur tot an, weil jede Aktion
denselben Screen sofort neu zeigte — bei delta=2 kann `Confirm` nie durch die
`MIN_DELTA`-Prüfung (750), und `Retry` sampelt dieselbe tote Trommel erneut.

### Warum drehte der Motor nicht?

`sample()` trieb die Trommel mit **`set_velocity(1700)`** an — der **closed-loop**
BEMF-Pfad (HAL: *"velocity target in BEMF units — firmware handles PID"*). Der
`drum_motor` hat in `src/hardware/defs.py` aber **keine BEMF-/Reibungs-Kalibrierung**:

```python
# Antriebsmotor — voll getunt:
MotorCalibration(ticks_to_rad=0.00385191, vel_lpf_alpha=0.05,
                 bemf_offset=-20.2116, static_friction_pct=11)
# drum_motor (Port 2) — nur Platzhalter:
MotorCalibration(ticks_to_rad=1.0, vel_lpf_alpha=1.0)
```

Ohne `bemf_offset` / `static_friction_pct` (beide Default 0) kommandiert die
Velocity-PID nur einen Bruchteil PWM und überwindet die Haftreibung nicht — der Motor
steht. Ein manueller Test mit **`set_speed`** (offene PWM) dreht ihn dagegen problemlos;
genau so hat der Nutzer "der Motor geht" verifiziert.

---

## 2. Durchgeführte Änderungen

### A) `src/service/drum_motor_calibration_mixin.py` — `sample()`

**Kern-Fix.** Antrieb des Sampling von closed-loop auf open-loop umgestellt:

| vorher | nachher |
|---|---|
| `velocity = int(motor_speed * FULL_VELOCITY)` | `speed_pct = int(motor_speed * 100)` |
| `self.motor.set_velocity(velocity)` | `self.motor.set_speed(speed_pct)` |
| `finally: self.motor.set_velocity(0)` | `finally: self.motor.set_speed(0)` |

**Warum:** Das Sampling braucht keine drehzahlgenaue Regelung, nur eine gleichmäßige
Drehung, damit der Sensor über die Streifen streicht. `set_speed` (PWM) ist unabhängig
vom BEMF-Tuning und damit für diesen Motor zuverlässig. Encoder-Reads (`get_position()`)
sind unberührt → Tick-Zählung und Streifenabstand funktionieren weiter.
`motor_speed=1.0` ⇒ `set_speed(100)` (volle PWM).

### B) `src/steps/drum_collector/calibration_step.py` — `_analyse()`

**Ehrliche Fehlermeldung statt irreführender Folgemeldung.** Neue Konstante und zwei
Guards nach dem Clustering:

- `MIN_SAMPLE_TICKS = 100` (neu).
- Wenn `service._sample_total_ticks < MIN_SAMPLE_TICKS` → Fehler
  *"drum motor did not spin (N encoder ticks) — check motor power/wiring or a
  mechanical jam"*.
- Wenn `max(samples) - min(samples) < MIN_DELTA` → Fehler
  *"no optical contrast (signal range … < …) — check light-sensor aim/distance or the
  drum stripes"*.

Beide geben weiterhin die geclusterten Werte zurück, damit der Review-Screen rendert —
aber mit der **echten** Ursache statt "stripe spacing not uniform".

### C) `src/steps/drum_collector/screens/confirm_screen.py` — `DrumConfirmScreen`

**UX, auf Nutzerwunsch + ehrliches Feedback.**

- `_primary_button_id`: `"confirm"` → `"retry"`. Der physische Robot-Knopf löst jetzt
  *Retry* aus statt eine schlechte Kalibrierung still zu bestätigen.
- Retry-Button: Style `"secondary"` → `"primary"` (liest sich als Default-Aktion).
- Confirm-Button: Style `"success" if is_good else "warning"` → `"success" if is_good
  else "secondary"`, **plus `disabled=not self.is_good`**. Vorher war Confirm klickbar,
  wurde aber stromabwärts still verworfen ("ich drücke, nichts passiert"); jetzt ist er
  ehrlich ausgegraut, bis `|blocked - pocket| ≥ MIN_DELTA`.
  Fluchtweg bleibt: die `NumericInput`-Felder sind editierbar, `on_change` ruft
  `refresh()`, der Button re-aktiviert sich live.

### D) `src/service/drum_motor_service.py` — Navigation (gleiche Ursache)

**Nachgezogen, nachdem im Collection-Log ein Stall auftrat**
(`EMERGENCY SHUTDOWN: Motor stalled during drum #2`). Das ist **dieselbe** Ursache:
die Navigation trieb die Trommel ebenfalls mit `set_velocity` an → kein PWM gegen die
Haftreibung → 0 Net-Ticks → `_make_stall_checker` löst `MotorStalledError` aus.

- Neuer Helper `_drive(velocity)`: mappt die BEMF-Einheiten-Ziele der Navigation auf
  PWM-Prozent (`FULL_VELOCITY == 100 %`) und treibt via `set_speed`. Encoder-Reads
  bleiben unberührt → Stall-Checker und IR-Tracker funktionieren weiter.
- Alle Dauerfahrten gehen jetzt durch `_drive()` bzw. `set_speed(0)` zum Stoppen:
  `_do_move`, `_retry_on_stall` (Backup), `_center_on_stripe` (Creep),
  `move_to_midpoint`, `move_from_midpoint`.
- **Offen:** die zwei `move_to_position()`-Aufrufe in `_center_on_stripe` nutzen
  Firmware-**Position-Mode** (anderer Pfad als set_velocity/set_speed). Unklar, ob der
  dort dieselbe Stiction hat — mit `TODO(drum-cal)` im Code markiert. Nur bei
  `precise=True` relevant.

---

## 3. TODO — am realen Robot zu prüfen

- [ ] **Kalibrierung mit dem `set_speed`-Fix laufen lassen.** Erwartung im Log:
      `ticks` steigt in die Tausende, `min/max` zeigen echten Hell/Dunkel-Hub,
      `Cluster spread` ≫ 2, kein "stripe spacing not uniform" mehr.
- [ ] **`MIN_SAMPLE_TICKS = 100` validieren.** Bei einer normalen 5-s-Probe sollten es
      tausende Ticks sein; 100 ist ein konservativer Boden. Bei sehr langsamer Trommel
      ggf. nachschärfen.
- [ ] **Navigation mit dem `_drive()`/`set_speed`-Umbau prüfen.** Drum #1..#8
      collecten + sorten ohne `Motor stalled`-Emergency. Erwartung: die Trommel dreht
      bei `advance`/`retreat`/`go_to_pocket`, Stall-Checker schlägt nicht mehr fälschlich
      an. Falls doch Stalls: PWM-Mapping in `_drive()` (`velocity / FULL_VELOCITY * 100`)
      ggf. anheben oder eine Mindest-PWM einziehen.
- [ ] **`_center_on_stripe` bei `precise=True` prüfen.** Die zwei
      `move_to_position()`-Aufrufe (Position-Mode) sind **nicht** umgestellt. Wenn das
      Zentrieren nicht greift / der Motor dort steht: auf `set_speed`-Creep zur
      Ziel-Encoder-Position umbauen.
- [ ] **Dauerhafter Fix (optional, sauberer):** `drum_motor`-`MotorCalibration` in
      `src/hardware/defs.py` mit echtem `bemf_offset` + `static_friction_pct` tunen (wie
      der Antriebsmotor). Dann könnte man `_drive()` wieder auf `set_velocity`
      zurückdrehen und die closed-loop-Präzision zurückgewinnen.
- [ ] **Retry/Confirm am Touchscreen + physischem Knopf gegenprüfen** nachdem die
      Kalibrierung echten Kontrast liefert (is_good=True): Confirm muss aktiv/klickbar
      werden, physischer Knopf löst Retry aus.

---

## 4. Geänderte Dateien (Referenz)

- `src/service/drum_motor_calibration_mixin.py` — `sample()` Antrieb `set_velocity` → `set_speed`.
- `src/steps/drum_collector/calibration_step.py` — `MIN_SAMPLE_TICKS` + zwei `_analyse()`-Guards.
- `src/steps/drum_collector/screens/confirm_screen.py` — Retry primär, Confirm disabled bei zu wenig Kontrast.
- `src/service/drum_motor_service.py` — `_drive()`-Helper; Navigation von `set_velocity` auf open-loop `set_speed` umgestellt (`move_to_position` in `_center_on_stripe` offen, mit TODO).
