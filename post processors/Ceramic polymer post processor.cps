description = "CHAMP Ceramic and Polymer";
vendor = "University of Leeds";
vendorUrl = "https://www.leeds.ac.uk/";
legal = "Copyright (C) 2024 by Daniel Bara";
certificationLevel = 2;
minimumRevision = 45917;

longDescription = "Post for exporting toolpath to a CHAMP machine";

extension = "gcode";
setCodePage("ascii");

capabilities = CAPABILITY_ADDITIVE;
tolerance = spatial(0.002, MM);

highFeedrate = 6000;
minimumChordLength = spatial(0.25, MM);
minimumCircularRadius = spatial(0.4, MM);
maximumCircularRadius = spatial(1000, MM);
minimumCircularSweep = toRad(0.01);
maximumCircularSweep = toRad(180);
allowHelicalMoves = false; // disable helical support
allowSpiralMoves = false; // disable spiral support
allowedCircularPlanes = 1 << PLANE_XY; // allow XY circular motion

// user-defined properties
properties.useImaging = {
  title      : "Imaging",
  description: "Collect Layerwise Images",
  type       : "boolean",
  value      : true,
  scope      : "post"
};

properties.collectLoadCellData = {
  title      : "Load Cell Data",
  description: "Collect Load Cell Data",
  type       : "boolean",
  value      : false,
  scope      : "post"
};

properties.defectCorrection = {
  title      : "Defect correction",
  description: "Insert placeholder for defect correction",
  type       : "boolean",
  value      : false,
  scope      : "post"
};

properties.finishing = {
  title      : "Finishing",
  description: "Insert placeholder for finishing",
  type       : "boolean",
  value      : false,
  scope      : "post"
};

properties.dryingTime = {
  title      : "Drying time (s)",
  description: "Drying time (seconds)",
  type       : "integer",
  value      : 30,
  scope      : "post"
};

properties.firstCorrectionLayer = {
  title      : "First Correction Layer",
  description: "Correct defects after this",
  type       : "integer",
  value      : 3,
  scope      : "post"
};

properties.laserScanning = {
  title      : "Laser scanning",
  description: "Enable laser scanning",
  type       : "boolean",
  value      : false,
  scope      : "post"
};

properties.standalone = {
  title      : "Standalone GCODE",
  description: "Standalone Additive GCODE (used without the Hybrid add-in)",
  type       : "boolean",
  value      : true,
  scope      : "post"
};

properties.zScalingPercentage = {
  title      : "Z shrinking (%)",
  description: "Adjust Z values to account for shrinking from drying",
  type       : "number",
  value      : 0,
  scope      : "post"
};

// included properties
if (typeof properties != "object") {
  properties = {};
}
if (typeof groupDefinitions != "object") {
  groupDefinitions = {};
}
// >>>>> INCLUDED FROM ../common/propertyTemperatureTower.cpi
properties._trigger = {
  title      : "Trigger",
  description: "Specifies whether to use the Z-height or layer number as the trigger to change temperature of the active Extruder.",
  type       : "enum",
  values     : [
    {title:"Disabled", id:"disabled"},
    {title:"by Height", id:"height"},
    {title:"by Layer", id:"layer"}
  ],
  value: "disabled",
  scope: "post",
  group: "temperatureTower"
};
properties._triggerValue = {
  title      : "Trigger Value",
  description: "This number specifies either the Z-height or the layer number increment on when a change should be triggered.",
  type       : "number",
  value      : 10,
  scope      : "post",
  group      : "temperatureTower"
};
properties.tempStart = {
  title      : "Start Temperature",
  description: "Specifies the starting temperature for the active Extruder (degrees C). Note that the temperature specified in the print settings will be overridden by this value.",
  type       : "integer",
  value      : 190,
  scope      : "post",
  group      : "temperatureTower"
};
properties.tempInterval = {
  title      : "Temperature Interval",
  description: "Every step, increase the temperature of the active Extruder by this amount (degrees C).",
  type       : "integer",
  value      : 5,
  scope      : "post",
  group      : "temperatureTower"
};
groupDefinitions.temperatureTower = {
  title      : "Temperature Tower",
  description: "Temperature Towers are used to test new filaments in order to identify the best printing temperature. " +
      "When utilized, this functionality generates a Gcode file where the temperature increases by a set amount, every step in height or layer number.",
  collapsed: true,
  order    : 0
};
// <<<<< INCLUDED FROM ../common/propertyTemperatureTower.cpi
// >>>>> INCLUDED FROM ../common/propertyRelativeExtrusion.cpi
properties.relativeExtrusion = {
  title      : "Relative extrusion mode",
  description: "Select the filament extrusion mode, either absolute or relative.",
  type       : "boolean",
  value      : false,
  scope      : "post"
};
// <<<<< INCLUDED FROM ../common/propertyRelativeExtrusion.cpi

