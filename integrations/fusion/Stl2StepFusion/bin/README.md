# Engine bundles

Release packaging will place the `stl2step` executable and its runtime libraries
under one of these directories:

- `windows-x86_64/`
- `macos-arm64/`
- `macos-x86_64/`

For development, setting `STL2STEP_EXECUTABLE` is usually faster than copying a
build here.
