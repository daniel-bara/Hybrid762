from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import adsk.fusion


@dataclass
class TempFilePaths:
    additive: Optional[Path]
    finishing: Optional[Path]
    planarising: Optional[Path]


@dataclass
class HybridPostConfig:
    """Carries configuration from the UI to the post processors"""
    useImaging: bool = True
    laserScanning: bool = False
    collectLoadCellData: bool = False
    dryingTime: int = 0
    finishingMilling: bool = False
    finishingMillingSetup: str = ""
    defectCorrection: bool = False
    firstCorrectionLayer: int = 2
    outputFilePath:Path = Path()