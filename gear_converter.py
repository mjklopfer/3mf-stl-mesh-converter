"""Convert mesh-based 3MF projects to plain 3MF and/or binary STL."""
import argparse
import math
import posixpath
import struct
import sys
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
MODEL_REL = "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"
PROD = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
SCALE = dict(micron=.001, millimeter=1, centimeter=10, inch=25.4, foot=304.8, meter=1000)
IDENTITY = (1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0)


def tag(name):
    return f"{{{CORE}}}{name}"


def part_path(target, parent=""):
    uri = urlsplit(target)
    if uri.scheme or uri.netloc or uri.query or uri.fragment:
        raise ValueError(f"Unsupported model part reference: {target}")
    path = unquote(uri.path)
    path = posixpath.normpath(path.lstrip("/") if path.startswith("/") else
                             posixpath.join(posixpath.dirname(parent), path))
    if path in (".", "..") or path.startswith("../") or "\\" in path:
        raise ValueError(f"Invalid model part reference: {target}")
    return path


def apply_transform(meshes, value, scale):
    m = tuple(map(float, value.split())) if value else IDENTITY
    if len(m) != 12 or not all(map(math.isfinite, m)):
        raise ValueError("Invalid 3MF transform")
    det = (m[0]*(m[4]*m[8]-m[5]*m[7]) - m[1]*(m[3]*m[8]-m[5]*m[6])
           + m[2]*(m[3]*m[7]-m[4]*m[6]))
    for vertices, faces in meshes:
        yield ([tuple(sum(v[i]*m[3*i+j] for i in range(3)) + m[9+j]*scale
                      for j in range(3)) for v in vertices],
               [(a, c, b) for a, b, c in faces] if det < 0 else faces)


def read_meshes(source):
    with zipfile.ZipFile(source) as archive:
        rels = ET.fromstring(archive.read("_rels/.rels"))
        roots = [r for r in rels if r.get("Type") == MODEL_REL]
        if len(roots) != 1 or roots[0].get("TargetMode") == "External":
            raise ValueError("Expected one internal 3MF root model")
        main = part_path(roots[0].attrib["Target"])
        parts = {}

        def load(path):
            if path not in parts:
                model = ET.fromstring(archive.read(path))
                if model.tag != tag("model"):
                    raise ValueError(f"Invalid model part: {path}")
                unit = model.get("unit", "millimeter")
                if unit not in SCALE:
                    raise ValueError(f"Unsupported model unit: {unit}")
                objects = {o.attrib["id"]: o for o in model.findall(
                    f"{tag('resources')}/{tag('object')}")}
                parts[path] = model, SCALE[unit], objects
            return parts[path]

        def resolve(path, ident, stack):
            key = (path, ident)
            if key in stack:
                raise ValueError("Circular component reference")
            _, scale, objects = load(path)
            if ident not in objects:
                raise ValueError(f"Missing object {ident} in {path}")
            obj = objects[ident]
            if obj.get("type", "model") not in ("model", "solid"):
                return
            mesh = obj.find(tag("mesh"))
            if mesh is not None:
                verts = [tuple(float(v.attrib[k])*scale for k in "xyz")
                         for v in mesh.findall(f"{tag('vertices')}/{tag('vertex')}")]
                faces = [tuple(int(t.attrib[k]) for k in ("v1", "v2", "v3"))
                         for t in mesh.findall(f"{tag('triangles')}/{tag('triangle')}")]
                if (not faces or not all(math.isfinite(x) for v in verts for x in v)
                        or any(not 0 <= i < len(verts) for f in faces for i in f)):
                    raise ValueError(f"Invalid or empty mesh in object {ident}")
                yield verts, faces
                return
            components = obj.findall(f"{tag('components')}/{tag('component')}")
            if not components:
                raise ValueError(f"Object {ident} has no supported mesh or components")
            for comp in components:
                target = comp.get(f"{{{PROD}}}path")
                yield from apply_transform(
                    resolve(part_path(target, path) if target else path,
                            comp.attrib["objectid"], stack | {key}),
                    comp.get("transform"), scale)

        model, scale, _ = load(main)
        meshes = []
        for item in model.findall(f"{tag('build')}/{tag('item')}"):
            if item.get("printable", "1").lower() in ("0", "false"):
                continue
            target = item.get(f"{{{PROD}}}path")
            meshes.extend(apply_transform(
                resolve(part_path(target, main) if target else main,
                        item.attrib["objectid"], set()), item.get("transform"), scale))
        if not meshes:
            raise ValueError("No printable triangle meshes found")
        if not all(math.isfinite(x) for vertices, _ in meshes for v in vertices for x in v):
            raise ValueError("Transformed mesh has invalid coordinates")
        return meshes