var gFormat = createFormat({prefix:"G", width:1, decimals:0});
var mFormat = createFormat({prefix:"M", width:1, zeropad:true, decimals:0});
var nFormat = createFormat({prefix:"N", width:1, decimals:0});
var pFormat = createFormat({prefix:"P", width:1, decimals:0});
var tFormat = createFormat({prefix:"T", width:1, decimals:0});
var floatFormat = createFormat({decimals:2})
var integerFormat = createFormat({decimals:0});
var gMotionModal = createOutputVariable({control:CONTROL_FORCE}, gFormat); // modal group 1 - G0-G3
var gAbsIncModal = createOutputVariable({}, gFormat); // modal group 3 - G90-91

// Specify the required commands for your printer below.
const commands = {
  laserScan             : mFormat.format(311),
  heatBed               : mFormat.format(332),
  heatBedAndExtruder    : mFormat.format(333),
  digitalInputOff       : mFormat.format(499),
  purgeNozzle           : mFormat.format(14),
  photo                 : mFormat.format(25),
  startLoadCellLog      : [mFormat.format(64), pFormat.format(20)],
  stopLoadCellLog       : [mFormat.format(65), pFormat.format(20)],
  toolChangeToPrinting  : [tFormat.format(1), mFormat.format(6)],
  dryNoPhoto            : mFormat.format(20), 
  dryAndPhoto           : mFormat.format(225),
  logEndOfLayer         : mFormat.format(111),
  stopProcessMonitoring : mFormat.format(999),
  turnEverythingOff     : mFormat.format(30),
  retractPolymerHotEnd  : [mFormat.format(65), pFormat.format(1)],
  augerOn               : mFormat.format(15),
  augerOff              : mFormat.format(16),
  resetAxis             : gFormat.format(92),
};

const settings = {
  useG0              : true, // specifies to either use G0 or G1 commands for rapid movements
  maximumExtruderTemp: 260, // specifies the maximum extruder temperature
  skipParkPosition   : true, // set to true to avoid output of the park position at the end of the program
  comments           : {
    permittedCommentChars: " abcdefghijklmnopqrstuvwxyz0123456789.,=_-*+:/", // letters are not case sensitive, use option 'outputFormat' below. Set to 'undefined' to allow any character
    prefix               : ";", // specifies the prefix for the comment
    suffix               : "", // specifies the suffix for the comment
    outputFormat         : "ignoreCase", // can be set to "upperCase", "lowerCase" and "ignoreCase". Set to "ignoreCase" to write comments without upper/lower case formatting
    maximumLineLength    : 80 // the maximum number of characters allowed in a line
  }
};

const extruders = {
  ceramic : 0,
  polymer : 1
}

// collected state
var activeExtruder = 0;      // track the active extruder.
var currentLayer = 0;        // track the current layer. Gets set to 1 before the first layer is printed.
var parkingActive  = false;  // set to true when printing is done
var isAugerOn = false;       // track the status of the auger screw
var anyExtruderUsed = false; // true if any extruder has been used
var lastComment = "";        // comments are the only way to track what part of the layer we are prinint (e.g. infill, w)
var extruderChangeFlag = false; // used for ignoring the first movement after an extruder change

// layer-based state
var layer_z = 0;  // most recent layer height
var layer_Zs = [0]; // save layer heights by layer
var layer_As = [0]; // save layer heights by layer
var max_x = 0;    // highest part position along X axis in the current layer
var min_x = 0;    // highest part position along X axis in the current layer
var usedCeramicCurrentLayer = false;
var usedPolymerCurrentLayer = false;


function setFormats(_desiredUnit) {
  if (_desiredUnit != unit) {
    writeComment(subst(localize("This printer does not support programs in %1."), _desiredUnit == IN ? "inches" : "millimeters"));
    writeComment(localize("The program has been converted to the supported unit."));
    unit = _desiredUnit;
  }

  xyzFormat = createFormat({decimals:(unit == MM ? 3 : 4)});
  feedFormat = createFormat({decimals:(unit == MM ? 0 : 1)});
  dimensionFormat = createFormat({decimals:(unit == MM ? 3 : 4), zeropad:false, suffix:(unit == MM ? "mm" : "in")});

  bOutput = createOutputVariable({prefix:"B"}, xyzFormat);

  xOutput = createOutputVariable({prefix:"X"}, xyzFormat);
  yOutput = createOutputVariable({prefix:"Y"}, xyzFormat);
  zOutput = createOutputVariable({prefix:"Z"}, xyzFormat);
  feedOutput = createOutputVariable({prefix:"F"}, feedFormat);
  aOutput = createOutputVariable({prefix:"A", type:getProperty("relativeExtrusion") ? TYPE_INCREMENTAL : TYPE_ABSOLUTE}, xyzFormat);
  sOutput = createOutputVariable({prefix:"S", control:CONTROL_FORCE}, xyzFormat); // parameter temperature or speed
  iOutput = createOutputVariable({prefix:"I", control:CONTROL_FORCE}, xyzFormat); // circular output
  jOutput = createOutputVariable({prefix:"J", control:CONTROL_FORCE}, xyzFormat); // circular output
}

