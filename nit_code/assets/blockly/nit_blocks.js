/* NIT-eigene Blöcke + Python/MicroPython-Generatoren.
 *
 * Die Code-Erzeugung folgt den Konventionen des NIT-Codegenerators
 * (siehe coder_panel.py CODER_SYSTEM_PROMPT) UND einem festen Aufbau:
 *   1. Bibliotheken einbinden   (from ... import ...)
 *   2. Instanzen definieren      (Pin/ADC/DAC/PWM/NeoPixel – EINMALIG, nicht in der Schleife)
 *   3. Variablen definieren
 *   4. Funktionen definieren
 *   5. Hauptprogramm
 *
 * Hardware-Objekte werden deshalb nicht inline im Hauptprogramm erzeugt,
 * sondern über definitions_ (mit Schlüssel-Präfix "inst_") in den
 * Instanz-Abschnitt gehoben. Die finish()-Überschreibung sortiert die
 * Abschnitte in die obige Reihenfolge.
 */
(function () {
  var P = Blockly.Python;

  // 4 Leerzeichen Einrückung wie in Standard-Python (statt Blockly-Default 2)
  P.INDENT = '    ';

  // Order-Konstante versionsrobust (neu: .Order.X, alt: .ORDER_X)
  function ord(name) {
    if (P.Order && P.Order[name] !== undefined) return P.Order[name];
    if (P['ORDER_' + name] !== undefined) return P['ORDER_' + name];
    return 99; // ORDER_NONE-Fallback
  }
  function reg(name, fn) {
    if (P.forBlock) P.forBlock[name] = fn;
    P[name] = fn;
  }
  var FNum = Blockly.FieldNumber;
  var FDrop = Blockly.FieldDropdown;
  var NIT_COLOUR = 20;
  var PIN_COLOUR = 200;

  // ── finish() überschreiben: feste Abschnitts-Reihenfolge ──────────────────
  var _origFinish = P.finish;
  P.finish = function (code) {
    var imports = [], instances = [], variables = [], functions = [], rest = [];
    for (var key in this.definitions_) {
      var def = this.definitions_[key];
      if (/^(from |import )/.test(def)) imports.push(def);
      else if (/^def /.test(def)) functions.push(def);
      else if (key.indexOf('inst_') === 0) instances.push(def);
      else if (key.indexOf('var_') === 0 || key === 'variables') variables.push(def);
      else rest.push(def);
    }
    // Mehrfache "from MODUL import ..." zu je einer Zeile pro Modul zusammenfassen
    imports = (function (lines) {
      var fromMods = {}, order = [], plain = [];
      lines.forEach(function (line) {
        var m = /^from (\S+) import (.+)$/.exec(line);
        if (m) {
          if (!fromMods[m[1]]) { fromMods[m[1]] = {}; order.push(m[1]); }
          m[2].split(',').forEach(function (n) { fromMods[m[1]][n.trim()] = true; });
        } else if (plain.indexOf(line) === -1) {
          plain.push(line);
        }
      });
      var out = order.map(function (mod) {
        return 'from ' + mod + ' import ' + Object.keys(fromMods[mod]).sort().join(', ');
      });
      return out.concat(plain);
    })(imports);

    // definitions_ leeren, damit die Original-finish nichts doppelt anhängt;
    // sie übernimmt aber weiterhin die Zustands-/nameDB-Bereinigung.
    this.definitions_ = Object.create(null);
    var mainOnly;
    try {
      mainOnly = _origFinish.call(this, code).replace(/^\s+/, '');
    } catch (e) {
      mainOnly = code;
    }
    var blocks = [];
    if (imports.length)   blocks.push(imports.join('\n'));
    if (instances.length) blocks.push(instances.join('\n'));
    if (variables.length) blocks.push(variables.join('\n'));
    if (rest.length)      blocks.push(rest.join('\n\n'));
    if (functions.length) blocks.push(functions.join('\n\n'));
    var head = blocks.join('\n\n');
    var out = head ? head + '\n\n' + mainOnly : mainOnly;
    return out.replace(/\n{3,}/g, '\n\n').replace(/\s+$/, '') + '\n';
  };

  // ── Roh-Python (Fallback für "Coder → Blockly") ───────────────────────────
  // Hält eine Zeile Python-Code unverändert. So bleibt ein aus Code erzeugtes
  // Block-Programm immer vollständig, auch wenn nicht jede Zeile als eigener
  // Block erkannt wird (z. B. Bibliotheksaufrufe).
  Blockly.Blocks['nit_raw'] = {
    init: function () {
      this.appendDummyInput()
        .appendField('Python:')
        .appendField(new Blockly.FieldTextInput(''), 'CODE');
      this.setPreviousStatement(true, null);
      this.setNextStatement(true, null);
      this.setColour('#7d8794');
      this.setTooltip('Eine Zeile Python-Code (unverändert übernommen).');
    }
  };
  reg('nit_raw', function (block) {
    var code = block.getFieldValue('CODE');
    // Import-Zeilen in den Import-Abschnitt heben (dedupliziert mit echten Blöcken)
    if (/^\s*(from |import )/.test(code)) {
      P.definitions_['rawimp_' + code.trim()] = code.trim();
      return '';
    }
    return code + '\n';
  });

  Blockly.Blocks['nit_raw_expr'] = {
    init: function () {
      this.appendDummyInput().appendField(new Blockly.FieldTextInput(''), 'CODE');
      this.setOutput(true, null);
      this.setColour('#7d8794');
      this.setTooltip('Ein Python-Ausdruck (unverändert übernommen).');
    }
  };
  reg('nit_raw_expr', function (block) { return [block.getFieldValue('CODE'), ord('ATOMIC')]; });

  // ── Warten ────────────────────────────────────────────────────────────────
  Blockly.Blocks['nit_warte'] = {
    init: function () {
      this.appendValueInput('SEK').setCheck('Number').appendField('warte');
      this.appendDummyInput().appendField('Sekunden');
      this.setInputsInline(true);
      this.setPreviousStatement(true, null);
      this.setNextStatement(true, null);
      this.setColour(NIT_COLOUR);
      this.setTooltip('Pausiert das Programm für die angegebene Zeit (Sekunden).');
    }
  };
  reg('nit_warte', function (block) {
    var sek = P.valueToCode(block, 'SEK', ord('NONE')) || '1';
    P.definitions_['from_time_sleep'] = 'from time import sleep';
    return 'sleep(' + sek + ')\n';
  });

  Blockly.Blocks['nit_warte_ms'] = {
    init: function () {
      this.appendValueInput('MS').setCheck('Number').appendField('warte');
      this.appendDummyInput().appendField('Millisekunden');
      this.setInputsInline(true);
      this.setPreviousStatement(true, null);
      this.setNextStatement(true, null);
      this.setColour(NIT_COLOUR);
      this.setTooltip('Pausiert das Programm für die angegebene Zeit (Millisekunden).');
    }
  };
  reg('nit_warte_ms', function (block) {
    var ms = P.valueToCode(block, 'MS', ord('NONE')) || '100';
    P.definitions_['from_time_sleep_ms'] = 'from time import sleep_ms';
    return 'sleep_ms(' + ms + ')\n';
  });

  // ── Digitaler Ausgang ─────────────────────────────────────────────────────
  Blockly.Blocks['nit_pin_write'] = {
    init: function () {
      this.appendDummyInput()
        .appendField('setze Pin')
        .appendField(new FNum(2, 0, 40, 1), 'PIN')
        .appendField('auf')
        .appendField(new FDrop([['HIGH (1)', '1'], ['LOW (0)', '0']]), 'VAL');
      this.setPreviousStatement(true, null);
      this.setNextStatement(true, null);
      this.setColour(PIN_COLOUR);
      this.setTooltip('Schaltet einen digitalen Ausgangs-Pin ein (HIGH) oder aus (LOW).');
    }
  };
  reg('nit_pin_write', function (block) {
    var pin = block.getFieldValue('PIN');
    var val = block.getFieldValue('VAL');
    P.definitions_['from_machine_pin'] = 'from machine import Pin';
    P.definitions_['inst_pin_out_' + pin] = 'pin_out_' + pin + ' = Pin(' + pin + ', Pin.OUT)';
    return 'pin_out_' + pin + '.value(' + val + ')\n';
  });

  // ── Digitaler Eingang (mit Pull-Up/-Down/ohne) ────────────────────────────
  Blockly.Blocks['nit_pin_read'] = {
    init: function () {
      this.appendDummyInput()
        .appendField('digitaler Eingang Pin')
        .appendField(new FNum(4, 0, 40, 1), 'PIN')
        .appendField(new FDrop([['ohne', 'none'], ['Pull-Up', 'up'], ['Pull-Down', 'down']]), 'PULL');
      this.setOutput(true, 'Number');
      this.setColour(PIN_COLOUR);
      this.setTooltip('Liest einen digitalen Eingang (0 oder 1). '
        + 'Pull-Up = HIGH wenn offen (z. B. Taster gegen GND), Pull-Down = LOW wenn offen.');
    }
  };
  reg('nit_pin_read', function (block) {
    var pin = block.getFieldValue('PIN');
    var pull = block.getFieldValue('PULL');
    var arg = pull === 'up' ? ', Pin.PULL_UP' : pull === 'down' ? ', Pin.PULL_DOWN' : '';
    var suffix = pull === 'up' ? '_up' : pull === 'down' ? '_down' : '';
    var name = 'pin_in_' + pin + suffix;
    P.definitions_['from_machine_pin'] = 'from machine import Pin';
    P.definitions_['inst_' + name] = name + ' = Pin(' + pin + ', Pin.IN' + arg + ')';
    return [name + '.value()', ord('FUNCTION_CALL')];
  });

  // ── Analoger Eingang (ADC) ────────────────────────────────────────────────
  Blockly.Blocks['nit_adc_read'] = {
    init: function () {
      this.appendDummyInput()
        .appendField('analog lesen (ADC) Pin')
        .appendField(new FNum(34, 0, 40, 1), 'PIN');
      this.setOutput(true, 'Number');
      this.setColour(PIN_COLOUR);
      this.setTooltip('Liest einen Analogwert (0–1023, 10-Bit, 0–3,6 V).');
    }
  };
  reg('nit_adc_read', function (block) {
    var pin = block.getFieldValue('PIN');
    P.definitions_['from_machine_adc'] = 'from machine import ADC, Pin';
    P.definitions_['inst_adc_' + pin] =
      'adc_' + pin + ' = ADC(Pin(' + pin + '))\n' +
      'adc_' + pin + '.width(ADC.WIDTH_10BIT)\n' +
      'adc_' + pin + '.atten(ADC.ATTN_11DB)';
    return ['adc_' + pin + '.read()', ord('FUNCTION_CALL')];
  });

  // ── Analoger Ausgang (DAC) ────────────────────────────────────────────────
  Blockly.Blocks['nit_dac_write'] = {
    init: function () {
      this.appendValueInput('WERT').setCheck('Number')
        .appendField('setze DAC Pin')
        .appendField(new FNum(25, 0, 40, 1), 'PIN')
        .appendField('auf');
      this.setInputsInline(true);
      this.setPreviousStatement(true, null);
      this.setNextStatement(true, null);
      this.setColour(PIN_COLOUR);
      this.setTooltip('Gibt eine analoge Spannung aus (0–255, nur Pin 25/26).');
    }
  };
  reg('nit_dac_write', function (block) {
    var pin = block.getFieldValue('PIN');
    var wert = P.valueToCode(block, 'WERT', ord('NONE')) || '0';
    P.definitions_['from_machine_dac'] = 'from machine import DAC, Pin';
    P.definitions_['inst_dac_' + pin] = 'dac_' + pin + ' = DAC(Pin(' + pin + '))';
    return 'dac_' + pin + '.write(' + wert + ')\n';
  });

  // ── PWM (z. B. Helligkeit/Motor) ──────────────────────────────────────────
  Blockly.Blocks['nit_pwm_write'] = {
    init: function () {
      this.appendValueInput('DUTY').setCheck('Number')
        .appendField('PWM Pin')
        .appendField(new FNum(2, 0, 40, 1), 'PIN')
        .appendField('Frequenz')
        .appendField(new FNum(1000, 1, 40000, 1), 'FREQ')
        .appendField('Tastgrad');
      this.setInputsInline(true);
      this.setPreviousStatement(true, null);
      this.setNextStatement(true, null);
      this.setColour(PIN_COLOUR);
      this.setTooltip('Pulsweitenmodulation (Tastgrad 0–1023).');
    }
  };
  reg('nit_pwm_write', function (block) {
    var pin = block.getFieldValue('PIN');
    var freq = block.getFieldValue('FREQ');
    var duty = P.valueToCode(block, 'DUTY', ord('NONE')) || '0';
    P.definitions_['from_machine_pwm'] = 'from machine import Pin, PWM';
    P.definitions_['inst_pwm_' + pin] = 'pwm_' + pin + ' = PWM(Pin(' + pin + '), freq=' + freq + ')';
    return 'pwm_' + pin + '.duty(' + duty + ')\n';
  });

  // ── NeoPixel ──────────────────────────────────────────────────────────────
  Blockly.Blocks['nit_neopixel_init'] = {
    init: function () {
      this.appendDummyInput()
        .appendField('NeoPixel an Pin')
        .appendField(new FNum(5, 0, 40, 1), 'PIN')
        .appendField('Anzahl LEDs')
        .appendField(new FNum(8, 1, 1000, 1), 'NUM');
      this.setPreviousStatement(true, null);
      this.setNextStatement(true, null);
      this.setColour(NIT_COLOUR);
      this.setTooltip('Richtet den NeoPixel-Streifen ein (Variable np, einmalig oben).');
    }
  };
  reg('nit_neopixel_init', function (block) {
    var pin = block.getFieldValue('PIN');
    var num = block.getFieldValue('NUM');
    P.definitions_['from_machine_pin'] = 'from machine import Pin';
    P.definitions_['from_neopixel'] = 'from neopixel import NeoPixel';
    P.definitions_['inst_np'] = 'np = NeoPixel(Pin(' + pin + '), ' + num + ')';
    return '';   // Instanz steht oben – kein Code im Hauptprogramm
  });

  Blockly.Blocks['nit_neopixel_set'] = {
    init: function () {
      this.appendValueInput('INDEX').setCheck('Number').appendField('NeoPixel LED');
      this.appendDummyInput()
        .appendField('Farbe R').appendField(new FNum(255, 0, 255, 1), 'R')
        .appendField('G').appendField(new FNum(0, 0, 255, 1), 'G')
        .appendField('B').appendField(new FNum(0, 0, 255, 1), 'B');
      this.setInputsInline(true);
      this.setPreviousStatement(true, null);
      this.setNextStatement(true, null);
      this.setColour(NIT_COLOUR);
      this.setTooltip('Setzt die Farbe einer einzelnen LED (erst "anzeigen" macht es sichtbar).');
    }
  };
  reg('nit_neopixel_set', function (block) {
    var idx = P.valueToCode(block, 'INDEX', ord('NONE')) || '0';
    var r = block.getFieldValue('R'), g = block.getFieldValue('G'), b = block.getFieldValue('B');
    return 'np[' + idx + '] = (' + r + ', ' + g + ', ' + b + ')\n';
  });

  Blockly.Blocks['nit_neopixel_fill'] = {
    init: function () {
      this.appendDummyInput()
        .appendField('NeoPixel alle Farbe R').appendField(new FNum(0, 0, 255, 1), 'R')
        .appendField('G').appendField(new FNum(0, 0, 255, 1), 'G')
        .appendField('B').appendField(new FNum(0, 0, 255, 1), 'B');
      this.setPreviousStatement(true, null);
      this.setNextStatement(true, null);
      this.setColour(NIT_COLOUR);
      this.setTooltip('Setzt alle LEDs auf dieselbe Farbe (erst "anzeigen" macht es sichtbar).');
    }
  };
  reg('nit_neopixel_fill', function (block) {
    var r = block.getFieldValue('R'), g = block.getFieldValue('G'), b = block.getFieldValue('B');
    return 'np.fill((' + r + ', ' + g + ', ' + b + '))\n';
  });

  Blockly.Blocks['nit_neopixel_show'] = {
    init: function () {
      this.appendDummyInput().appendField('NeoPixel anzeigen');
      this.setPreviousStatement(true, null);
      this.setNextStatement(true, null);
      this.setColour(NIT_COLOUR);
      this.setTooltip('Überträgt die gesetzten Farben an den LED-Streifen.');
    }
  };
  reg('nit_neopixel_show', function () {
    return 'np.write()\n';
  });
})();
