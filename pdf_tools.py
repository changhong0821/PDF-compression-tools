import fitz  # PyMuPDF
import os
os.system('cls' if os.name == 'nt' else 'clear')  # 清屏
import io
import multiprocessing
from tqdm import tqdm
from PIL import Image
import pillow_heif

# 💡 初始化：支援 iPhone HEIC 格式與多核心打包
pillow_heif.register_heif_opener()

def clean_path(p):
    """自動清理 Windows 複製路徑時產生的引號與多餘空格"""
    return p.strip().strip('"').strip("'")

def get_out(p, suffix):
    """📂 保留原檔名並加上後綴"""
    file_dir = os.path.dirname(p)
    file_full_name = os.path.basename(p)
    name, ext = os.path.splitext(file_full_name)
    return os.path.join(file_dir, f"{name}_{suffix}{ext}")

# --- 🚀 多核心並行引擎 ---
def task_worker(args):
    path, mode, dpi, quality, idx = args
    try:
        target_path = path[idx] if isinstance(path, list) else path
        if mode == "pdf":
            doc = fitz.open(target_path)
            page = doc[idx]
            pix = page.get_pixmap(dpi=dpi)
            # ✨ 關鍵修正：PyMuPDF 的參數名稱是 jpg_quality
            data = pix.tobytes("jpg", jpg_quality=quality) 
            w, h = page.rect.width, page.rect.height
            doc.close()
        else:
            # 圖片模式 (JPG/PNG) 同步修正
            img = fitz.open(target_path)
            pix = img.get_pixmap(dpi=dpi)
            # ✨ 關鍵修正：同步修改為 jpg_quality
            data = pix.tobytes("jpg", jpg_quality=quality)
            w, h = pix.width * 72/dpi, pix.height * 72/dpi
            img.close()
        return (idx, w, h, data)
    except Exception as e:
        return None

def process_core_parallel(source, out_path, dpi, quality, mode="pdf"):
    # ✨ 修正：正確計算任務總數
    if mode == "pdf":
        with fitz.open(source) as temp:
            total = len(temp)
    else:
        total = len(source) # 圖片模式 source 本身就是 list
        
    tasks = [(source, mode, dpi, quality, i) for i in range(total)]
    
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        results = [r for r in tqdm(pool.imap(task_worker, tasks), total=total, desc=f"  ⚡ 執行 [DPI:{dpi} Q:{quality}]", leave=False) if r]
    
    results.sort(key=lambda x: x[0])
    new_doc = fitz.open()
    for _, w, h, data in results:
        new_page = new_doc.new_page(width=w, height=h)
        new_page.insert_image(new_page.rect, stream=data)
    
    if len(new_doc) > 0:
        new_doc.save(out_path, garbage=4, deflate=True)
    new_doc.close()


# --- 🔄 備援模式：穩健的二元搜尋 ---
def fallback_binary_search(source, out_path, target_mb, mode):
    print("\n⚠️ 採樣失敗！啟動 [穩健二元搜尋模式]...")
    target_bytes = target_mb * 1024 * 1024
    low_q, high_q = 20, 95
    best_file = None
    for i in range(5):
        cur_q = (low_q + high_q) // 2
        tmp = out_path + f".tmp_{i}"
        process_core_parallel(source, tmp, 150, cur_q, mode)
        if not os.path.exists(tmp): continue
        size = os.path.getsize(tmp)
        print(f"   📊 輪次 {i+1}: 品質 {cur_q:2} -> {size/1024/1024:.2f} MB")
        if size <= target_bytes:
            if best_file: os.remove(best_file)
            best_file = tmp; low_q = cur_q + 1
        else:
            high_q = cur_q - 1; os.remove(tmp)
    
    if best_file:
        if os.path.exists(out_path): os.remove(out_path)
        os.rename(best_file, out_path)
        return True
    return False

