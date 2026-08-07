# 2026 夏之甲子園 賽程籤表

第108回全国高等学校野球選手権大会 的籤表、賽程與每日賽果。

## 檔案

| 檔案 | 說明 |
|---|---|
| `index.html` | 網頁本體。籤表結構、賽程、樣式全部在這裡，可單獨開啟 |
| `fetch_results.py` | 從 スポーツナビ 抓賽果，產生 `results.json` |
| `results.json` | 賽果資料（給 http server 用） |
| `results.js` | 同內容，包成 `window.KOSHIEN_RESULTS`。直接雙擊 index.html 也讀得到 |
| `.github/workflows/update-results.yml` | 台灣時間 07:00–21:00 每 10 分鐘跑一次 |

## 建置順序

> Windows 使用者請把以下指令的 `python3` 一律改成 `python`。
> Windows 的 `python3.exe` 是 Microsoft Store 的殼層，執行後不做任何事就結束。
> 若 `python --version` 會跳出 Store，去「設定 → 應用程式 → 應用程式執行別名」
> 把 `python.exe` / `python3.exe` 兩個開關關掉。

### 1. 本機驗證抓取

```bash
pip install requests beautifulsoup4
python3 fetch_results.py --dry-run
```

確認 stderr 印出「解析 48 場，其中 N 場已完賽」。

### 2. 本機驗證前端

```bash
python3 fetch_results.py     # 產生 results.json 與 results.js
```

**直接用瀏覽器開啟 `index.html` 即可**，不需要架 server。
`results.js` 是用 `<script>` 標籤載入的，不受 `file://` 的 CORS 限制。

若要模擬正式環境（讓網頁走 `results.json`）再架 server：

```bash
python3 -m http.server 8000 --bind 127.0.0.1
```

正常啟動會印出 `Serving HTTP on 127.0.0.1 port 8000 ...` 並**停住不回提示字元**。
若指令秒回、或瀏覽器顯示 `ERR_CONNECTION_REFUSED`，代表 server 根本沒起來
（最常見原因就是上面那個 `python3` 別名問題）。

檢查重點：已完賽的隊伍有沒有正確晉級到下一輪。若 console 出現
`校名對不上`，代表 Yahoo 的校名寫法與籤表不同，去 `index.html` 的
`NORM()` 補一條替換規則。

### 3. 推上 GitHub Pages

```bash
git init && git add . && git commit -m "init"
git branch -M main
git remote add origin git@github.com:<帳號>/koshien2026.git
git push -u origin main
```

Settings → Pages → Source 選 `main` / `(root)`。

### 4. 開自動更新

Actions 頁面 → 「更新賽果」→ Run workflow 手動跑一次，確認會 commit。
之後每天台灣時間 07:00–21:00 每 10 分鐘自動執行。

## 兩個更新頻率，不要搞混

```
Yahoo ──(A) 10 分鐘 ──> GitHub Actions ──> results.json ──(B) 5 分鐘 ──> 瀏覽器
```

**(A) 爬蟲頻率**：GitHub 去 Yahoo 抓資料、更新 `results.json`。
改 `.github/workflows/update-results.yml` 的 `cron`。cron 用 UTC，台灣時間 = UTC + 8。

| 需求 | cron |
|---|---|
| 台灣 07:00–21:00 / 10 分鐘（目前，涵蓋全部比賽） | `*/10 23,0-13 * 8 *` |
| 台灣 09:00–23:00 / 10 分鐘 | `*/10 1-15 * 8 *` |
| 每小時一次 | `0 23,0-13 * 8 *` |

`23,0-13` 拆成兩段寫，是因為台灣 07:00 對應到 UTC 前一天的 23:00。

日本時間 = 台灣 + 1 小時。當天第1試合台灣 07:00 開打、09:15 前後結束；
第4試合台灣 17:30 開打、19:45 前後結束。

**(B) 網頁重讀頻率**：開著的分頁去自己的網站重讀 `results.json`，
**完全不碰 Yahoo**，只是省下手動 F5。改 `index.html` 的 `REFRESH_MS`。
僅在分頁可見、且當天有比賽時才運作。

B 刻意設得比 A 短：B 不知道 A 何時更新，設短一點才能保證 A 一更新、
最多 5 分鐘內就看得到。兩者不衝突。

`fetch_results.py` 裡沒有任何頻率設定，它只負責「抓一次」；
裡面的 `timeout=20` 是單次 HTTP 請求逾時，與頻率無關。

## 手動更新

爬蟲掛掉時，直接改 `results.json` 就行（`results.js` 是同一份內容包一層賦值）：

```json
"r1-1": { "teams": ["札幌日大", "仙台育英"], "score": [1, 3], "status": "試合終了" }
```

`teams` 的順序不重要，前端會依校名對齊——實測 Yahoo 的排列時而勝隊在前
（仙台育英 3-1 札幌日大）、時而敗隊在前（聖隷 0-1 佐野日大），不能靠位置判斷。

載入優先序是 `results.js` → `results.json` → `index.html` 內建。兩個檔案
都刪掉則退回內建籤表，頁面仍可正常顯示。

用 PowerShell 檢視檔案內容要加編碼參數，否則日文校名會顯示成亂碼
（只是顯示問題，檔案本身沒壞）：

```powershell
Get-Content results.json -Encoding UTF8 -TotalCount 15
```

## 八強抽籤

8/16 三回戰全部結束後，抽出八強配對。改 `index.html` 的 `DRAW`：

```js
const DRAW = {
  qf1:{a:"r3-1", b:"r3-5"}, qf2:{a:"r3-2", b:"r3-7"},
  qf3:{a:"r3-3", b:"r3-6"}, qf4:{a:"r3-4", b:"r3-8"},
  sf1:null, sf2:null
};
```

8/18 八強打完再抽四強，填 `sf1` / `sf2`（值是 `qf` 的 id）。填完後八強盒子
會自動重新排位，讓配對的兩場落在同一側，連接線不會交叉。

## 注意

- `gid`（スポーツナビ 場次編號）是連號的，`index.html` 由 `2021048480`
  依出賽順序自動推算，不需維護。若朝日改制導致連號中斷，在 `DATA`
  個別填 `gid:"..."` 覆蓋。
- 抓取對象是他人網站。目前每天約 85 次、每次一頁，整屆大會約 1,500 次請求。
  以單一頁面計算仍屬極小的量，但不建議把 (A) 再往下壓，也不要平行化。
  GitHub Pages 每小時的建置次數有軟性上限（約 10 次），10 分鐘一次是 6 次／小時，
  剛好在界內；壓到 5 分鐘就是 12 次／小時，Pages 反而來不及重建。
  這個限制只適用於 (A)，(B) 不受影響。
- **先攻後攻**：スポーツナビ 一律「後攻 － 先攻」排列，前端據此反轉成國際慣例
  （客隊在上、主隊在下）。此資訊在比賽開打後才出現，賽前維持籤表順序。
- **進行中的比分不會晉級**：`decided()` 要求 `status` 含「試合終了」，
  所以 5 回領先 1-0 只會顯示比分與紅色 LIVE 標記，不會把隊伍送進下一輪。
- 雨天順延會讓日期與時刻改變，`ORDER` 的 (日期, 時刻) 主鍵會對不上，
  屆時 stderr 會印出 `對不到賽程表的列`，手動修 `ORDER` 即可。
