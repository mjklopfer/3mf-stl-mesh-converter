# 3MF and STL Converter for Aligned Parts

Convert mesh geometry between 3MF and STL for use in slicers such as UltiMaker
Cura. Extract geometry from Bambu Studio projects, or start with an existing
STL. Keep the whole model in one file or export existing parts as separate,
aligned STLs.

**Input:** A mesh-based Bambu Studio or standard `.3mf`, or a binary or ASCII
`.stl`. STL has no units; the converter assumes millimeters.

**Output:** Choose one STL, plain 3MF, both, or one registered STL per source
mesh instance. Plain 3MF contains the geometry without Bambu Studio's settings.

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
| **Registered STL parts** | You want one STL per existing part, with all parts retaining their shared coordinates. |

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

1. Browse to the input **.3mf** or **.stl**.
2. Choose an existing save folder. It defaults to the input folder.
3. Choose an export format. Leave **Separate parts (registered STLs)** unchecked
   for a single STL. Check it with **Binary STL** or **Both** to export one STL
   per mesh, then click **Convert**.

## Use the command line

```sh
python convert_3mf.py "input.3mf" --output-dir "." --format both
```

Use `--format stl`, `--format 3mf`, `--format both`, or `--format stl-parts`. If omitted, the
converter saves both formats beside the input. Outputs are named
`input_generic.stl` and `input_generic.3mf`. The source is left untouched,
and existing outputs are not overwritten. Use `--help` for the full options.

## How multipart export works

A multipart 3MF can hold several meshes in one file, each with its own
position and orientation. For example, an assembly with a base and two accent
meshes can be exported as one plain 3MF with all three meshes in place.
Import it into Cura as a model and assign each mesh to an extruder. You don't
need a separate 3MF for each color, and the original filament assignments
aren't copied into the plain 3MF.

Choose separate STLs when you want one file per mesh. Registered means the
files share the same coordinate system: the converter doesn't center or drop
each mesh separately.

```sh
python convert_3mf.py "assembly.3mf" --output-dir "." --format stl-parts
```

Equivalently, use `--format stl --separate-parts`; with `--format both`, this
writes the registered STLs and one multipart 3MF.

Each existing mesh instance becomes an `assembly_part_001.stl` (and so on).
If the Bambu project explicitly assigns the mesh or its parent to a filament
slot, the output is labeled, for example, `assembly_filament_02_part_001.stl`.
Parts for the same filament sort together by filename and remain separate files.
Unassigned parts receive no filament label. The label is not embedded in STL.
Import the STLs into Cura, assign each part to an
extruder, and use **Merge Models** to assemble them at their shared origin.
Check the result in Cura Preview before printing.

If a generator exported each color as a separate 3MF and gave each file a
different plate position or rotation, select **Ignore 3MF build-plate
placement** or pass `--ignore-build-placement` for each input. This keeps
component transforms and skips only the build-item transform. Use it only if
the sources were designed with a shared origin.

Separate meshes are not the same as painted faces. If the source is a single
binary STL or a single painted 3MF mesh, this mode writes one STL. It does
not infer color regions, recover missing filament assignments, or transfer sliced
layers. An ASCII STL with several explicit solids can export one STL per solid.

If the source has only one painted mesh, use the generator's separate color
exports to get assignable geometry.

## Optional: Running automated tests

Skip this section if you just want to convert a file. Use the window or
command-line instructions above. The tests check the converter with generated
sample data; they do not convert your files.

```sh
python -m unittest -v
```

The automated tests generate their own 3MF fixture and check unit conversion,
placement, both output formats, invalid input handling, and overwrite
protection. They run headlessly using only Python's standard library.

Converted output has also been tested by importing it into UltiMaker Cura.
