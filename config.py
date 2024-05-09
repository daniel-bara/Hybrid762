# Application Global Variables
# This module serves as a way to share variables across different
# modules (global variables).

from pathlib import Path

# Flag that indicates to run in Debug mode or not. When running in Debug mode
# more information is written to the Text Command window.
DEBUG = False

HYBRID_TAB_ID = 'HybridTab'
POST_PANEL_ID = 'HybridPostPanel'

# Gets the name of the add-in from the name of the folder the py file is in.
# This is used when defining unique internal names for various UI elements 
# that need a unique name. It's also recommended to use a company name as 
# part of the ID to better ensure the ID is unique.
ADDIN_NAME = Path(__file__).parent.name
COMPANY_NAME = 'UniOfLeeds'

DEFECT_CORRECTION_SETUP_NAME = "Defect Correction (with operation template)"
LAYER_HEIGHT = 0.6
RAFT_HEIGHT = 1.8

OUTPUT_FOLDER = Path(__file__).parent.joinpath('outputs')

ADDITIVE_POST_PROCESSOR_PATH = Path(__file__).parent.joinpath('post processors', 'Ceramic polymer post processor.cps')
MILLING_POST_PROCESSOR_PATH = Path(__file__).parent.joinpath('post processors', 'mach4mill.cps')
PRINTSETTING_PATH = Path(__file__).parent.joinpath('settings', 'Ceramic polymer.printsetting')
MACHINE_SETTING_PATH = Path(__file__).parent.joinpath('settings', 'CHAMP.mch')
DEFECT_CORRECTION_TEMPLATE_PATH = Path(__file__).parent.joinpath('templates', 'defect correction.f3dhsm-template')
FINISHING_TEMPLATE_PATH = Path(__file__).parent.joinpath('templates', 'finishing.f3dhsm-template')