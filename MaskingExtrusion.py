import adsk.core
import adsk.fusion
from . import fusion_utils
from .lib import fusion360utils as futil


class MaskingExtrusion:
    '''A wide extrusion in the Design workspace that is intersected with the part to slice it vertically.'''
    def __init__(self,
                 ui: adsk.core.UserInterface,
                 rootComp: adsk.fusion.Component):
        # Create a new sketch on the xy plane and draw a circle.
        xyPlane = rootComp.xYConstructionPlane
        self.sketch = rootComp.sketches.add(xyPlane)
        self.sketch.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), 500.0)

        # Create a thin extrusion to check if the body touches the build plate
        extrusion_input = rootComp.features.extrudeFeatures.createInput(
            self.sketch.profiles.item(0),
            adsk.fusion.FeatureOperations.IntersectFeatureOperation)  # type: ignore
        initial_distance = adsk.core.ValueInput.createByString(f"10 mm")
        extrusion_input.setDistanceExtent(False, initial_distance)
        futil.log(f"Masking extrusion created in {rootComp.name}")
        try:
            self.extrusion = rootComp.features.extrudeFeatures.add(extrusion_input)
        except RuntimeError as ex:
            # fusion_utils.messageBox(ui,
            #                  'Body does not rest on XY plane. Please use the Move/Copy or Align tools to move it to the XY plane.', 'Body not on XY plane', icon=adsk.core.MessageBoxIconTypes.WarningIconType)
            # raise RuntimeError("Body does not rest on XY plane. Could not slice for planarising.")
            fusion_utils.messageBox(ui,
                             'Could not create extrusion', '', icon=adsk.core.MessageBoxIconTypes.WarningIconType)
            raise RuntimeError("Could not create extrusion")
    
    def set_height(self, height_mm: float):
        self.extrusion.timelineObject.rollTo(True)
        extrusion_height = adsk.core.ValueInput.createByString(f"{round(height_mm, 2)} mm")

        self.extrusion.extentOne = adsk.fusion.DistanceExtentDefinition.create(extrusion_height)
        self.extrusion.timelineObject.rollTo(False)

    def deleteMe(self):
        self.extrusion.deleteMe()
        self.sketch.deleteMe()
