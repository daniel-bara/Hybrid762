from pathlib import Path
import re
import shutil
import adsk.core
import adsk.cam
import adsk.fusion
from . import config
from . import fusion_utils
from . import hybrid_utils
from .lib import fusion360utils as futil
from .InDesignSlicer import InDeisgnSlicer
from .PostProcessorConnector import PostProcessorConnector


class HybridPostProcessor:
    def __init__(self,
                 ui: adsk.core.UserInterface,
                 doc: adsk.core.Document,
                 cam: adsk.cam.CAM):
        self.ui = ui
        self.doc = doc
        self.cam = cam
        design: adsk.fusion.Design = adsk.fusion.Design.cast(doc.products.itemByProductType('DesignProductType'))
        if not design:
            ui.messageBox('No active Fusion design', 'No Design')
            raise RuntimeError("No active Fusion design")
        self.rootComp: adsk.fusion.Component = design.rootComponent

    def hybrid_post_process(self, hybrid_post_config: hybrid_utils.HybridPostConfig):
        '''Export an additive or hybrid toolpath depending on the configuration'''
        assert hybrid_post_config.outputFilePath.parent.exists()
        fusion_utils.generateAllTootpaths(self.ui, self.cam)
        setups = fusion_utils.get_setups(self.doc)
        try:
            # assuming there is exactly one additive setup in the document
            additive_setup = next(filter(lambda s: s.operationType ==
                                  adsk.cam.OperationTypes.AdditiveOperation, setups))
        except StopIteration:
            fusion_utils.messageBox(self.ui, "No Additive setup found",
                                    icon=adsk.core.MessageBoxIconTypes.WarningIconType)
        finishing_milling_setup = fusion_utils.get_setup_by_name(
            self.doc, hybrid_post_config.finishingMillingSetup) if hybrid_post_config.finishingMilling else None

        tmp_output_folder = config.OUTPUT_FOLDER.joinpath("temp")
        if tmp_output_folder.exists():
            shutil.rmtree(tmp_output_folder)
        tmp_output_folder.mkdir(exist_ok=False)

        temp_files = hybrid_utils.TempFilePaths(additive=Path.joinpath(tmp_output_folder, 'tmpAdditive.gcode'),
                                                finishing=Path.joinpath(tmp_output_folder, 'tmpFinishing.tap'),
                                                planarising=Path.joinpath(tmp_output_folder, 'tmpDefectCorrection.tap'))
        post_processor_connector = PostProcessorConnector(self.ui, self.cam)
        post_processor_connector.post_process_to_temp_files(combined_post_config=hybrid_post_config,
                                                            output_file_paths=temp_files,
                                                            additiveSetup=additive_setup,
                                                            finishingMillingSetup=finishing_milling_setup,
                                                            planarisingSetup=None)

        if hybrid_post_config.defectCorrection:
            in_design_slicer = InDeisgnSlicer(self.rootComp, self.ui, self.cam, post_processor_connector)
            # layer_height = additive_setup.printSetting.parameters(adsk.cam.PrintSettingItemTypes.GENERAL).itemByName("layer_height")
            # futil.log(f"printsettings: {list(map(lambda p: p, additive_setup.printSetting.parameters(adsk.cam.PrintSettingItemTypes.GENERAL)))}")
            # futil.log(f"printsettings/layer height: {layer_height}")
            layer_height = config.LAYER_HEIGHT  # TODO: find out how to get layer height and first layer height from printsettings https://forums.autodesk.com/t5/fusion-api-and-scripts/how-to-access-printsetting-properties/td-p/12743370

            futil.log(f"slicing with layer height: {layer_height}")
            in_design_slicer.slice(temp_files, increment_mm=layer_height)

        # read the additive gcode
        if (temp_files.additive):
            with open(temp_files.additive) as additive_tmp:
                additive_gcode = ''.join(additive_tmp.readlines())

        # combine additive with milling
        if hybrid_post_config.defectCorrection and temp_files.planarising:
            combined_gcode_removed_placeholders1 = self._replace_layer_removal_placeholders(
                additive_gcode, temp_files.planarising.parent)
            combined_gcode_step2 = self._replace_overextrusion_removal_placeholders(
                combined_gcode_removed_placeholders1, temp_files.planarising.parent)
        else:
            combined_gcode_step2 = additive_gcode

        if hybrid_post_config.finishingMilling and temp_files.finishing:
            combined_gcode_step3 = self._replace_finishing_placeholder(combined_gcode_step2, temp_files.finishing)
        else:
            combined_gcode_step3 = combined_gcode_step2

        # write the combined gcode to file
        with open(hybrid_post_config.outputFilePath, 'w+') as outfile:
            for line in combined_gcode_step3.splitlines(keepends=True):
                outfile.write(line)

        fusion_utils.show_folder(hybrid_post_config.outputFilePath.parent)

    def _get_defect_correction_gcode(self, match: re.Match, planarising_files_folder: Path, throw_on_failure) -> str:
        height = float(match.group('height'))
        planarising_file_path = planarising_files_folder.joinpath(f"Planarising at {format(height, '.2f')}.tap")
        if Path.exists(planarising_file_path):
            with open(planarising_file_path) as planarising_gcode:
                return ''.join(planarising_gcode.readlines())
        else:
            if throw_on_failure:
                raise RuntimeError(f"Layer removal gcode not found at {round(height, 2)}")

            return f'; Planarising toolpath does not exist at {format(height, ".2f")} for over-extrusion removal'

    def _replace_layer_removal_placeholders(self, additive_gcode: str, planarising_files_folder: Path) -> str:
        placeholder_pattern = re.compile(r";PLACEHOLDER_LAYER_REMOVAL at Z (?P<height>[\d.]+)")
        return re.sub(placeholder_pattern,
                      lambda match: self._get_defect_correction_gcode(
                          match, planarising_files_folder, throw_on_failure=True),
                      additive_gcode)

    def _replace_overextrusion_removal_placeholders(self, additive_gcode: str, planarising_files_folder: Path) -> str:
        placeholder_pattern = re.compile(r";PLACEHOLDER_OVEREXTRUSION_REMOVAL at Z (?P<height>[\d.]+)")
        return re.sub(placeholder_pattern,
                      lambda match: self._get_defect_correction_gcode(
                          match, planarising_files_folder, throw_on_failure=False),
                      additive_gcode)

    def _replace_finishing_placeholder(self, additive_gcode: str, finishing_file: Path) -> str:

        def get_finishing_gcode(_) -> str:
            if Path.exists(finishing_file):
                with open(finishing_file) as finishing_gcode:
                    return ''.join(finishing_gcode.readlines())
            else:
                return f"finishing gcode {finishing_file} not found"

        placeholder_pattern = re.compile(r";PLACEHOLDER_FINISHING at Z(?P<height>[\d.]+)")
        return re.sub(placeholder_pattern, get_finishing_gcode, additive_gcode, 1)
