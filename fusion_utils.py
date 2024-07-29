import os
import time
import adsk.core
import adsk.cam
import adsk.fusion
from .lib import fusion360utils as futil
from . import cam_setup_utils
from . import config


def get_setups(doc: adsk.core.Document) -> list[adsk.cam.Setup]:
    '''Based on ASMBL. A safe getter for setups (returns an empty list instead of raising exceptions)'''
    try:
        cam: adsk.cam.CAM = adsk.cam.CAM.cast(doc.products.itemByProductType('CAMProductType'))
    except RuntimeError:
        pass

    if not cam:
        return []

    if cam.allOperations.count == 0:
        return []

    setups = [setup for setup in cam.setups if not setup.isSuppressed]

    return setups


def assert_CAM_setup_correct(ui: adsk.core.UserInterface, doc: adsk.core.Document):
    '''Display message boxes and raises exceptions if CAM operations are not set up correctly'''
    try:
        cam: adsk.cam.CAM = adsk.cam.CAM.cast(doc.products.itemByProductType('CAMProductType'))
    except RuntimeError:
        messageBox(ui, 'No Manufacturing workspace exists in the active document.',
                   title="No Manufacturing workspace",
                   icon=adsk.core.MessageBoxIconTypes.WarningIconType)
        raise AssertionError("No Manufacturing workspace exists in the active document.")

    if cam.setups.count == 0:
        messageBox(ui, 'No Manufacturing setups exist in the active document.',
                   title="No Setups",
                   icon=adsk.core.MessageBoxIconTypes.WarningIconType)
        raise AssertionError('No Manufacturing setups exist in the active document.')

    if cam.allOperations.count == 0:
        messageBox(ui, 'No Manufacturing operations are set up in the active document.',
                   title="No CAM operations",
                   icon=adsk.core.MessageBoxIconTypes.WarningIconType)
        raise AssertionError('No Manufacturing operations are set up in the active document.')
    
    if config.CENTER_BODY_IN_MANUFACTURING_MODEL:
        for model in cam.manufacturingModels:
            if not cam_setup_utils.body_is_in_middle(model):
                result = messageBox(futil.ui, f"The current settings require the part to be centered, but the body's center of mass is not at the origin in the Manufacturing Model \"{model.name}\". You can delete the Manufacturing Model \"{model.name}\" and run the Setup Wizard, or move the body in the Manufacturing Model manually. \n"+
                                    "Do you want to continue without the part being centered?",
                                        "Part not centered in Manufacturing Model",
                                        buttons=adsk.core.MessageBoxButtonTypes.YesNoButtonType,
                                        icon=adsk.core.MessageBoxIconTypes.WarningIconType)
                if result == adsk.core.DialogResults.DialogNo:
                    raise AssertionError("Part not centered")


def get_setup_by_name(doc: adsk.core.Document, name: str) -> adsk.cam.Setup | None:
    '''Returns the setup with that name, or None if no setup exists with that name'''
    setups = get_setups(doc)
    try:
        return next(filter(lambda s: s.name == name, setups))  # type: ignore
    except StopIteration:
        futil.log(f'No setup exists with name "{name}"')
        return None


def generateAllTootpaths(ui, cam: adsk.cam.CAM):
    # Based on ASMBL

    future = cam.generateAllToolpaths(False)
    message = '<br>Please do not press OK until the Additive toolpath has finished.</br>\
        <br>The toolpaths for all cam operations in the document have been generated.</br>'

    numOps = future.numberOfOperations

    #  create and show the progress dialog while the toolpaths are being generated.
    progress = ui.createProgressDialog()
    progress.isCancelButtonShown = False
    progress.show('Toolpath Generation Progress', 'Generating Toolpaths', 0, 10)

    # Enter a loop to wait while the toolpaths are being generated and update
    # the progress dialog.
    while not future.isGenerationCompleted:
        # since toolpaths are calculated in parallel, loop the progress bar while the toolpaths
        # are being generated but none are yet complete.
        n = 0
        start = time.time()
        while future.numberOfCompleted == 0:
            if time.time() - start > .125:  # increment the progess value every .125 seconds.
                start = time.time()
                n += 1
                progress.progressValue = n
                adsk.doEvents()
            if n > 10:
                n = 0

        # The first toolpath has finished computing so now display better
        # information in the progress dialog.

        # set the progress bar value to the number of completed toolpaths
        progress.progressValue = future.numberOfCompleted

        # set the progress bar max to the number of operations to be completed.
        progress.maximumValue = numOps

        # set the message for the progress dialog to track the progress value and the total number of operations to be completed.
        progress.message = 'Generating %v of %m' + ' Toolpaths'
        adsk.doEvents()

    progress.hide()


def try_create_tab(workspace: adsk.core.Workspace, tab_name, tab_id: str) -> adsk.core.ToolbarTab:
    # Based on ASMBL

    allTabs = workspace.toolbarTabs

    # check if tab exists
    newTab = allTabs.itemById(tab_id)

    if not newTab:
        # Add a new tab to the workspace:
        newTab = allTabs.add(tab_id, tab_name)
    return newTab


def try_remove_panel(tab, panel_id):
    # Based on ASMBL

    # check if tab exists
    panel = tab.toolbarPanels.itemById(panel_id)
    if panel is None:
        return
    # Remove the controls we added to our panel
    for control in panel.controls:
        if control.isValid:
            control.deleteMe()

    panel.deleteMe()


def try_create_panel(workspace: adsk.core.Workspace, tab: adsk.core.ToolbarTab, panel_name: str, panel_id: str) -> adsk.core.ToolbarPanel:
    # Based on ASMBL

    allTabPanels = tab.toolbarPanels

    # Activate the Cam Workspace before activating the newly added Tab
    workspace.activate()

    panel = None
    panel = allTabPanels.itemById(panel_id)
    if panel is None:
        # Add setup panel
        panel = allTabPanels.add(panel_id, panel_name)
    return panel


def messageBox(ui: adsk.core.UserInterface,
               text: str,
               title: str = "",
               buttons: int = adsk.core.MessageBoxButtonTypes.OKButtonType,
               icon: int = adsk.core.MessageBoxIconTypes.NoIconIconType):
    """Show a message box.
    Wrapper around ui.messageBox because of the buggy implementation
    of optional keyword arguments and type hinting of enums"""
    return ui.messageBox(text, title, buttons, icon)  # type: ignore


def show_folder(folder):
    '''open the output folder in Finder on Mac or in Explorer on Windows'''
    if (os.name == 'posix'):
        os.system('open "%s"' % folder)
    elif (os.name == 'nt'):
        os.startfile(folder)
