"""Verständliche Erklärungen für Netzwerkfehler in Schulumgebungen.

Rohe requests-/urllib-Fehlermeldungen (ProxyError, Tunnel connection failed,
Max retries exceeded …) sind für Lehrkräfte und Schüler nicht zu entziffern.
:func:`with_network_hint` hängt an bekannte Fehlerbilder eine deutsche
Erklärung samt konkretem Behebungs-Schritt an – besonders für die typischen
Schulnetz-Probleme (authentifizierender Proxy, gesperrte Domains, TLS-Inspektion).
"""

# Domains, die NIT_Code für Downloads braucht – tauchen im Proxy-Hinweis auf,
# damit Administratoren wissen, was freizugeben ist.
REQUIRED_DOMAINS = (
    "raw.githubusercontent.com (NIT-Bibliotheken)",
    "api.github.com (Bibliotheksliste)",
    "micropython.org (Firmware)",
    "pypi.org + files.pythonhosted.org (pip)",
)


def friendly_network_error(err) -> str:
    """Liefert einen verständlichen Hinweis zu einem Netzwerkfehler – oder ""."""
    low = str(err).lower()

    if ("407" in low or "proxy authentication required" in low
            or "proxyerror" in low or "tunnel connection failed" in low):
        domains = "\n".join(f"     • {d}" for d in REQUIRED_DOMAINS)
        return (
            "→ Der Internet-Proxy der Schule verlangt eine Anmeldung und lässt\n"
            "   NIT_Code deshalb nicht ins Internet (der Browser meldet sich\n"
            "   automatisch mit der Windows-Anmeldung an, Programme können das nicht).\n"
            "   Bitte den Administrator, diese Adressen am Proxy freizugeben:\n"
            f"{domains}\n"
            "   Alternative ohne Internet: „Aus Ordner installieren …“ im\n"
            "   Bibliotheks-Manager (ZIP von github.com/juchemGDG/NIT_Bibliotheken\n"
            "   zu Hause laden und entpackt mitbringen)."
        )

    if ("getaddrinfo" in low or "name resolution" in low
            or "nodename nor servname" in low or "name or service not known" in low):
        return (
            "→ Der Server wurde nicht gefunden – vermutlich besteht keine\n"
            "   Internetverbindung (WLAN/Netzwerkkabel prüfen) oder das Schulnetz\n"
            "   blockiert die Adresse."
        )

    if "timed out" in low or "timeout" in low:
        return (
            "→ Zeitüberschreitung – die Verbindung ist sehr langsam oder wird vom\n"
            "   Schulnetz blockiert. Später erneut versuchen oder den Administrator\n"
            "   fragen, ob die Adresse freigegeben ist."
        )

    if "certificate" in low or "ssl" in low:
        return (
            "→ Zertifikatsproblem – im Schulnetz prüft vermutlich ein Proxy den\n"
            "   HTTPS-Verkehr (TLS-Inspektion). NIT_Code nutzt den Zertifikatspeicher\n"
            "   des Betriebssystems; bitte den Administrator prüfen lassen, ob das\n"
            "   Proxy-Zertifikat auf diesem Rechner installiert ist."
        )

    if "connection refused" in low or "unreachable" in low:
        return (
            "→ Verbindung abgelehnt – der Server ist nicht erreichbar oder das\n"
            "   Schulnetz blockiert den Zugriff."
        )

    return ""


def git_network_hint(output: str) -> str:
    """Verständlicher Hinweis zu Git-Netzwerkfehlern (clone/pull/push) – oder "".

    Git bringt seine eigene Netzwerkschicht (libcurl) mit und nutzt – anders
    als der Browser – den Windows-System-Proxy nicht automatisch. NIT_Code
    reicht den System-Proxy zwar an Git durch (siehe ``_git_network_env`` im
    Hauptfenster), aber bei PAC-Skripten oder Sonderkonfigurationen bleibt
    nur die manuelle Einrichtung – die erklärt dieser Hinweis.
    """
    low = (output or "").lower()

    if ("failed to connect" in low or "could not connect to server" in low
            or "couldn't connect to server" in low
            or "connection timed out" in low or "operation timed out" in low):
        return (
            "→ Git konnte den Server nicht direkt erreichen. Im Schulnetz muss\n"
            "   auch Git den Internet-Proxy verwenden – NIT_Code gibt dazu den in\n"
            "   Windows hinterlegten System-Proxy automatisch an Git weiter.\n"
            "   Wird der Proxy nur über ein Automatik-Skript (PAC) verteilt,\n"
            "   findet Git ihn nicht; dann einmalig einrichten (Proxy-Adresse\n"
            "   beim Administrator erfragen):\n"
            "       git config --global http.proxy http://PROXYNAME:PORT\n"
            "   Zusätzlich muss der Git-Server (z. B. gitcamp-bw.de) am Proxy\n"
            "   für ALLE Programme freigegeben sein, nicht nur für den Browser."
        )

    if "407" in low or "proxy authentication required" in low:
        return (
            "→ Der Internet-Proxy der Schule verlangt eine Anmeldung und lässt\n"
            "   Git deshalb nicht durch (der Browser meldet sich automatisch mit\n"
            "   der Windows-Anmeldung an, Git kann das nicht). Bitte den\n"
            "   Administrator, den Git-Server am Proxy ohne Anmeldung freizugeben."
        )

    if "ssl certificate problem" in low or "unable to get local issuer" in low:
        return (
            "→ Zertifikatsproblem – im Schulnetz prüft vermutlich ein Proxy den\n"
            "   HTTPS-Verkehr (TLS-Inspektion). Git unter Windows einmalig auf den\n"
            "   Windows-Zertifikatspeicher umstellen:\n"
            "       git config --global http.sslBackend schannel"
        )

    if "could not resolve host" in low:
        return (
            "→ Der Server wurde nicht gefunden – vermutlich besteht keine\n"
            "   Internetverbindung (WLAN/Netzwerkkabel prüfen) oder das Schulnetz\n"
            "   blockiert die Adresse."
        )

    return ""


def with_network_hint(err, prefix: str = "") -> str:
    """Fehlermeldung plus (falls erkannt) verständlicher Hinweis."""
    msg = f"{prefix}{err}"
    hint = friendly_network_error(err)
    return f"{msg}\n\n{hint}" if hint else msg
