"""Fusion add-in prototype for stl2step.

The converter runs in a worker thread. Fusion API calls remain on the main
thread and the generated STEP is imported from a custom-event handler after the
toolbar command has ended.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import threading
import traceback
from pathlib import Path

import adsk.core
import adsk.fusion

import engine


COMMAND_ID = "cdracars_stl2step_fusion_convert"
COMMAND_NAME = "STL to STEP Solid"
COMMAND_DESCRIPTION = "Reconstruct an STL as STEP B-Rep geometry with stl2step."
PANEL_ID = "SolidScriptsAddinsPanel"
COMPLETED_EVENT_ID = "cdracars_stl2step_fusion_completed"

_app = None
_ui = None
_completed_event = None
_handlers = []
_workers = set()


def _show_error(message: str) -> None:
    if _ui:
        _ui.messageBox(message, COMMAND_NAME)


def _result_summary(result: dict) -> str:
    lines = [
        "The STEP geometry was imported.",
        "",
        f"Triangles: {result.get('triangles', 0)}",
        f"Solids: {result.get('solids', 0)}",
        f"Open shells: {result.get('openShells', 0)}",
        f"Faces after reconstruction: {result.get('facesAfterSmooth', result.get('facesAfterUnify', 0))}",
        f"Planes recovered: {result.get('smoothPlanes', 0)}",
        f"Cylinders recovered: {result.get('smoothCylinders', 0)}",
        f"Fillets recovered: {result.get('smoothFillets', 0)}",
        f"Elapsed: {result.get('seconds', 0):.2f}s",
    ]
    warnings = result.get("warnings") or []
    if warnings:
        lines.extend(["", "Warnings:", *[f"- {warning}" for warning in warnings]])
    return "\n".join(lines)


def _remove_temp_directory(payload: dict) -> None:
    temp_directory = payload.get("tempDirectory")
    if temp_directory:
        shutil.rmtree(temp_directory, ignore_errors=True)


class ConversionCompletedHandler(adsk.core.CustomEventHandler):
    def notify(self, args):
        payload = {}
        try:
            payload = json.loads(args.additionalInfo)
            if not payload.get("ok"):
                _show_error(payload.get("error", "Conversion failed."))
                return

            if _ui.activeCommand != "SelectCommand":
                select_command = _ui.commandDefinitions.itemById("SelectCommand")
                if select_command:
                    select_command.execute()

            design = adsk.fusion.Design.cast(_app.activeProduct)
            if not design:
                _show_error(
                    "Conversion finished, but no Fusion Design is active.\n\n"
                    f"The generated STEP remains at:\n{payload['stepPath']}"
                )
                payload.pop("tempDirectory", None)
                return

            import_manager = _app.importManager
            options = import_manager.createSTEPImportOptions(payload["stepPath"])
            imported = import_manager.importToTarget2(options, design.rootComponent)
            if imported is None:
                raise RuntimeError("Fusion returned no objects while importing the STEP file")

            _ui.messageBox(_result_summary(payload["result"]), COMMAND_NAME)
        except Exception:
            _show_error(f"Could not import the converted STEP:\n\n{traceback.format_exc()}")
        finally:
            _remove_temp_directory(payload)


def _worker(input_path: str, units: str) -> None:
    current_thread = threading.current_thread()
    temp_directory = Path(tempfile.mkdtemp(prefix="stl2step-fusion-"))
    output_path = temp_directory / f"{Path(input_path).stem}.step"
    payload = {
        "ok": False,
        "tempDirectory": str(temp_directory),
        "stepPath": str(output_path),
    }

    try:
        executable = engine.resolve_executable(Path(__file__).resolve().parent)
        payload["result"] = engine.convert(
            executable,
            Path(input_path),
            output_path,
            units=units,
        )
        payload["ok"] = True
    except Exception as exc:
        payload["error"] = str(exc)
    finally:
        _app.fireCustomEvent(COMPLETED_EVENT_ID, json.dumps(payload))
        _workers.discard(current_thread)


class ExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, _args):
        try:
            design = adsk.fusion.Design.cast(_app.activeProduct)
            if not design:
                _show_error("Open or create a Fusion Design before running this command.")
                return

            file_dialog = _ui.createFileDialog()
            file_dialog.title = "Choose an STL to reconstruct"
            file_dialog.filter = "STL mesh (*.stl)"
            if file_dialog.showOpen() != adsk.core.DialogResults.DialogOK:
                return

            buttons = adsk.core.MessageBoxButtonTypes.YesNoCancelButtonType
            choice = _ui.messageBox(
                "Does this STL use millimetres?\n\n"
                "Yes = millimetres\nNo = inches\nCancel = stop",
                COMMAND_NAME,
                buttons,
            )
            if choice == adsk.core.DialogResults.DialogCancel:
                return
            units = "mm" if choice == adsk.core.DialogResults.DialogYes else "in"

            worker = threading.Thread(
                target=_worker,
                args=(file_dialog.filename, units),
                name="stl2step-fusion-convert",
                daemon=True,
            )
            _workers.add(worker)
            worker.start()
        except Exception:
            _show_error(f"Could not start conversion:\n\n{traceback.format_exc()}")


class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        handler = ExecuteHandler()
        args.command.execute.add(handler)
        _handlers.append(handler)


def run(_context):
    global _app, _ui, _completed_event
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface

        _completed_event = _app.registerCustomEvent(COMPLETED_EVENT_ID)
        completed_handler = ConversionCompletedHandler()
        _completed_event.add(completed_handler)
        _handlers.append(completed_handler)

        command_definition = _ui.commandDefinitions.itemById(COMMAND_ID)
        if not command_definition:
            command_definition = _ui.commandDefinitions.addButtonDefinition(
                COMMAND_ID,
                COMMAND_NAME,
                COMMAND_DESCRIPTION,
            )

        created_handler = CommandCreatedHandler()
        command_definition.commandCreated.add(created_handler)
        _handlers.append(created_handler)

        panel = _ui.allToolbarPanels.itemById(PANEL_ID)
        if not panel:
            raise RuntimeError(f"Fusion toolbar panel not found: {PANEL_ID}")
        control = panel.controls.itemById(COMMAND_ID)
        if not control:
            control = panel.controls.addCommand(command_definition)
        control.isPromoted = True
    except Exception:
        _show_error(f"Could not start the add-in:\n\n{traceback.format_exc()}")


def stop(_context):
    global _completed_event
    try:
        if _ui:
            panel = _ui.allToolbarPanels.itemById(PANEL_ID)
            if panel:
                control = panel.controls.itemById(COMMAND_ID)
                if control:
                    control.deleteMe()
            command_definition = _ui.commandDefinitions.itemById(COMMAND_ID)
            if command_definition:
                command_definition.deleteMe()

        if _completed_event and _app:
            _app.unregisterCustomEvent(COMPLETED_EVENT_ID)
            _completed_event = None
        _handlers.clear()
    except Exception:
        _show_error(f"Could not stop the add-in cleanly:\n\n{traceback.format_exc()}")
