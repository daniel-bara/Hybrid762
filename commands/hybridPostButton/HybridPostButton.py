from pathlib import Path
import traceback
import adsk.core
import adsk.cam
from ...lib import fusion360utils as futil
from ... import config
from ... import fusion_utils
from ... import hybrid_utils
from ...HybridPostProcessor import HybridPostProcessor

app = adsk.core.Application.get()
ui: adsk.core.UserInterface = app.userInterface

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []


class HybridPostButton:
    CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_hybridPostDialog'
    CMD_NAME = 'Hybrid Post Process'
    CMD_Description = 'Hybrid post processor for Additive and Milling. Required operations may be set up through the Setup Wizard or manually.'

    # Specify that the command will be promoted to the panel.
    IS_PROMOTED = True

    BUTTON_ID = 'CombinedPostProcessCommand'

    ICON_FOLDER = Path(__file__).parent.joinpath('resources', 'HybridPostButton')

    def __init__(self):
        self.imaging_tickbox: adsk.core.BoolValueCommandInput
        self.laser_scanning_tickbox: adsk.core.BoolValueCommandInput
        self.load_cell_data_tickbox: adsk.core.BoolValueCommandInput
        self.drying_tickbox: adsk.core.BoolValueCommandInput
        self.drying_time_input: adsk.core.IntegerSpinnerCommandInput
        self.defect_correction_tickbox: adsk.core.BoolValueCommandInput
        self.first_correction_layer_input: adsk.core.IntegerSpinnerCommandInput
        self.finishing_milling_tickbox: adsk.core.BoolValueCommandInput
        self.finishing_milling_selector: adsk.core.DropDownCommandInput
        self.output_filename_input: adsk.core.StringValueCommandInput

        self.hybrid_config: hybrid_utils.HybridPostConfig
        self.last_doc: adsk.core.Document | None = None
        self.registered_command_definitions: list[adsk.core.CommandDefinition] = []

    def start(self):
        '''Executed when add-in is started. Creates a button in the ribbon.'''
        # Get the target workspace the button will be created in.
        workspace = ui.workspaces.itemById('CAMEnvironment')

        # Create the Hybrid tab
        hybrid_tab = fusion_utils.try_create_tab(workspace, "Hybrid", config.HYBRID_TAB_ID)

        # Create the Post panel
        panel_post = fusion_utils.try_create_panel(workspace, hybrid_tab, "Post", config.POST_PANEL_ID)

        # Create a command Definition.
        hybrid_post_cmd_def = ui.commandDefinitions.addButtonDefinition(
            HybridPostButton.CMD_ID, HybridPostButton.CMD_NAME, HybridPostButton.CMD_Description, str(HybridPostButton.ICON_FOLDER))

        # Define an event handler for the command created event. It will be called when the button is clicked.
        futil.add_handler(hybrid_post_cmd_def.commandCreated, self.command_created)

        # Create the button command control in the UI after the specified existing command.
        hybrid_post_button = panel_post.controls.addCommand(hybrid_post_cmd_def)
        hybrid_post_button.isPromoted = True
        self.registered_command_definitions.append(hybrid_post_cmd_def)

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

        futil.log(f'{HybridPostButton.CMD_NAME} Command Created Event, args: {args}')
        args.command.setDialogSize(400, 600)

        inputs = args.command.commandInputs

        self.imaging_tickbox = inputs.addBoolValueInput("useImaging", "Imaging", True)
        self.imaging_tickbox.tooltip = "Enable Layerwise photos"
        self.imaging_tickbox.tooltipDescription = "Imaging between layers."

        # Laser scanning
        self.laser_scanning_tickbox = inputs.addBoolValueInput("laserScanning", "Laser Scanning", True)
        self.laser_scanning_tickbox.tooltip = "Enable laser scanning"
        self.laser_scanning_tickbox.tooltipDescription = "Laser scanning between layers."

        # Load cell data
        self.load_cell_data_tickbox = inputs.addBoolValueInput("collectLoadCellData", "Load Cell Data", True)
        self.load_cell_data_tickbox.tooltip = "Collect load cell data"

        # Drying
        self.drying_tickbox = inputs.addBoolValueInput("drying", "Drying", True)
        self.drying_tickbox.tooltip = "Enable Drying"
        self.drying_time_input = inputs.addIntegerSpinnerCommandInput("dryingTime", "Drying Time", 1, 600, 1, 30)
        self.drying_time_input.tooltip = "Drying Time (s)"
        self.drying_time_input.tooltipDescription = "Drying Time in seconds"

        # Defect correction
        self.defect_correction_tickbox = inputs.addBoolValueInput("defectCorrection", "Defect Correction", True)
        self.defect_correction_tickbox.tooltip = "Enable Defect Correction"
        self.defect_correction_tickbox.toolClipFilename = str(
            Path(__file__).parent.joinpath("resources", "PlanarisingTooltip.png"))
        self.defect_correction_tickbox.tooltipDescription = "Takes a picture of each layer after printing, \n \
            and if printing errors are detected, removbes the layer by milling and re-prints it."
        self.first_correction_layer_input = inputs.addIntegerSpinnerCommandInput(
            "firstCorrectionLayer", "First Correction Layer", 2, 10000, 1, 4)
        self.first_correction_layer_input.tooltip = "First correction layer"
        self.first_correction_layer_input.tooltipDescription = "Including raft. e.g. if you have 3 layers of raft,\n \
            the first layer you should be correcting is 4."

        # Finishing
        self.finishing_milling_tickbox = inputs.addBoolValueInput("contourMilling", "Finishing", True)
        self.finishing_milling_tickbox.tooltip = "Enable Finishing Milling Operation"
        self.finishing_milling_tickbox.toolClipFilename = str(
            Path(__file__).parent.joinpath("resources", "FinishingTooltip.png"))
        self.finishing_milling_selector = inputs.addDropDownCommandInput(
            "contourMillingSetup",
            "Finishing Mililng Setup",
            adsk.core.DropDownStyles.TextListDropDownStyle)  # type: ignore
        self.finishing_milling_selector.tooltip = "Finishing Milling Setup"
        self.finishing_milling_selector.tooltipDescription = "Select a milling setup to perform after printing.\n \
            The setup can contain multiple milling operations. \
            Do not use together with polymer supports or rafts."
        self._update_finishing_milling_setup_selector(app.activeDocument)

        # Output
        output_group = inputs.addGroupCommandInput("outputPathSelectorGroup", "Output")
        self.output_folder_browser_button = output_group.children.addBoolValueInput(
            "outputFolderBrowser", "", False, str(Path(__file__).parent.joinpath("resources", 'FolderButton')))
        default_output_folder = Path(__file__).parents[2].joinpath("outputs")
        if not default_output_folder.exists():
            default_output_folder.mkdir(exist_ok=True)
        self.output_folder_input = output_group.children.addStringValueInput(
            "outputFolder", "Output Folder", str(default_output_folder))
        self.output_filename_input = output_group.children.addStringValueInput(
            "outputFilename", "Output Filename", f"{app.activeDocument.name}.tap")
        output_folder_prompt = output_group.children.addTextBoxCommandInput(
            "outputFolderPrompt", "", "Output folder", 1, True)
        output_filename_prompt = output_group.children.addTextBoxCommandInput(
            "outputFilenamePrompt", "", "File name", 1, True)
        output_path_table = output_group.children.addTableCommandInput("outputPathTable", "Output Path", -1, "9:16:1")
        output_path_table.tablePresentationStyle = adsk.core.TablePresentationStyles.transparentBackgroundTablePresentationStyle  # type: ignore
        output_path_table.addCommandInput(output_folder_prompt, 0, 0)
        output_path_table.addCommandInput(self.output_folder_input, 0, 1)
        output_path_table.addCommandInput(self.output_folder_browser_button, 0, 2)
        output_path_table.addCommandInput(output_filename_prompt, 1, 0)
        output_path_table.addCommandInput(self.output_filename_input, 1, 1, 0, 1)

        # load state if this is the same document the user was in the last time this dialog was opem
        if self.last_doc == app.activeDocument:
            self._restore_selections()
        else:
            self._update_config()

        self.last_doc = app.activeDocument

        args.command.isExecutedWhenPreEmpted = False  # Do not execute unless the user clicks the OK button
        args.command.okButtonText = "Post"

        futil.add_handler(args.command.execute, self.command_execute, local_handlers=local_handlers)
        futil.add_handler(args.command.inputChanged, self.command_input_changed, local_handlers=local_handlers)
        futil.add_handler(args.command.executePreview, self.command_preview, local_handlers=local_handlers)
        futil.add_handler(args.command.validateInputs, self.command_validate_input, local_handlers=local_handlers)
        futil.add_handler(args.command.destroy, self.command_destroy, local_handlers=local_handlers)

    def command_execute(self, args: adsk.core.CommandEventArgs):
        '''This event handler is called when the user clicks the OK button in the command dialog'''
        doc = app.activeDocument
        futil.log(f'{HybridPostButton.CMD_NAME} Command Execute Event')

        if self.hybrid_config.outputFilePath.exists():
            warning_result = fusion_utils.messageBox(ui, "The specified output file already exists. Do you want to overwrite it?", 
                                                     "File exists", 
                                                     buttons=adsk.core.MessageBoxButtonTypes.YesNoButtonType, 
                                                     icon=adsk.core.MessageBoxIconTypes.WarningIconType)
            if warning_result == adsk.core.DialogResults.DialogNo:
                return

        fusion_utils.assert_CAM_setup_correct(ui, doc)
        try:
            cam = adsk.cam.CAM.cast(doc.products.itemByProductType('CAMProductType'))
            hybrid_post_processor = HybridPostProcessor(ui, doc, cam)
            hybrid_post_processor.hybrid_post_process(self.hybrid_config)
        except Exception as e:
            fusion_utils.messageBox(ui, str(e) + traceback.format_exc(), title="Error whie running hybrid post processor",
                                    icon=adsk.core.MessageBoxIconTypes.CriticalIconType)
            args.executeFailed = True
            args.executeFailedMessage = str(e)

    def command_preview(self, args: adsk.core.CommandEventArgs):
        '''This event handler is called when the command needs to compute a new preview in the graphics window.'''
        futil.log(f'{HybridPostButton.CMD_NAME} command preview')

        self._update_enablings()

    def _update_enablings(self):
        """Enable/disable (grey out) inputs"""
        self.defect_correction_tickbox.isEnabled = self.imaging_tickbox.value
        self.drying_time_input.isEnabled = self.drying_tickbox.value
        self.first_correction_layer_input.isEnabled = self.defect_correction_tickbox.value
        self.finishing_milling_selector.isEnabled = self.finishing_milling_tickbox.value

    def command_input_changed(self, args: adsk.core.InputChangedEventArgs):
        '''This event handler is called when the user changes anything in the command dialog
        allowing you to modify values of other inputs based on that change.'''
        doc = app.activeDocument
        changed_input = args.input
        futil.log(f'{HybridPostButton.CMD_NAME} Input Changed Event fired from a change to {changed_input.id}')

        if changed_input == self.finishing_milling_tickbox:
            self._update_finishing_milling_setup_selector(doc)

        if changed_input == self.output_folder_browser_button:
            folder_browser = ui.createFolderDialog()
            folder_browser.title = "Output Folder"
            folder_browser.initialDirectory = str(self.hybrid_config.outputFilePath.parent)
            folder_result = folder_browser.showDialog()
            if folder_result == adsk.core.DialogResults.DialogCancel:
                futil.log("canceled")
            else:
                futil.log(f"folder result: {folder_browser.folder}")
                self.output_folder_input.value = folder_browser.folder

        if changed_input == self.defect_correction_tickbox and self.defect_correction_tickbox.value == True:
            fusion_utils.messageBox(ui, f"Defect correction will assume a layer height of {config.LAYER_HEIGHT} mm and a raft height of {config.RAFT_HEIGHT} mm\
                                    with 0 mm clearance. To change these values, go to <i>config.py</i>, re-load the add-in, and delete and re-generate or adjust \
                                    the Milling Setup. (This is a temporary measure until the developer can figure out how to read from printsettings.)",
                                    "Defect Correction")

        self._update_config()

    def _update_finishing_milling_setup_selector(self, doc):
        """Update the list of dropdown items in the Finishing Milling selector"""
        self.finishing_milling_selector.listItems.clear()
        # There is a UI bug the the first item is not in view when the dropdown is opened
        self.finishing_milling_selector.listItems.add("", True)

        setups = fusion_utils.get_setups(doc)
        for setup in filter(lambda s: s.operationType == adsk.cam.OperationTypes.MillingOperation, setups):
            self.finishing_milling_selector.listItems.add(setup.name, False)

    def _update_config(self):
        '''Store the selections in a config object to be able to reload them after the dialog gets closed'''
        if not self._validate_all():
            return
        self.hybrid_config = hybrid_utils.HybridPostConfig(
            useImaging=self.imaging_tickbox.value,
            laserScanning=self.laser_scanning_tickbox.value,
            collectLoadCellData=self.load_cell_data_tickbox.value,
            dryingTime=0 if self.drying_tickbox.value == False else self.drying_time_input.value,
            finishingMilling=self.finishing_milling_tickbox.value,
            finishingMillingSetup=self.finishing_milling_selector.selectedItem.name if (
                self.finishing_milling_tickbox.value == True and self.finishing_milling_selector.selectedItem is not None) else "",
            defectCorrection=self.defect_correction_tickbox.value,
            firstCorrectionLayer=self.first_correction_layer_input.value,
            outputFilePath=Path(self.output_folder_input.value) / self.output_filename_input.value
        )

    def _restore_selections(self):
        hybrid_config = self.hybrid_config
        futil.log("restoring settings")
        self.imaging_tickbox.value = hybrid_config.useImaging 
        self.laser_scanning_tickbox.value = hybrid_config.laserScanning
        self.load_cell_data_tickbox.value = hybrid_config.collectLoadCellData
        self.drying_tickbox.value = hybrid_config.dryingTime != 0
        self.drying_time_input.value = hybrid_config.dryingTime
        self.finishing_milling_tickbox.value = hybrid_config.finishingMilling
        finishing_setup_list_item = next(
            filter(lambda item: item.name == hybrid_config.finishingMillingSetup, self.finishing_milling_selector.listItems), None)
        if finishing_setup_list_item is not None:
            finishing_setup_list_item.isSelected = True
        self.defect_correction_tickbox.value = hybrid_config.defectCorrection
        self.first_correction_layer_input.value = hybrid_config.firstCorrectionLayer
        self.output_folder_input.value = str(hybrid_config.outputFilePath.parent)
        self.output_filename_input.value = hybrid_config.outputFilePath.name

    def command_validate_input(self, args: adsk.core.ValidateInputsEventArgs):
        '''This event handler is called when the user interacts with any of the inputs in the dialog
        which allows you to verify that all of the inputs are valid and enables the OK button.'''
        # futil.log(f'validate input')

        self._update_enablings()

        args.areInputsValid = self._validate_all()

    def command_destroy(self, args: adsk.core.CommandEventArgs):
        '''This event handler is called when the command terminates.'''
        futil.log(f'{HybridPostButton.CMD_NAME} Command Destroy Event')
        global local_handlers
        local_handlers = []

    def _validate_all(self):
        if self.finishing_milling_tickbox.value == True and (
                self.finishing_milling_selector.selectedItem is None or
                self.finishing_milling_selector.selectedItem.name == ""):
            futil.log(f"1 invalidated {self.finishing_milling_selector.selectedItem}")

            return False

        if not Path(self.output_folder_input.value).exists():
            self.output_folder_input.isValueError = True
            return False
        else:
            self.output_folder_input.isValueError = False

        return True
