/* Blöcke für die nitbw-Bibliotheken (ESP32/MicroPython).
 *
 * Die erzeugten Code-Schablonen folgen exakt der API aus
 * coder_panel.py (CODER_SYSTEM_PROMPT). Instanzen werden über definitions_
 * (Schlüssel "inst_*") angelegt und landen so – dank des finish()-Overrides in
 * nit_blocks.js – im Abschnitt "Instanzen", nicht im Hauptprogramm.
 *
 * Eine kleine DSL (B(spec)) hält die vielen Blöcke kompakt.
 */
(function () {
  var P = Blockly.Python;
  function ord(name) {
    if (P.Order && P.Order[name] !== undefined) return P.Order[name];
    if (P['ORDER_' + name] !== undefined) return P['ORDER_' + name];
    return 99;
  }
  var FNum = Blockly.FieldNumber, FDrop = Blockly.FieldDropdown, FText = Blockly.FieldTextInput;
  var LIB = 290;   // Farbe nitbw-Bibliotheken

  // I2C-Bus (von OLED/LCD/BME280/TOF/RTC/AS7262/Compass gemeinsam genutzt)
  var I2C_DEFS = [
    ['from_machine_i2c', 'from machine import I2C, Pin'],
    ['inst_i2c', 'i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)']
  ];

  function subst(tpl, block) {
    return tpl.replace(/%(\w+)%/g, function (_, name) {
      if (block.getInput(name)) return P.valueToCode(block, name, ord('NONE')) || '0';
      var v = block.getFieldValue(name);
      return v == null ? '' : v;
    });
  }

  function buildBlock(b, spec) {
    b.setColour(spec.colour || LIB);
    if (spec.tip) b.setTooltip(spec.tip);
    var pending = [];
    function flush(input) { pending.forEach(function (f) { input.appendField(f[0], f[1]); }); pending = []; }
    (spec.parts || []).forEach(function (p) {
      if (typeof p === 'string') pending.push([p]);
      else if (p.f !== undefined) pending.push([new FNum(p.d != null ? p.d : 0, p.lo, p.hi), p.f]);
      else if (p.sel !== undefined) pending.push([new FDrop(p.o), p.sel]);
      else if (p.txt !== undefined) pending.push([new FText(String(p.d != null ? p.d : '')), p.txt]);
      else if (p.v !== undefined) { var inp = b.appendValueInput(p.v); if (p.c) inp.setCheck(p.c); flush(inp); }
    });
    if (pending.length) flush(b.appendDummyInput());
    b.setInputsInline(true);
    if (spec.out) b.setOutput(true, spec.out === true ? null : spec.out);
    else { b.setPreviousStatement(true, null); b.setNextStatement(true, null); }
  }

  function B(spec) {
    Blockly.Blocks[spec.type] = { init: function () { buildBlock(this, spec); } };
    var fn = function (block) {
      (spec.defs || []).forEach(function (d) {
        P.definitions_[d[0]] = typeof d[1] === 'function' ? d[1](block) : subst(d[1], block);
      });
      var code = spec.code != null ? subst(spec.code, block) : '';
      if (spec.out) return [code, ord(spec.outOrder || 'FUNCTION_CALL')];
      return code ? code + '\n' : '';
    };
    if (P.forBlock) P.forBlock[spec.type] = fn;
    P[spec.type] = fn;
  }

  // ════════════════════════ OLED-Display (I2C) ════════════════════════
  var OLED_INIT = [['from_nitbw_oled', 'from nitbw_oled import OLED']].concat(I2C_DEFS)
    .concat([['inst_oled', "oled = OLED(i2c, chip='%CHIP%')"]]);
  B({ type: 'oled_init', parts: ['OLED-Display Chip', { sel: 'CHIP', o: [['SSD1306', 'ssd1306'], ['SH1106', 'sh1106']] }],
      defs: OLED_INIT, tip: 'Richtet ein OLED-Display am I2C-Bus ein.' });
  B({ type: 'oled_clear', parts: ['OLED löschen'], code: 'oled.clear()' });
  B({ type: 'oled_print', parts: ['OLED schreibe', { v: 'TEXT' }, 'bei x', { f: 'X', d: 0, lo: 0, hi: 127 }, 'y', { f: 'Y', d: 0, lo: 0, hi: 63 }],
      code: 'oled.print(%TEXT%, %X%, %Y%)' });
  B({ type: 'oled_show', parts: ['OLED anzeigen'], code: 'oled.show()' });
  B({ type: 'oled_line', parts: ['OLED Linie x1', { f: 'X1', d: 0, lo: 0, hi: 127 }, 'y1', { f: 'Y1', d: 0, lo: 0, hi: 63 }, 'x2', { f: 'X2', d: 20, lo: 0, hi: 127 }, 'y2', { f: 'Y2', d: 20, lo: 0, hi: 63 }],
      code: 'oled.line(%X1%, %Y1%, %X2%, %Y2%)' });
  B({ type: 'oled_rect', parts: ['OLED Rechteck x', { f: 'X', d: 0, lo: 0, hi: 127 }, 'y', { f: 'Y', d: 0, lo: 0, hi: 63 }, 'b', { f: 'W', d: 20, lo: 1, hi: 128 }, 'h', { f: 'H', d: 10, lo: 1, hi: 64 }],
      code: 'oled.draw_rect(%X%, %Y%, %W%, %H%)' });
  B({ type: 'oled_circle', parts: ['OLED Kreis x', { f: 'X', d: 64, lo: 0, hi: 127 }, 'y', { f: 'Y', d: 32, lo: 0, hi: 63 }, 'r', { f: 'R', d: 10, lo: 1, hi: 64 }],
      code: 'oled.draw_circle(%X%, %Y%, %R%)' });
  B({ type: 'oled_svg', parts: ['OLED zeige SVG-Datei', { txt: 'DATEI', d: 'bild.svg' }],
      code: "oled.show_svg('%DATEI%')",
      tip: 'Zeigt eine SVG-Datei vom Board (nur einfache Formen: Linien, Rechtecke, Kreise, Pfade). Danach "OLED anzeigen" aufrufen.' });
  B({ type: 'oled_bmp', parts: ['OLED zeige BMP-Datei', { txt: 'DATEI', d: 'bild.bmp' }],
      code: "oled.show_bmp('%DATEI%')",
      tip: 'Zeigt eine BMP-Datei vom Board (1/24/32 Bit, wird schwarz/weiss umgewandelt). Danach "OLED anzeigen" aufrufen.' });
  B({ type: 'oled_image', parts: ['OLED zeige Bild', { txt: 'DATEI', d: 'bild1_bitmap' }, 'bei x', { f: 'X', d: 0, lo: 0, hi: 127 }, 'y', { f: 'Y', d: 0, lo: 0, hi: 63 }],
      code: "oled.show_image('%DATEI%', %X%, %Y%)",
      tip: 'Zeigt ein vorbereitetes Bitmap-Bild (mit svg_zu_bitmap.py auf dem PC erzeugt, '
        + 'Modulname ohne .py angeben). Danach "OLED anzeigen" aufrufen.' });

  // ════════════════════════ LCD-Display (I2C) ═════════════════════════
  B({ type: 'lcd_init', parts: ['LCD-Display Adresse', { txt: 'ADDR', d: '0x27' }],
      defs: [['from_nitbw_lcd', 'from nitbw_lcd import LCD']].concat(I2C_DEFS).concat([['inst_lcd', 'lcd = LCD(i2c, addr=%ADDR%)']]),
      tip: 'Richtet ein LCD-Display (HD44780/PCF8574) am I2C-Bus ein.' });
  B({ type: 'lcd_print', parts: ['LCD schreibe', { v: 'TEXT' }, 'Spalte', { f: 'SP', d: 0, lo: 0, hi: 19 }, 'Zeile', { f: 'ZE', d: 0, lo: 0, hi: 3 }],
      code: 'lcd.print(%TEXT%, %SP%, %ZE%)' });
  B({ type: 'lcd_clear', parts: ['LCD löschen'], code: 'lcd.clear()' });

  // ════════════════════════ Töne (Piezo) ══════════════════════════════
  B({ type: 'toene_init', parts: ['Lautsprecher an Pin', { f: 'PIN', d: 15, lo: 0, hi: 40 }, 'Tempo', { f: 'GESCHW', d: 60, lo: 20, hi: 400 }],
      defs: [['from_nitbw_toene', 'from nitbw_toene import TOENE'], ['from_machine_pin', 'from machine import Pin'],
             ['inst_speaker', 'speaker = TOENE(Pin(%PIN%), geschwindigkeit=%GESCHW%)']],
      tip: 'Richtet einen passiven Piezo-Lautsprecher ein.' });
  B({ type: 'toene_ton', parts: ['spiele Note', { txt: 'NOTE', d: 'C4' }, 'Dauer', { sel: 'DAUER', o: [['Ganze', '1'], ['Halbe', '1/2'], ['Viertel', '1/4'], ['Achtel', '1/8'], ['Pause', 'P'] ] }],
      code: 'speaker.ton(("%NOTE%", %DAUER%))' });
  B({ type: 'toene_stop', parts: ['Ton stoppen'], code: 'speaker.stop()' });

  // ════════════════════════ Töne erweitert (NITon) ════════════════════
  var NOTEN = [['c', 'c'], ['d', 'd'], ['e', 'e'], ['f', 'f'], ['g', 'g'], ['a', 'a'], ['h', 'h'], ['c²', 'c2']];
  var DAUERN = [['Viertel', 'viertel'], ['Achtel', 'achtel'], ['Halbe', 'halbe'], ['Ganze', 'ganze'],
                ['punkt. Viertel', 'viertelpunkt'], ['punkt. Halbe', 'halbepunkt'], ['Viertel-Triole', 'vierteltriole']];
  B({ type: 'niton_init', parts: ['NITon-Lautsprecher an Pin', { f: 'PIN', d: 15, lo: 0, hi: 40 }, 'Tempo', { f: 'GESCHW', d: 80, lo: 20, hi: 400 }, 'Legato', { f: 'LEGATO', d: 95, lo: 0, hi: 100 }],
      defs: [['from_nitbw_niton', 'from nitbw_niton import NITon, c, d, e, f, g, a, h, c2, viertel, achtel, halbe, ganze, viertelpunkt, halbepunkt, vierteltriole'],
             ['inst_niton', 'niton = NITon(%PIN%, geschwindigkeit=%GESCHW%, legato=%LEGATO%)']],
      tip: 'Töne mit Notenkonstanten (NITon).' });
  B({ type: 'niton_ton', parts: ['NITon spiele Note', { sel: 'NOTE', o: NOTEN }, 'Dauer', { sel: 'DAUER', o: DAUERN }], code: 'niton.ton(%NOTE%, %DAUER%)' });
  B({ type: 'niton_pause', parts: ['NITon Pause Dauer', { sel: 'DAUER', o: DAUERN }], code: 'niton.ton(0, %DAUER%)' });
  B({ type: 'niton_tempo', parts: ['NITon Tempo (BPM)', { f: 'BPM', d: 120, lo: 20, hi: 400 }], code: 'niton.setGeschw(%BPM%)' });

  // ════════════════════════ MP3-Player MP3-TF-16P (UART) ══════════════
  B({ type: 'mp3_init', parts: ['MP3-Player TX Pin', { f: 'TX', d: 17, lo: 0, hi: 40 }, 'RX Pin', { f: 'RX', d: 16, lo: 0, hi: 40 }],
      defs: [['from_machine_pin', 'from machine import Pin'],
             ['from_machine_uart', 'from machine import UART'],
             ['from_nitbw_mp3', 'from nitbw_mp3 import MP3TF16P'],
             ['inst_mp3_uart', 'mp3_uart = UART(2, baudrate=9600, tx=Pin(%TX%), rx=Pin(%RX%))'],
             ['inst_mp3', 'mp3 = MP3TF16P(mp3_uart)'],
             ['inst_mp3_source', 'mp3.set_source(MP3TF16P.DEVICE_TF)']],
      tip: 'MP3-Modul MP3-TF-16P (DFPlayer-kompatibel) an UART2. TX des ESP32 an RX des Moduls und umgekehrt. '
        + 'Die Musik liegt auf der MicroSD-Karte (Ordner MP3: 0001.mp3, 0002.mp3, ...).' });
  B({ type: 'mp3_volume', parts: ['MP3 Lautstärke', { f: 'VOL', d: 20, lo: 0, hi: 30 }], code: 'mp3.set_volume(%VOL%)',
      tip: 'Lautstärke 0 bis 30.' });
  B({ type: 'mp3_lauter', parts: ['MP3 lauter'], code: 'mp3.volume_up()' });
  B({ type: 'mp3_leiser', parts: ['MP3 leiser'], code: 'mp3.volume_down()' });
  B({ type: 'mp3_play', parts: ['MP3 spiele Titel Nr.', { f: 'NR', d: 1, lo: 1, hi: 3000 }], code: 'mp3.play_mp3(%NR%)',
      tip: 'Spielt die Datei aus dem Ordner MP3 der SD-Karte (Nr. 1 = 0001.mp3).' });
  B({ type: 'mp3_play_folder', parts: ['MP3 spiele Ordner', { f: 'ORDNER', d: 1, lo: 1, hi: 99 }, 'Titel', { f: 'NR', d: 1, lo: 1, hi: 255 }],
      code: 'mp3.play_folder(folder=%ORDNER%, track=%NR%)',
      tip: 'Spielt eine Datei aus einem nummerierten Ordner (Ordner 01..99, Datei 001.mp3..255.mp3).' });
  B({ type: 'mp3_pause', parts: ['MP3 Pause'], code: 'mp3.pause()' });
  B({ type: 'mp3_weiter', parts: ['MP3 fortsetzen'], code: 'mp3.resume()' });
  B({ type: 'mp3_stop', parts: ['MP3 Stopp'], code: 'mp3.stop()' });
  B({ type: 'mp3_next', parts: ['MP3 nächster Titel'], code: 'mp3.next()' });
  B({ type: 'mp3_prev', parts: ['MP3 vorheriger Titel'], code: 'mp3.previous()' });
  B({ type: 'mp3_eq', parts: ['MP3 Equalizer', { sel: 'MODE', o: [['normal', '0'], ['Pop', '1'], ['Rock', '2'], ['Jazz', '3'], ['Klassik', '4'], ['Bass', '5']] }],
      code: 'mp3.set_eq(%MODE%)' });
  B({ type: 'mp3_repeat', parts: ['MP3 Titel wiederholen', { sel: 'EIN', o: [['ein', 'True'], ['aus', 'False']] }], code: 'mp3.repeat_current(%EIN%)' });
  B({ type: 'mp3_loop_all', parts: ['MP3 alle Titel wiederholen', { sel: 'EIN', o: [['ein', 'True'], ['aus', 'False']] }], code: 'mp3.loop_all(%EIN%)' });
  B({ type: 'mp3_random', parts: ['MP3 Zufallswiedergabe'], code: 'mp3.random_all()' });

  // ════════════════════════ MPU6050 (Lage/Bewegung, I2C) ══════════════
  B({ type: 'mpu_init', parts: ['MPU6050 einrichten'],
      defs: [['from_nitbw_mpu6050', 'from nitbw_mpu6050 import MPU6050']].concat(I2C_DEFS).concat([['inst_mpu', 'mpu = MPU6050(i2c, addr=0x68)']]),
      tip: 'Beschleunigungs-/Gyrosensor MPU6050.' });
  B({ type: 'mpu_calibrate', parts: ['MPU6050 Gyro kalibrieren'], code: 'mpu.calibrate_gyro()' });
  B({ type: 'mpu_temp', parts: ['Temperatur (MPU6050)'], out: 'Number', code: 'mpu.read_temperature()' });
  B({ type: 'mpu_pitch', parts: ['Nick-Winkel (pitch)'], out: 'Number', code: 'mpu.read_pitch()' });
  B({ type: 'mpu_roll', parts: ['Roll-Winkel (roll)'], out: 'Number', code: 'mpu.read_roll()' });
  B({ type: 'mpu_tilt', parts: ['Gesamtneigung in Grad'], out: 'Number', code: 'mpu.read_tilt_angle()' });
  B({ type: 'mpu_level', parts: ['ist waagerecht?'], out: 'Boolean', code: 'mpu.is_level()' });
  B({ type: 'mpu_orient', parts: ['Orientierung (Text)'], out: 'String', code: 'mpu.read_orientation_text()' });
  B({ type: 'mpu_accel', parts: ['Beschleunigung messen'], code: 'ax, ay, az = mpu.read_accel()' });
  B({ type: 'mpu_ax', parts: ['Beschleunigung x'], out: 'Number', outOrder: 'ATOMIC', code: 'ax' });
  B({ type: 'mpu_ay', parts: ['Beschleunigung y'], out: 'Number', outOrder: 'ATOMIC', code: 'ay' });
  B({ type: 'mpu_az', parts: ['Beschleunigung z'], out: 'Number', outOrder: 'ATOMIC', code: 'az' });
  B({ type: 'mpu_gyro', parts: ['Drehrate messen'], code: 'gx, gy, gz = mpu.read_gyro()' });
  B({ type: 'mpu_gx', parts: ['Drehrate x'], out: 'Number', outOrder: 'ATOMIC', code: 'gx' });
  B({ type: 'mpu_gy', parts: ['Drehrate y'], out: 'Number', outOrder: 'ATOMIC', code: 'gy' });
  B({ type: 'mpu_gz', parts: ['Drehrate z'], out: 'Number', outOrder: 'ATOMIC', code: 'gz' });

  // ════════════════════════ Ultraschall HC-SR04 ═══════════════════════
  B({ type: 'us_init', parts: ['Ultraschall Trigger Pin', { f: 'TRIG', d: 5, lo: 0, hi: 40 }, 'Echo Pin', { f: 'ECHO', d: 18, lo: 0, hi: 40 }],
      defs: [['from_nitbw_ultraschall', 'from nitbw_ultraschall import Ultraschall'],
             ['inst_ultraschall', 'ultraschall = Ultraschall(trigger=%TRIG%, echo=%ECHO%)']],
      tip: 'Richtet einen HC-SR04 Ultraschallsensor ein.' });
  B({ type: 'us_cm', parts: ['Abstand in cm'], out: 'Number', code: 'ultraschall.messen_cm()' });
  B({ type: 'us_mm', parts: ['Abstand in mm'], out: 'Number', code: 'ultraschall.messen_mm()' });

  // ════════════════════════ Servo ═════════════════════════════════════
  B({ type: 'servo_init', parts: ['Servo an Pin', { f: 'PIN', d: 13, lo: 0, hi: 40 }],
      defs: [['from_nitbw_servo', 'from nitbw_servo import Servo'], ['inst_servo', 'servo = Servo(pin=%PIN%)']],
      tip: 'Richtet einen Servomotor ein.' });
  B({ type: 'servo_winkel', parts: ['Servo Winkel', { v: 'GRAD', c: 'Number' }, 'Grad'], code: 'servo.winkel(%GRAD%)' });
  B({ type: 'servo_mitte', parts: ['Servo Mittelstellung'], code: 'servo.mitte()' });
  B({ type: 'servo_aus', parts: ['Servo aus'], code: 'servo.aus()' });
  B({ type: 'servo_lese', parts: ['Servo Winkel lesen'], out: 'Number', code: 'servo.lese_winkel()' });

  // ════════════════════════ Schrittmotor NEMA17 (A4988) ═══════════════
  B({ type: 'stepperdir_init', parts: ['Schrittmotor (A4988) step', { f: 'STEP', d: 14, lo: 0, hi: 40 }, 'dir', { f: 'DIR', d: 27, lo: 0, hi: 40 }, 'enable', { f: 'EN', d: 26, lo: 0, hi: 40 }],
      defs: [['from_nitbw_stepper', 'from nitbw_stepper import StepperDir, VOR, ZURUECK'],
             ['inst_motor', 'motor = StepperDir(step_pin=%STEP%, dir_pin=%DIR%, enable_pin=%EN%, schritte_pro_umdrehung=200, geschwindigkeit=400)']],
      tip: 'Schrittmotor NEMA17 mit A4988/DRV8825.' });
  B({ type: 'stepperdir_schritte', parts: ['Motor Schritte', { v: 'N', c: 'Number' }, { sel: 'RICHT', o: [['vorwärts', 'VOR'], ['zurück', 'ZURUECK']] }], code: 'motor.schritte(%N%, %RICHT%)' });
  B({ type: 'stepperdir_winkel', parts: ['Motor Winkel', { v: 'GRAD', c: 'Number' }, 'Grad', { sel: 'RICHT', o: [['vorwärts', 'VOR'], ['zurück', 'ZURUECK']] }], code: 'motor.winkel(%GRAD%, %RICHT%)' });
  B({ type: 'stepperdir_aus', parts: ['Motor aus'], code: 'motor.aus()' });

  // ════════════════════════ Schrittmotor 28BYJ-48 (ULN2003) ═══════════
  B({ type: 'stepperuln_init', parts: ['Schrittmotor (ULN2003) IN1', { f: 'I1', d: 19, lo: 0, hi: 40 }, 'IN2', { f: 'I2', d: 18, lo: 0, hi: 40 }, 'IN3', { f: 'I3', d: 5, lo: 0, hi: 40 }, 'IN4', { f: 'I4', d: 17, lo: 0, hi: 40 }],
      defs: [['from_nitbw_stepper2', 'from nitbw_stepper import StepperULN, VOR, ZURUECK'],
             ['inst_motor', 'motor = StepperULN(in1=%I1%, in2=%I2%, in3=%I3%, in4=%I4%, schritte_pro_umdrehung=2048, geschwindigkeit=200)']],
      tip: 'Schrittmotor 28BYJ-48 mit ULN2003.' });
  B({ type: 'stepperuln_umdr', parts: ['Motor Umdrehungen', { v: 'N', c: 'Number' }, { sel: 'RICHT', o: [['vorwärts', 'VOR'], ['zurück', 'ZURUECK']] }], code: 'motor.umdrehungen(%N%, %RICHT%)' });

  // ════════════════════════ Temperatur DS18B20 ════════════════════════
  B({ type: 'ds18b20_init', parts: ['DS18B20 an Pin', { f: 'PIN', d: 4, lo: 0, hi: 40 }],
      defs: [['from_machine_pin', 'from machine import Pin'], ['from_nitbw_ds18b20', 'from nitbw_ds18b20 import DS18B20'],
             ['inst_ds18b20', 'ds18b20 = DS18B20(Pin(%PIN%))']],
      tip: 'Temperatursensor DS18B20 (OneWire).' });
  B({ type: 'ds18b20_messen', parts: ['Temperatur (DS18B20)'], out: 'Number', code: 'ds18b20.messen()' });

  // ════════════════════════ DHT22 (Temp + Feuchte) ════════════════════
  B({ type: 'dht_init', parts: ['DHT22 an Pin', { f: 'PIN', d: 15, lo: 0, hi: 40 }],
      defs: [['from_machine_pin', 'from machine import Pin'], ['from_dht', 'from dht import DHT22'],
             ['inst_dht', 'dht = DHT22(Pin(%PIN%))']],
      tip: 'Temperatur-/Feuchtesensor DHT22.' });
  B({ type: 'dht_measure', parts: ['DHT22 messen'], code: 'dht.measure()' });
  B({ type: 'dht_temp', parts: ['Temperatur (DHT22)'], out: 'Number', code: 'dht.temperature()' });
  B({ type: 'dht_hum', parts: ['Feuchte (DHT22)'], out: 'Number', code: 'dht.humidity()' });

  // ════════════════════════ BME280 (Temp/Druck/Feuchte) ═══════════════
  B({ type: 'bme280_init', parts: ['BME280 einrichten'],
      defs: [['from_nitbw_bme280', 'from nitbw_bme280 import BME280']].concat(I2C_DEFS).concat([['inst_bme280', 'bme280 = BME280(i2c)']]),
      tip: 'Sensor BME280 am I2C-Bus.' });
  B({ type: 'bme280_read', parts: ['BME280 messen'], code: 'temperatur, druck, feuchtigkeit = bme280.read_all()' });
  B({ type: 'bme280_temp', parts: ['Temperatur (BME280)'], out: 'Number', outOrder: 'ATOMIC', code: 'temperatur' });
  B({ type: 'bme280_druck', parts: ['Druck (BME280)'], out: 'Number', outOrder: 'ATOMIC', code: 'druck' });
  B({ type: 'bme280_feuchte', parts: ['Feuchte (BME280)'], out: 'Number', outOrder: 'ATOMIC', code: 'feuchtigkeit' });

  // ════════════════════════ Pulssensor (ADC) ══════════════════════════
  B({ type: 'puls_init', parts: ['Pulssensor an ADC-Pin', { f: 'PIN', d: 34, lo: 0, hi: 40 }],
      defs: [['from_nitbw_puls', 'from nitbw_puls import Pulssensor'], ['inst_puls', 'puls = Pulssensor(adc_pin=%PIN%)']],
      tip: 'Analoger Pulssensor.' });
  B({ type: 'puls_lesen', parts: ['Puls (Mittelwert)'], out: 'Number', code: 'puls.lesen_roh_mittelwert(samples=8, pause_ms=2)' });

  // ════════════════════════ Farbsensor TCS3200 ════════════════════════
  B({ type: 'tcs_init', parts: ['Farbsensor out', { f: 'OUT', d: 27, lo: 0, hi: 40 }, 's2', { f: 'S2', d: 14, lo: 0, hi: 40 }, 's3', { f: 'S3', d: 12, lo: 0, hi: 40 }, 's0', { f: 'S0', d: 26, lo: 0, hi: 40 }, 's1', { f: 'S1', d: 25, lo: 0, hi: 40 }],
      defs: [['from_nitbw_tcs3200', 'from nitbw_tcs3200 import TCS3200'],
             ['inst_farbsensor', 'farbsensor = TCS3200(out=%OUT%, s2=%S2%, s3=%S3%, s0=%S0%, s1=%S1%)']],
      tip: 'Farbsensor TCS3200.' });
  B({ type: 'tcs_farbe', parts: ['dominante Farbe'], out: 'String', code: 'farbsensor.dominante_farbe(messungen=8)' });

  // ════════════════ TOF VL53L0X / VL6180X (I2C) ═══════════════════════
  // sensor_typ='auto' ist der Bibliotheks-Default – bei "automatisch" wird der
  // Parameter weggelassen, damit der Code auch mit älteren nitbw_tof-Versionen läuft.
  B({ type: 'tof_init',
      parts: ['TOF-Sensor einrichten', 'Typ',
              { sel: 'TYP', o: [['automatisch', 'auto'], ['VL53L0X (bis 2 m)', 'vl53l0x'], ['VL6180X (bis 20 cm)', 'vl6180x']] }],
      defs: [['from_nitbw_tof', 'from nitbw_tof import TOF']].concat(I2C_DEFS).concat([
        ['inst_tof', function (block) {
          var typ = block.getFieldValue('TYP');
          return typ === 'auto' ? 'tof = TOF(i2c)' : "tof = TOF(i2c, sensor_typ='" + typ + "')";
        }]]),
      tip: 'Laser-Abstandssensor am I2C-Bus: VL53L0X (Langbereich bis ca. 2 m) oder '
        + 'VL6180X (Kurzdistanz bis ca. 20 cm). "automatisch" erkennt den Sensortyp selbst.' });
  B({ type: 'tof_mm', parts: ['Abstand TOF in mm'], out: 'Number', code: 'tof.messen_mm()' });
  B({ type: 'tof_cm', parts: ['Abstand TOF in cm'], out: 'Number', code: 'tof.messen_cm()' });

  // ════════════════════════ Joystick KY-023 ═══════════════════════════
  B({ type: 'joy_init', parts: ['Joystick VRx', { f: 'VRX', d: 34, lo: 0, hi: 40 }, 'VRy', { f: 'VRY', d: 35, lo: 0, hi: 40 }, 'SW', { f: 'SW', d: 32, lo: 0, hi: 40 }],
      defs: [['from_nitbw_ky023', 'from nitbw_ky023 import KY023'],
             ['inst_joystick', 'joystick = KY023(vrx_pin=%VRX%, vry_pin=%VRY%, sw_pin=%SW%)']],
      tip: 'Joystick KY-023.' });
  B({ type: 'joy_lesen', parts: ['Joystick lesen'], code: 'd = joystick.daten()' });
  B({ type: 'joy_x', parts: ['Joystick x'], out: 'Number', outOrder: 'ATOMIC', code: "d['x']" });
  B({ type: 'joy_y', parts: ['Joystick y'], out: 'Number', outOrder: 'ATOMIC', code: "d['y']" });
  B({ type: 'joy_sw', parts: ['Joystick Taster'], out: 'Boolean', outOrder: 'ATOMIC', code: "d['sw']" });
  B({ type: 'joy_richtung', parts: ['Joystick Richtung'], out: 'String', outOrder: 'ATOMIC', code: "d['richtung']" });

  // ════════════════════════ RTC (I2C) ═════════════════════════════════
  B({ type: 'rtc_init', parts: ['Uhr (RTC)', { sel: 'CHIP', o: [['DS3231', 'DS3231'], ['DS1307', 'DS1307']] }],
      defs: [['from_nitbw_rtc', 'from nitbw_rtc import RTC']].concat(I2C_DEFS).concat([['inst_rtc', "rtc = RTC(chip='%CHIP%', i2c=i2c)"]]),
      tip: 'Echtzeituhr DS3231/DS1307.' });
  B({ type: 'rtc_string', parts: ['Uhrzeit als Text', { txt: 'FORMAT', d: 'DD.MM.YYYY hh:mm:ss' }], out: 'String', code: 'rtc.toString("%FORMAT%")' });

  // ════════════════════════ Kompass (I2C) ═════════════════════════════
  B({ type: 'compass_init', parts: ['Kompass einrichten'],
      defs: [['from_nitbw_compass', 'from nitbw_compass import Compass']].concat(I2C_DEFS).concat([['inst_kompass', 'kompass = Compass(i2c)']]),
      tip: 'Kompass / Magnetometer.' });
  B({ type: 'compass_heading', parts: ['Richtung (Grad)'], out: 'Number', code: 'kompass.read_heading()' });

  // ════════════════════════ Spektralsensor AS7262 (I2C) ═══════════════
  B({ type: 'as7262_init', parts: ['Spektralsensor einrichten'],
      defs: [['from_nitbw_as7262', 'from nitbw_as7262 import AS7262']].concat(I2C_DEFS).concat([['inst_spektral', 'spektral = AS7262(i2c)']]),
      tip: 'Spektralsensor AS7262.' });
  B({ type: 'as7262_messen', parts: ['Spektralwerte (roh)'], out: true, code: 'spektral.messen_roh()' });

  // ════════════════════════ ESP-NOW (Funk) ════════════════════════════
  B({ type: 'espnow_init', parts: ['ESP-NOW einrichten'],
      defs: [['from_nitbw_espnow', 'from nitbw_espnow import ESPNow'], ['inst_espnow', 'espnow = ESPNow()']],
      tip: 'Funkverbindung zwischen zwei ESP32.' });
  B({ type: 'espnow_peer', parts: ['ESP-NOW Empfänger', { txt: 'MAC', d: 'AA:BB:CC:DD:EE:FF' }], code: 'espnow.add_peer("%MAC%")' });
  B({ type: 'espnow_send', parts: ['ESP-NOW sende an', { txt: 'MAC', d: 'AA:BB:CC:DD:EE:FF' }, 'Nachricht', { v: 'MSG' }], code: 'espnow.send("%MAC%", %MSG%)' });

  // ════════════════════════ MQTT (WiFi) ═══════════════════════════════
  B({ type: 'mqtt_init', parts: ['MQTT Broker', { txt: 'SERVER', d: '192.168.0.1' }, 'ID', { txt: 'ID', d: 'esp32' }],
      defs: [['from_nitbw_mqtt', 'from nitbw_mqtt import MQTTClient'],
             ['inst_mqtt', 'mqtt_client = MQTTClient(client_id=b"%ID%", server="%SERVER%", keepalive=30)']],
      tip: 'MQTT-Client (Broker z. B. Raspberry Pi).' });
  B({ type: 'mqtt_connect', parts: ['MQTT verbinden'], code: 'mqtt_client.connect()' });
  B({ type: 'mqtt_publish', parts: ['MQTT sende Thema', { txt: 'TOPIC', d: 'nit/topic' }, 'Wert', { v: 'WERT' }], code: 'mqtt_client.publish(b"%TOPIC%", %WERT%)' });
  B({ type: 'mqtt_check', parts: ['MQTT Nachrichten prüfen'], code: 'mqtt_client.check_msg()' });

  // ════════════════════════ Maschinelles Lernen ═══════════════════════
  // Daten
  B({ type: 'mlearn_init', parts: ['ML-Modell k =', { f: 'K', d: 3, lo: 1, hi: 50 }],
      defs: [['from_nitbw_mlearn', 'from nitbw_mlearn import MLearn'], ['inst_model', 'model = MLearn(k=%K%)']],
      tip: 'Maschinelles Lernen (kNN, Baum, Wald, Netz, …).' });
  B({ type: 'mlearn_load', parts: ['ML lade CSV', { txt: 'DATEI', d: 'daten.csv' }, 'Zielspalte', { f: 'TARGET', d: 0, lo: 0, hi: 50 }],
      code: "model.load_csv('%DATEI%', separator=',', target=%TARGET%)" });
  B({ type: 'mlearn_add', parts: ['ML Beispiel Merkmale', { v: 'FEATURES' }, 'Label', { v: 'LABEL' }], code: 'model.add_sample(%FEATURES%, %LABEL%)' });
  B({ type: 'mlearn_clear', parts: ['ML Daten löschen'], code: 'model.clear_data()' });
  B({ type: 'mlearn_split', parts: ['ML aufteilen Testanteil', { txt: 'ANTEIL', d: '0.2' }, 'Seed', { f: 'SEED', d: 42, lo: 0, hi: 9999 }], code: 'model.split_data(%ANTEIL%, %SEED%)' });
  // kNN
  B({ type: 'mlearn_train_knn', parts: ['ML trainiere kNN'], code: 'model.train_knn()' });
  B({ type: 'mlearn_predict_knn', parts: ['kNN Vorhersage für', { v: 'FEATURES' }], out: true, code: 'model.predict_knn(%FEATURES%)' });
  // Entscheidungsbaum
  B({ type: 'mlearn_train_tree', parts: ['ML trainiere Baum max. Tiefe', { f: 'DEPTH', d: 3, lo: 1, hi: 20 }], code: 'model.train_tree(max_depth=%DEPTH%)' });
  B({ type: 'mlearn_predict_tree', parts: ['Baum Vorhersage für', { v: 'FEATURES' }], out: true, code: 'model.predict_tree(%FEATURES%)' });
  // Random Forest
  B({ type: 'mlearn_train_forest', parts: ['ML trainiere Wald Bäume', { f: 'NTREES', d: 5, lo: 1, hi: 100 }, 'max. Tiefe', { f: 'DEPTH', d: 3, lo: 1, hi: 20 }], code: 'model.train_forest(n_trees=%NTREES%, max_depth=%DEPTH%)' });
  B({ type: 'mlearn_predict_forest', parts: ['Wald Vorhersage für', { v: 'FEATURES' }], out: true, code: 'model.predict_forest(%FEATURES%)' });
  // Logistische Regression
  B({ type: 'mlearn_train_logreg', parts: ['ML trainiere log. Regression'], code: 'model.train_logreg()' });
  B({ type: 'mlearn_predict_logreg', parts: ['log. Regression Vorhersage für', { v: 'FEATURES' }], out: true, code: 'model.predict_logreg(%FEATURES%)' });
  // Neuronales Netz
  B({ type: 'mlearn_train_netz', parts: ['ML trainiere Netz versteckt', { f: 'HIDDEN', d: 8, lo: 1, hi: 64 }, 'Epochen', { f: 'EPOCHS', d: 200, lo: 1, hi: 5000 }], code: 'model.train_netz(hidden=%HIDDEN%, epochs=%EPOCHS%, lr=0.01)' });
  B({ type: 'mlearn_predict_netz', parts: ['Netz Vorhersage für', { v: 'FEATURES' }], out: true, code: 'model.predict_netz(%FEATURES%)' });
  // Bewertung & Speichern
  B({ type: 'mlearn_save', parts: ['ML Modell speichern', { txt: 'DATEI', d: 'modell.json' }, 'Typ', { sel: 'TYP', o: [['kNN', 'knn'], ['Baum', 'tree'], ['Wald', 'forest'], ['Netz', 'netz'], ['log. Regression', 'logreg']] }],
      code: "model.save_model('%DATEI%', model_type='%TYP%')" });
  B({ type: 'mlearn_load_model', parts: ['ML Modell laden', { txt: 'DATEI', d: 'modell.json' }], code: "model.load_model('%DATEI%')" });
})();
