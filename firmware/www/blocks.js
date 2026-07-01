// blocks.js
// Eigene, einfache Bloecke fuer den GPIO-Einstieg.
// Spaeter 1:1 erweiterbar um deine nitbw_-Funktionen (Sensoren etc.)
//
// Pin-Bereich 0-21: gueltige GPIOs des ESP32-C3. Fuer den klassischen ESP32
// (GPIO 0-39) hier ggf. den Maximalwert der FieldNumber-Felder anpassen.

Blockly.Blocks['nit_pin_write'] = {
  init: function () {
    this.appendDummyInput()
        .appendField("Pin")
        .appendField(new Blockly.FieldNumber(2, 0, 21, 1), "PIN")
        .appendField("setzen auf")
        .appendField(new Blockly.FieldDropdown([
          ["HIGH (1)", "1"],
          ["LOW (0)", "0"]
        ]), "STATE");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(200);
    this.setTooltip("Setzt einen GPIO-Pin auf HIGH oder LOW");
  }
};

Blockly.Blocks['nit_pin_read'] = {
  init: function () {
    this.appendDummyInput()
        .appendField("Pin")
        .appendField(new Blockly.FieldNumber(4, 0, 21, 1), "PIN")
        .appendField("lesen");
    this.setOutput(true, "Boolean");
    this.setColour(200);
    this.setTooltip("Liest den Zustand eines GPIO-Pins (digital)");
  }
};

Blockly.Blocks['nit_wait'] = {
  init: function () {
    this.appendDummyInput()
        .appendField("warte")
        .appendField(new Blockly.FieldNumber(500, 0, 60000, 1), "MS")
        .appendField("ms");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(120);
    this.setTooltip("Wartet eine bestimmte Anzahl Millisekunden");
  }
};

// --- Python-Codegenerator ---
// Erzeugt Code, der zu deinen bestehenden nitbw_-Konventionen passt.
// Aktuell: reines machine.Pin / time.sleep_ms, spaeter austauschbar
// gegen z.B. "from nitbw_gpio import Pin" etc.

const pythonGenerator = Blockly.Python;

pythonGenerator.forBlock['nit_pin_write'] = function (block) {
  const pin = block.getFieldValue('PIN');
  const state = block.getFieldValue('STATE');
  pythonGenerator.definitions_['import_machine'] = 'import machine';
  const varName = `pin_${pin}`;
  pythonGenerator.definitions_[`pin_${pin}`] =
    `${varName} = machine.Pin(${pin}, machine.Pin.OUT)`;
  return `${varName}.value(${state})\n`;
};

pythonGenerator.forBlock['nit_pin_read'] = function (block) {
  const pin = block.getFieldValue('PIN');
  pythonGenerator.definitions_['import_machine'] = 'import machine';
  const varName = `pin_in_${pin}`;
  pythonGenerator.definitions_[`pin_in_${pin}`] =
    `${varName} = machine.Pin(${pin}, machine.Pin.IN)`;
  const code = `${varName}.value()`;
  return [code, pythonGenerator.ORDER_FUNCTION_CALL];
};

pythonGenerator.forBlock['nit_wait'] = function (block) {
  const ms = block.getFieldValue('MS');
  pythonGenerator.definitions_['import_time'] = 'import time';
  return `time.sleep_ms(${ms})\n`;
};