function scaleZ(z){
  if (currentLayer == 0){
    return z;
  }
  scaling_factor = (1 - getPropertyLinted(properties.zScalingPercentage)/100);
  scaled_proportion = (currentLayer-1) / currentLayer; // we don't want to scale the current layer
  unscaled_proportion = 1 - scaled_proportion;
  return z * (scaled_proportion * scaling_factor + unscaled_proportion) ;
}

function ceramicOff(){
  setFormats(unit)
  writeComment("CERAMIC OFF");
  writeBlock(gFormat.format(58));
  writeBlock(gFormat.format(91));
  writeBlock(gFormat.format(1), zOutput.format(20), feedOutput.format(540));
  writeBlock(gFormat.format(90));
}

function ceramicOn(){
  setFormats(unit)
  writeComment("CERAMIC ON");
  writeBlock(gFormat.format(58));
  writeBlock(commands.resetAxis, aOutput.format(0));
  writeBlock(gFormat.format(0), gFormat.format(90), xOutput.format(0), yOutput.format(0));
  writeBlock(gFormat.format(0), zOutput.format(layer_z+20), feedOutput.format(540));
  if (currentLayer > 1){
    writeComment("Purge nozzle");
    writeBlock(commands.purgeNozzle);
  }
}

function polymerOff(){
  writeComment("POLYMER OFF")
  writeBlock(gFormat.format(55), gFormat.format(91) ,gFormat.format(1), zOutput.format(20), feedOutput.format(540));
  writeBlock(gFormat.format(90));
  writeBlock(mFormat.format(65), pFormat.format(1));
}

function polymerOn(){
  writeComment("POLYMER ON");
  writeBlock(gFormat.format(55));
  writeBlock(commands.resetAxis, bOutput.format(0));
  writeBlock(gFormat.format(0), gFormat.format(90), xOutput.format(0), yOutput.format(0), zOutput.format(20));
  writeBlock(mFormat.format(64), pFormat.format(1));
}

function onOpen() {
  setFormats(unit);
  if (getPropertyLinted(properties.defectCorrection)) { 
    writeBlock("%"); 
  }
  writeComment("DT: " + getPropertyLinted(properties.dryingTime))

  if (typeof writeProgramHeader == "function") {
    writeProgramHeader();
  }
  writeComment("START GCODE");
  
  writeBlock(gFormat.format(58), gFormat.format(1), gFormat.format(90), xOutput.format(0), yOutput.format(0), zOutput.format(50), feedOutput.format(1500));
  writeBlock(gFormat.format(21), gFormat.format(17), gFormat.format(64));
  writeBlock(gFormat.format(58), gFormat.format(0), xOutput.format(0), yOutput.format(0), zOutput.format(20));
  writeBlock(commands.resetAxis, aOutput.format(0));
  writeBlock(gFormat.format(55));
  writeBlock(commands.resetAxis, bOutput.format(0));
  writeBlock(gFormat.format(58), gFormat.format(90), feedOutput.format(540));
  var polymerUsed = getExtruder(2).filamentDiameter > 0;
  if (polymerUsed){
    writeComment("Polymer is used, heating polymer extruder and bed");
    writeBlock(commands.heatBedAndExtruder);
  }
  else {
    writeComment("Polymer is not used, heating bed only");
    writeBlock(commands.heatBed);
  }
  writeComment("END OF START GCODE");
}

function onSection() {
  // writeBlock(gAbsIncModal.format(90)); // absolute spatial coordinates
  // // writeBlock(getCode(getProperty("relativeExtrusion") ? commands.extrusionMode.relative : commands.extrusionMode.absolute));

  // writeBlock(gFormat.format(28), zOutput.format(0)); // homing Z

  // // lower build plate before homing in XY
  // feedOutput.reset();
  var initialPosition = getFramePosition(currentSection.getInitialPosition());
  // writeBlock(gMotionModal.format(1), zOutput.format(initialPosition.z), feedOutput.format(toPreciseUnit(highFeedrate, MM)));
  // writeBlock(gFormat.format(28), xOutput.format(0), yOutput.format(0)); // homing XY
  // writeBlock(gFormat.format(92), aOutput.format(0));
  writeComment("onSection Z: " + initialPosition.z);
  forceXYZE();
  writeComment("end of onSection");
}

