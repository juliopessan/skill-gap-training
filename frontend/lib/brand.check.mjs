// Runtime check for lib/brand.ts and the generated icon files (no extra dependencies).
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
const say = (...parts) => process.stdout.write(parts.join(" ") + "\n");

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");
const out = mkdtempSync(join(tmpdir(), "brand-check-"));
execFileSync("npx", ["tsc", join(here, "brand.ts"), "--outDir", out, "--module", "nodenext",
  "--target", "es2022", "--lib", "es2022,dom", "--skipLibCheck", "--types", "node"],
  { stdio: "inherit", cwd: root });
const B = await import(pathToFileURL(join(out, "brand.js")).href);

// (a) geometry: bars ascending, inside the square, no overlap, standing on the baseline row
const inside = (r, o) => r.x >= o.x && r.y >= o.y && r.x + r.width <= o.x + o.width && r.y + r.height <= o.y + o.height;
const apart = (a, b) => a.x + a.width <= b.x || b.x + b.width <= a.x || a.y + a.height <= b.y || b.y + b.height <= a.y;
assert.equal(B.BRAND_SQUARE.width, B.BRAND_SIZE);
assert.equal(B.BRAND_SQUARE.height, B.BRAND_SIZE);
assert.equal(B.BRAND_BARS.length, 3);
B.BRAND_BARS.forEach((b, i) => {
  assert.equal(b.y + b.height, B.BRAND_BAR_BOTTOM, `bar ${i} shares the bottom edge`);
  assert.ok(inside(b, B.BRAND_SQUARE), `bar ${i} inside square`);
  if (i > 0) {
    assert.ok(b.height > B.BRAND_BARS[i - 1].height, `bar ${i} taller than previous`);
    assert.ok(b.x > B.BRAND_BARS[i - 1].x, `bar ${i} to the right`);
    assert.ok(apart(b, B.BRAND_BARS[i - 1]), `bar ${i} does not overlap previous`);
  }
  assert.ok(apart(b, B.BRAND_BASELINE), `bar ${i} clear of baseline`);
});
assert.ok(inside(B.BRAND_BASELINE, B.BRAND_SQUARE));
// legibility at 16px: every bar stays >= 1.5px wide
for (const b of B.BRAND_BARS) assert.ok((b.width * 16) / B.BRAND_SIZE >= 1.5, "bar >= 1.5px at 16px");
say("ok: geometry (ascending, inside, no overlap, bars >= 1.5px at 16px)");

// (b) faviconFrame: valid, distinct per step, all 4 steps x light/dark
const seen = new Set();
for (const dark of [false, true]) {
  const c = dark ? B.BRAND_COLORS.dark : B.BRAND_COLORS.light;
  for (let step = 0; step < B.FAVICON_STEPS; step++) {
    const svg = B.faviconFrame(step, dark);
    assert.match(svg, /^<svg xmlns="http:\/\/www\.w3\.org\/2000\/svg" viewBox="0 0 28 28">.*<\/svg>$/s);
    assert.equal((svg.match(/<rect /g) ?? []).length, 5);
    assert.ok(svg.includes(`fill="${c.ink}"`) && svg.includes(`fill="${c.paper}"`));
    assert.ok(!/clay|mint|#ed6738|#2a7548/i.test(svg));
    assert.ok(!seen.has(svg), `frame ${step}/${dark} is unique`);
    seen.add(svg);
    const url = B.faviconFrameUrl(step, dark);
    assert.ok(url.startsWith("data:image/svg+xml,"));
    const payload = url.slice("data:image/svg+xml,".length);
    assert.ok(!/[<>"#\s]/.test(payload), "payload is URL-encoded (no raw < > \" # or space)");
    assert.equal(decodeURIComponent(payload), svg);
  }
}
assert.equal(seen.size, B.FAVICON_STEPS * 2);
assert.equal(B.faviconFrame(4, false), B.faviconFrame(0, false), "step wraps");
assert.deepEqual(B.FAVICON_HEIGHTS[B.FAVICON_BUSY_STATIC_STEP], [14, 14, 14], "static busy frame = all bars full height");
say("ok: faviconFrame x", seen.size, "(valid, unique, URL-encoded)");

// (c) app/icon.svg carries exactly the rects of brand.ts
const svg = readFileSync(join(root, "app", "icon.svg"), "utf8");
const rects = [...svg.matchAll(/<rect\s+x="([\d.]+)"\s+y="([\d.]+)"\s+width="([\d.]+)"\s+height="([\d.]+)"/g)]
  .map((m) => ({ x: +m[1], y: +m[2], width: +m[3], height: +m[4] }));
assert.deepEqual(rects, [B.BRAND_SQUARE, ...B.BRAND_BARS, B.BRAND_BASELINE], "icon.svg rects == brand.ts");
assert.match(svg, /@media \(prefers-color-scheme: dark\)/);
for (const c of [...Object.values(B.BRAND_COLORS.light), ...Object.values(B.BRAND_COLORS.dark)]) assert.ok(svg.includes(c), `icon.svg uses ${c}`);
say("ok: app/icon.svg matches brand.ts + dark-mode media query");

// (d) favicon.ico header (16/32/48, PNG entries) and apple-icon.png IHDR (180x180, opaque RGB)
const PNG_SIG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
const ico = readFileSync(join(root, "app", "favicon.ico"));
assert.deepEqual([ico.readUInt16LE(0), ico.readUInt16LE(2)], [0, 1], "ICO header");
const n = ico.readUInt16LE(4);
const sizes = [];
for (let i = 0; i < n; i++) {
  const e = 6 + i * 16;
  const w = ico[e] || 256;
  const len = ico.readUInt32LE(e + 8);
  const off = ico.readUInt32LE(e + 12);
  assert.ok(ico.subarray(off, off + 8).equals(PNG_SIG), `entry ${w} is PNG-compressed`);
  assert.equal(ico.readUInt32BE(off + 16), w, "PNG width matches entry");
  assert.ok(off + len <= ico.length);
  sizes.push(w);
}
assert.deepEqual(sizes, [16, 32, 48]);
const apple = readFileSync(join(root, "app", "apple-icon.png"));
assert.ok(apple.subarray(0, 8).equals(PNG_SIG));
assert.deepEqual([apple.readUInt32BE(16), apple.readUInt32BE(20)], [180, 180]);
assert.notEqual(apple[25], 6, "apple-icon has no alpha channel (colour type != RGBA)");
assert.equal(apple[25], 2, "apple-icon is RGB (opaque)");
say("ok: favicon.ico [16,32,48] PNG entries; apple-icon.png 180x180 RGB");
say("brand checks passed");
