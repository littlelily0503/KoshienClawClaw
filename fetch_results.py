#!/usr/bin/env python3
"""
第108回全国高等学校野球選手権大会 賽果擷取

從 スポーツナビ「バーチャル高校野球」的日程・結果頁抓取全 48 場的比分，
輸出 results.json 供前端 index.html 讀取。

用法：
    python3 fetch_results.py              # 寫入 ./results.json
    python3 fetch_results.py --dry-run    # 只印出，不寫檔
    python3 fetch_results.py -o out.json

設計要點：
  * 以 (日期, 開賽時刻) 當主鍵對應到我們的 match id。全大會 48 場沒有
    重複的 (日期, 時刻) 組合，比用校名比對安全得多。
  * 比賽結束後 Yahoo 會把勝隊排在前面，與先攻後攻無關，所以 teams 欄位
    照原樣輸出，由前端依自己的籤表順序對齊翻轉。
  * 校名寫法不一致（智弁／智辯、ケ／ヶ），正規化交給前端處理。
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta

import requests
from bs4 import BeautifulSoup

# Windows 主控台預設 cp950，日文校名會噴 UnicodeEncodeError
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

URL = "https://baseball.yahoo.co.jp/hsb_summer/schedule/competition"
UA = "Mozilla/5.0 (compatible; koshien-bracket/1.0; personal use)"
JST = timezone(timedelta(hours=9))

# (match id, 日期, 開賽時刻) —— 順序即出賽順序
ORDER = [
    ("r1-1", "8/5", "17:30"),
    ("r1-2", "8/6", "16:00"), ("r1-3", "8/6", "18:30"),
    ("r1-4", "8/7", "8:00"), ("r1-5", "8/7", "13:30"),
    ("r1-6", "8/7", "16:00"), ("r1-7", "8/7", "18:30"),
    ("r1-8", "8/8", "8:00"), ("r1-9", "8/8", "13:30"),
    ("r1-10", "8/8", "16:00"), ("r1-11", "8/8", "18:30"),
    ("r1-12", "8/9", "8:00"), ("r1-13", "8/9", "13:30"),
    ("r1-14", "8/9", "16:00"), ("r1-15", "8/9", "18:30"),
    ("r1-16", "8/10", "8:00"), ("r1-17", "8/10", "13:30"),
    ("r2-1", "8/10", "16:00"), ("r2-2", "8/10", "18:30"),
    ("r2-3", "8/11", "8:00"), ("r2-4", "8/11", "13:30"),
    ("r2-5", "8/11", "16:00"), ("r2-6", "8/11", "18:30"),
    ("r2-7", "8/12", "8:00"), ("r2-8", "8/12", "13:30"),
    ("r2-9", "8/12", "16:00"), ("r2-10", "8/12", "18:30"),
    ("r2-11", "8/13", "13:30"), ("r2-12", "8/13", "16:00"), ("r2-13", "8/13", "18:30"),
    ("r2-14", "8/14", "13:30"), ("r2-15", "8/14", "16:00"), ("r2-16", "8/14", "18:30"),
    ("r3-1", "8/15", "8:00"), ("r3-2", "8/15", "10:30"),
    ("r3-3", "8/15", "13:00"), ("r3-4", "8/15", "15:30"),
    ("r3-5", "8/16", "8:00"), ("r3-6", "8/16", "10:30"),
    ("r3-7", "8/16", "13:00"), ("r3-8", "8/16", "15:30"),
    ("qf1", "8/18", "8:00"), ("qf2", "8/18", "10:30"),
    ("qf3", "8/18", "13:00"), ("qf4", "8/18", "15:30"),
    ("sf1", "8/20", "8:00"), ("sf2", "8/20", "10:30"),
    ("f", "8/22", "10:00"),
]
KEY2ID = {(d, t): mid for mid, d, t in ORDER}

RE_DATE = re.compile(r"(\d{1,2})月(\d{1,2})日")
RE_TIME = re.compile(r"\b(\d{1,2}:\d{2})\b")
RE_SCORE = re.compile(r"(\d+)\s*[-－ー]\s*(\d+)")
RE_GAME = re.compile(r"/game/(\d+)/")


def fetch_html(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def parse(html: str):
    soup = BeautifulSoup(html, "html.parser")
    games, warnings = {}, []
    cur_date = None

    for tr in soup.find_all("tr"):
        game_a = tr.find("a", href=RE_GAME)
        if not game_a:
            continue

        row_text = tr.get_text(" ", strip=True)

        m = RE_DATE.search(row_text)
        if m:
            cur_date = f"{int(m.group(1))}/{int(m.group(2))}"
        if not cur_date:
            continue

        mt = RE_TIME.search(row_text)
        if not mt:
            continue
        time_s = mt.group(1).lstrip("0") or "0:00"

        key = (cur_date, time_s)
        mid = KEY2ID.get(key)
        if not mid:
            warnings.append(f"對不到賽程表的列：{key} / {row_text[:60]}")
            continue

        gid = RE_GAME.search(game_a["href"]).group(1)
        status = game_a.get_text(strip=True)

        teams = [a.get_text(strip=True)
                 for a in tr.find_all("a", href=re.compile(r"/entryteams/\d+"))]
        teams = [t for t in teams if t][:2]

        # 比分只取狀態連結前的那一段，避免誤抓校名裡的數字
        head = row_text.split(status)[0] if status in row_text else row_text
        ms = RE_SCORE.search(head)
        score = [int(ms.group(1)), int(ms.group(2))] if ms else None

        entry = {"gid": gid, "status": status}
        if len(teams) == 2:
            entry["teams"] = teams
        if score:
            entry["score"] = score
        games[mid] = entry

    return games, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="results.json")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--url", default=URL)
    args = ap.parse_args()

    games, warnings = parse(fetch_html(args.url))

    for w in warnings:
        print("[warn]", w, file=sys.stderr)

    if len(games) < 40:
        print(f"[error] 只解析到 {len(games)} 場，版面可能改版了，中止寫檔",
              file=sys.stderr)
        sys.exit(1)

    # 依出賽順序輸出，前端才能依序套用晉級
    ordered = {mid: games[mid] for mid, _, _ in ORDER if mid in games}
    payload = {
        "updated": datetime.now(JST).strftime("%Y/%m/%d %H:%M JST"),
        "source": args.url,
        "games": ordered,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=1)

    done = sum(1 for g in ordered.values() if g.get("status") == "試合終了")
    print(f"解析 {len(ordered)} 場，其中 {done} 場已完賽", file=sys.stderr)

    if args.dry_run:
        print(text)
        return

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"寫入 {args.out}", file=sys.stderr)

    # 同內容再輸出一份 .js。<script> 標籤不受 CORS 限制，
    # 直接用瀏覽器開啟本機 index.html（file://）也讀得到。
    js_path = args.out.rsplit(".", 1)[0] + ".js"
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.KOSHIEN_RESULTS = " + text + ";\n")
    print(f"寫入 {js_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