def write_stl(file, meshes):
    count = sum(len(faces) for _, faces in meshes)
    file.write(b"Converted 3MF geometry (millimeters)".ljust(80, b"\0"))
    file.write(struct.pack("<I", count))
    for vertices, faces in meshes:
        for ids in faces:
            a, b, c = (vertices[i] for i in ids)
            u, v = ([p[j]-a[j] for j in range(3)] for p in (b, c))
            n = [u[(j+1)%3]*v[(j+2)%3]-u[(j+2)%3]*v[(j+1)%3] for j in range(3)]
            length = math.hypot(*n)
            file.write(struct.pack("<12fH", *(x/length if length else 0 for x in n),
                                   *a, *b, *c, 0))


def write_3mf(file, meshes):
    model = ET.Element("model", xmlns=CORE, unit="millimeter")
    resources = ET.SubElement(model, "resources")
    build = ET.SubElement(model, "build")
    for ident, (vertices, faces) in enumerate(meshes, 1):
        obj = ET.SubElement(resources, "object", id=str(ident), type="model")
        mesh = ET.SubElement(obj, "mesh")
        verts = ET.SubElement(mesh, "vertices")
        for x, y, z in vertices:
            ET.SubElement(verts, "vertex", x=str(x), y=str(y), z=str(z))
        tris = ET.SubElement(mesh, "triangles")
        for a, b, c in faces:
            ET.SubElement(tris, "triangle", v1=str(a), v2=str(b), v3=str(c))
        ET.SubElement(build, "item", objectid=str(ident))
    rels = ET.Element("Relationships", xmlns=REL)
    ET.SubElement(rels, "Relationship", Id="rel0", Type=MODEL_REL, Target="/3D/3dmodel.model")
    types = ET.Element("Types", xmlns=CT)
    ET.SubElement(types, "Default", Extension="rels",
                  ContentType="application/vnd.openxmlformats-package.relationships+xml")
    ET.SubElement(types, "Default", Extension="model",
                  ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml")
    with zipfile.ZipFile(file, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, xml in (("[Content_Types].xml", types), ("_rels/.rels", rels),
                          ("3D/3dmodel.model", model)):
            archive.writestr(name, ET.tostring(xml, encoding="utf-8", xml_declaration=True))


def convert(source, output_dir, fmt):
    source, output_dir = Path(source), Path(output_dir)
    if not source.is_file() or source.suffix.lower() != ".3mf":
        raise ValueError("Select an existing .3mf file.")
    if not output_dir.is_dir():
        raise ValueError("Select an existing output folder.")
    meshes = read_meshes(source)
    formats = ("stl", "3mf") if fmt == "both" else (fmt,)
    outputs = [output_dir / f"{source.stem}_generic.{ext}" for ext in formats]
    for dest in outputs:
        if dest.exists():
            raise FileExistsError(f"Output already exists: {dest}")
    for ext, dest in zip(formats, outputs):
        with dest.open("xb") as file:
            try:
                (write_stl if ext == "stl" else write_3mf)(file, meshes)
            except Exception:
                file.close()
                dest.unlink()
                raise
    return outputs


def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    root = tk.Tk()
    root.title("3MF Mesh Converter")
    root.columnconfigure(1, weight=1)
    source, output, fmt = tk.StringVar(), tk.StringVar(), tk.StringVar(value="both")

    def select_file():
        path = filedialog.askopenfilename(filetypes=[("3MF projects", "*.3mf")])
        if path:
            source.set(path)
            if not output.get():
                output.set(str(Path(path).parent))

    def select_dir():
        path = filedialog.askdirectory()
        if path:
            output.set(path)

    def save():
        try:
            paths = convert(source.get(), output.get(), fmt.get())
        except Exception as exc:
            messagebox.showerror("Conversion failed", str(exc), parent=root)
        else:
            messagebox.showinfo("Conversion complete", "\n".join(map(str, paths)), parent=root)

    for row, (label, var, choose) in enumerate(
            (("Input 3MF", source, select_file), ("Save folder", output, select_dir))):
        ttk.Label(root, text=label).grid(row=row, column=0, padx=8, pady=6, sticky="w")
        ttk.Entry(root, textvariable=var, width=55).grid(row=row, column=1, sticky="ew")
        ttk.Button(root, text="Browse…", command=choose).grid(row=row, column=2, padx=8)
    ttk.Label(root, text="Export as").grid(row=2, column=0, padx=8, sticky="w")
    ttk.Combobox(root, textvariable=fmt, values=("stl", "3mf", "both"),
                 state="readonly", width=10).grid(row=2, column=1, sticky="w")
    ttk.Button(root, text="Convert", command=save).grid(row=3, column=1, pady=10)
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, nargs="?", help="input .3mf project; omit for GUI")
    parser.add_argument("-o", "--output-dir", type=Path, help="existing save folder (default: input folder)")
    parser.add_argument("-f", "--format", choices=("stl", "3mf", "both"), default="both")
    args = parser.parse_args()
    if args.source is None:
        gui()
        return 0
    try:
        for path in convert(args.source, args.output_dir or args.source.parent, args.format):
            print(path.resolve())
    except (OSError, ValueError, KeyError, ET.ParseError, zipfile.BadZipFile,
            struct.error, RecursionError) as exc:
        print(f"Conversion failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
