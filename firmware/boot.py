# boot.py
# Wird beim Start automatisch ausgefuehrt (vor main.py).
# Richtet den ESP32 als eigenen WLAN-Accesspoint ein.

import network
import machine
import time
import ubinascii

AP_PASSWORD = "mint2026"   # min. 8 Zeichen fuer WPA2, fuer alle Boards gleich
# Nur die drei ueberlappungsfreien 2,4-GHz-Kanaele. Jedes Board waehlt anhand
# seiner Chip-ID fest einen davon: Im Klassensatz verteilen sich die APs so
# auf drei Kanaele, statt sich alle auf einem Kanal gegenseitig zu stoeren
# (haeufigste Ursache fuer "Verbindung fehlgeschlagen" auf dem iPad).
AP_CHANNELS = (1, 6, 11)
NAME_FILE = "ap_name.txt"   # optionaler, beim Deploy gesetzter Board-Name

# WPA2-PSK. Die Namens-Konstante existiert nicht in jeder MicroPython-Version,
# der Zahlwert 3 (WPA2-PSK) ist aber stabil – daher mit Fallback.
AUTHMODE_WPA2_PSK = getattr(network, "AUTH_WPA2_PSK", 3)


def ap_ssid():
    """SSID dieses Boards.

    Reihenfolge fuer eindeutige Namen im Klassensatz:
      1. Inhalt von ``ap_name.txt`` (beim Aufspielen gesetzt) -> NIT-ESP32-<Name>
      2. sonst automatisch die letzten 4 Hex-Stellen der eindeutigen Chip-ID
         -> z. B. NIT-ESP32-A1B2 (nie zwei gleiche SSIDs, auch ohne Konfiguration)
    """
    name = ""
    try:
        with open(NAME_FILE) as f:
            name = f.read().strip()
    except OSError:
        name = ""
    if not name:
        name = ubinascii.hexlify(machine.unique_id()).decode().upper()[-4:]
    return "NIT-ESP32-" + name


def ap_channel():
    """Fester, aus der Chip-ID abgeleiteter Kanal (1, 6 oder 11)."""
    return AP_CHANNELS[machine.unique_id()[-1] % len(AP_CHANNELS)]


def start_ap():
    ssid = ap_ssid()

    # Station-Modus zuerst abschalten: ein spaeterer Moduswechsel wuerde den
    # AP kurz neu starten und laufende Verbindungsversuche abbrechen.
    sta = network.WLAN(network.STA_IF)
    sta.active(False)

    ap = network.WLAN(network.AP_IF)
    ap.active(True)

    # Direkt nach active(True) wirft config() auf dem C3 gelegentlich
    # "Wifi Internal Error" - der AP liefe dann mit Default-SSID/-Passwort
    # weiter. Deshalb mit kurzen Pausen erneut versuchen.
    for _ in range(5):
        try:
            ap.config(essid=ssid, password=AP_PASSWORD,
                      authmode=AUTHMODE_WPA2_PSK, channel=ap_channel())
            break
        except OSError:
            time.sleep_ms(200)

    # WLAN-Stromsparmodus (Modem-Sleep) abschalten: Der AP verpasst sonst
    # Anmelde-Frames des iPads -> haeufige "Verbindung fehlgeschlagen"-Fehler.
    try:
        ap.config(pm=network.WLAN.PM_NONE)
    except (AttributeError, ValueError, OSError):
        pass   # aeltere MicroPython-Version ohne pm-Option

    while not ap.active():
        pass

    print("Accesspoint aktiv")
    print("SSID:    ", ssid)
    print("Passwort:", AP_PASSWORD)
    print("Kanal:   ", ap.config("channel"))
    print("IP:      ", ap.ifconfig()[0])
    return ap


start_ap()
