# Hybrid762
An Autodesk Fusion add-in for hybrid machines with additive and milling capabilities. Tested on (Fusion 2.0.18961; x86_64; Windows 11), with a bespoke machine at the University of Leeds.

## Glossary
- 'Add-in' and 'plugin' are used interchangeably.
- 'Planarisation', 'Defect Correction', and 'Face milling' are used to refer to milling operations between printed layers.
- 'Hybrid762' is the name of the plugin. The numbers were chosen at random.
- 'CHAMP' stands for Ceramic Hybrid Additive Manufacturing Platform. It is the multi-tool hybrid machine this plugin was developed for.
- 'Post-processing', 'Post Processing', and 'Exporting' are used interchangeably to refer to the G-code generation process in Fusion.

# Installation guide
- Download this repository
- Open Autodesk Fusion
- Click the `Utilities` tab -> `Add-Ins` -> Click `Scripts and Add-Ins`
- Switch to the `Add-Ins` tab
- Click the green plus icon next to `My Add-Ins`
- Navigate to the downloaded repository and select the `Hybrid762` folder
- Select the `Run on Startup` box
- Click `Run`

# Usage guide
## Fusion Features
Despite the author's best efforts, the usage of this plugin requires a high level of familiarity with Autodesk Fusion. The most relevant features will be introduced here:

At the highest level, Fusion has workspaces. Of these, two are of interest to us: `Design` and `Manufacturing`.

The `Design` tab lets you create a 3D model using sequential operations like sketches and extrusions. Alternatively, you can import a 3D CAD file here.

The `Manufacturing` tab contains all the tools related to additive manufacturing (3D printing) and milling, and this is where this plugin adds new functionalities.
As a starting point for the Manufacturing workspace, Fusion has `Setups`. These contain geometries from the Design tab, manufacturing operation(s), and their settings. Setups can be milling or additive setups, and can be assigned `Manufacturing Models`, `Machines`,  `Post Processors`, `Print Settings`, and `Operations`.
- **Manufacturing Models** are derivations of bodies from the Design workspace. They may contain additional modifications to the referenced body.
- **Machines** contain settings such as maximum allowed speeds, and nozzle and filament diameters.
- **Post-processors** are usually bundled with Machines. They are JavaScript-based programs that turn a Setup into a G-code file that can be loaded onto the machine.
- **Print settings** only apply to additive setups, and contain settings such as layer heights and printing temperatures.
- **Operations** only apply to milling setups, and define what shape the toolpath will be. They have settings such as feedrate, retraction height, and tolerance.


## Plugin and CHAMP Features
The CHAMP contains 
- a milling tool
- a polymer extruder
- a ceramic extruder
- a drying lamp
- a camera with defect detection functionality. 

Therefore, most of the features of this plugin require these specific capabilities.

By default, the plugin prints using an **additive** Setup. Two kinds of **milling** strategies can be added to this to make a **hybrid** operation.
- **Additive (required)**: Prints ceramic and/or polymer parts.
- **Defect correction** (optional): Checks for defects after each layer. If it finds over-extrusions, it removes them using the milling tool. If it finds under-extrusions, it removes the layer using the milling tool and re-prints it.
- **Finishing** milling (optional): Performs a series of milling operations after printing. This is used to make the part surface smoother and more precise.

## Plugin workflow
- Create a body in the `Design` workspace. It is advised that you create a single body that rests on the XY plane in the exact orientation that you wish to print it.

- Go to the `Manufacturing` workspace and select the `Hybrid` tab. In the `POST` section, select `Setup Wizard`. This creates three Setups and two manufacturing models.

- **Manufacturing Models**:
  - **Additive**: If you are using the Finishing setting on convex parts, it is recommended that you scale the part up in this Manufacturing Model by ~2 mm. This will result in the outer surface of the part being machined away, leaving a smooth and precise surface.
  - **Milling**: This Manufacturing Model is used to align the position of the milling operations with the Additive operation. If a Raft is enabled in print settings, for Additive, the part will get raised by a certain height. Therefore, the part gets raise in this Manufacturing Model to align the two. The Setup Wizard automatically raises the part by the raft height, which is currently stored in `config.py`. If you change the raft height for the current document only, you can modify the Move feature in this Manufacturing Model. If you wish to change this height for new setups,  modify the value in `config.py` and reload the plugin.

- **Setups**: Modify the settings on these as required. Keep positions aligned between setups.
  
  - **Additive**: By default, the **Machine settings** and **Print settings** are loaded from files. If you wish to make your changes default, you will need to export them from the Machine Library or the Print Setting Library, and overwrite the relevant files bundled with this add-in.

  - **Finishing**: By default, a single milling operation is created from a Template. If you wish to make you settings default, you need to export the template from the Template Library, and overwrite `finishing.f3dhsm-template`.
  
  - **Defect Correction**: This feature is automated. The part will be automatically sliced to generate milling toolpaths at different layer heights. If you would like to preivew the toolpath, you will need to slice the part and select the face on the top. **All  operations will be created from a Template**. If you wish to save your settings on the Operation, you need to export the template from the Template Library, and overwrite `defect correction.f3dhsm-template`.

- Once you are happy with the settings, click the `Hybrid Post Process` button. This brings up a dialog box for you to adjust settings for hybrid strategies and machine-specific functions.

- Click the `Post` button to export the setups to a G-code file. The file will be revealed in the explorer once it has been generated. (It takes anywhere from 5 seconds to 3 minutes depending on the selected operations and part size).


# Background Info

## Implementation
- The basis of the plugin is a customised **additive post-processor**. This contains multiple input parameters, and inserts placeholders into the additive G-code, which get replaced by milling G-code when the add-in is executed.

## Known bugs
- Modified first layer height breaks defect correction slicing and the layer height prediction in the post-processor
- Layer height needs to be set in config because of lack of documentation on prinstetting API
- Objects with no flat top surface are not always sliced for defect correction.
- If a post processor is invalid, this is not clear from the error message when the Hybrid Post Processor is run

## Features to add/improve
- Better tooltip descriptions and pictures
- Mid-print contour milling to access inner areas
- Asynchronous toolpath generation for defect correction
- Support for more than one additive setup per document
- Support for rotating/moving in Manufacturing workspace
- Automatically select finishing setup (first one where name contains 'Finishing')

## Acknowledgements
- This add-in uses code from Andy Everitt's 2021 project 'ASMBL'. Available at https://github.com/AndyEveritt/ASMBL
- This add-in uses code from examples by Autodesk (generated through the 'Create New Script or Add-In' window or available from https://help.autodesk.com)
- This add-in uses code from the Autodesk Forum user kandennti's 2024 forum post. Available at https://forums.autodesk.com/t5/fusion-api-and-scripts/how-to-create-an-additive-setup-using-createsetupcmd/m-p/12738098#M21435
