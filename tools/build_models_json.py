"""Extract part geometry from ToolboxModels/*.rbxm (XML) into models.json for the web viewer."""
import json, os, re, xml.etree.ElementTree as ET
SRC = os.path.join(os.path.dirname(__file__), "..", "ToolboxModels")
OUT = os.path.join(os.path.dirname(__file__), "..", "models.json")

def num(e, tag, d=0.0):
    c = e.find(tag)
    try: return float(c.text)
    except (AttributeError, TypeError, ValueError): return d

def find(props, kind, names):
    for e in props.iter(kind):
        if e.get("name") in names: return e

out = []
for f in sorted(os.listdir(SRC), key=lambda x: int(x.split()[0]) if x[0].isdigit() else 0):
    if not f.endswith(".rbxm"): continue
    m = re.match(r"(\d+)\s+(.*)\.rbxm", f)
    parts = []
    try: root = ET.parse(os.path.join(SRC, f)).getroot()
    except ET.ParseError: root = None
    for item in (root.iter("Item") if root is not None else []):
        if item.get("class") not in ("Part", "TrussPart"): continue
        p = item.find("Properties")
        if p is None: continue
        cf = find(p, "CoordinateFrame", {"CoordinateFrame", "CFrame"})
        sz = find(p, "Vector3", {"size", "Size"})
        col = find(p, "Color3", {"Color"})
        if cf is None or sz is None: continue
        shape = p.find(".//token[@name='shape']")
        tr = p.find(".//float[@name='Transparency']")
        top = p.find(".//Complex[@name='Top']/token[@name='Type']")
        parts.append({
            "cf": [round(num(cf, k), 4) for k in ("X","Y","Z","R00","R01","R02","R10","R11","R12","R20","R21","R22")],
            "s": [num(sz, "X", 1), num(sz, "Y", 1), num(sz, "Z", 1)],
            "c": [round(num(col, k, .5), 3) for k in "RGB"] if col is not None else [.6, .6, .6],
            "sh": "Truss" if item.get("class") == "TrussPart" else (shape.text if shape is not None else "Block"),
            "t": float(tr.text) if tr is not None else 0,
            "studs": top is not None and top.text == "Bumps",
        })
    out.append({"id": m.group(1), "name": m.group(2), "file": f, "kb": round(os.path.getsize(os.path.join(SRC, f))/1024, 1), "parts": parts})

json.dump(out, open(OUT, "w"), separators=(",", ":"))
print(len(out), "models,", sum(len(o["parts"]) for o in out), "parts; empty:", [o["name"] for o in out if not o["parts"]])
