# PDF-compression-tools
這是一款基於 Python 開發的高效能 PDF 處理工具，專門解決 超大型文件 (如 600MB+) 的壓縮與轉換痛點。具備智能採樣預判與多核心並行運算，讓 PDF 處理不再卡頓。

✨ 核心特色
⚡ 多核心並行加速：利用 Multiprocessing 技術，處理速度提升 3-8 倍，充分榨乾 CPU 效能。
🃏 洗牌式深度採樣：自動抽取文件 20% 頁面 交叉分析，精準鎖定最佳壓縮參數（DPI & Quality）。
🛡️ 容量硬性限制：具備 「二次重壓機制」。如果你指定 200MB，輸出的檔案就絕對不會是 201MB。
📸 全格式支援：除了 PDF 壓縮，還支援 JPG/PNG 合併，甚至是 iPhone 預設的 HEIC 格式。

⚙️ 全能工具選單：
壓縮 PDF：自動目標大小優化。
圖片轉 PDF：支援批量資料夾匯入。
合併 PDF：快速整合多份文件。
拆分 PDF：一頁一檔極速拆解。
安全加密：AES-256 強力保護。
數位浮水印：自定義文字標註。
PDF 轉圖片：高解析度 PNG 產出。
頁面刪除：支援範圍（如 1-5）與特定頁碼。

🛠️ 安裝教學
1. 複製專案
   
git clone https://github.com

cd PDF-compression-tools

2. 安裝依賴套件
pip install pymupdf tqdm pillow pillow-heif

🚀 使用說明
直接執行 Python 腳本：
bash
python pdf_turbo_v10.5.py
請謹慎使用程式碼。

操作小撇步：
路徑輸入：在 Windows 上，您可以直接將檔案或資料夾用滑鼠拖入終端機視窗，程式會自動清理路徑中的引號。
目標大小：壓縮時輸入 0 即可切換為「無限制大小（最高品質模式）」。
📦 打包為 .exe (Windows 適用)
如果您需要製作成獨立執行檔，請使用以下指令確保 HEIC 解碼器 與 多核心引擎 被正確封裝：
pyinstaller --onefile --collect-all pillow_heif --hidden-import multiprocessing --icon="icon.ico" --name "PDF終極工具箱_V10.5" pdf_turbo_v10.5.py

⚠️ 注意事項
有損壓縮：本工具壓縮後會將文字層轉為圖片（Rasterization），以換取極限的空間縮減，因此壓縮後的檔案無法選取文字。
安全性：若文件受密碼保護，請先使用「功能 5」解除限制。
📄 授權條款
本專案採用 MIT License 授權。
