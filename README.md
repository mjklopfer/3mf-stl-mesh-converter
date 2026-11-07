# 3MF Mesh Converter

Convert a Bambu Studio .3mf project to binary STL, plain 3MF, or both.
Uses Python 3's standard library. The window requires Tkinter, included in
the standard Windows Python installer when Tcl/Tk support is installed.

Open a PowerShell window in this folder and run:

```powershell
python .\gear_converter.py
```

Select the input .3mf, choose a save folder and format, and click **Convert**.
The save folder initially defaults to the input folder.

For the command line:

```powershell
python .\gear_converter.py "input.3mf" --output-dir "." --format both
```

Use `--format stl`, `--format 3mf`, or `--format both`. The default is both.
The script appends `_generic` to output names and refuses to overwrite files.

The converter follows linked mesh parts, applies object and build transforms,
and exports coordinates in millimeters. Plain 3MF retains individual mesh
instances; STL combines their triangles into one mesh file. Both outputs
preserve model geometry and placement but discard slicer settings, materials,
colors, painted supports, and printer profiles. Projects that require
non-mesh extensions are outside the intended scope. Open the result as a
model in Cura, then choose the printer, material, and slice there.

## Quick test

From the converter folder:

```powershell
python -m unittest -v
```

The test suite builds a small linked 3MF project in a temporary folder. It
checks both exports, including geometry, units and placement, and verifies
that an empty input fails cleanly and existing output files are preserved.
It does not need Cura, Tkinter, or any external model files.

To check the window manually, run `python .\gear_converter.py`, select a
Bambu .3mf and a fresh save folder, and choose **Both**. Open the two
resulting files as models in Cura. If the input STL is empty, use the original
.3mf project as the source; an empty STL has no geometry to recover.
