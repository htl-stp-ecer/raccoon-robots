# Eject-Mechanik — Annahmen & Verifikationsplan

Ziel: Bestätigen, dass `EjectNearestColorStep` beim physischen Robot wirklich 4 Drums der korrekten Farbe auswirft. Vor Code-Änderungen am Auswurf erst **mit echten Drums** prüfen, wo Modell und Realität auseinanderlaufen.

---

## 1. Arbeits-Modell (zu bestätigen)

### Pocket- und Loch-Geometrie

- Karussell hat **8 Pockets**, Index 0–7.
- `current_pocket = X` heißt: **Pocket X steht gerade auf der "Slot-5-Seite" direkt vor dem Auswurf-Loch.**
- Das Auswurf-Loch liegt bei **Position 5.5** (zwischen Slot-5 und Slot-6).
- Bei einer Transition `current_pocket: X → X+1` (advance) wandert Pocket X durch die Loch-Position → **der Drum aus Pocket X fällt raus.**
- Symmetrisch bei retreat: Transition `X+1 → X` → Drum aus Pocket X+1 fällt raus (das Pocket, das vorher auf Slot-6-Seite stand, kreuzt jetzt das Loch).

Test-Code (`tests/test_eject_edge_cases.py:11-15`) formuliert das knapper: **"A drum in pocket X is ejected at the moment current_pocket transitions to X."** Beides ist konsistent, wenn die obige Geometrie stimmt.

### Konsequenz: pro Transition fällt genau ein Drum

- 4 Transitions ⇒ 4 Drops.
- Welche Pockets gedroppt werden, hängt nur von der Sequenz der `current_pocket`-Werte ab, **nicht** davon, ob die Transition durch `go_to_pocket`, `advance` oder `retreat` ausgelöst wurde.
- Folgerung für Auswurf: Wir wollen genau die 4 Pockets der Zielfarbe in der Transitionsfolge haben — und **keinen** Pocket der anderen Farbe.

---

## 2. Beobachtete Bugs (Hypothesen, am Robot zu prüfen)

### Bug 1 — Sweep ist 1 Transition zu kurz

`src/steps/drum_collector/sort_into_slot_step.py:151–174`:

```python
pockets_to_eject = len(slots) - 1            # = 3 für 4 Drums
await drum_service.go_to_pocket(start_slot)  # variable Transitions
for _ in range(pockets_to_eject - 1):        # 2 Transitions
    advance(1) / retreat(1)
# turn_left/right (keine Karussell-Bewegung)
advance(1) / retreat(1)                      # 1 Transition
```

Sweep nach `go_to_pocket` = **2 + 1 = 3 Transitions**. Der Kommentar im Code rechnet einen "implicit drop from go_to_pocket" mit ein — der existiert aber nur, wenn die Anfahrt **genau 1 Transition** macht **und** diese genau auf einen zu-eject Slot fällt. Das ist nicht der Allgemeinfall.

**Erwartete Folge:** Bei manchen Start-Positionen bleibt 1 Drum der Zielfarbe in der Trommel. Bei Tests wäre `claimed = {3,4,5,6}` statt `{4,5,6,7}`.

### Bug 2 — Anfahrt zu `start_slot` ignoriert belegte Pockets

`go_to_pocket(start_slot)` im Eject wird **ohne** `occupied`-Argument gerufen (im Gegensatz zum Sort, den wir gerade gefixt haben). Bei vollem Sortier-State kann die Anfahrt also über die andere Farbe fahren und ungewollte Drops auslösen.

**Konkretes Beispiel (zu reproduzieren):**
- Sort fertig: blue in {0,1,2,3}, pink in {4,5,6,7}.
- `current_pocket = 4` (typisch nach letztem sort).
- Code nimmt pink zuerst (näher zu Slot 5).
- `slots = sorting.pink_slots = [7,6,5,4]`, `lo=4`, `hi=7`.
- `ring_dist(4,4)=0 ≤ ring_dist(4,7)=3` ⇒ forward, `start_slot = lo-1 = 3`.
- `go_to_pocket(3)` von `cur=4` ⇒ retreat(1). Transition: `4 → 3`.
  - **Modell-Vorhersage:** Drum aus Pocket 4 (pink, richtig) fällt — Pocket 3 (blue, falsch) ist auf der Slot-5-Seite gelandet, fällt aber bei dieser Transition NICHT (der drop happens für das Pocket, das *vom* 5er auf den 6er wechselt, also Pocket 4).
  - **Alternative Modell-Lesart:** Pocket 3 fällt (Bug 2 würde dann Pocket 3 = blue verlieren).
