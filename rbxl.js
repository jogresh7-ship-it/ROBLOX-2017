// Minimal reader for Roblox binary place/model files (.rbxl / .rbxm "<roblox!" format).
// Returns every BasePart with its world CFrame, size, color, shape and transparency.

function lz4(src, outLen) {
  const out = new Uint8Array(outLen); let i = 0, o = 0;
  while (i < src.length) {
    const tok = src[i++]; let lit = tok >> 4;
    if (lit === 15) { let b; do { b = src[i++]; lit += b; } while (b === 255); }
    out.set(src.subarray(i, i + lit), o); i += lit; o += lit;
    if (i >= src.length) break;
    const off = src[i] | (src[i + 1] << 8); i += 2;
    let ml = tok & 15;
    if (ml === 15) { let b; do { b = src[i++]; ml += b; } while (b === 255); }
    ml += 4; for (let k = 0; k < ml; k++, o++) out[o] = out[o - off];
  }
  return out;
}

class R {
  constructor(b) { this.b = b; this.p = 0; this.v = new DataView(b.buffer, b.byteOffset, b.byteLength); }
  u8() { return this.b[this.p++]; }
  u32() { const x = this.v.getUint32(this.p, true); this.p += 4; return x; }
  f32() { const x = this.v.getFloat32(this.p, true); this.p += 4; return x; }
  str() { const n = this.u32(); const s = new TextDecoder().decode(this.b.subarray(this.p, this.p + n)); this.p += n; return s; }
  // interleaved big-endian 32-bit words
  raw32(n) { const a = new Uint32Array(n), b = this.b, p = this.p;
    for (let i = 0; i < n; i++) a[i] = ((b[p + i] << 24) | (b[p + n + i] << 16) | (b[p + 2 * n + i] << 8) | b[p + 3 * n + i]) >>> 0;
    this.p += 4 * n; return a; }
  i32s(n) { return Array.from(this.raw32(n), x => (x >>> 1) ^ -(x & 1)); }
  refs(n) { const a = this.i32s(n); for (let i = 1; i < n; i++) a[i] += a[i - 1]; return a; }
  f32s(n) { const u = this.raw32(n), f = new Float32Array(1), w = new Uint32Array(f.buffer);
    return Array.from(u, x => { w[0] = ((x >>> 1) | (x << 31)) >>> 0; return f[0]; }); }
}

const AX = [[1,0,0],[0,1,0],[0,0,1],[-1,0,0],[0,-1,0],[0,0,-1]];
function rotFromId(id) {
  const c0 = AX[Math.floor((id - 1) / 6)], c1 = AX[(id - 1) % 6];
  const c2 = [c0[1]*c1[2]-c0[2]*c1[1], c0[2]*c1[0]-c0[0]*c1[2], c0[0]*c1[1]-c0[1]*c1[0]];
  return [c0[0],c1[0],c2[0], c0[1],c1[1],c2[1], c0[2],c1[2],c2[2]];
}

// Common BrickColor palette (id -> rgb 0-255), used when a part has no Color3uint8.
const BRICK = {1:[242,243,243],5:[215,197,154],9:[232,186,200],18:[204,142,105],21:[196,40,28],23:[13,105,172],24:[245,205,48],26:[27,42,53],28:[40,127,71],29:[161,196,140],37:[75,151,75],38:[160,95,53],45:[180,210,228],101:[218,134,122],102:[110,153,202],104:[107,50,124],105:[226,155,64],106:[218,133,65],107:[0,143,156],119:[164,189,71],125:[234,184,146],135:[116,134,157],141:[39,70,45],151:[120,144,130],153:[149,121,119],192:[105,64,40],194:[163,162,165],199:[99,95,98],208:[229,228,223],217:[124,92,70],226:[253,234,141],1001:[248,248,248],1002:[205,205,205],1003:[17,17,17],1004:[255,0,0],1009:[255,255,0],1010:[0,0,255],1020:[0,255,0]};
const PART_CLASSES = new Set(["Part","WedgePart","CornerWedgePart","TrussPart","SpawnLocation","Seat","VehicleSeat","SkateboardPlatform","MeshPart","UnionOperation","PartOperation","NegateOperation","FlagStand"]);
const SHAPES = ["Ball","Block","Cylinder","Wedge","CornerWedge"];

