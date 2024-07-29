from pathlib import Path
import adsk.core
import adsk.cam
import adsk.fusion
from ...lib import fusion360utils as futil
from ... import config
from ... import fusion_utils
from ... import cam_setup_utils

app = adsk.core.Application.get()
ui: adsk.core.UserInterface = app.userInterface

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []


class AutoSetupButton:
    CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_autoSetupDialog'
    CMD_NAME = 'Setup Wizard'
    CMD_Description = '''Automatically creates setups and manufacturing models used for hybrid manufacturing.
    Creates 
    - an 'Additive' manufacturing model. This can be used to modify the design for printing, such as expanding the walls that will be machined down anyway.
    - a 'Machining' manufacturing model. This is raised by the raft height to ensure correct milling heights.
    - an Additive setup
    - a Defect Correction setup which will be applied to every layer if it needs to be corrected after printing.
        This contains a single Adaptive2D operation, which is loaded from a template. If you wish to 
        save your modifications, save the template to the local Template Library, 
        then export it and overwrite 'defect correction.f3dhsm-template' bundled with the add-in.
        An invalid toolpath is expected behaviour and should be ignored if the part 
        does not have a horizontal top surface.
    - a Finishing milling setup which will be performed after printing.'''

    # Specify that the command will be appear in the panel (not just the dropdown).
    IS_PROMOTED = True

    BUTTON_ID = 'AutoSetupCommand'

    ICON_FOLDER = Path(__file__).parent.joinpath('resources', 'AutoSetupIcon')

    def __init__(self):
        self.registered_command_definitions: list[adsk.core.CommandDefinition] = []

    def start(self):
        '''Executed when add-in is started. Creates a button in the ribbon.'''
        # Get the target workspace the button will be created in.
        workspace = ui.workspaces.itemById('CAMEnvironment')

        # Create the Hybrid tab
        hybrid_tab = fusion_utils.try_create_tab(workspace, "Hybrid", config.HYBRID_TAB_ID)

        # Create the Post panel
        post_panel = fusion_utils.try_create_panel(workspace, hybrid_tab, "Post", config.POST_PANEL_ID)

        # Create a command Definition.
        auto_setup_cmd_def = ui.commandDefinitions.addButtonDefinition(
            AutoSetupButton.CMD_ID, AutoSetupButton.CMD_NAME, AutoSetupButton.CMD_Description, str(AutoSetupButton.ICON_FOLDER))

        # Define an event handler for the command created event. It will be called when the button is clicked.
        futil.add_handler(auto_setup_cmd_def.commandCreated, self.command_created)

        # Create the button command control in the UI after the specified existing command.
        auto_setup_button = post_panel.controls.addCommand(auto_setup_cmd_def, AutoSetupButton.BUTTON_ID, False)
        auto_setup_button.isPromoted = True
        self.registered_command_definitions.append(auto_setup_cmd_def)

    def stop(self):
        '''Executed when add-in is stopped. Removes button from the ribbon.'''
        manufacturing_workspace = ui.workspaces.itemById('CAMEnvironment')
        hybridTab = manufacturing_workspace.toolbarTabs.itemById(config.HYBRID_TAB_ID)
        fusion_utils.try_remove_panel(hybridTab, config.POST_PANEL_ID)

        for command_definition in self.registered_command_definitions:
            command_definition.deleteMe()

    def command_created(self, args: adsk.core.CommandCreatedEventArgs):
        '''Function that is called when a user clicks the command's button in the UI.
        It defines the contents of the command dialog and connects to the command related events.'''
        futil.log(f'{AutoSetupButton.CMD_NAME} Command Created Event, args: {args}')
        futil.add_handler(args.command.execute, self.command_execute, local_handlers=local_handlers)

    def command_execute(self, args: adsk.core.CommandEventArgs):
        '''This event handler is called when the user clicks the OK button in the command dialog'''
        futil.log(f'{AutoSetupButton.CMD_NAME} Command Execute Event')

        fusion_utils.messageBox(ui, f"Generating Setups based on a layer height of {config.LAYER_HEIGHT} mm and a raft height of {config.RAFT_HEIGHT} mm.\
                                These can be changed in <i>config.py</i>. If you change these configurations, the add-in needs to be reloaded and the Setups\
                                deleted to generate new ones based on the new values. (This is a temporary measure until the developer can figure out how to\
                                    read from printsettings.)", "Setup Wizard")

        # check conditions are met
        design: adsk.fusion.Design = adsk.fusion.Design.cast(
            app.activeDocument.products.itemByProductType('DesignProductType'))
        if not design:
            fusion_utils.messageBox(ui, 'No active Fusion design', 'No Design',
                                    icon=adsk.core.MessageBoxIconTypes.WarningIconType)
            raise RuntimeError("No active Fusion design")
        rootComp: adsk.fusion.Component = design.rootComponent
        if rootComp.bRepBodies.count == 0:
            fusion_utils.messageBox(ui, 'No bodies found', title='No bodies',
                                    icon=adsk.core.MessageBoxIconTypes.WarningIconType)
            raise RuntimeError("No bodies")

        # show progress bar
        progress_bar = ui.createProgressDialog()
        progress_bar.show("Setup wizard", "Creating setups", 0, 3)

        # create setups
        cam = adsk.cam.CAM.cast(app.activeDocument.products.itemByProductType('CAMProductType'))
        cam_setup_utils.create_additive_setup(app.activeDocument, cam)
        progress_bar.progressValue += 1

        cam_setup_utils.create_finishing_setup(cam)
        progress_bar.progressValue += 1

        defect_correction_setup_name = config.DEFECT_CORRECTION_SETUP_NAME
        defect_correction_setup = fusion_utils.get_setup_by_name(app.activeDocument, defect_correction_setup_name)
        if defect_correction_setup is None:
            defect_correction_setup = cam_setup_utils.create_face_milling_setup(
                cam, rootComp, defect_correction_setup_name)
            if defect_correction_setup is None:
                raise RuntimeError("Could not create defect correction setup")
        progress_bar.hide()
        fusion_utils.messageBox(ui, "Setups have been created.", "Setups Created")
