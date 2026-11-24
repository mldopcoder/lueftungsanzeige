# Lüftungsanzeige für Home Assistant

Zeigt pro Raum, wie lange noch gelüftet werden muss, und lernt aus jeder Lüftung.

## Installation

1. Über HACS → Benutzerdefinierte Repositories dieses Repo (Typ: Integration) hinzufügen und installieren – oder den Ordner `custom_components/lueftungsanzeige` manuell nach `/config/custom_components/` kopieren.
2. Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → „Lüftungsanzeige“**. Das einmal pro Raum machen:

Pro Raum: Messgröße (CO2 oder absolute Feuchte), Raumsensor, ggf. Außensensor für Feuchte, optional Fensterkontakt, Raum-/Außentemperatur und Messverzögerung.

Fensterkontakt, Raum- und Außentemperatur sind optional. Mit Fensterkontakt startet und endet die Lüftung automatisch. Mit beiden lernt die Integration getrennt nach Wetterlage (kalt = schnellerer Luftaustausch).

## Entitäten pro Raum

- **Lüften starten** und **Lüften beenden** (Knöpfe)
- **Restlüftzeit** in Minuten, nur während einer Lüftung
- **Empfohlene Lüftungsdauer**: wie lange man jetzt lüften müsste
- **Lüften empfohlen**, **Lüftung aktiv**, **Fenster schließen** (Ziel erreicht)
- **Gelernte Lüftungen** (Diagnose): Anzahl, gelernte Rate, Halbwertszeit
- **Gelerntes zurücksetzen** (standardmäßig deaktiviert)

Ohne Fensterkontakt endet eine Lüftung von selbst, wenn der Wert nach dem Tiefpunkt wieder steigt (Fenster zu) oder nach 90 Minuten. Gelernt wird nur, wenn der Wert spürbar gefallen ist.

## Ereignisse

- `lueftungsanzeige_ziel_erreicht` mit `raum`
- `lueftungsanzeige_beendet` mit `raum`, `grund`, `dauer_min`, `gelernt`

## Beispiel: Push bei „Fenster zu“

```yaml
alias: Lüftung – Fenster schließen
triggers:
  - trigger: event
    event_type: lueftungsanzeige_ziel_erreicht
actions:
  - action: notify.notify
    data:
      title: "Fenster zu 🪟"
      message: "{{ trigger.event.data.raum }}: Lüften reicht."
mode: queued
```

## Beispiel-Karte

```yaml
type: entities
title: Lüften
entities:
  - entity: button.luftung_wohnzimmer_luften_starten
  - entity: sensor.luftung_wohnzimmer_restluftzeit
  - entity: sensor.luftung_wohnzimmer_empfohlene_luftungsdauer
```

Die Entity-IDs ergeben sich aus dem Raumnamen. Am besten nach der Einrichtung im Gerät nachschauen.

## Hinweise

- Netatmo meldet nur etwa alle 6 Minuten und mit Verzögerung. Dafür „Messverzögerung“ auf ca. 5 min stellen. Dazwischen rechnet die Integration den Wert hoch.
- Im Bad ist der Ausgangswert der Tiefstwert der letzten 3 Stunden. Direkt nach einem HA-Neustart fehlt diese Historie noch.
