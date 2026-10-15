#!/usr/bin/env python3
"""小转盘：给 AI 的自由时间用。没想好做什么的时候，转一下。

    python3 wheel.py            转一次
    python3 wheel.py --list     看每一格现在被抽到的机会（不抽、不记）
    python3 wheel.py --dry      抽一次，但不记下来
    python3 wheel.py --history  看最近抽过什么

格子、抽中时说的话、每一轮最多转几次，全在 wheel.json 里改。
只用 Python 自带的东西，不用装任何包。
"""
import argparse
import json
import random
import re
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
NEVER = 14          # 从没抽到过 / 超过 14 天没抽到，都按 14 天算
TODAY_FACTOR = 0.4  # 今天已经抽到过的，机会少一点


def load_config(path):
    conf = json.loads(path.read_text(encoding="utf-8"))
    conf.setdefault("每轮最多", 3)
    conf.setdefault("一轮多长（小时）", 3)
    return conf


def load_history(path):
    out = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
                out.append((datetime.fromisoformat(d["ts"]), d["name"]))
            except (ValueError, KeyError):
                continue
    return out


def last_seen(history, extra_path):
    """每一格最后一次去是什么时候：转盘自己的记录，加上（可选）你家自己的记录。"""
    last = {}
    for t, name in history:
        if name not in last or t > last[name]:
            last[name] = t
    if extra_path and extra_path.exists():
        # 可选：别的程序写的 {"格子名": "2026-10-15T13:17:00"}，比如从你家 AI 的日志里算出来的
        for name, ts in json.loads(extra_path.read_text(encoding="utf-8")).items():
            try:
                t = datetime.fromisoformat(ts).replace(tzinfo=None)
            except ValueError:
                continue
            if name not in last or t > last[name]:
                last[name] = t
    return last


def weights(items, last, now):
    out = []
    for it in items:
        w = float(it.get("w", 1))
        t = last.get(it["name"])
        if t is None:
            f, why = 1 + NEVER / 7, "还没轮到过"
        elif t.date() == now.date():
            f, why = TODAY_FACTOR, "今天轮到过"
        else:
            days = (now - t).total_seconds() / 86400
            f, why = 1 + min(days, NEVER) / 7, f"{days:.0f} 天没轮到"
        out.append((it, w * f, why))
    return out


def pick_topic(path):
    """从题目清单里抽一题。
    一题从「1.」或「- 」开头的那一行开始；下面空了格的几行算同一题。
    编号后面带 ✓ 的，表示写过了，不再抽。"""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    items, cur = [], None
    for line in lines:
        m = re.match(r"^(?:[-*+]|\d+[.、)])\s+(\S.*)$", line)
        if m:
            cur = [m.group(1).rstrip()]
            items.append(cur)
        elif cur is not None and line.startswith((" ", "\t")) and line.strip():
            cur.append(line.strip())
        elif line.strip():
            cur = None          # 标题、引用、顶格的普通段落：不算题目
    items = ["\n".join(x) for x in items if not x[0].startswith(("✓", "[x]"))]
    return random.choice(items) if items else None


def main():
    ap = argparse.ArgumentParser(description="小转盘")
    ap.add_argument("--config", default=str(HERE / "wheel.json"))
    ap.add_argument("--list", action="store_true", help="看每一格现在的机会")
    ap.add_argument("--dry", action="store_true", help="抽一次，但不记")
    ap.add_argument("--history", action="store_true", help="看最近抽过什么")
    a = ap.parse_args()

    cfg_path = Path(a.config).resolve()
    conf = load_config(cfg_path)
    base = cfg_path.parent
    hist_path = base / conf.get("记录文件", "history.jsonl")
    extra = conf.get("外部记录")
    history = load_history(hist_path)
    now = datetime.now()
    ws = weights(conf["items"], last_seen(history, base / extra if extra else None), now)

    if a.history:
        for t, name in history[-20:]:
            print(t.strftime("%m-%d %H:%M"), name)
        return
    if a.list:
        total = sum(w for _, w, _ in ws)
        for it, w, why in sorted(ws, key=lambda x: -x[1]):
            print(f"{it.get('icon', '·')} {it['name']:<10} {w / total:5.1%}  {why}")
        return

    cap, hours = int(conf["每轮最多"]), float(conf["一轮多长（小时）"])
    done = [n for t, n in history if t >= now - timedelta(hours=hours)]
    if len(done) >= cap and not a.dry:
        print(f"🎡 这一轮已经转了 {len(done)} 次啦：{'、'.join(done)}。\n先去做吧，下一轮再转。")
        return

    it = random.choices([x[0] for x in ws], weights=[x[1] for x in ws])[0]
    msg = f"🎡 转到了：{it.get('icon', '')} {it['name']}".rstrip()
    if it.get("say"):
        msg += "\n" + it["say"]
    if it.get("topics"):
        t = pick_topic(base / it["topics"])
        msg += f"\n题目：{t}\n（不想写这题，就写你自己想写的。）" if t else "\n清单里还没有题目，写你自己想写的。"
    left = cap - len(done) - 1
    msg += f"\n（这一轮还能再转 {left} 次）" if left > 0 else "\n（这是这一轮最后一次啦）"
    print(msg)

    if not a.dry:
        with hist_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": now.isoformat(timespec="seconds"), "name": it["name"]}, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
