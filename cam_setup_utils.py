import os
from pathlib import Path
import adsk.core
import adsk.cam
import adsk.fusion
from . import fusion_utils
from .lib import fusion360utils as futil
import xml.etree.ElementTree as ET
from . import config


def create_additive_setup(doc, cam: adsk.cam.CAM, name="Additive") -> adsk.cam.Setup | None:
    '''Creates an additive setup for ceramic 3D printing
    Based on https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-{482C239A-22E9-4943-A63F-70CAA8C6CC1B}'''

    setups = cam.setups
    setup = fusion_utils.get_setup_by_name(doc, name)
    if setup is not None:
        return setup

    occs = _try_create_manufacturing_model(cam, "Additive")
    if occs is None:
        raise RuntimeError("Could not create manufacturing model")

    input = setups.createInput(adsk.cam.OperationTypes.AdditiveOperation)  # type: ignore
    input.models = occs  # type: ignore
    input.name = name

    libraryManager = adsk.cam.CAMManager.get().libraryManager
    printsetting = _get_printsetting_through_library(config.PRINTSETTING_PATH, libraryManager)
    machine: adsk.cam.Machine = adsk.cam.Machine.createFromFile(
        adsk.cam.LibraryLocations.LocalLibraryLocation,  # type: ignore
        str(config.MACHINE_SETTING_PATH))
    machineLibrary = libraryManager.machineLibrary

    machineUrl = machineLibrary.urlByLocation(
        adsk.cam.LibraryLocations.LocalLibraryLocation)  # type: ignore
    machines = machineLibrary.childMachines(machineUrl)

    for m in machines:
        # TODO: import to library if not present
        futil.log(f"machine id: {m.model}")

    input.machine = machine
    input.printSetting = printsetting
    setup = setups.add(input)

    cam.generateToolpath(setup)
    return setup


def create_finishing_setup(cam: adsk.cam.CAM, name="Finishing") -> adsk.cam.Setup | None:
    """Creates a milling setup and adds a finishing operation from a finishing template"""
    # create setup input
    setupInput = cam.setups.createInput(adsk.cam.OperationTypes.MillingOperation)  # type: ignore

    # assign Milling manufacturing model
    manufacturing_model_occs = _try_create_manufacturing_model(cam, "Milling", raft_offset=True)
    if manufacturing_model_occs is None:
        raise RuntimeError("Could not create manufacturing model")
    setupInput.models = manufacturing_model_occs  # type: ignore

    # add setup
    setup = cam.setups.add(setupInput)
    setup.parameters.itemByName("wcs_origin_mode").expression = "'modelOrigin'"

    # create milling operation from template
    operation_template = adsk.cam.CAMTemplate.createFromFile(str(config.FINISHING_TEMPLATE_PATH))
    template_input = adsk.cam.CreateFromCAMTemplateInput.create()
    template_input.camTemplate = operation_template
    setup.createFromCAMTemplate2(template_input)

    # ensure the same setup does not exist already
    if any(filter(lambda s: s.name == name, cam.setups)):  # type: ignore
        futil.log(f"Setup {name} already exists", force_console=True)
        setup.deleteMe()
        return None
    setup.name = name
    cam.generateToolpath(setup)
    return setup


def create_face_milling_setup(cam: adsk.cam.CAM, rootComp: adsk.fusion.Component, new_setup_name) -> adsk.cam.Setup | None:
    """Creates a setup with a single Adaptive2D operation to be used for planarisation/defect correction"""
    # create milling setup
    setupInput = cam.setups.createInput(adsk.cam.OperationTypes.MillingOperation)  # type: ignore

    # create Milling manufacturing model
    manufacturing_model_occs = _try_create_manufacturing_model(cam, "Milling", raft_offset=True)
    if manufacturing_model_occs is None:
        raise RuntimeError("Could not create manufacturing model")
    setupInput.models = manufacturing_model_occs  # type: ignore

    # add setup
    setup = cam.setups.add(setupInput)
    setup.parameters.itemByName("wcs_origin_mode").expression = "'modelOrigin'"

    # create Adaptive2D operation from template
    operation_template = adsk.cam.CAMTemplate.createFromFile(str(config.DEFECT_CORRECTION_TEMPLATE_PATH))
    template_input = adsk.cam.CreateFromCAMTemplateInput.create()
    template_input.camTemplate = operation_template
    setup.createFromCAMTemplate2(template_input)
    adaptive2D = setup.operations[0]

    # select top face and ensure the same setup does not exist already
    _try_update_adaptive2d_face(cam, rootComp, setup, adaptive2D)

    if any(filter(lambda s: s.name == new_setup_name, cam.setups)):  # type: ignore
        futil.log(f"Setup {new_setup_name} already exists", force_console=True)
        setup.deleteMe()
        return None
    futil.log(f"Setup {new_setup_name} created")
    
    setup.name = new_setup_name
    return setup


def _get_printsetting_through_library(printsetting_path: Path, libraryManager: adsk.cam.CAMLibraryManager):
    printsetting_name = "Ceramic and Polymer"
    printsetting_xml = ET.parse(printsetting_path)
    # TODO: get name dynamically form xml
    # futil.log(f"printsetting id: {ps.name}, xml name: {printsetting_xml.getroot().find('name').text}")
    with open(printsetting_path) as printsetting_file:
        loaded_printsetting: adsk.cam.PrintSetting = adsk.cam.PrintSetting.createFromXML(printsetting_file.read())

    printSettingLibrary = libraryManager.printSettingLibrary
    localLibraryUrl = printSettingLibrary.urlByLocation(
        adsk.cam.LibraryLocations.LocalLibraryLocation)  # type: ignore
    printSettings = printSettingLibrary.childPrintSettings(localLibraryUrl)

    if not any(map(lambda ps: ps.name == printsetting_name, printSettings)):
        printSettingLibrary.importPrintSetting(loaded_printsetting,
                                               localLibraryUrl,  # type: ignore
                                               printsetting_name)
    return next(filter(lambda ps: ps.name == printsetting_name, printSettingLibrary.childPrintSettings(localLibraryUrl)))


