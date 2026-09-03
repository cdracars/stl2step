# FreeCAD workbench prototype

This is intentionally a small, throwaway integration prototype. It answers one
question:

> Can a FreeCAD command run `stl2step` outside FreeCAD and turn either a
> selected mesh or an STL file into imported STEP geometry without blocking the
> interface?

## Install for development

Copy or link the `Stl2StepFreeCAD` directory into the `Mod` directory beneath
FreeCAD's user application-data directory. You can print that directory in the
FreeCAD Python console with:

```python
App.getUserAppDataDir()
```

Restart FreeCAD and select the **STL to STEP** workbench.

Make the engine available in one of these locations, checked in order:

1. The path in the `STL2STEP_EXECUTABLE` environment variable.
2. A platform-specific path inside `Stl2StepFreeCAD/bin/`:
   - `windows-x86_64/stl2step.exe`
   - `macos-arm64/stl2step`
   - `macos-x86_64/stl2step`
   - `linux-x86_64/stl2step`
3. `stl2step` on `PATH`.

## Current behavior

- Uses one selected `Mesh::Feature`, or prompts for an STL when no mesh is
  selected.
- Treats a FreeCAD mesh export as millimetres; prompts for units when opening an
  external STL.
- Runs TrueForm with `--quiet --no-verify --engine trueform` using `QProcess`.
- Treats converter exit codes 0 and 2 as a produced STEP file.
- Imports the STEP into the document that started the conversion.
- Hides the selected source mesh after a successful import.
- Shows the key `RESULT` statistics and warnings after import.

The imported STEP is direct B-Rep geometry. This does not reconstruct sketches,
constraints, dimensions, or a Part Design feature history.
