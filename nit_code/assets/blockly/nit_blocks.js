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
      else if (key === 'variables') { /* 'x = None'-Vordeklaration weglassen –
          in Python unnoetig; Variablen werden bei der ersten Zuweisung erzeugt */ }
      else if (key.indexOf('var_') === 0) variables.push(def);
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

  // Farbe als (R, G, B)-Tupel – kompakt mit Zahlenfeldern. Dient als Voreinstellung
  // (Shadow) in den NeoPixel-Blöcken, kann aber durch ein eigenes Tupel oder eine
  // Variable ersetzt werden. Gibt genau ein Python-Tupel aus.
  Blockly.Blocks['nit_color_rgb'] = {
    init: function () {
      this.appendDummyInput()
        .appendField('Farbe R').appendField(new FNum(255, 0, 255, 1), 'R')
        .appendField('G').appendField(new FNum(0, 0, 255, 1), 'G')
        .appendField('B').appendField(new FNum(0, 0, 255, 1), 'B');
      this.setOutput(true, null);
      this.setInputsInline(true);
      this.setColour(NIT_COLOUR);
      this.setTooltip('Eine Farbe als (R, G, B)-Tupel. Jeder Wert von 0 bis 255.');
    }
  };
  reg('nit_color_rgb', function (block) {
    var r = block.getFieldValue('R'), g = block.getFieldValue('G'), b = block.getFieldValue('B');
    return ['(' + r + ', ' + g + ', ' + b + ')', ord('ATOMIC')];
  });

  Blockly.Blocks['nit_neopixel_set'] = {
    init: function () {
      this.appendValueInput('INDEX').setCheck('Number').appendField('NeoPixel LED');
      this.appendValueInput('COLOR');
      this.setInputsInline(true);
      this.setPreviousStatement(true, null);
      this.setNextStatement(true, null);
      this.setColour(NIT_COLOUR);
      this.setTooltip('Setzt die Farbe einer einzelnen LED als (R, G, B)-Tupel '
        + '(erst "anzeigen" macht es sichtbar). Statt der R/G/B-Felder kannst du '
        + 'auch ein eigenes Tupel oder eine Variable einsetzen.');
    }
  };
  reg('nit_neopixel_set', function (block) {
    var idx = P.valueToCode(block, 'INDEX', ord('NONE')) || '0';
    var color = P.valueToCode(block, 'COLOR', ord('NONE')) || '(0, 0, 0)';
    return 'np[' + idx + '] = ' + color + '\n';
  });

  Blockly.Blocks['nit_neopixel_fill'] = {
    init: function () {
      this.appendValueInput('COLOR').appendField('NeoPixel alle');
      this.setInputsInline(true);
      this.setPreviousStatement(true, null);
      this.setNextStatement(true, null);
      this.setColour(NIT_COLOUR);
      this.setTooltip('Setzt alle LEDs auf dieselbe Farbe als (R, G, B)-Tupel '
        + '(erst "anzeigen" macht es sichtbar). Statt der R/G/B-Felder kannst du '
        + 'auch ein eigenes Tupel oder eine Variable einsetzen.');
    }
  };
  reg('nit_neopixel_fill', function (block) {
    var color = P.valueToCode(block, 'COLOR', ord('NONE')) || '(0, 0, 0)';
    return 'np.fill(' + color + ')\n';
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

  // ════════════════════════════════════════════════════════════════════════
  //  Datenstrukturen: Tupel und Dictionary
  // ════════════════════════════════════════════════════════════════════════
  // Beide werden über einen Mutator beliebig erweitert (wie die Standard-Liste).
  // Die Serialisierung nutzt – passend zu Blockly-Standardblöcken und zum
  // Rück-Mapping in py2blockly.py – den Zustand { itemCount: n }.
  var TUPLE_COLOUR = 285;
  var DICT_COLOUR  = 195;

  // Generischer "create-with"-Block mit Mutator. prefixes = Value-Input-Präfixe
  // je Element (Tupel: ['ADD'], Dictionary: ['KEY','VALUE']).
  function installVariadic(blockType, itemType, containerType, cfg) {
    var prefixes = cfg.prefixes;
    var nameOf = function (pfx, i) { return pfx + i; };

    // Mutator-Container (Kopf des Mutator-Popups)
    Blockly.Blocks[containerType] = {
      init: function () {
        this.appendDummyInput().appendField(cfg.containerLabel);
        this.appendStatementInput('STACK');
        this.setColour(cfg.colour);
        this.contextMenu = false;
      }
    };
    // Mutator-Element (Flyout des Mutator-Popups)
    Blockly.Blocks[itemType] = {
      init: function () {
        this.appendDummyInput().appendField(cfg.itemLabel);
        this.setPreviousStatement(true);
        this.setNextStatement(true);
        this.setColour(cfg.colour);
        this.contextMenu = false;
      }
    };

    Blockly.Blocks[blockType] = {
      init: function () {
        this.itemCount_ = cfg.initCount;
        this.updateShape_();
        this.setOutput(true, cfg.output || null);
        this.setInputsInline(true);
        this.setColour(cfg.colour);
        this.setMutator(new Blockly.icons.MutatorIcon([itemType], this));
        this.setTooltip(cfg.tooltip);
      },
      saveExtraState: function () { return { itemCount: this.itemCount_ }; },
      loadExtraState: function (state) {
        this.itemCount_ = (state && state['itemCount']) || 0;
        this.updateShape_();
      },
      decompose: function (workspace) {
        var container = workspace.newBlock(containerType);
        container.initSvg();
        var conn = container.getInput('STACK').connection;
        for (var i = 0; i < this.itemCount_; i++) {
          var item = workspace.newBlock(itemType);
          item.initSvg();
          conn.connect(item.previousConnection);
          conn = item.nextConnection;
        }
        return container;
      },
      compose: function (container) {
        var item = container.getInputTargetBlock('STACK');
        var saved = [];           // je Element: Array der Ziel-Verbindungen
        while (item) {
          if (item.isInsertionMarker()) { item = item.getNextBlock(); continue; }
          saved.push(item.valueConnections_ ||
            prefixes.map(function () { return null; }));
          item = item.getNextBlock();
        }
        // Überzählige Kindblöcke trennen
        for (var i = 0; i < this.itemCount_; i++) {
          prefixes.forEach(function (pfx) {
            var input = this.getInput(nameOf(pfx, i));
            var target = input && input.connection.targetConnection;
            if (target && !saved.some(function (cs) { return cs.indexOf(target) !== -1; })) {
              target.disconnect();
            }
          }, this);
        }
        this.itemCount_ = saved.length;
        this.updateShape_();
        for (var i = 0; i < this.itemCount_; i++) {
          for (var p = 0; p < prefixes.length; p++) {
            var c = saved[i][p];
            if (c) c.reconnect(this, nameOf(prefixes[p], i));
          }
        }
      },
      saveConnections: function (container) {
        var item = container.getInputTargetBlock('STACK');
        var i = 0;
        while (item) {
          if (item.isInsertionMarker()) { item = item.getNextBlock(); continue; }
          item.valueConnections_ = prefixes.map(function (pfx) {
            var input = this.getInput(nameOf(pfx, i));
            return input && input.connection.targetConnection;
          }, this);
          i++;
          item = item.getNextBlock();
        }
      },
      updateShape_: function () {
        if (this.itemCount_ && this.getInput('EMPTY')) {
          this.removeInput('EMPTY');
        } else if (!this.itemCount_ && !this.getInput('EMPTY')) {
          this.appendDummyInput('EMPTY').appendField(cfg.emptyLabel);
        }
        for (var i = 0; i < this.itemCount_; i++) {
          if (!this.getInput(nameOf(prefixes[0], i))) {
            for (var p = 0; p < prefixes.length; p++) {
              cfg.decorate(this.appendValueInput(nameOf(prefixes[p], i)), i, p);
            }
          }
        }
        for (var i = this.itemCount_; this.getInput(nameOf(prefixes[0], i)); i++) {
          for (var p = 0; p < prefixes.length; p++) {
            this.removeInput(nameOf(prefixes[p], i));
          }
        }
      }
    };
  }

  // ── Tupel ─────────────────────────────────────────────────────────────────
  installVariadic('nit_tuple_create', 'nit_tuple_item', 'nit_tuple_container', {
    colour: TUPLE_COLOUR, initCount: 2, output: null, prefixes: ['ADD'],
    containerLabel: 'Tupel', itemLabel: 'Element', emptyLabel: 'leeres Tupel ()',
    tooltip: 'Erzeugt ein Tupel – eine feste, unveränderliche Reihe von Werten, z. B. (3, 4).',
    decorate: function (input, i) { input.appendField(i === 0 ? 'Tupel mit' : 'und'); }
  });
  reg('nit_tuple_create', function (block) {
    var items = [];
    for (var i = 0; i < block.itemCount_; i++) {
      items.push(P.valueToCode(block, 'ADD' + i, ord('NONE')) || 'None');
    }
    if (items.length === 1) return ['(' + items[0] + ',)', ord('ATOMIC')];
    return ['(' + items.join(', ') + ')', ord('ATOMIC')];
  });

  // ── Dictionary: erstellen ───────────────────────────────────────────────────
  installVariadic('nit_dict_create', 'nit_dict_pair_item', 'nit_dict_container', {
    colour: DICT_COLOUR, initCount: 2, output: null, prefixes: ['KEY', 'VALUE'],
    containerLabel: 'Dictionary', itemLabel: 'Eintrag', emptyLabel: 'leeres Dictionary {}',
    tooltip: 'Erzeugt ein Dictionary – Paare aus Schlüssel und Wert, z. B. {"name": "Anna"}.',
    decorate: function (input, i, p) {
      if (p === 0) input.appendField(i === 0 ? 'Dictionary mit' : 'und');
      else input.appendField(':');
    }
  });
  reg('nit_dict_create', function (block) {
    var pairs = [];
    for (var i = 0; i < block.itemCount_; i++) {
      var k = P.valueToCode(block, 'KEY' + i, ord('NONE')) || "''";
      var v = P.valueToCode(block, 'VALUE' + i, ord('NONE')) || 'None';
      pairs.push(k + ': ' + v);
    }
    return ['{' + pairs.join(', ') + '}', ord('ATOMIC')];
  });

  // ── Dictionary: Zugriff & Methoden ──────────────────────────────────────────
  Blockly.Blocks['nit_dict_get'] = {
    init: function () {
      this.appendValueInput('DICT').appendField('Wert aus');
      this.appendValueInput('KEY').appendField('bei Schlüssel');
      this.setInputsInline(true);
      this.setOutput(true, null);
      this.setColour(DICT_COLOUR);
      this.setTooltip('Liest den Wert zu einem Schlüssel: dict[schluessel].');
    }
  };
  reg('nit_dict_get', function (block) {
    var d = P.valueToCode(block, 'DICT', ord('MEMBER')) || '{}';
    var k = P.valueToCode(block, 'KEY', ord('NONE')) || "''";
    return [d + '[' + k + ']', ord('MEMBER')];
  });

  Blockly.Blocks['nit_dict_set'] = {
    init: function () {
      this.appendValueInput('DICT').appendField('setze in');
      this.appendValueInput('KEY').appendField('Schlüssel');
      this.appendValueInput('VALUE').appendField('den Wert');
      this.setInputsInline(true);
      this.setPreviousStatement(true, null);
      this.setNextStatement(true, null);
      this.setColour(DICT_COLOUR);
      this.setTooltip('Schreibt einen Wert: dict[schluessel] = wert.');
    }
  };
  reg('nit_dict_set', function (block) {
    var d = P.valueToCode(block, 'DICT', ord('MEMBER')) || 'd';
    var k = P.valueToCode(block, 'KEY', ord('NONE')) || "''";
    var v = P.valueToCode(block, 'VALUE', ord('NONE')) || 'None';
    return d + '[' + k + '] = ' + v + '\n';
  });

  Blockly.Blocks['nit_dict_get_default'] = {
    init: function () {
      this.appendValueInput('DICT').appendField('Wert aus');
      this.appendValueInput('KEY').appendField('bei Schlüssel');
      this.appendValueInput('DEFAULT').appendField('sonst');
      this.setInputsInline(true);
      this.setOutput(true, null);
      this.setColour(DICT_COLOUR);
      this.setTooltip('Liest dict.get(schluessel, ersatz): fehlt der Schlüssel, kommt der Ersatzwert.');
    }
  };
  reg('nit_dict_get_default', function (block) {
    var d = P.valueToCode(block, 'DICT', ord('MEMBER')) || '{}';
    var k = P.valueToCode(block, 'KEY', ord('NONE')) || "''";
    var def = P.valueToCode(block, 'DEFAULT', ord('NONE')) || 'None';
    return [d + '.get(' + k + ', ' + def + ')', ord('FUNCTION_CALL')];
  });

  Blockly.Blocks['nit_dict_remove'] = {
    init: function () {
      this.appendValueInput('DICT').appendField('entferne aus');
      this.appendValueInput('KEY').appendField('den Schlüssel');
      this.setInputsInline(true);
      this.setPreviousStatement(true, null);
      this.setNextStatement(true, null);
      this.setColour(DICT_COLOUR);
      this.setTooltip('Löscht einen Eintrag: del dict[schluessel].');
    }
  };
  reg('nit_dict_remove', function (block) {
    var d = P.valueToCode(block, 'DICT', ord('MEMBER')) || 'd';
    var k = P.valueToCode(block, 'KEY', ord('NONE')) || "''";
    return 'del ' + d + '[' + k + ']\n';
  });

  Blockly.Blocks['nit_dict_contains'] = {
    init: function () {
      this.appendValueInput('KEY').appendField('Schlüssel');
      this.appendValueInput('DICT').appendField('kommt vor in');
      this.setInputsInline(true);
      this.setOutput(true, 'Boolean');
      this.setColour(DICT_COLOUR);
      this.setTooltip('Prüft, ob ein Schlüssel vorhanden ist: schluessel in dict.');
    }
  };
  reg('nit_dict_contains', function (block) {
    var k = P.valueToCode(block, 'KEY', ord('RELATIONAL')) || "''";
    var d = P.valueToCode(block, 'DICT', ord('RELATIONAL')) || '{}';
    return [k + ' in ' + d, ord('RELATIONAL')];
  });

  [['nit_dict_keys', 'Schlüssel von', 'keys'],
   ['nit_dict_values', 'Werte von', 'values'],
   ['nit_dict_items', 'Einträge von', 'items']].forEach(function (spec) {
    Blockly.Blocks[spec[0]] = {
      init: function () {
        this.appendValueInput('DICT').appendField(spec[1]);
        this.setOutput(true, null);
        this.setColour(DICT_COLOUR);
        this.setTooltip('Liefert ' + spec[1] + ' (z. B. für eine for-jede-Schleife).');
      }
    };
    reg(spec[0], function (block) {
      var d = P.valueToCode(block, 'DICT', ord('MEMBER')) || '{}';
      return [d + '.' + spec[2] + '()', ord('FUNCTION_CALL')];
    });
  });

  Blockly.Blocks['nit_dict_length'] = {
    init: function () {
      this.appendValueInput('DICT').appendField('Anzahl Einträge in');
      this.setOutput(true, 'Number');
      this.setColour(DICT_COLOUR);
      this.setTooltip('Anzahl der Einträge: len(dict).');
    }
  };
  reg('nit_dict_length', function (block) {
    var d = P.valueToCode(block, 'DICT', ord('NONE')) || '{}';
    return ['len(' + d + ')', ord('FUNCTION_CALL')];
  });
})();