function onClose() {
  writeComment("START OF THE END GCODE");  
  ceramicOff();

  writeComment("CERAMIC_LAYER_END");
  
  if (activeExtruder == extruders.ceramic && currentLayer > 0)
  {
    if (getPropertyLinted(properties.collectLoadCellData))
    {
    writeComment("Stop collecting load cell data");
    writeBlock(commands.stopLoadCellLog);
    }
    if (getPropertyLinted(properties.laserScanning))
    {
      writeComment("Laser Scan")
      writeBlock(commands.laserScan, "#635=" + floatFormat.format(max_x), "#636=" + floatFormat.format(Math.abs(min_x)));
    }
    insertDryPhoto();
    if (getPropertyLinted(properties.laserScanning)){
      writeComment("Laser scan");
      writeBlock(commands.laserScan, "#635=" + floatFormat.format(max_x), "#636=" + floatFormat.format(Math.abs(min_x)));
    }
    writeComment("record end of layer data");
    writeBlock(commands.logEndOfLayer, "#622=" + floatFormat.format(layer_z));
    
    writeComment("Cancel return signal ")
    writeBlock(commands.digitalInputOff)
  }
    if (getPropertyLinted(properties.defectCorrection)){
      insertDefectCorrectionBlock(true);
    }

    if (getPropertyLinted(properties.finishing)){
      writeComment("PLACEHOLDER_FINISHING at Z" + floatFormat.format(layer_z));
      writeBlock(commands.toolChangeToPrinting);
    }

    writeComment("Camera Photo");
    writeBlock(commands.photo, "#625=" + floatFormat.format(layer_z));

    writeBlock(mFormat.format(65), pFormat.format(12));
    writeBlock(gFormat.format(1), gFormat.format(53), zOutput.format(-10), feedOutput.format(1000))
    writeBlock(gFormat.format(1), gFormat.format(54), xOutput.format(0), yOutput.format(-100), feedOutput.format(2000))

    writeComment("Exit process monitoring script")
    writeBlock(commands.stopProcessMonitoring); 
  
    writeBlock(commands.turnEverythingOff);

    writeComment("End of GCODE generated by Ceramic+polymer post processor (except for a ");
    writeComment("percent sign that may be inserted in the next line)")

    if (getPropertyLinted(properties.defectCorrection)){
      writeBlock("%");
    }
}

// >>>>> INCLUDED FROM ../common/onBedTemp.cpi
function onBedTemp(temp, wait) {
  // do nothing
}
// <<<<< INCLUDED FROM ../common/onBedTemp.cpi
// >>>>> INCLUDED FROM ../common/onExtruderTemp.cpi
function onExtruderTemp(temp, wait, id) {
  // do nothing
}
// <<<<< INCLUDED FROM ../common/onExtruderTemp.cpi
// >>>>> INCLUDED FROM ../common/onExtruderChange.cpi
function onExtruderChange(id) {
  setFormats(unit)
  writeComment("Extruder Change to " + id)
  if (id > machineConfiguration.getNumberExtruders()) {
    error(subst(localize("This printer does not support the extruder '%1'."), integerFormat.format(id)));
    return;
  }

  if (parkingActive){
    writeComment("Ignoring extruder change")
    return;
  }

  if (id == extruders.ceramic){
    writeComment("Extruder change to " + id + " - ceramic");
    if (anyExtruderUsed){
      polymerOff();
    }
    ceramicOn();
  }
  if (id == extruders.polymer){
    writeComment("Extruder change to " + id + " - polymer");
    if (anyExtruderUsed){
      ceramicOff(); 
    }
    polymerOn();
  }
  // writeBlock(getCode(commands.extruderChangeCommand), tFormat.format(id));
  activeExtruder = id;
  anyExtruderUsed = true;
  forceXYZE();
  extruderChangeFlag = true;
  writeComment("Done extruder change")
}
// <<<<< INCLUDED FROM ../common/onExtruderChange.cpi
// >>>>> INCLUDED FROM ../common/onExtrusionReset.cpi
function onExtrusionReset(length) {
  // writeComment("onExtrusionReset");
  // if (getPropertyLinted(properties.relativeExtrusion)) {
  //   aOutput.setCurrent(0);
  // }
  // aOutput.reset();
  // writeBlock(gFormat.format(92), aOutput.format(length));
}
// <<<<< INCLUDED FROM ../common/onExtrusionReset.cpi
// >>>>> INCLUDED FROM ../common/onFanSpeed.cpi
function onFanSpeed(speed, id) {
  if (!commands.fan) {
    return;
  }
  if (speed == 0) {
    writeBlock(getCode(commands.fan.off));
  } else {
    writeBlock(getCode(commands.fan.on), sOutput.format(speed));
  }
}
// <<<<< INCLUDED FROM ../common/onFanSpeed.cpi
// >>>>> INCLUDED FROM ../common/onLayer.cpi
function onLayer(num) {
  setFormats(unit)
  currentLayer = num;
  if (typeof executeTempTowerFeatures == "function") {
    executeTempTowerFeatures(num);
  }
  writeComment(localize("Layer") + SP + integerFormat.format(num) + SP + localize("of") + SP + integerFormat.format(layerCount));
  if (typeof changeFilament == "function" && getProperty("changeLayers") != undefined) {
    changeFilament(num);
  }
  if (typeof pausePrint == "function" && getProperty("pauseLayers") != undefined) {
    pausePrint(num);
  }
  if (usedCeramicCurrentLayer && currentLayer > 1) {
    writeComment("CERAMIC_LAYER_END");
    //writeBlock(commands.retractPolymerHotEnd);

    if (getPropertyLinted(properties.collectLoadCellData)){
      writeComment("Stop collecting load cell data");
      writeBlock(commands.stopLoadCellLog);
    }

    if (getPropertyLinted(properties.laserScanning)){
      writeComment("Laser Scan");
      writeBlock(commands.laserScan, "#635=" + floatFormat.format(max_x), "#636=" + Math.abs(min_x).toFixed(2))
    }
    insertDryPhoto();
    if (getPropertyLinted(properties.laserScanning)){
      writeComment("Laser scan");
      writeBlock(commands.laserScan, "#635=" + floatFormat.format(max_x), "#636=" + Math.abs(min_x).toFixed(2))
    }
    writeComment("record end of layer data");
    writeBlock(commands.logEndOfLayer, "#622=" + floatFormat.format(layer_z));

    if (getPropertyLinted(properties.collectLoadCellData)){
      writeComment("Start collecting load cell data");
      writeBlock(commands.startLoadCellLog);
    } 
  }

  if (getPropertyLinted(properties.defectCorrection)){
    insertDefectCorrectionBlock();
  }

  if (activeExtruder == extruders.ceramic){
    writeComment("Purge nozzle");
    writeBlock(commands.purgeNozzle);
  }

  writeComment("End of layer change block");
  usedCeramicCurrentLayer = false;
  usedPolymerCurrentLayer = false;
}
// <<<<< INCLUDED FROM ../common/onLayer.cpi

