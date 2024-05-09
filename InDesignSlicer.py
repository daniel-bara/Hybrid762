from pathlib import Path
import time
import adsk.core
import adsk.cam
import adsk.fusion
from . import config
from . import fusion_utils
from . import hybrid_utils
from .lib import fusion360utils as futil
from . import cam_setup_utils
from .MaskingExtrusion import MaskingExtrusion
from .PostProcessorConnector import PostProcessorConnector


class InDeisgnSlicer:
    def __init__(self,
                 rootComp: adsk.fusion.Component,
                 ui: adsk.core.UserInterface,
                 cam: adsk.cam.CAM,
                 post_processor_connector: PostProcessorConnector) -> None:
        self.rootComp = rootComp
        self.ui = ui
        self.cam = cam
        self.post_processor_connector = post_processor_connector

    def slice(self, temp_files: hybrid_utils.TempFilePaths, increment_mm: float = 2):
        """Slice the part by creating a temporary extrusion in the Design workspace, and export toolpaths for planarising/defect correction operations"""
        assert temp_files.planarising is not None
        planrising_generation_start_time = time.time()

        setup = cam_setup_utils.create_face_milling_setup(self.cam,
                                                          self.rootComp,
                                                          f"Defect corr.")
        if setup is None:
            raise Exception("Defect correction setup could not be created")
        futil.log(f"setup: {setup.name}, ops: {setup.operations[0].name}")
        operation = setup.operations[0]
        component = adsk.fusion.Occurrence.cast(setup.models.item(0)).component
        max_Z = component.boundingBox.maxPoint.z*10

        slicing_extrusion = MaskingExtrusion(self.ui, component)
        futil.log(f"COMP: {component.name}")
        progress_bar = self.ui.createProgressDialog()
        progress_bar.show("Generating toolpaths", "Generating defect correction toolpaths",
                          0, round((max_Z - config.RAFT_HEIGHT) / increment_mm))

        for milling_height in self._generate_slicing_heights(max_Z, config.RAFT_HEIGHT, increment_mm):
            progress_bar.progressValue += 1
            if progress_bar.wasCancelled:
                raise Exception("Cancelled by user")
            futil.log(f"milling height: {milling_height}", force_console=True)

            if milling_height == config.RAFT_HEIGHT:
                # a hack for machining the first layer. Otherwise no intersection exists between the part and the slicing extrusion. TODO: select the bottom face instead.
                milling_height_offset = 0.01
            elif milling_height == max_Z:
                milling_height_offset = -0.01  # a hack for machining the top layer. Otherwise no top face might exist
            else:
                milling_height_offset = 0
            slicing_extrusion.set_height(milling_height + milling_height_offset)

            cam_setup_utils._try_update_adaptive2d_face(self.cam, component, setup, operation)

            if not self.cam.checkToolpath(setup.allOperations):
                futil.log("defective toolpath", force_console=True)
                setup.deleteMe()
                continue

            temp_files.planarising = Path.joinpath(temp_files.planarising.parent,
                                                   f"Planarising at {format(milling_height, '.2f')}.tap")
            self.post_processor_connector.post_process_to_temp_files(hybrid_utils.HybridPostConfig(defectCorrection=True),
                                                                     temp_files, planarisingSetup=setup)
        setup.deleteMe()
        slicing_extrusion.deleteMe()
        futil.log(
            f"Generated {round(max_Z / increment_mm)} toolpaths in {round(time.time()-planrising_generation_start_time, 2)} seconds", force_console=True)

    def _generate_slicing_heights(self, full_height: float, min_height: float, layer_height: float):
        '''Generate slicing heights from top to bottom'''
        assert (full_height >= min_height and layer_height > 0)
        top_layer_height = layer_height * round(full_height / layer_height)
        height = top_layer_height
        while round(height, 2) >= round(min_height, 2):
            yield round(height, 2)
            height -= layer_height
