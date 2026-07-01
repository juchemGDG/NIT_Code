# boot.py
# Wird beim Start automatisch ausgefuehrt (vor main.py).
# Richtet den ESP32 als eigenen WLAN-Accesspoint ein.

import network

AP_SSID = "NIT-ESP32-Blockly"
AP_PASSWORD = "mint2026"   # min. 8 Zeichen fuer WPA2, gerne anpassen
AP_CHANNEL = 6

# WPA2-PSK. Die Namens-Konstante existiert nicht in jeder MicroPython-Version,
# der Zahlwert 3 (WPA2-PSK) ist aber stabil – daher mit Fallback.
AUTHMODE_WPA2_PSK = getattr(network, "AUTH_WPA2_PSK", 3)

def start_ap():
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=AP_SSID, password=AP_PASSWORD,
              authmode=AUTHMODE_WPA2_PSK, channel=AP_CHANNEL)

    # Eigenes Wifi (Station-Modus) sicherheitshalber abschalten,
    # damit der ESP32 wirklich nur als AP arbeitet
    sta = network.WLAN(network.STA_IF)
    sta.active(False)

    while not ap.active():
        pass

    print("Accesspoint aktiv")
    print("SSID:    ", AP_SSID)
    print("Passwort:", AP_PASSWORD)
    print("IP:      ", ap.ifconfig()[0])
    return ap

start_ap()