function insertDefectCorrectionBlock(is_after_last_layer){
  var newLayer = currentLayer // for easier readability (because this is used during a layer change)
  var oldLayer = newLayer - 1 // >= 1 because newLayer is >= 2
  var oldOldLayer = oldLayer - 1 // >= 0 because newLayer is >= 2
  

  var old_layer_top_z = layer_z;
  var old_layer_base_z = layer_Zs[oldOldLayer]

  defect_correction_possible = (newLayer > 3 && newLayer > getPropertyLinted(properties.firstCorrectionLayer))
  if (defect_correction_possible){

    writeBlock("IF [[#1005 EQ 0] AND [#1006 EQ 0]] GOTO " + integerFormat.format(newLayer*2));  // if nothing to correct, jump to print new layer
    writeBlock("IF [#1006 EQ 0] GOTO " + integerFormat.format(oldLayer*2 + 1)); // if no big defects, only remove over-extrusion

    writeBlock(";PLACEHOLDER_FACE_MILLING at Z", old_layer_base_z.toFixed(2)); // remove old layer
    writeBlock(commands.toolChangeToPrinting);

    writeComment("Setting A to end of layer " + oldOldLayer)
    var old_a = layer_As[oldOldLayer]
    if (old_a == null) old_a = 0;
    writeBlock(commands.resetAxis, aOutput.format(old_a));

    writeBlock("GOTO " + integerFormat.format(oldLayer*2));
  }
  writeBlock(nFormat.format(oldLayer*2 + 1));

  if (defect_correction_possible){
    if (!is_after_last_layer){
      writeBlock(";PLACEHOLDER_FACE_MILLING at Z", old_layer_top_z.toFixed(2)); // only remove over-extrusion
      writeBlock(commands.toolChangeToPrinting);
      writeBlock(commands.photo, "#625=" + floatFormat.format(layer_z));
    }
    writeBlock(gFormat.format(58), gFormat.format(90)); // go back to ceramic wcs
    writeBlock(commands.digitalInputOff);
  }
  writeBlock(nFormat.format(newLayer*2));
}

