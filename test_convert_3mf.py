"""Run with python -m unittest -v in this folder."""
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import convert_3mf as converter


class ConverterTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder / "linked.3mf"
        core = converter.CORE
        with zipfile.ZipFile(self.source, "w") as archive:
            archive.writestr("_rels/.rels",
                f'<Relationships xmlns="{converter.REL}"><Relationship '
                f'Id="r" Type="{converter.MODEL_REL}" Target="/3D/main.model"/>'
                '</Relationships>')
            archive.writestr("3D/main.model", f'''
                <model xmlns="{core}" xmlns:p="{converter.PROD}" unit="millimeter">
                  <resources><object id="2"><components>
                    <component objectid="1" p:path="/3D/Objects/mesh.model"
                      transform="1 0 0 0 1 0 0 0 1 2 0 0"/>
                  </components></object></resources>
                  <build><item objectid="2" transform="0 1 0 -1 0 0 0 0 1 10 20 3"/>
                  <item objectid="999" printable="false"/></build>
                </model>''')
            archive.writestr("3D/Objects/mesh.model", f'''
                <model xmlns="{core}" unit="centimeter">
                  <resources><object id="1"><mesh><vertices>
                    <vertex x="0" y="0" z="0"/><vertex x="1" y="0" z="0"/>
                    <vertex x="0" y="1" z="0"/>
                  </vertices><triangles><triangle v1="0" v2="1" v3="2"/>
                  </triangles></mesh></object></resources><build/>
                </model>''')

    def run_cli(self, source, fmt="both"):
        return subprocess.run(
            [sys.executable, str(Path(converter.__file__)), str(source),
             "-o", str(self.folder), "--format", fmt],
            capture_output=True, text=True, timeout=10)

    def test_linked_project_exports_both_formats(self):
        result = self.run_cli(self.source)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = (self.folder / "linked_generic.stl").read_bytes()
        self.assertEqual(len(data), 134)
        self.assertEqual(struct.unpack_from("<I", data, 80)[0], 1)
        expected = [(10, 22, 3), (10, 32, 3), (0, 22, 3)]
        self.assertEqual(struct.unpack_from("<9f", data, 96),
                         tuple(x for vertex in expected for x in vertex))
        output = self.folder / "linked_generic.3mf"
        with zipfile.ZipFile(output) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(set(archive.namelist()),
                             {"[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model"})
        self.assertEqual(converter.read_meshes(output), [(expected, [(0, 1, 2)])])

    def test_existing_output_is_not_overwritten(self):
        existing = self.folder / "linked_generic.3mf"
        existing.write_bytes(b"keep me")
        result = self.run_cli(self.source)
        self.assertEqual(result.returncode, 1)
        self.assertIn("already exists", result.stderr)
        self.assertEqual(existing.read_bytes(), b"keep me")
        self.assertFalse((self.folder / "linked_generic.stl").exists())

    def test_empty_archive_fails_without_output(self):
        empty = self.folder / "empty.3mf"
        empty.touch()
        result = self.run_cli(empty)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Conversion failed", result.stderr)
        self.assertFalse(list(self.folder.glob("empty_generic.*")))

    def test_registered_stls_keep_shared_coordinates(self):
        stl = self.folder / "two.stl"
        def solid(name, x):
            return (f"solid {name}\nfacet normal 0 0 1\nouter loop\n"
                    f"vertex {x} 0 2\nvertex {x+1} 0 2\nvertex {x} 1 2\n"
                    f"endloop\nendfacet\nendsolid {name}\n")
        stl.write_text(solid("left", 4) + solid("right", 20), encoding="ascii")
        parts = converter.convert(stl, self.folder, "stl-parts")
        self.assertEqual(len(parts), 2)
        for part, x in zip(parts, (4, 20)):
            vertices, faces = converter.read_stl(part)[0]
            self.assertEqual(vertices, [(x, 0, 2), (x+1, 0, 2), (x, 1, 2)])
            self.assertEqual(faces, [(0, 1, 2)])
        stl_out, model_out = converter.convert(parts[0], self.folder, "both")
        self.assertEqual(converter.read_stl(stl_out), converter.read_meshes(model_out))

    def test_ignoring_placement_keeps_component_offset(self):
        part, = converter.convert(self.source, self.folder, "stl-parts",
                                  ignore_build_placement=True)
        self.assertEqual(converter.read_stl(part)[0][0],
                         [(2, 0, 0), (12, 0, 0), (2, 10, 0)])


if __name__ == "__main__":
    unittest.main()
