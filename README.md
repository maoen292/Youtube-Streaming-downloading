# YouTube 錄影

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![macOS Optimized](https://img.shields.io/badge/OS-macOS_Optimized-lightgrey.svg)]()

這是一個基於 Python (`customtkinter` + `yt-dlp`) 開發的圖形化介面工具，專門用來長時間監控 YouTube 頻道並自動錄製直播或待機台。支援讀取 Chrome Cookie 以驗證會員權限，並特別針對 macOS 進行了優化，非常適合需要大量存檔喜愛 V-Tuber 直播的使用者。

### 核心功能
* **自動頻道監控**：自動輪詢偵測指定 YouTube 頻道是否在直播或處於待機狀態。
* **無損自動錄影**：偵測到直播後自動開始下載，並使用 FFmpeg 完美合併音訊與影像。
* **會員內容支援**：支援讀取 Google Chrome 設定檔 (Profile) 的 Cookie，輕鬆驗證並下載會員限定內容。
* **macOS 特別優化**：內建處理 macOS 環境變數，並支援一鍵從 GitHub 自動更新 `yt-dlp_macos` 核心。
* **現代化介面與日誌**：採用舒適的深色模式 (Dark Mode)，提供完整的下載進度、速度監測與系統活動日誌。

### 如何使用
1. 安裝必要的套件：`yt-dlp`, `customtkinter`
   *(同時請確保系統已安裝 [FFmpeg](https://ffmpeg.org/download.html)，macOS 使用者可透過 `brew install ffmpeg` 安裝)*
2. 執行主程式 `yt_recorder_v9.py`
3. 在設定區塊中，選擇您的 Chrome 設定檔路徑，並點擊「測試存取權限」確保 Cookie 可正常讀取。
4. 輸入要監控的「頻道直播網址」並設定「儲存位置」與「檢查間隔」。
5. 點擊「開始監控」，系統即可在背景自動輪詢，遇到直播即自動錄影存檔。

### 聲明與授權條款 (License)
* 本專案採用 **[MIT License](https://opensource.org/licenses/MIT)** 開源授權。歡迎自由分享、修改與使用本代碼，但請保留原作者署名。
* 本專案僅供**個人學習與程式開發測試**使用。請尊重創作者版權並遵守 YouTube 服務條款。
* 本專案的大部分程式碼是在 AI（Gemini）的輔助下編寫與優化完成的。

---

### 私心推薦
既然你都滑到這裡了，除了寫代碼，我也想藉這個小空間推廣一下我最喜歡的 V-Tuber！
如果你覺得這個工具幫你省下了寶貴的時間，希望你可以去看看她的頻道，**記得訂閱她：白星優米**！
[白星優米 YouTube 頻道連結](https://youtube.com/@umitw46?si=YAS3N6vEymUu1UDW)
