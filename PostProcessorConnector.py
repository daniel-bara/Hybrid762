import os
from pathlib import Path
import re
from typing import Optional
import adsk.core
import adsk.cam
import adsk.fusion
from . import fusion_utils
from . import hybrid_utils
from .lib import fusion360utils as futil
from . import config


class PostProcessorConnector:
    '''Translates configurations and file paths to post processor settings and runs post processors.'''

    def __init__(self,
                 ui: adsk.core.UserInterface,
                 cam: adsk.cam.CAM) -> None:
        self.ui = ui
        self.cam = cam

    def post_process_to_temp_files(self,
                                   combined_post_config: hybrid_utils.HybridPostConfig,
                                   output_file_paths: hybrid_utils.TempFilePaths,
                                   additiveSetup: Optional[adsk.cam.Setup] = None,
                                   finishingMillingSetup: Optional[adsk.cam.Setup] = None,
                                   planarisingSetup: Optional[adsk.cam.Setup] = None):
        '''Export (post-process) the passed in setups to the provided file paths using the provided config'''
        if additiveSetup is not None and additiveSetup.operationType != adsk.cam.OperationTypes.AdditiveOperation:
            fusion_utils.messageBox(self.ui, f'"{additiveSetup.name}" is not an additive setup',
                                    "Error", icon=adsk.core.MessageBoxIconTypes.CriticalIconType)
            raise RuntimeError(f'"{additiveSetup.name}" is not an additive setup')

        if finishingMillingSetup is not None and finishingMillingSetup.operationType != adsk.cam.OperationTypes.MillingOperation:
            fusion_utils.messageBox(self.ui, f'"{finishingMillingSetup.name}" is not a milling setup',
                                    "Error", icon=adsk.core.MessageBoxIconTypes.CriticalIconType)
            raise RuntimeError(f'"{finishingMillingSetup.name}" is not a milling setup')

        if planarisingSetup is not None and planarisingSetup.operationType != adsk.cam.OperationTypes.MillingOperation:
            fusion_utils.messageBox(self.ui, f'"{planarisingSetup.name}" is not a milling setup',
                                    "Error", icon=adsk.core.MessageBoxIconTypes.CriticalIconType)
            raise RuntimeError(f'"{planarisingSetup.name}" is not a milling setup')

        # specify the NC file output units
        units = adsk.cam.PostOutputUnitOptions.DocumentUnitsOutput

        setups = [s for s in (additiveSetup, finishingMillingSetup, planarisingSetup) if s is not None]
        for setup in setups:
            # verify there are operations in setup
            if setup.operations.count == 0:
                fusion_utils.messageBox(self.ui, f'No Operations exist in {setup.name}.',
                                        icon=adsk.core.MessageBoxIconTypes.WarningIconType)
                raise RuntimeError(f'No Operations exist in {setup.name}.')

        millingPostProcessorPath = str(config.MILLING_POST_PROCESSOR_PATH)

        if finishingMillingSetup is not None and output_file_paths.finishing is not None:
            finishingMillingPostInput = adsk.cam.PostProcessInput.create(
                output_file_paths.finishing.stem,
                millingPostProcessorPath,
                str(output_file_paths.finishing.parent),
                units)  # type: ignore (Pylance)
            finishingMillingPostInput.isOpenInEditor = False

            finishingMillingPostInput.postProperties.add(
                "standalone", adsk.core.ValueInput.createByBoolean(False))

            self.cam.postProcess(finishingMillingSetup, finishingMillingPostInput)

        if planarisingSetup is not None and output_file_paths.planarising is not None:
            planarisingPostInput = adsk.cam.PostProcessInput.create(
                output_file_paths.planarising.stem,
                millingPostProcessorPath,
                str(output_file_paths.planarising.parent),
                units)  # type: ignore (Pylance)
            planarisingPostInput.isOpenInEditor = False

            planarisingPostInput.postProperties.add(
                "standalone", adsk.core.ValueInput.createByBoolean(False))
            if planarisingSetup.operations[0].hasWarning:
                futil.log(f"Planarising setups warning: '{planarisingSetup.operations[0].warning}'")
                if re.match(r'Empty toolpath[\W]*', planarisingSetup.operations[0].warning) is not None:
                    futil.log(f"Empty toolpath, exporting empty file")
                    with open(output_file_paths.planarising, 'w+') as file:
                        pass
            else:
                self.cam.postProcess(planarisingSetup, planarisingPostInput)

        if additiveSetup is not None and output_file_paths.additive is not None:
            futil.log(f"additive path: {output_file_paths.additive.parent}   {output_file_paths.additive.stem}")
            additivePostInput = adsk.cam.PostProcessInput.create(
                output_file_paths.additive.stem,
                str(config.ADDITIVE_POST_PROCESSOR_PATH),
                str(output_file_paths.additive.parent),
                units)  # type: ignore (Pylance)
            additivePostInput.isOpenInEditor = False

            additivePostInput.postProperties.add(
                "standalone", adsk.core.ValueInput.createByBoolean(False))
            additivePostInput.postProperties.add(
                "useImaging", adsk.core.ValueInput.createByBoolean(combined_post_config.useImaging))
            additivePostInput.postProperties.add(
                "laserScanning", adsk.core.ValueInput.createByBoolean(combined_post_config.laserScanning))
            additivePostInput.postProperties.add(
                "collectLoadCellData", adsk.core.ValueInput.createByBoolean(combined_post_config.collectLoadCellData))
            additivePostInput.postProperties.add(
                "dryingTime", adsk.core.ValueInput.createByReal(combined_post_config.dryingTime))
            additivePostInput.postProperties.add(
                "finishing", adsk.core.ValueInput.createByBoolean(combined_post_config.finishingMilling))
            additivePostInput.postProperties.add(
                "defectCorrection", adsk.core.ValueInput.createByBoolean(combined_post_config.defectCorrection))
            additivePostInput.postProperties.add(
                "firstCorrectionLayer", adsk.core.ValueInput.createByReal(combined_post_config.firstCorrectionLayer))

            self.cam.postProcess(additiveSetup, additivePostInput)