// >>>>> INCLUDED FROM ../common/writeProgramHeader.cpi
function writeProgramHeader() {
  if (programName) {
    writeComment(programName);
  }
  if (programComment) {
    writeComment(programComment);
  }
  writeComment(subst(localize("Printer name: %1 %2"), machineConfiguration.getVendor(), machineConfiguration.getModel()));
  writeComment("TIME:" + integerFormat.format(printTime));  // do not localize
  writeComment(subst(localize("Print time: %1"), formatCycleTime(printTime)));
  for (var i = 1; i <= numberOfExtruders; ++i) {

    writeComment(subst(localize("Extruder %1 material used: %2"), i, dimensionFormat.format(getExtruder(i).extrusionLength)));
    writeComment(subst(localize("Extruder %1 material name: %2"), i, getExtruder(i).materialName));
    writeComment(subst(localize("Extruder %1 filament diameter: %2"), i, xyzFormat.format(getExtruder(i).filamentDiameter) + localize("mm")));
    writeComment(subst(localize("Extruder %1 nozzle diameter: %2"), i, xyzFormat.format(getExtruder(i).nozzleDiameter) + localize("mm")));
    writeComment(subst(localize("Extruder %1 offset x: %2"), i, dimensionFormat.format(machineConfiguration.getExtruderOffsetX(i))));
    writeComment(subst(localize("Extruder %1 offset y: %2"), i, dimensionFormat.format(machineConfiguration.getExtruderOffsetY(i))));
    writeComment(subst(localize("Extruder %1 offset z: %2"), i, dimensionFormat.format(machineConfiguration.getExtruderOffsetZ(i))));
    writeComment(subst(localize("Extruder %1 max temp: %2"), i, integerFormat.format(getExtruder(i).temperature)));
  }
  writeComment(subst(localize("Bed temp: %1"), integerFormat.format(bedTemp)));
  writeComment(subst(localize("Layer count: %1"), integerFormat.format(layerCount)));
  writeComment(subst(localize("Width: %1"), dimensionFormat.format(machineConfiguration.getWidth() - machineConfiguration.getCenterPositionX())));
  writeComment(subst(localize("Depth: %1"), dimensionFormat.format(machineConfiguration.getDepth() - machineConfiguration.getCenterPositionY())));
  writeComment(subst(localize("Height: %1"), dimensionFormat.format(machineConfiguration.getHeight() + machineConfiguration.getCenterPositionZ())));
  writeComment(subst(localize("Center x: %1"), dimensionFormat.format((machineConfiguration.getWidth() / 2.0) - machineConfiguration.getCenterPositionX())));
  writeComment(subst(localize("Center y: %1"), dimensionFormat.format((machineConfiguration.getDepth() / 2.0) - machineConfiguration.getCenterPositionY())));
  writeComment(subst(localize("Center z: %1"), dimensionFormat.format(machineConfiguration.getCenterPositionZ())));
  writeComment(subst(localize("Count of bodies: %1"), integerFormat.format(partCount)));
  writeComment(subst(localize("Fusion version: %1"), getGlobalParameter("version")));
}
// <<<<< INCLUDED FROM ../common/writeProgramHeader.cpi
// >>>>> INCLUDED FROM ../common/commonAdditiveFunctions.cpi
function writeBlock() {
  writeWords(arguments);
}

validate(settings.comments, "Setting 'comments' is required but not defined.");
function formatComment(text) {
  var prefix = settings.comments.prefix;
  var suffix = settings.comments.suffix;
  var _permittedCommentChars = settings.comments.permittedCommentChars == undefined ? "" : settings.comments.permittedCommentChars;
  switch (settings.comments.outputFormat) {
  case "upperCase":
    text = text.toUpperCase();
    _permittedCommentChars = _permittedCommentChars.toUpperCase();
    break;
  case "lowerCase":
    text = text.toLowerCase();
    _permittedCommentChars = _permittedCommentChars.toLowerCase();
    break;
  case "ignoreCase":
    _permittedCommentChars = _permittedCommentChars.toUpperCase() + _permittedCommentChars.toLowerCase();
    break;
  default:
    error(localize("Unsupported option specified for setting 'comments.outputFormat'."));
  }
  if (_permittedCommentChars != "") {
    text = filterText(String(text), _permittedCommentChars);
  }
  text = String(text).substring(0, settings.comments.maximumLineLength - prefix.length - suffix.length);
  return text != "" ?  prefix + text + suffix : "";
}

function writeComment(text) {
  if (!text) {
    return;
  }
  var comments = String(text).split(EOL);
  for (comment in comments) {
    var _comment = formatComment(comments[comment]);
    if (_comment) {
      writeln(_comment);
    }
  }
  if(text == "move to park position"){
    parkingActive = 1;
    writeln(";Ignoring parking!");
  }
}

function onComment(text) {
  lastComment = text;
  writeComment(text);
}

function forceXYZE() {
  xOutput.reset();
  yOutput.reset();
  zOutput.reset();
  aOutput.reset();
}

function getCode(code) {
  return typeof code == "undefined" ? "" : code;
}

function onParameter(name, value) {
  switch (name) {
  case "feedRate":
    rapidFeedrate = toPreciseUnit(value > highFeedrate ? highFeedrate : value, MM);
    break;
  }
}

var nextTriggerValue;
var newTemperature;
var maximumExtruderTemp = 260;
function executeTempTowerFeatures(num) {
  if (settings.maximumExtruderTemp != undefined) {
    maximumExtruderTemp = settings.maximumExtruderTemp;
  }
  if (getProperty("_trigger") != "disabled") {
    var multiplier = getProperty("_trigger") == "height" ? 100 : 1;
    var currentValue = getProperty("_trigger") == "height" ? xyzFormat.format(getCurrentPosition().z * 100) : (num - 1);
    if (num == 1) { // initialize
      nextTriggerValue = getProperty("_triggerValue") * multiplier;
      newTemperature = getProperty("tempStart");
    } else {
      if (currentValue >= nextTriggerValue) {
        newTemperature += getProperty("tempInterval");
        nextTriggerValue += getProperty("_triggerValue") * multiplier;
        if (newTemperature <= maximumExtruderTemp) {
          onExtruderTemp(newTemperature, false, activeExtruder);
        } else {
          error(subst(
            localize("Requested extruder temperature of '%1' exceeds the maximum value of '%2'."), newTemperature, maximumExtruderTemp)
          );
        }
      }
    }
  }
}

