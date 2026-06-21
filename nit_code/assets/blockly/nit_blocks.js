/* NIT-eigene Blöcke + Python/MicroPython-Generatoren.
 *
 * Die Code-Erzeugung folgt den Konventionen des NIT-Codegenerators
 * (siehe coder_panel.py CODER_SYSTEM_PROMPT):
 *   - Importe immer als "from ... import ..."
 *   - Warten über "from time import sleep" / "from time import sleep_ms"
 *   - ADC: 10-Bit-Auflösung (WIDTH_10BIT) + volle Bandbreite (ATTN_11DB)
 *   - NeoPixel: from neopixel import NeoPixel, np[i] = (r,g,b), np.write()
 *   - keine main()/__main__-Konstruktion, Code beginnt direkt
 */
(function () {
  var P = Blockly.Python;

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
    return 'Pin(' + pin + ', Pin.OUT).value(' + val + ')\n';
  });

  // ── Digitaler Eingang ─────────────────────────────────────────────────────
  Blockly.Blocks['nit_pin_read'] = {
    init: function () {
      this.appendDummyInput()
        .appendField('digitaler Eingang Pin')
        .appendField(new FNum(4, 0, 40, 1), 'PIN');
      this.setOutput(true, 'Number');
      this.setColour(PIN_COLOUR);
      this.setTooltip('Liest einen digitalen Eingang (0 oder 1).');
    }
  };
  reg('nit_pin_read', function (block) {
    var pin = block.getFieldValue('PIN');
    P.definitions_['from_machine_pin'] = 'from machine import Pin';
    return ['Pin(' + pin + ', Pin.IN).value()', ord('FUNCTION_CALL')];
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
    var fn = P.provideFunction_('lies_adc', [
      'def ' + P.FUNCTION_NAME_PLACEHOLDER_ + '(pin):',
      '    adc = ADC(Pin(pin))',
      '    adc.width(ADC.WIDTH_10BIT)',
      '    adc.atten(ADC.ATTN_11DB)',
      '    return adc.read()'
    ]);
    return [fn + '(' + pin + ')', ord('FUNCTION_CALL')];
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
    return 'DAC(Pin(' + pin + ')).write(' + wert + ')\n';
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
    return 'PWM(Pin(' + pin + '), freq=' + freq + ', duty=' + duty + ')\n';
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
      this.setTooltip('Richtet den NeoPixel-Streifen ein (Variable np).');
    }
  };
  reg('nit_neopixel_init', function (block) {
    var pin = block.getFieldValue('PIN');
    var num = block.getFieldValue('NUM');
    P.definitions_['from_machine_pin'] = 'from machine import Pin';
    P.definitions_['from_neopixel'] = 'from neopixel import NeoPixel';
    return 'np = NeoPixel(Pin(' + pin + '), ' + num + ')\n';
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
      this.setTooltip('Setzt die Farbe einer einzelnen LED (noch nicht sichtbar – erst "anzeigen").');
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
