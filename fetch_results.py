#!/usr/bin/env python3
"""
第108回全国高等学校野球選手権大会 賽果擷取

從 スポーツナビ「バーチャル高校野球」的日程・結果頁抓取所有比賽列，
輸出 results.json / results.js 供前端 index.html 讀取。

用法：
    python3 fetch_results.py              # 寫入 ./results.json 與 ./results.js
    python3 fetch_results.py --dry-run    # 只印出，不寫檔
    python3 fetch_results.py -o out.json

設計要點：
  * 本程式「不」把比賽對應到我們的籤表編號，只照實吐出 Yahoo 表格的每一列。
    對應工作交給 index.html，因為前端本來就有逐輪解析勝隊的機制。
  * 原因是順延會同時破壞日期與 gid：實測 8/12 的東海大甲府－健大高崎
    順延後，原列保留為「試合中止」（gid 2021048506），另在 8/13 新增
    一列「試合終了」，gid 卻跳號為 2021048619。因此 (日期,時刻) 與 gid
    都不是穩定主鍵，唯一穩定的是「輪次 + 對戰組合」。
  * 比賽結束後 Yahoo 一律以「後攻 － 先攻」排列，teams[0] 即主隊。
    此順序在開打前不成立，由前端自行判斷是否採信。
  * 校名寫法不一致（智弁／智辯、ケ／ヶ）的正規化交給前端處理。
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

ROUNDS = {
    "1回戦": 1, "2回戦": 2, "3回戦": 3,
    "準々決勝": 4, "準決勝": 5, "決勝": 6,
}

RE_DAY = re.compile(r"第(\d{1,2})日目")
RE_DATE = re.compile(r"(\d{1,2})月(\d{1,2})日")
RE_TIME = re.compile(r"\b(\d{1,2}:\d{2})\b")
RE_SCORE = re.compile(r"(\d+)\s*[-－ー]\s*(\d+)")
RE_GAME = re.compile(r"/game/(\d+)/")
RE_ROUND = re.compile("|".join(map(re.escape, ROUNDS)))
RE_NO = re.compile(r"第(\d{1,2})試合")


def fetch_html(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def parse(html: str):
    soup = BeautifulSoup(html, "html.parser")
    games, warnings = [], []
    cur_day = cur_date = None

    for tr in soup.find_all("tr"):
        game_a = tr.find("a", href=RE_GAME)
        if not game_a:
            continue

        text = tr.get_text(" ", strip=True)

        # 日期只出現在該日第一列，其餘列留白，需往下沿用
        m = RE_DAY.search(text)
        if m:
            cur_day = "第%d日" % int(m.group(1))
        m = RE_DATE.search(text)
        if m:
            cur_date = "%d/%d" % (int(m.group(1)), int(m.group(2)))
        if not cur_date:
            continue

        mt = RE_TIME.search(text)
        if not mt:
            warnings.append("無開賽時刻：" + text[:60])
            continue

        mr = RE_ROUND.search(text)
        if not mr:
            warnings.append("無法判斷輪次：" + text[:60])
            continue

        status = game_a.get_text(strip=True)
        gid = RE_GAME.search(game_a["href"]).group(1)

        teams = [a.get_text(strip=True)
                 for a in tr.find_all("a", href=re.compile(r"/entryteams/\d+"))]
        teams = [t for t in teams if t][:2]

        # 比分只取狀態連結前的那一段，避免誤抓校名或日期裡的數字
        head = text.split(status)[0] if status in text else text
        ms = RE_SCORE.search(head)

        mn = RE_NO.search(text)

        row = {
            "gid": gid,
            "round": ROUNDS[mr.group(0)],
            "no": int(mn.group(1)) if mn else None,   # 該輪的第幾試合（Yahoo 的編號）
            "day": cur_day,
            "date": cur_date,
            "time": mt.group(1).lstrip("0") or "0:00",
            "status": status,
        }
        if len(teams) == 2:
            row["teams"] = teams          # [後攻, 先攻]
        if ms:
            row["score"] = [int(ms.group(1)), int(ms.group(2))]
        games.append(row)

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

    # 正常應為 48 列；順延會使列數增加（中止列與重賽列並存），故只設下限
    if len(games) < 40:
        print("[error] 只解析到 %d 列，版面可能改版了，中止寫檔" % len(games),
              file=sys.stderr)
        sys.exit(1)

    payload = {
        "updated": datetime.now(JST).strftime("%Y/%m/%d %H:%M JST"),
        "source": args.url,
        "games": games,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=1)

    done = sum(1 for g in games if "終了" in g["status"])
    cancelled = sum(1 for g in games if "中止" in g["status"])
    msg = "解析 %d 列，完賽 %d" % (len(games), done)
    if cancelled:
        msg += "，中止／順延 %d" % cancelled
    print(msg, file=sys.stderr)

    if args.dry_run:
        print(text)
        return

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print("寫入 " + args.out, file=sys.stderr)

    # 同內容再輸出一份 .js。<script> 標籤不受 CORS 限制，
    # 直接用瀏覽器開啟本機 index.html（file://）也讀得到。
    js_path = args.out.rsplit(".", 1)[0] + ".js"
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.KOSHIEN_RESULTS = " + text + ";\n")
    print("寫入 " + js_path, file=sys.stderr)


if __name__ == "__main__":
    main()