function formatCycleTime(cycleTime) {
  var seconds = cycleTime % 60 | 0;
  var minutes = ((cycleTime - seconds) / 60 | 0) % 60;
  var hours = (cycleTime - minutes * 60 - seconds) / (60 * 60) | 0;
  if (hours > 0) {
    return subst(localize("%1h:%2m:%3s"), hours, minutes, seconds);
  } else if (minutes > 0) {
    return subst(localize("%1m:%2s"), minutes, seconds);
  } else {
    return subst(localize("%1s"), seconds);
  }
}

var rapidFeedrate = highFeedrate;
function onRapid(_x, _y, _z) {
  var x = xOutput.format(_x);
  var y = yOutput.format(_y);
  var z = zOutput.format(scaleZ(_z));
  var f = feedOutput.format(rapidFeedrate);

  if (settings.skipParkPosition && parkingActive) {
      return; // skip movements to park position
  }
  if (x || y || z || f) {
    // writeComment("onRapid");
    if (lastComment == "rapid-dry" && extruderChangeFlag){
      writeComment("ignoring X and Y in the first movement after extruder change"); // this is a patch for the toolpath Fusion to avoid going to the previous position after an extruder change (e.g. the infill before printing the part)
      writeBlock(gMotionModal.format(settings.useG0 ? 0 : 1), z, f);
      extruderChangeFlag = false;
    }
    else{
      writeBlock(gMotionModal.format(settings.useG0 ? 0 : 1), x, y, z, f);
    }
    feedOutput.reset();
  }
}

function onLinearExtrude(_x, _y, _z, _f, _e) {
  var x = xOutput.format(_x);
  var y = yOutput.format(_y);
  var z = zOutput.format(scaleZ(_z));
  var f = feedOutput.format(_f);

  if (_e == 0){
    writeComment("extrusion is 0, skipping");
    return;
  }

  if (activeExtruder == extruders.ceramic){
    var extrusion = aOutput.format(_e);
    layer_As[currentLayer] = _e;
    usedCeramicCurrentLayer = true;
  }
  else {
    var extrusion = bOutput.format(_e);
    usedPolymerCurrentLayer = true;
  }

  if (settings.skipParkPosition && parkingActive){
    return;
  }

  var isNextOperationAnExtrusion = [10, 28].includes(getNextRecord().getType());
  // writeComment("LinearExtrude, prev type:" + getPreviousRecord().getType() + " curr type:" + getRecord(getCurrentRecordId()).getType() + " next type:" + getNextRecord().getType());
  
  if (x || y || z || f || extrusion) {
    if (extrusion && activeExtruder == extruders.ceramic && !isAugerOn){
      augerOn();
    }
    if (!extrusion && activeExtruder == extruders.ceramic && isAugerOn){
      augerOff();
    }
    // writeComment("Linear extrude, type: " + getRecord(getCurrentRecordId()).getType())

    writeBlock(gMotionModal.format(1), x, y, z, f, extrusion);

    if (!isNextOperationAnExtrusion && activeExtruder == extruders.ceramic && isAugerOn){
      augerOff();
    }
  }
  
  // track layer height
  layer_z = scaleZ(_z);
  layer_Zs[currentLayer] = scaleZ(_z);

  // tracking minimum and maximum x
  if (_x > max_x){
    max_x = _x;
  }
  if (_x < min_x){
    min_x = _x;
  }
}

function onCircularExtrude(_clockwise, _cx, _cy, _cz, _x, _y, _z, _f, _e) {
  // writeComment("circular extrude")
  var x = xOutput.format(_x);
  var y = yOutput.format(_y);
  var z = zOutput.format(scaleZ(_z));
  var f = feedOutput.format(_f);
  var start = getCurrentPosition();
  var i = iOutput.format(_cx - start.x);
  var j = jOutput.format(_cy - start.y);

  if (_e == 0){
    writeComment("extrusion is 0, skipping");
    return;
  }

  if (activeExtruder == extruders.ceramic){
    var extrusion = aOutput.format(_e);
    layer_As[currentLayer] = _e;
    usedCeramicCurrentLayer = true;
  }
  else {
    var extrusion = bOutput.format(_e);
    usedPolymerCurrentLayer = true;
  }

  switch (getCircularPlane()) {
  case PLANE_XY:

    if (extrusion && activeExtruder == 0 && !isAugerOn){
      augerOn();
    }
    if (!extrusion && activeExtruder == 0 && isAugerOn){
      augerOff();
    }
    
    writeBlock(gMotionModal.format(_clockwise ? 2 : 3), x, y, i, j, f, extrusion);

    var isNextOperationAnExtrusion = [10, 28].includes(getNextRecord().getType());
    // writeComment("Circular extrude, type: " + getRecord(getCurrentRecordId()).getType())
    if (!isNextOperationAnExtrusion && activeExtruder == 0 && isAugerOn){
      augerOff();
    }
    
    break;
  default:
    linearize(tolerance);
  }

  // track layer height
  layer_z = scaleZ(_z);
  layer_Zs[currentLayer] = scaleZ(_z);

  if (_x > max_x){
    max_x = _x;
  }
  if (_x < min_x){
    min_x = _x;
  }
}

