import traceback
import adsk.core
import adsk.cam
from ...lib import fusion360utils as futil
from ... import config
from ... import fusion_utils

app = adsk.core.Application.get()
ui: adsk.core.UserInterface = app.userInterface
_handlers = []  # See 'Additive setup bug'
_activeToolTabId = ""  # See 'Additive setup bug'

PANEL_MILLING_ID = 'HybridMillingPanel'
PANEL_TOOLS_ID = 'HybridToolsPanel'
PANEL_ADDITIVE_ID = 'HybridAdditivePanel'
CLONED_ADDITIVE_SETUP_CMD_ID = "ClonedAdditiveSetup"


class ClonedCommands:
    """Clones commands from the Milling and Additive tabs to the Hybrid tab"""

    def __init__(self):
        self.registered_command_definitions: list[adsk.core.CommandDefinition] = []

    def start(self):
        '''Executed when add-in is started. Creates buttons in the ribbon.'''
        # Get the target workspace the button will be created in.
        manufacturing_workspace = ui.workspaces.itemById('CAMEnvironment')

        # Get the panel the button will be created in.
        hybrid_tab = fusion_utils.try_create_tab(manufacturing_workspace, "Hybrid", config.HYBRID_TAB_ID)

        if False:
            manufacturing_workspace = ui.workspaces.itemById('CAMEnvironment')
            print_command_definitions(manufacturing_workspace)

        panel_additive = fusion_utils.try_create_panel(manufacturing_workspace, hybrid_tab, "Additive", PANEL_ADDITIVE_ID)

        self._create_cloned_additive_setup_button(panel_additive)
        self._clone_button("MSFWmdCreateAggregationAssetWorkingModelCmd", panel_additive)
        self._clone_button('IronStrategy_areavolume_additive_fff_support', panel_additive)
        self._clone_button('IronStrategy_areabar_additive_fff_support', panel_additive, True)
        self._clone_button('IronStrategy_setter_additive_support', panel_additive, True)
        self._clone_button('IronPrintSettingLibrary', panel_additive)

        panel_milling = fusion_utils.try_create_panel(manufacturing_workspace, hybrid_tab, "Milling", PANEL_MILLING_ID)
        self._clone_button("CreateSetupCmd", panel_milling)
        self._clone_button("IronStrategy_face", panel_milling)
        self._clone_button("IronStrategy_adaptive2d", panel_milling)
        self._clone_button("IronStrategy_adaptive", panel_milling)
        self._clone_button("IronStrategy_scallop_new", panel_milling)

        panel_tools = fusion_utils.try_create_panel(manufacturing_workspace, hybrid_tab, "Tools", PANEL_TOOLS_ID)
        self._clone_button("IronGenerateToolpath", panel_tools)
        self._clone_button("IronAdditiveSimulation", panel_tools)
        self._clone_button("IronSimulation", panel_tools)

    def stop(self):
        '''Executed when add-in is stopped. Removes buttons from the ribbon.'''
        manufacturing_workspace = ui.workspaces.itemById('CAMEnvironment')
        hybridTab = manufacturing_workspace.toolbarTabs.itemById(config.HYBRID_TAB_ID)
        fusion_utils.try_remove_panel(hybridTab, PANEL_ADDITIVE_ID)
        fusion_utils.try_remove_panel(hybridTab, PANEL_MILLING_ID)
        fusion_utils.try_remove_panel(hybridTab, PANEL_TOOLS_ID)
        for command_definition in self.registered_command_definitions:
            command_definition.deleteMe()

    def _create_cloned_additive_setup_button(self, panel: adsk.core.ToolbarPanel):
        """Additive setup bug: Fusion is missing a feature to tell the CreateSetupCmd command what type of setup we want to create, so we have to
         switch to the Additiva tab before executing the command.
         Further info: https://forums.autodesk.com/t5/fusion-api-and-scripts/how-to-create-an-additive-setup-using-createsetupcmd/m-p/12738098#M21435"""
        original_cmd_def = ui.commandDefinitions.itemById("CreateSetupCmd")
        cloned_cmd_def = ui.commandDefinitions.addButtonDefinition(
            CLONED_ADDITIVE_SETUP_CMD_ID, original_cmd_def.name, original_cmd_def.tooltip, original_cmd_def.resourceFolder)
        cloned_cmd_def.toolClipFilename = original_cmd_def.toolClipFilename

        futil.add_handler(cloned_cmd_def.commandCreated, self._create_additive_setup)
        cloned_additive_setup_button = panel.controls.addCommand(cloned_cmd_def, "ClonedAdditiveSetupButton", False)
        cloned_additive_setup_button.isPromoted = True
        self.registered_command_definitions.append(cloned_cmd_def)
        onCommandStarting = CommandStartingHandler()
        ui.commandStarting.add(onCommandStarting)
        _handlers.append(onCommandStarting)

        onCommandTerminated = CommandTerminatedHandler()
        ui.commandTerminated.add(onCommandTerminated)
        _handlers.append(onCommandTerminated)

    def _clone_button(self, command_definition_id: str, target_panel: adsk.core.ToolbarPanel, dropdown_only=False):
        """Copy buttons from other tabs using their command definition id"""
        cmd_def = ui.commandDefinitions.itemById(command_definition_id)
        button = target_panel.controls.addCommand(cmd_def, "", False)
        button.isPromoted = not dropdown_only

    def _create_additive_setup(self, args: adsk.core.CommandCreatedEventArgs):
        # see 'Additive setup bug'
        try:
            cmd_def = ui.commandDefinitions.itemById("CreateSetupCmd")
            cmd_def.execute()
        except:
            if ui:
                ui.messageBox("Failed:\n{}".format(traceback.format_exc()))


