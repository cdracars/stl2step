# Fusion add-in prototype

This is intentionally a small, throwaway integration prototype. It answers one
question:

> Can a Fusion toolbar command run `stl2step` outside Fusion and safely import
> the resulting STEP body back into the active design?

The prototype converts an STL selected from disk. It does not yet convert an
already-imported Fusion mesh body or bundle release binaries.

## Install for development

Copy or link the `Stl2StepFusion` directory into Fusion's add-in directory:

- Windows: `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns`
- macOS: `~/Library/Application Support/Autodesk/Autodesk Fusion/API/AddIns`

Alternatively, use the **+** button in **Utilities → Scripts and Add-Ins** and
select `Stl2StepFusion.py` from this directory.

Make the engine available in one of these locations, checked in order:

1. The path in the `STL2STEP_EXECUTABLE` environment variable.
2. A platform-specific path inside `Stl2StepFusion/bin/`:
   - `windows-x86_64/stl2step.exe`
   - `macos-arm64/stl2step`
   - `macos-x86_64/stl2step`
3. `stl2step` on `PATH`.

Start the add-in, open a Design document, and use **Solid → Utilities →
STL to STEP Solid**.

## Current behavior

- Prompts for an STL file.
- Prompts whether the unitless STL coordinates represent millimetres or inches.
- Runs TrueForm with `--quiet --no-verify --engine trueform` on a worker thread.
- Treats converter exit codes 0 and 2 as a produced STEP file.
- Imports the STEP only after the Fusion command has ended, using a custom event
  on Fusion's main thread.
- Shows the key `RESULT` statistics and warnings after import.
- Removes the temporary conversion directory after a successful import.

The imported STEP is direct B-Rep geometry. This does not reconstruct Fusion
sketches, constraints, dimensions, or timeline features.