function getLayersFromProperty(_property) {
  var layer = getProperty(_property).toString().split(",");
  for (var i in layer) {
    if (!isNaN(parseFloat(layer[i])) && !isNaN(layer[i] - 0) && (layer[i] - Math.floor(layer[i])) === 0) {
      layer[i] = parseFloat(layer[i], 10);
    } else {
      error(subst(
        localize("The property '%1' contains an invalid value of '%2'. Only integers are allowed."), _property.title, layer[i])
      );
      return undefined;
    }
  }
  return layer; // returns an array of layer numbers as integers
}

var pauseLayers;
function pausePrint(num) {
  if (getProperty("pauseLayers") != "") {
    validate(commands.pauseCommand != undefined, "The pause command is not defined.");
    if (num == 1) { // initialize array
      pauseLayers = getLayersFromProperty(properties.pauseLayers);
    }
    if (pauseLayers.indexOf(num) > -1) {
      writeComment(localize("PAUSE PRINT"));
      writeBlock(getCode(commands.displayCommand), getProperty("pauseMessage"));
      forceXYZE();
      writeBlock(gMotionModal.format(1), zOutput.format(machineConfiguration.getParkPositionZ()));
      writeBlock(gMotionModal.format(1), xOutput.format(machineConfiguration.getParkPositionX()), yOutput.format(machineConfiguration.getParkPositionY()));
      writeBlock(getCode(commands.pauseCommand));
    }
  }
}

var changeLayers;
function changeFilament(num) {
  if (getProperty("changeLayers") != "") {
    validate(commands.changeFilament.command != undefined, "The filament change command is not defined.");
    if (num == 1) { // initialize array
      changeLayers = getLayersFromProperty(properties.changeLayers);
    }
    if (changeLayers.indexOf(num) > -1) {
      writeComment(localize("FILAMENT CHANGE"));
      if (getProperty("changeMessage") != "") {
        writeBlock(getCode(commands.displayCommand), getProperty("changeMessage"));
      }
      var words = new Array();
      words.push(commands.changeFilament.command);
      /*
      if (!getProperty("useFirmwareConfiguration")) {
        words.push("X" + xyzFormat.format(machineConfiguration.getParkPositionX()));
        words.push("Y" + xyzFormat.format(machineConfiguration.getParkPositionY()));
        words.push("Z" + xyzFormat.format(getProperty("zPosition")));
        words.push(commands.changeFilament.initialRetract + xyzFormat.format(getProperty("initialRetract")));
        words.push(commands.changeFilament.removalRetract + xyzFormat.format(getProperty("removalRetract")));
      }
      */
      writeBlock(words);
      forceXYZE();
      feedOutput.reset();
    }
  }
}

function isLastMotionRecord(record) {
  while (!(getRecord(record).isMotion())) {
    if (getRecord(record).getType() == RECORD_OPERATION_END) {
      return true;
    }
    ++record;
  }
  return false;
}

function augerOn(){
  writeBlock(commands.augerOn);
  isAugerOn = true;
}

function augerOff() {
  writeBlock(commands.augerOff);
  isAugerOn = false;
}

function insertDryPhoto(){
  if (getProperty("dryingTime") == 0 && getProperty("useImaging") == 0) return;
  
  if (getProperty("dryingTime") > 0 && getProperty("useImaging") == 0){
      writeComment("Drying");
      writeBlock(commands.dryNoPhoto, "#620=" + getProperty("dryingTime"));
      return;
    }
  if (getProperty("dryingTime") == 0 && getProperty("useImaging") == 1){
      writeComment("Photo");
      writeBlock(commands.photo, "#625=" + floatFormat.format(layer_z));
      return;
    }
  if (getProperty("dryingTime") > 0 && getProperty("useImaging") == 1){
      writeComment("Dry and Photo");
      writeBlock(commands.dryAndPhoto, "#620=" + getProperty("dryingTime"), "#622=" + floatFormat.format(layer_z));
      return;
    }
  }
/**
 * A wrapper around getProperty to enable the linting of properties
 * @param prop A reference to the property you want to get, e.g. properties.relativeExtrusion
 * @returns The value of the property
 */
function getPropertyLinted(prop){
  return getProperty(Object.entries(properties).find(([k, v]) => v === prop)[0])
}