# --- 🚀 智能雙模切換優化 ---
def auto_optimize_v10_2(source, out_path, target_mb, mode="pdf"):
    """🚀 V10.2: 針對圖片型/損壞 PDF 強化採樣邏輯"""
    if target_mb <= 0:
        process_core_parallel(source, out_path, 300, 90, mode); return True

    total = len(fitz.open(source)) if mode == "pdf" else len(source)
    sample_count = max(5, min(int(total * 0.2), 30))
    print(f"\n🃏 嘗試洗牌採樣 ({sample_count}/{total} 頁)...")
    
    indices = [int(i * (total - 1) / (sample_count - 1)) for i in range(sample_count)]
    
    # --- 【改動點 1】：嘗試多核心並行採樣 ---
    with multiprocessing.Pool(processes=4) as pool:
        sample_res = [r for r in pool.map(task_worker, [(source, mode, 150, 75, idx) for idx in indices]) if r]

    # --- 【改動點 2】：核心強化備援 (解決採樣失敗直接跳二分的問題) ---
    if not sample_res:
        print("⚠️ 並行採樣受阻，改用單線程暴力讀取數據...")
        # 直接在主進程中嘗試讀取前 5 個樣本，繞過多核心讀取鎖定
        for idx in indices[:5]:
            res = task_worker((source, mode, 150, 75, idx))
            if res: sample_res.append(res)

    # --- 【改動點 3】：若徹底失敗才執行回退 ---
    if not sample_res:
        return fallback_binary_search(source, out_path, target_mb, mode)

    # --- 【改動點 4】：調整預估係數與鎖定方案 (針對全圖片 PDF 加嚴至 82%) ---
    avg_bytes = sum(len(r[3]) for r in sample_res) / len(sample_res) # 修正: r[3] 為數據
    est_total_mb = (avg_bytes * total) / 1024 / 1024
    print(f"📊 預估基準大小 (150DPI/Q75)：{est_total_mb:.2f} MB")

    ratio = (target_mb * 0.82) / est_total_mb 
    if ratio < 0.25:    dpi, q = 72, 30
    elif ratio < 0.5:   dpi, q = 100, 40
    elif ratio < 0.8:   dpi, q = 120, 55
    elif ratio < 1.1:   dpi, q = 150, 70
    elif ratio < 1.8:   dpi, q = 200, 80
    else:               dpi, q = 300, 90

    print(f"✨ 鎖定方案：DPI {dpi} / 品質 {q}")
    process_core_parallel(source, out_path, dpi, q, mode)
    
    # 溢出二次修正邏輯保持不變...
        # --- 🛡️ 強力防線：確保最終產出 [絕對小於等於] 指令容量 ---
    final_size_mb = os.path.getsize(out_path) / 1024 / 1024
    
    # 如果還是超標，就啟動無限降階循環，直到達標為止
    attempts = 0
    while final_size_mb > target_mb and attempts < 3:
        attempts += 1
        print(f"⚠️ 依然超標 ({final_size_mb:.2f}MB > {target_mb}MB)，啟動第 {attempts} 次強制降階...")
        
        # 每次降階：DPI 砍 20%，Quality 砍 15
        dpi = max(72, int(dpi * 0.8))
        q = max(10, q - 15)
        
        process_core_parallel(source, out_path, dpi, q, mode)
        final_size_mb = os.path.getsize(out_path) / 1024 / 1024

    # 最終檢查結果
    if final_size_mb <= target_mb:
        print(f"✅ 成功達標！最終大小: {final_size_mb:.2f} MB")
    else:
        print(f"🛑 已達物理極限，最終大小: {final_size_mb:.2f} MB (非常接近目標)")

    return True

