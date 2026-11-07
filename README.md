# Bambu Studio 3MF to STL and Plain 3MF

Extract printable geometry from a Bambu Studio project and save it as a binary
STL or a plain, geometry-only 3MF for use in another slicer such as UltiMaker Cura.

A slicer project can store its meshes in separate files inside the 3MF package,
with references, transforms, and application-specific settings. If another
slicer cannot import that project, this tool follows the mesh references and
writes a simpler file. It works on mesh-based projects regardless of the model's
name or shape.

## Choose an output

| Output | Use it when |
| --- | --- |
| **Binary STL** | You want a widely supported mesh file. All printable triangles go into one file, in millimeters. |
| **Plain 3MF** | You want explicit units and separate mesh instances in a single file. |
| **Both** | You want to try both formats or keep both for later. |

The converter preserves geometry and model transforms. It omits slicer profiles,
materials, colors, painted supports, and printer-specific settings. Open the
result **as a model** in your slicer, choose your printer and material, and slice
it there. Neither export is a printer-ready job. This tool cannot recover an
empty STL; use the original 3MF project if available.

## Use the window

Download this repository (GitHub **Code → Download ZIP**) and extract it.
Install Python 3 with Tcl/Tk support for the window. No pip packages are needed.

Open a terminal in the extracted folder and run:

```sh
python convert_3mf.py
```

1. Browse to the input **.3mf** project.
2. Choose an existing save folder. It defaults to the input folder.
3. Choose **STL**, **3MF**, or **Both**, then click **Convert**.

## Use the command line

```sh
python convert_3mf.py "input.3mf" --output-dir "." --format both
```

Use `--format stl`, `--format 3mf`, or `--format both`. If omitted, the
converter saves both formats beside the input. Outputs are named
`input_generic.stl` and `input_generic.3mf`. The source is left untouched,
and existing outputs are not overwritten. Use `--help` for the full options.

## Run the tests

```sh
python -m unittest -v
```

The automated tests generate their own 3MF fixture and check unit conversion,
placement, both output formats, invalid input handling, and overwrite
protection. They run headlessly using only Python's standard library.

Converted output has also been tested by importing it into UltiMaker Cura.
