#!/usr/bin/env python3
"""Merge the sizes.csv of each configuration into one Markdown report.

Usage: report.py BASELINE OUTDIR CSV...
  BASELINE  configuration name the others are compared with
  OUTDIR    gets report.md and sizes-wide.csv
flash and ram come from build.sh (flash image size, static RAM).
"""
import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path

baseline, outdir, files = sys.argv[1], Path(sys.argv[2]), sys.argv[3:]
outdir.mkdir(parents=True, exist_ok=True)

rows = defaultdict(dict)  # example -> config -> row
configs = []
for f in files:
    for r in csv.DictReader(open(f)):
        r.setdefault("seconds", "")
        if r["config"] not in configs:
            configs.append(r["config"])
        if r["status"] == "ok":
            r.update(flash=int(r["flash"]), ram=int(r["ram"]))
        rows[r["example"]][r["config"]] = r
if baseline in configs:
    configs.remove(baseline)
    configs.insert(0, baseline)
others = configs[1:]


def ok(ex, c):
    r = rows[ex].get(c)
    return r is not None and r["status"] == "ok"


def pct(a, b):
    return f"{(a - b) / b * 100:+.2f}%" if b else "-"


out = []
p = out.append
p("# ch32fun ツールチェーン別サイズ比較\n")
p(f"基準: `{baseline}`。Flash = 書き込むイメージ(.bin)のサイズ、RAM = 静的に使う RAM(.data + .bss + CH5xx の highcode)。単位はバイト。\n")

p("## ビルド結果\n")
p("| 構成 | 成功 | 失敗 |")
p("|---|---:|---:|")
for c in configs:
    n_ok = sum(ok(e, c) for e in rows)
    n_fail = sum(1 for e in rows if c in rows[e] and not ok(e, c))
    p(f"| `{c}` | {n_ok} | {n_fail} |")
p("")
for c in configs:
    failed = sorted(e for e in rows if c in rows[e] and not ok(e, c))
    if failed:
        p(f"<details><summary><code>{c}</code> で失敗したサンプル({len(failed)})</summary>\n")
        p("\n".join(f"- `{e}`" for e in failed))
        p("\n</details>\n")

common = sorted(e for e in rows if all(ok(e, c) for c in configs))

p(f"## ビルド時間(全構成で成功した {len(common)} サンプル)\n")
p("サンプルごとの make の実時間(コンパイルとリンク)。ツールチェーンの準備は含まない。ランナーごとの性能差があるので目安。\n")
p("| 構成 | 合計 [s] | 基準比 | 中央値 [s] | 最大 [s] | 全体の実時間 |")
p("|---|---:|---:|---:|---:|---|")
walls = {}
for f in files:
    t = Path(f).with_name("time.txt")
    if t.exists():
        name = next(csv.DictReader(open(f)), {}).get("config")
        walls[name] = t.read_text().strip()
base_sec = sum(float(rows[e][baseline].get("seconds") or 0) for e in common)
for c in configs:
    secs = [float(rows[e][c].get("seconds") or 0) for e in common]
    tot = sum(secs)
    p(f"| `{c}` | {tot:.1f} | {pct(tot, base_sec)} | {statistics.median(secs) if secs else 0:.2f} | {max(secs, default=0):.2f} | {walls.get(c, '-')} |")
p("")
p(f"## 合計(全構成で成功した {len(common)} サンプル)\n")
p("| 構成 | Flash 合計 | 基準比 | RAM 合計 | 基準比 | Flash 比の中央値 | 小さくなった | 大きくなった | 同じ |")
p("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
base_flash = sum(rows[e][baseline]["flash"] for e in common)
base_ram = sum(rows[e][baseline]["ram"] for e in common)
for c in configs:
    fl = sum(rows[e][c]["flash"] for e in common)
    ram = sum(rows[e][c]["ram"] for e in common)
    ratios = [rows[e][c]["flash"] / rows[e][baseline]["flash"] for e in common]
    med = f"{(statistics.median(ratios) - 1) * 100:+.2f}%" if ratios else "-"
    smaller = sum(rows[e][c]["flash"] < rows[e][baseline]["flash"] for e in common)
    larger = sum(rows[e][c]["flash"] > rows[e][baseline]["flash"] for e in common)
    p(f"| `{c}` | {fl} | {pct(fl, base_flash)} | {ram} | {pct(ram, base_ram)} | {med} | {smaller} | {larger} | {len(common) - smaller - larger} |")
p("")

p("## 系列(ディレクトリ)別の Flash 合計\n")
groups = sorted({e.split("/")[0] for e in common})
p("| ディレクトリ | 数 | " + " | ".join(f"`{c}`" for c in configs) + " |")
p("|---|---:|" + "---:|" * len(configs))
for g in groups:
    ex = [e for e in common if e.split("/")[0] == g]
    b = sum(rows[e][baseline]["flash"] for e in ex)
    cells = [str(b)] + [f"{sum(rows[e][c]['flash'] for e in ex)} ({pct(sum(rows[e][c]['flash'] for e in ex), b)})" for c in others]
    p(f"| `{g}` | {len(ex)} | " + " | ".join(cells) + " |")
p("")

for c in others:
    diffs = sorted(((rows[e][c]["flash"] - rows[e][baseline]["flash"], e) for e in common))
    p(f"## `{c}` と基準の差が大きいサンプル(Flash)\n")
    p("| サンプル | 基準 | " + c + " | 差 |")
    p("|---|---:|---:|---:|")
    picked = diffs[:10] + [x for x in diffs[-10:] if x not in diffs[:10]]
    for d, e in picked:
        b = rows[e][baseline]["flash"]
        p(f"| `{e}` | {b} | {rows[e][c]['flash']} | {d:+d} ({pct(rows[e][c]['flash'], b)}) |")
    p("")

(outdir / "report.md").write_text("\n".join(out) + "\n")

with open(outdir / "sizes-wide.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["example"] + [f"{c}:{k}" for c in configs for k in ("status", "text", "data", "bss", "flash", "ram")])
    for e in sorted(rows):
        line = [e]
        for c in configs:
            r = rows[e].get(c, {})
            line += [r.get("status", "")] + [str(r.get(k, "")) for k in ("text", "data", "bss", "flash", "ram")]
        w.writerow(line)