- Dann 2 advances (Transitions `3→4`, `4→5`): Drums aus Pockets 3/4 oder 4/5 fallen — je nach Modell.
- Final advance (Transition `5→6`): Pocket 5 oder 6 fällt.

Die zwei möglichen Outcomes sind erst am realen Robot eindeutig zu trennen. **Das ist der Grund für diesen Verifikationsplan.**

### Bug 3 — Reihenfolge der Farben muss zwingend pink-zuerst sein (im 4+4-Fall)

Bei vollem 4+4-Layout liegen sowohl `(min(blue)-1) % 8 = 7` als auch `(max(blue)+1) % 8 = 4` **in pink**. Heißt: jede Anfahrt zum blue-Sweep-Startpunkt erfordert Transition durch ein pink-Pocket. **Blue zuerst auszuwerfen ist physikalisch nicht "sauber" möglich**, ohne pink-Drums vorher zu droppen.

Aktueller Code wählt über `nearest_dist` die Loch-näheste Farbe — bei normalem Layout pink. Das ist ✓. Aber: **Wenn die Eject-Reihenfolge je geändert wird (z. B. Mission ruft blue-Eject zuerst), bricht das.**

---

## 3. Verifikationsplan am Robot

### Setup

Vor jedem Test: Trommel komplett leer, manuell mit gefärbten Drums in **definierter Belegung** bestücken (siehe Szenarien). `current_pocket` auf einen **definierten** Startwert setzen (entweder vor dem Test mit `reset_position(...)` oder durch manuelle Ausrichtung + `reset_position` aufrufen).

Für jeden Test mitloggen / aufschreiben:
- **Start-`current_pocket`** und Belegung pro Pocket (Farbe).
- **Welche Pockets nach dem Eject leer sind** (visuelle Prüfung der Trommel).
- **Welche Farbe(n) tatsächlich aus dem Loch gefallen sind** (Boden/Auffangkorb).
- **End-`current_pocket`**.

### Szenario A — Sweep-Länge (Bug 1)

**Setup:** nur 4 pink in Pockets {4,5,6,7}, Rest leer. `current_pocket = 0`.

**Aktueller Code-Plan:**
- `nearest_dist(pink)=0`, pink wird gewählt.
- `lo=4, hi=7`. `ring_dist(0,4)=4`, `ring_dist(0,7)=1` ⇒ backward, `start_slot = hi+1 = 0`.
- `go_to_pocket(0)`: kein Move (0 → 0).
- 2 retreats (`0→7`, `7→6`), final retreat (`6→5`). Transitions: 7, 6, 5.

**Modell-Vorhersage:**
- Drops: Pockets 7, 6, 5 (3 Drums).
- **Pocket 4 bleibt drin** ⇒ Bug 1 bestätigt.
- End-`current_pocket` = 5.

**Robot-Check:**
- Wieviele pink Drums fallen tatsächlich raus? Wenn 3 → Bug 1 bestätigt.
- Welche Pockets sind nach dem Eject leer? Wenn {5,6,7} → Bug 1 + Modell bestätigt.

### Szenario B — Anfahrt durch fremde Farbe (Bug 2)

**Setup:** voller Sort-State, blue in {0,1,2,3}, pink in {4,5,6,7}. `current_pocket = 4`.

**Aktueller Code-Plan:** siehe Bug 2 oben. Transitions-Folge laut Code (forward sweep, start_slot=3):
- `go_to_pocket(3)` von 4: retreat 1 → `current_pocket: 4→3`.
- 2 advances: `3→4`, `4→5`.
- Final advance: `5→6`.

**Modell-Vorhersage (mit Convention X→X+1 droppt X):**
- Transition 4→3 ist eine retreat-Transition. Drops Pocket 4 (pink) per Symmetrie.
- Transition 3→4: drops Pocket 3 (blue!) ⇒ Bug 2 bestätigt — pink-Eject droppt ein blue-Drum.
- Transition 4→5: drops Pocket 4 — ABER Pocket 4 wurde schon beim ersten Schritt geleert. **Leer-Drop**.
- Transition 5→6: drops Pocket 5 (pink).

