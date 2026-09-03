"""FreeCAD command that converts a selected mesh or external STL."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui
import Import
import Mesh
from PySide import QtCore, QtWidgets

from . import engine


def _addon_directory() -> Path:
    return Path(__file__).resolve().parents[1]


def _decode(data) -> str:
    return bytes(data).decode("utf-8", errors="replace")


def _selected_mesh():
    selection = Gui.Selection.getSelection()
    meshes = [obj for obj in selection if obj.isDerivedFrom("Mesh::Feature")]
    return meshes[0] if len(meshes) == 1 else None


def _external_stl(parent) -> tuple[Path | None, str | None]:
    filename, _selected_filter = QtWidgets.QFileDialog.getOpenFileName(
        parent,
        "Choose an STL to reconstruct",
        "",
        "STL mesh (*.stl)",
    )
    if not filename:
        return None, None

    choice = QtWidgets.QMessageBox.question(
        parent,
        "STL to STEP",
        "Does this unitless STL use millimetres?\n\n"
        "Choose Yes for millimetres or No for inches.",
        QtWidgets.QMessageBox.Yes
        | QtWidgets.QMessageBox.No
        | QtWidgets.QMessageBox.Cancel,
        QtWidgets.QMessageBox.Yes,
    )
    if choice == QtWidgets.QMessageBox.Cancel:
        return None, None
    return Path(filename), "mm" if choice == QtWidgets.QMessageBox.Yes else "in"


def _result_summary(result: dict) -> str:
    lines = [
        "The STEP geometry was imported.",
        "",
        f"Triangles: {result.get('triangles', 0)}",
        f"Solids: {result.get('solids', 0)}",
        f"Open shells: {result.get('openShells', 0)}",
        "Faces after reconstruction: "
        f"{result.get('facesAfterSmooth', result.get('facesAfterUnify', 0))}",
        f"Planes recovered: {result.get('smoothPlanes', 0)}",
        f"Cylinders recovered: {result.get('smoothCylinders', 0)}",
        f"Fillets recovered: {result.get('smoothFillets', 0)}",
        f"Elapsed: {result.get('seconds', 0):.2f}s",
    ]
    warnings = result.get("warnings") or []
    if warnings:
        lines.extend(["", "Warnings:", *[f"- {warning}" for warning in warnings]])
    return "\n".join(lines)


class ConvertCommand:
    NAME = "Stl2Step_Convert"

    def __init__(self):
        self._process = None
        self._temp_directory = None
        self._output_step = None
        self._document_name = None
        self._source_mesh_name = None

    def GetResources(self):
        return {
            "Pixmap": str(_addon_directory() / "resources" / "stl2step.svg"),
            "MenuText": "STL to STEP Solid",
            "ToolTip": "Reconstruct a selected mesh or STL as STEP B-Rep geometry.",
        }

    def IsActive(self):
        return self._process is None

    def Activated(self):
        parent = Gui.getMainWindow()
        document = App.ActiveDocument or App.newDocument("Stl2Step")
        source_mesh = _selected_mesh()

        self._temp_directory = Path(tempfile.mkdtemp(prefix="stl2step-freecad-"))
        if source_mesh:
            input_stl = self._temp_directory / f"{source_mesh.Name}.stl"
            try:
                Mesh.export([source_mesh], str(input_stl))
            except Exception as exc:
                self._cleanup()
                QtWidgets.QMessageBox.critical(
                    parent, "STL to STEP", f"Could not export the selected mesh:\n\n{exc}"
                )
                return
            units = "mm"
            self._source_mesh_name = source_mesh.Name
        else:
            input_stl, units = _external_stl(parent)
            if not input_stl:
                self._cleanup()
                return
            self._source_mesh_name = None

        try:
            executable = engine.resolve_executable(_addon_directory())
        except engine.EngineError as exc:
            self._cleanup()
            QtWidgets.QMessageBox.critical(parent, "STL to STEP", str(exc))
            return

        self._document_name = document.Name
        self._output_step = self._temp_directory / f"{input_stl.stem}.step"
        self._process = QtCore.QProcess(parent)
        self._process.finished.connect(self._finished)
        self._process.setProgram(str(executable))
        self._process.setArguments(
            engine.arguments(input_stl, self._output_step, units=units)
        )
        self._process.start()

        if not self._process.waitForStarted(1000):
            error = self._process.errorString()
            self._process = None
            self._cleanup()
            QtWidgets.QMessageBox.critical(
                parent, "STL to STEP", f"Could not start stl2step:\n\n{error}"
            )
            return

        App.Console.PrintMessage(f"stl2step: converting {input_stl}\n")

    def _finished(self, exit_code, _exit_status):
        parent = Gui.getMainWindow()
        process = self._process
        self._process = None
        stdout = _decode(process.readAllStandardOutput())
        stderr = _decode(process.readAllStandardError()).strip()

        try:
            result = engine.parse_result(stdout)
            if exit_code not in {0, 2} or not result.get("ok"):
                detail = result.get("error") or stderr or "conversion failed"
                raise engine.EngineError(f"stl2step exited {exit_code}: {detail}")
            if not self._output_step.is_file():
                raise engine.EngineError(
                    "stl2step reported success but the STEP file is missing"
                )

            try:
                document = App.getDocument(self._document_name)
            except NameError as exc:
                raise engine.EngineError(
                    "The document that started the conversion is no longer open. "
                    f"The STEP remains at {self._output_step}."
                ) from exc

            Import.insert(str(self._output_step), document.Name)
            document.recompute()

            if self._source_mesh_name:
                source = document.getObject(self._source_mesh_name)
                if source:
                    source.ViewObject.Visibility = False

            QtWidgets.QMessageBox.information(
                parent, "STL to STEP", _result_summary(result)
            )
            self._cleanup()
        except Exception as exc:
            App.Console.PrintError(f"stl2step: {exc}\n")
            retained = f"\n\nTemporary files remain at:\n{self._temp_directory}"
            QtWidgets.QMessageBox.critical(
                parent, "STL to STEP", f"Could not import the conversion:\n\n{exc}{retained}"
            )

    def _cleanup(self):
        if self._temp_directory:
            shutil.rmtree(self._temp_directory, ignore_errors=True)
        self._temp_directory = None
        self._output_step = None
        self._document_name = None
        self._source_mesh_name = None

    @classmethod
    def install(cls):
        Gui.addCommand(cls.NAME, cls())
