"""GUI entry point for the STL to STEP prototype workbench."""

from pathlib import Path

import FreeCADGui as Gui

from stl2step_freecad.command import ConvertCommand


class Stl2StepWorkbench(Gui.Workbench):
    MenuText = "STL to STEP"
    ToolTip = "Experimental stl2step integration"
    Icon = str(Path(__file__).parent / "resources" / "stl2step.svg")

    def Initialize(self):
        ConvertCommand.install()
        self.appendToolbar("STL to STEP", [ConvertCommand.NAME])
        self.appendMenu("STL to STEP", [ConvertCommand.NAME])

    def GetClassName(self):
        return "Gui::PythonWorkbench"


Gui.addWorkbench(Stl2StepWorkbench())
