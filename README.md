# P710BT-Auto — Brother 標籤列印

同一套標籤工具有兩個入口：瀏覽器版和桌面程式。兩種都能讀取資料、畫出標籤，再用 USB 列印 Brother PT 系列（P710BT、P750W、E550W）。

## 兩種用法

| | 瀏覽器版 | 桌面程式 |
|---|---|---|
| 怎麼開 | 用 Chrome 或 Edge 打開 [網頁版](https://wing9897.github.io/P710BT-Auto_webUI/)，可安裝到電腦 | 從 [Releases](../../releases) 下載 exe、AppImage 或 dmg |
| 資料 | 只留在你的瀏覽器，不會上傳 | 只留在這部電腦 |
| 列印 | 瀏覽器直接經 USB 送給打印機 | 程式直接經 USB 送給打印機 |

瀏覽器版放在 GitHub Pages，網址是 [https://wing9897.github.io/P710BT-Auto_webUI/](https://wing9897.github.io/P710BT-Auto_webUI/)。它在你自己的瀏覽器裡使用。安裝到電腦後，沒有網絡也能設計標籤。請打開這個網頁來用，不要把網頁另存後雙擊檔案，否則連不到打印機。請用 Chrome 或 Edge。

Windows 不論瀏覽器版或桌面程式，都要先用 [Zadig](https://zadig.akeo.ie/) 把打印機驅動換成 WinUSB。只需做一次。

桌面程式打開就能用，不必另外開瀏覽器。

![](GUI.png)

## 瀏覽器版畫面

用 Chrome 或 Edge 打開網頁版。載入資料後可以改每一欄的類型，並立刻看到標籤。

載入範例後的資料、設定與標籤預覽：

![](docs/web-sample.png)

把條碼改成 QR Code、只留這一欄之後的預覽和列印：

![](docs/web-qr.png)

## 下載與安裝

已經打包好的桌面程式在 [Releases](../../releases)，下載後就能用。

| 系統 | 處理器 | 形式 | 檔名 |
|------|--------|------|------|
| Windows | 64 位元 | 免安裝壓縮檔 | `P710BT-Auto-windows-x64.zip` |
| Windows | 64 位元 | 安裝程式 | `P710BT-Auto-windows-x64-setup.exe` |
| Linux | 64 位元 | AppImage（免安裝） | `P710BT-Auto-linux-x64.AppImage` |
| Linux | 64 位元 | DEB 安裝包 | `P710BT-Auto-linux-x64.deb` |
| Linux | ARM 64 位元 | AppImage（免安裝） | `P710BT-Auto-linux-arm64.AppImage` |
| Linux | ARM 64 位元 | DEB 安裝包 | `P710BT-Auto-linux-arm64.deb` |
| macOS | Apple 晶片（M1、M2、M3、M4）；Intel 電腦可用 Rosetta 2 | DMG | `P710BT-Auto-macos-arm64.dmg` |

### 怎麼安裝

- **Windows 免安裝**：解開 `.zip`，執行 `main_desktop.exe`
- **Windows 安裝程式**：執行 `setup.exe`，會自動建立桌面捷徑
- **Linux AppImage**：在終端機執行 `chmod +x *.AppImage`，然後直接開啟，不必安裝
- **Linux DEB**：在終端機執行 `sudo dpkg -i *.deb`，再用 `p710bt-auto` 開啟
- **macOS**：打開 `.dmg`，雙擊 `main_desktop.app`

> **只有 Windows 需要**：安裝 [Zadig](https://zadig.akeo.ie/)，把打印機驅動設成 WinUSB（只需做一次）。

## 設計理念

這個工具用來一次印很多張標籤。做法是用資料產生標籤：

```
匯入資料 → 設計版型 → 即時預覽 → 一鍵批量列印
```

每一行資料對應一張標籤。程式會把欄位套進版型，不必一張一張手動輸入。

## 工作流程

### 1. 匯入資料

可以直接匯入檔案，也可以貼上文字：

| 格式 | 說明 |
|------|------|
| CSV | 可以自訂分隔符號 |
| JSON | 陣列格式 |
| Excel | `.xlsx` |
| 貼上文字 | 依你設的分隔符號拆開 |

資料表先顯示前 50 筆，也可以刪掉其中一行。

### 2. 設計標籤版型

- **膠帶寬度**：3.5 / 6 / 9 / 12 / 18 / 24 mm（接上打印機後會自動偵測）
- **欄位類型**：純文字、QR Code、Code128、Code39、EAN13
- **自動排版**：字體會配合標籤寬度縮放、太長會自動換行、文字置中

### 3. 即時預覽

- 用實際資料畫出標籤縮圖
- 可以前後翻頁（先看前 10 張）
- 可以放大到全螢幕

### 4. 列印

- 用 USB 直接連到打印機
- 自動看出已裝上的膠帶寬度和餘量
- 一次列印全部資料，並顯示進度及結果
- **連續列印**：標籤之間不切開，比較省膠帶

## 應用場景

- 倉庫貨品標籤（一次印貨號和條碼）
- 活動名牌（用 CSV 名單一次印完）
- 零售價格標籤（用 Excel 產品表）
- 資產管理（一次做出很多 QR Code）