def _getValidOccurrences(occurrence: adsk.fusion.Occurrence) -> list[adsk.fusion.Occurrence]:
    '''From https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-{482C239A-22E9-4943-A63F-70CAA8C6CC1B}'''
    result = []
    for childOcc in occurrence.childOccurrences:
        if (childOcc.bRepBodies.count + childOcc.component.meshBodies.count > 0):
            result.append(childOcc)

        result.extend(_getValidOccurrences(childOcc))

    return result


def _try_create_manufacturing_model(cam: adsk.cam.CAM, manufacturing_model_name: str, raft_offset:bool = False) -> list[adsk.fusion.Occurrence] | None:
    manufacturingModels = cam.manufacturingModels
    if any(map(lambda m: m.name == manufacturing_model_name, manufacturingModels)):
        manufacturingModel = manufacturingModels.itemByName(manufacturing_model_name)[0]
        is_new = False
    else:
        mmInput = manufacturingModels.createInput()
        mmInput.name = manufacturing_model_name
        manufacturingModel = manufacturingModels.add(mmInput)
        is_new = True

    occs = _getValidOccurrences(manufacturingModel.occurrence)
    if len(occs) == 0:
        futil.log("No occurrences found")
        return None
    if raft_offset and is_new:
        _offset_for_raft(occs)
    if config.CENTER_BODY_IN_MANUFACTURING_MODEL:
        if is_new:
            _move_to_middle(occs)
    return occs

def body_is_in_middle(manufacturing_model: adsk.cam.ManufacturingModel):
    occs = _getValidOccurrences(manufacturing_model.occurrence)
    occs:list[adsk.fusion.Occurrence]
    futil.log(f"checking body is in middle: {occs[0].getPhysicalProperties().centerOfMass}")
    return all(map(lambda x: abs(x) < 0.1, [occs[0].getPhysicalProperties().centerOfMass.x, occs[0].getPhysicalProperties().centerOfMass.y]))

def _move_to_middle(occs:list[adsk.fusion.Occurrence]):
    body = occs[0].component.bRepBodies[0]
    to_move = adsk.core.ObjectCollection.create()
    to_move.add(body)
    move_input = occs[0].component.features.moveFeatures.createInput2(to_move)

    x_offset = adsk.core.ValueInput.createByReal(-body.getPhysicalProperties().centerOfMass.x)
    y_offset = adsk.core.ValueInput.createByReal(-body.getPhysicalProperties().centerOfMass.y)
    move_input.defineAsTranslateXYZ(x_offset, y_offset, adsk.core.ValueInput.createByReal(0), True)
    occs[0].component.features.moveFeatures.add(move_input)

def _offset_for_raft(occs:list[adsk.fusion.Occurrence]):
    '''offset milling manufacturing model to compensate for for raft in 3D printing'''
    to_move = adsk.core.ObjectCollection.create()
    to_move.add(occs[0].component.bRepBodies[0])
    move_input = occs[0].component.features.moveFeatures.createInput2(to_move)
    z_offset = adsk.core.ValueInput.createByReal(config.RAFT_HEIGHT/10)
    move_input.defineAsTranslateXYZ(adsk.core.ValueInput.createByReal(0), adsk.core.ValueInput.createByReal(0), z_offset, True)
    occs[0].component.features.moveFeatures.add(move_input)


def _try_update_adaptive2d_face(cam: adsk.cam.CAM, comp: adsk.fusion.Component, setup: adsk.cam.Setup, operation: adsk.cam.Operation) -> float | None:
    """Sets the pocket parameter on an Adaptive2D operation to the top face and returns the height of the face or None if the face was not found.
    Necessary to run at each height for planarisation/defect correction G-code generation, otherwise not all faces may be machined if the 
    part splits, e.g. if it has legs, only one leg may get machined otherwise."""
    # find the top face for each body
    top_faces = [_get_top_face(body) for body in comp.bRepBodies]

    # select the top face of one of the bodies
    if all(map(lambda f: f is None, top_faces)):
        futil.log("no top face 1")
        return None
    top_face = next(filter(lambda f: f is not None, top_faces), None)
    if top_face is None:
        futil.log("no top face 2")
        return None
    futil.log(f"number of bods: {comp.bRepBodies.count}")
    futil.log(f"model name: {comp.name}")
    futil.log(f"top face: {top_face.boundingBox.minPoint.z*10}")
    # set this face as the pocket for the clearing operation
    pockets_parameter = adsk.cam.CadContours2dParameterValue.cast(operation.parameters.itemByName("pockets").value)
    pocket_selections = pockets_parameter.getCurveSelections()
    pocket_selections.clear()
    new_selection = pocket_selections.createNewPocketSelection()
    new_selection.inputGeometry = [top_face]
    new_selection.isSelectingSamePlaneFaces = True
    pockets_parameter.applyCurveSelections(pocket_selections)
    future = cam.generateToolpath(setup)
    while not future.isGenerationCompleted:
        adsk.doEvents()
    return top_face.boundingBox.minPoint.z*10


def _get_top_face(body: adsk.fusion.BRepBody) -> adsk.fusion.BRepFace | None:
    for face in body.faces:
        if (face.boundingBox.minPoint.z == body.boundingBox.maxPoint.z):
            return face
    return None