**Mögliche Outcomes am Robot:**
- 4 Drops insgesamt (3 pink + 1 blue) ⇒ Bug 2 bestätigt.
- 3 Drops (2 pink + 1 blue) wenn das "leer-Drop" Pocket 4 sich anders verhält.
- 4 pink Drops (kein blue) ⇒ mein Modell der retreat-Transition stimmt nicht.

**Welche Pockets sind danach leer:** Genau das ist der Indikator.

### Szenario C — Idealer Plan (Kontrolle)

**Setup:** voller Sort-State (wie B). `current_pocket = 4`.

**Manueller Test:** statt Eject-Step zu starten, das Modell von Hand testen:
1. Notiere Belegung + cur=4.
2. Führe **4× retreat(1)** aus (z. B. via Service-Konsole oder durch temporäres Skript).
3. Erwartung lt. Modell:
   - Transitions: 4→3, 3→2, 2→1, 1→0.
   - Drops nach "X→X-1 droppt X+1"-Lesart (retreat): Pockets 4, 3, 2, 1.
   - Das wären 1 pink + 3 blue. Nicht sauber.
4. Variante: 4× advance(1). Transitions: 4→5, 5→6, 6→7, 7→0.
   - Drops nach "X→X+1 droppt X": Pockets 4, 5, 6, 7. **Alle 4 pink ✓**.
5. Setze cur=4 wieder + 4× advance(1) als sauberer pink-Eject am vollen Layout.

**Wenn (4) funktioniert, ist der Fix klar:** Pink-Eject = "stell sicher cur=4, dann 4× advance". Blue-Eject (nachdem pink leer) = "stell sicher cur=7, dann 4× advance".

### Szenario D — Retreat-Symmetrie

Nur zur Sicherheit, weil das Modell symmetrisch sein sollte:

**Setup:** nur 4 blue in {0,1,2,3}. `current_pocket = 4`.

**Plan:** 4× retreat(1).
- Transitions: 4→3, 3→2, 2→1, 1→0.
- Modell-Vorhersage (retreat X+1→X droppt X+1): Pockets 4 (leer), 3, 2, 1.
  - Oder (retreat-symmetrisch zu advance, droppt das, was vom 6er auf den 5er wechselt): Pockets 4, 3, 2, 1.
- **Vermutlich bleibt Pocket 0 drin.**

**Alternative:** 4× retreat aus `cur=0`. Transitions: 0→7, 7→6, 6→5, 5→4. Drops Pockets 0,7,6,5 — falsch für blue.

**Sauberer blue-Eject Plan (zu validieren):** cur=4, 4× retreat ⇒ Drops 4(leer), 3, 2, 1 ⇒ Pocket 0 bleibt! ⇒ Plan falsch.
Oder cur=3, 4× retreat ⇒ Transitions 3→2,2→1,1→0,0→7 ⇒ Drops 3,2,1,0 — alle blue ✓ (Pocket 7 ist anyway leer in diesem Szenario).

⇒ **Hypothese:** "saubere" Plans sind:
- Forward-Eject von Pockets {a, a+1, …, a+k-1}: cur = (a-1) mod N, dann k× advance.
- Backward-Eject derselben: cur = (a+k-1+1) mod N = a+k mod N, dann k× retreat. *(zu prüfen)*

---

## 4. Was wir nach den Tests wissen werden

Pro Szenario notieren:
- ✓ / ✗ Modell-Vorhersage stimmt mit Realität überein.
- Genaue Drop-Anzahl und -Farben.
- End-`current_pocket`.

Daraus leiten wir ab:
1. **Welche Konvention** (advance droppt "from" oder "to" Pocket; retreat-Symmetrie) tatsächlich gilt.
2. Ob **Bug 1 + Bug 2** real sind.
3. Den **richtigen Fix** für `EjectNearestColorStep` mit konkreten Start-Positions und Sweep-Längen pro Layout.

Erst danach: Code anpassen — mit den verifizierten Annahmen explizit als Kommentar im Step.

---

## 5. Offene Fragen für vor den Tests

- Gibt es Pockets, in denen Drums *nicht* durchs Loch fallen können (z. B. weil eine Klappe sie hält)? Falls ja, beeinflusst das die Drop-Mechanik komplett.
- Ist `current_pocket` nach der Sort-Phase wirklich beim zuletzt sortierten Slot? (Log sagt ja — drum 8 SORTED pocket=4, danach kein move.)
- Gibt es zwischen Collect und Eject einen zusätzlichen Re-Position-Step, der `current_pocket` auf einen definierten Wert bringt? (Aktuell nein.)