export function parseRbxBinary(buf) {
  const all = new Uint8Array(buf);
  if (new TextDecoder().decode(all.subarray(0, 8)) !== "<roblox!") throw new Error("Not a binary Roblox file");
  const classes = {}; let p = 32;
  const props = {}; // classId -> {name: values[]}
  while (p < all.length) {
    const name = new TextDecoder().decode(all.subarray(p, p + 4)).replace(/\0/g, "");
    const cl = new DataView(all.buffer, all.byteOffset + p + 4, 8).getUint32(0, true);
    const ul = new DataView(all.buffer, all.byteOffset + p + 8, 4).getUint32(0, true);
    const body = all.subarray(p + 16, p + 16 + (cl || ul));
    p += 16 + (cl || ul);
    if (name === "END") break;
    if (name !== "INST" && name !== "PROP") continue;
    let data = body;
    if (cl) { if (body[0] === 0x28 && body[1] === 0xb5) throw new Error("This file uses Zstandard compression, which the viewer doesn't support yet"); data = lz4(body, ul); }
    const r = new R(data);
    const id = r.u32();
    if (name === "INST") {
      const cname = r.str(); r.u8(); const n = r.u32();
      classes[id] = { name: cname, refs: r.refs(n) };
      continue;
    }
    const c = classes[id]; if (!c || !PART_CLASSES.has(c.name)) continue;
    const pname = r.str(), type = r.u8(), n = c.refs.length;
    const P = props[id] || (props[id] = {});
    try {
      if (type === 0x0E) { const x = r.f32s(n), y = r.f32s(n), z = r.f32s(n); P[pname] = x.map((_, i) => [x[i], y[i], z[i]]); }
      else if (type === 0x10) {
        const rots = [];
        for (let i = 0; i < n; i++) { const k = r.u8(); if (k === 0) { const m = []; for (let j = 0; j < 9; j++) m.push(r.f32()); rots.push(m); } else rots.push(rotFromId(k)); }
        const x = r.f32s(n), y = r.f32s(n), z = r.f32s(n);
        P[pname] = rots.map((m, i) => [x[i], y[i], z[i], ...m]);
      }
      else if (type === 0x1A) { const a = r.b.subarray(r.p, r.p + 3 * n); P[pname] = Array.from({ length: n }, (_, i) => [a[i] / 255, a[n + i] / 255, a[2 * n + i] / 255]); }
      else if (type === 0x0C) { const a = r.f32s(n), b = r.f32s(n), d = r.f32s(n); P[pname] = a.map((_, i) => [a[i], b[i], d[i]]); }
      else if (type === 0x0B || type === 0x12) P[pname] = Array.from(r.raw32(n));
      else if (type === 0x04) P[pname] = r.f32s(n);
    } catch (e) { /* skip unreadable property */ }
  }
  const parts = [];
  for (const id in props) {
    const c = classes[id], P = props[id], cf = P.CFrame; if (!cf) continue;
    const size = P.size || P.Size || P.InitialSize;
    for (let i = 0; i < cf.length; i++) {
      let col = P.Color3uint8?.[i] || P.Color?.[i];
      if (!col) { const b = BRICK[P.BrickColor?.[i]] || [163, 162, 165]; col = b.map(v => v / 255); }
      let sh = c.name === "WedgePart" ? "Wedge" : c.name === "CornerWedgePart" ? "CornerWedge" : c.name === "TrussPart" ? "Truss" : "Block";
      if (c.name === "Part" && P.shape) sh = SHAPES[P.shape[i]] || "Block";
      parts.push({ cf: cf[i], s: size ? size[i] : [4, 1, 2], c: col, sh, t: P.Transparency?.[i] || 0, cls: c.name,
        top: P.TopSurface?.[i] ?? 0, bot: P.BottomSurface?.[i] ?? 0 });
    }
  }
  return parts;
}