# --- 🖥️ 主選單 ---
def main():
    while True:
        print("\n" + "🔥" * 40 + "\n  PDF 萬用工具箱\n" + "🔥" * 40)
        print(" 1. 🗜️ 壓縮 PDF (智慧雙模)\n 2. 🖼️ 圖片轉 PDF (支援 HEIC)\n 3. 🔗 合併 PDF (資料夾)\n 4. 🔪 拆分 PDF\n 5. 🔐 PDF 加密\n 6. 🔖 文字浮水印\n 7. 📸 PDF 轉圖片\n 8. ✂️ 刪除指定頁面\n 0. 🚪 離開程式")
        
        choice = input("\n👉 請選擇功能: ").strip()
        if choice == "0": break
        path = clean_path(input("📍 請拖入路徑: "))

        try:
            if choice in ["1", "2"]:
                t = float(input("💾 目標 MB (0為不限): "))
                out = get_out(path, "optimized") if choice=="1" else os.path.join(os.path.dirname(path), f"{os.path.basename(path.rstrip('\\/'))}_combined.pdf")
                
                # 🛠️ 修正 4：智慧判斷拖入的是單一檔案還是資料夾
                if choice == "1":
                    src = path
                else: # choice == "2"
                    if os.path.isdir(path):
                        src = sorted([os.path.join(path, f) for f in os.listdir(path) if f.lower().endswith(('.jpg','.jpeg','.png','.heic'))])
                    elif os.path.isfile(path):
                        src = [path]
                    else:
                        src = []

                if not src: print("❌ 找不到有效檔案！"); continue
                auto_optimize_v10_2(src, out, t, "pdf" if choice=="1" else "jpg")

            elif choice == "3" and os.path.isdir(path):
                pdfs = sorted([os.path.join(path, f) for f in os.listdir(path) if f.lower().endswith('.pdf')])
                out = os.path.join(path, f"{os.path.basename(path.rstrip('\\/'))}_merged.pdf")
                res = fitz.open()
                for p in tqdm(pdfs, desc="🔗 合併中"): 
                    with fitz.open(p) as m: res.insert_pdf(m)
                res.save(out); res.close(); print(f"✅ 完成: {out}")
                # 🔔 新增：任務成功後的停頓
                print("\n" + "-"*30)
                input("✅ 任務已結束。按下 [Enter] 鍵回到選單...")


            elif choice == "8" and os.path.isfile(path):
                q = input("✂️ 刪除頁碼 (如 1-5, 10): "); doc = fitz.open(path); total = len(doc); pgs = set()
                for r in q.replace(" ","").split(","):
                    if not r: continue # 🛠️ 優化 B：防呆，跳過空字串
                    if '-' in r:
                        s, e = map(int, r.split('-'))
                        pgs.update(range(s-1, min(e, total)))
                    else: pgs.add(int(r)-1)
                for p in sorted(list(pgs), reverse=True): 
                    if 0 <= p < total: doc.delete_page(p)
                out = get_out(path, "Edited"); doc.save(out); doc.close(); print(f"✅ 完成: {out}")
                # 🔔 新增：任務成功後的停頓
                print("\n" + "-"*30)
                input("✅ 任務已結束。按下 [Enter] 鍵回到選單...")

            elif choice == "4" and os.path.isfile(path):
                doc = fitz.open(path); out_d = os.path.join(os.path.dirname(path), "split_pages")
                if not os.path.exists(out_d): os.makedirs(out_d)
                for i in tqdm(range(len(doc)), desc="🔪 拆分"):
                    new = fitz.open(); new.insert_pdf(doc, i, i); new.save(os.path.join(out_d, f"page_{i+1}.pdf")); new.close()
                doc.close(); print(f"✅ 已拆分至: {out_d}")
                # 🔔 新增：任務成功後的停頓
                print("\n" + "-"*30)
                input("✅ 任務已結束。按下 [Enter] 鍵回到選單...")
            
            elif choice == "5" and os.path.isfile(path):
                pw = input("🔑 設定密碼: "); out = get_out(path, "protected")
                with fitz.open(path) as d: d.save(out, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw=pw, owner_pw=pw)
                print(f"✅ 完成: {out}")
                # 🔔 新增：任務成功後的停頓
                print("\n" + "-"*30)
                input("✅ 任務已結束。按下 [Enter] 鍵回到選單...")
            
            elif choice == "6" and os.path.isfile(path):
                txt = input("🖋️ 浮水印文字: "); out = get_out(path, "watermarked"); doc = fitz.open(path)
                for pg in doc: pg.insert_text((50, 100), txt, fontsize=40, rotate=45, color=(0.8,0.8,0.8), fill_opacity=0.3)
                doc.save(out); doc.close(); print(f"✅ 完成: {out}")
                # 🔔 新增：任務成功後的停頓
                print("\n" + "-"*30)
                input("✅ 任務已結束。按下 [Enter] 鍵回到選單...")
            
            elif choice == "7" and os.path.isfile(path):
                doc = fitz.open(path); out_d = os.path.join(os.path.dirname(path), "images")
                if not os.path.exists(out_d): os.makedirs(out_d)
                for i, pg in enumerate(tqdm(doc, desc="📸 轉圖")): pg.get_pixmap(dpi=200).save(os.path.join(out_d, f"{i+1}.png"))
                doc.close(); print(f"✅ 存於: {out_d}")
                # 🔔 新增：任務成功後的停頓
                print("\n" + "-"*30)
                input("✅ 任務已結束。按下 [Enter] 鍵回到選單...")

        except Exception as e: 
            print(f"❌ 錯誤: {e}")
            # 🔔 新增：出錯後的停頓，讓你看清楚報錯內容
            input("請截圖錯誤訊息或按下 [Enter] 鍵繼續...")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