class CommandTerminatedHandler(adsk.core.ApplicationCommandEventHandler):
    """A handler to switch back to the hybrid tab after the create setup command was used. See 'Additive setup bug'"""

    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.ApplicationCommandEventArgs):
        if args.commandId != "CreateSetupCmd":
            return

        manufacturing_workspace: adsk.core.Workspace = ui.workspaces.itemById("CAMEnvironment")
        manufacturing_workspace.toolbarTabs.itemById(_activeToolTabId).activate()


class CommandStartingHandler(adsk.core.ApplicationCommandEventHandler):
    """A handler to switch  to the additive tab before the create setup command was used. See 'Additive setup bug'"""

    def __init__(self):
        super().__init__()

    def notify(self, args: adsk.core.ApplicationCommandEventArgs):
        if args.commandId != CLONED_ADDITIVE_SETUP_CMD_ID:
            return

        manufacturing_workspace: adsk.core.Workspace = ui.workspaces.itemById("CAMEnvironment")

        global _activeToolTabId
        for tab in manufacturing_workspace.toolbarTabs:
            if tab.isActive:
                _activeToolTabId = tab.id
                break

        manufacturing_workspace.toolbarTabs.itemById("AdditiveTab").activate()
        adsk.doEvents()


def _print_command_definitions(manufacturing_workspace: adsk.core.Workspace):
    '''Print command definition ids of existing commands so that we know how to refer to them when cloning
    them. Used for development only. 
    to learn more about command definitions: https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-3922697A-7BF1-4799-9A5B-C8539DF57051'''
    futil.log(f"All command defition IDs: {list(map(lambda cd: cd.id, ui.commandDefinitions))}")
    tab_index = 2
    panel_range = 10
    for i in range(panel_range):
        tab = manufacturing_workspace.toolbarTabs[tab_index]
        panel = tab.toolbarPanels[i]
        if panel is None:
            continue
        futil.log(f"Command defition IDs in {tab.name} / {panel.name}: {list(map(lambda x: x.id, panel.controls))}")
