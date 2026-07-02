<?php
// bugreport.php – Relay-Endpoint für NIT_Code-Fehlerberichte
// ---------------------------------------------------------------------------
// Empfängt den JSON-POST aus "Hilfe → Fehler melden" und leitet ihn als E-Mail
// an $RECIPIENT weiter. Dadurch liegen KEINE Mail-Zugangsdaten im Programm.
//
// Installation:
//   1. Diese Datei auf den Webspace von mint-checker.de legen, z. B. unter
//      https://mint-checker.de/nitcode/bugreport.php
//   2. Dieselbe URL in nit_code/config.py als BUG_REPORT_URL eintragen.
//   3. Sicherstellen, dass PHP mail() (oder ein SMTP-Ersatz) funktioniert.
// ---------------------------------------------------------------------------

header('Content-Type: text/plain; charset=utf-8');

$RECIPIENT = 'nitcode@mint-checker.de';
$FROM      = 'nitcode-bot@mint-checker.de';   // Absender-Domain = eigene Domain
$MAX_BYTES = 200000;                          // 200 KB Obergrenze

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo 'Method Not Allowed';
    exit;
}

$raw = file_get_contents('php://input', false, null, 0, $MAX_BYTES + 1);
if ($raw === false || strlen($raw) > $MAX_BYTES) {
    http_response_code(413);
    echo 'Payload zu gross';
    exit;
}

$data = json_decode($raw, true);
if (!is_array($data)) {
    http_response_code(400);
    echo 'Ungueltiges JSON';
    exit;
}

// Einfaches Rate-Limit pro IP (dateibasiert): max. 1 Bericht / 30 s.
$ip = $_SERVER['REMOTE_ADDR'] ?? '?';
$rl = sys_get_temp_dir() . '/nitcode_rl_' . md5($ip);
if (file_exists($rl) && (time() - filemtime($rl)) < 30) {
    http_response_code(429);
    echo 'Zu viele Anfragen – bitte kurz warten.';
    exit;
}
@touch($rl);

// Globales Stunden-Limit: schuetzt das Postfach vor Flutung auch dann, wenn ein
// Angreifer viele verschiedene IPs nutzt (das Pro-IP-Limit oben greift dann nicht).
$MAX_PER_HOUR = 60;
$gc = sys_get_temp_dir() . '/nitcode_global_count';
$windowStart = time();
$count = 0;
if (file_exists($gc)) {
    $parts = explode(':', trim((string)@file_get_contents($gc)));
    if (count($parts) === 2) {
        $windowStart = (int)$parts[0];
        $count = (int)$parts[1];
    }
    if (time() - $windowStart >= 3600) {   // Zeitfenster abgelaufen -> zuruecksetzen
        $windowStart = time();
        $count = 0;
    }
}
if ($count >= $MAX_PER_HOUR) {
    http_response_code(429);
    echo 'Stundenlimit erreicht – bitte spaeter erneut.';
    exit;
}
@file_put_contents($gc, $windowStart . ':' . ($count + 1), LOCK_EX);

$clip = function ($v, $n) { return mb_substr(trim((string)$v), 0, $n); };
// Fuer Header/Betreff: Zeilenumbrueche entfernen -> verhindert Header-Injection.
$hdr = function ($v) { return trim(str_replace(array("\r", "\n"), ' ', (string)$v)); };

$desc = $clip($data['description'] ?? '', 5000);
if ($desc === '') {
    http_response_code(400);
    echo 'Beschreibung fehlt';
    exit;
}
$email   = $clip($data['email'] ?? '', 200);
$ver     = $clip($data['version'] ?? '', 50);
$plat    = $clip($data['platform'] ?? '', 120);
$ts      = $clip($data['timestamp'] ?? '', 40);
$code    = $clip($data['code'] ?? '', 60000);
$console = $clip($data['console'] ?? '', 60000);

$body  = "Beschreibung:\n$desc\n\n";
$body .= "Version:   $ver\n";
$body .= "Plattform: $plat\n";
$body .= "Zeit:      $ts\n";
$body .= "Melder:    " . ($email !== '' ? $email : '(keine Angabe)') . "\n";
$body .= "IP:        $ip\n\n";
$body .= "----- Code -----\n$code\n\n";
$body .= "----- Konsole -----\n$console\n";

// $ver kommt aus dem Request und geht in den Betreff (Header!) -> CR/LF entfernen.
$verH = $hdr($ver);
$subject = 'NIT_Code Fehlerbericht (' . ($verH !== '' ? $verH : '?') . ')';

$headers  = "From: $FROM\r\n";
if ($email !== '' && filter_var($email, FILTER_VALIDATE_EMAIL)) {
    $headers .= "Reply-To: $email\r\n";
}
$headers .= "Content-Type: text/plain; charset=utf-8\r\n";

if (@mail($RECIPIENT, $subject, $body, $headers)) {
    http_response_code(200);
    echo 'OK';
} else {
    http_response_code(500);
    echo 'Mailversand fehlgeschlagen';
}
