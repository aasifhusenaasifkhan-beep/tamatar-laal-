import os
import sys
import zipfile
import shutil
import asyncio
import time
import base64
import requests
import re
from pyrogram import Client
import pyrogram.utils

# Maximize CPU multithreading/utilization optimally
os.environ["OMP_NUM_THREADS"] = "4"
os.environ["MKL_NUM_THREADS"] = "4"
os.environ["OPENBLAS_NUM_THREADS"] = "4"
os.environ["VECLIB_MAXIMUM_THREADS"] = "4"
os.environ["NUMEXPR_NUM_THREADS"] = "4"

# Set optimal thread count for PyTorch CPU operations
try:
    import torch
    torch.set_num_threads(4)
except ImportError:
    pass

# Pyrogram Utils Interception
pyrogram.utils.get_peer_type = lambda p: "channel" if str(p).startswith("-100") else "chat" if str(p).startswith("-") else "user"

FILE_ID = os.getenv("FILE_ID", "").strip()
CHAT_ID = int(os.getenv("CHAT_ID", "0"))
MSG_ID = int(os.getenv("MSG_ID", "0"))
USER_ID = int(os.getenv("USER_ID", "0"))
LANG = os.getenv("LANG", "english").strip().lower()
STYLE = os.getenv("STYLE", "style1").strip()
FNAME = os.getenv("FNAME", "translated_manga.zip").strip()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "").strip()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
REPO_NAME = os.getenv("REPO_NAME", "").strip()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()

print(f"=== DEEP-ANNELISE MANUAL ENGINE ON CPU | USER: {USER_ID} ===")
if not BOT_TOKEN or not API_ID:
    print("❌ CRITICAL ERROR: GitHub Secrets parameters are missing!")
    sys.exit(1)

# Robust helper to extract numeric page/block indices safely
def parse_block_idx(block_idx_str):
    digits = "".join([c for c in block_idx_str if c.isdigit()])
    return int(digits) if digits else 0

# Helper function to send files to PM cleanly using raw HTTP
def send_document_via_http(bot_token, chat_id, file_path, caption):
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    try:
        with open(file_path, "rb") as doc:
            r = requests.post(url, data={
                "chat_id": chat_id,
                "caption": caption,
                "parse_mode": "Markdown"
            }, files={"document": doc}, timeout=20)
            return r.status_code == 200
    except Exception as e:
        print("Failed to send document via HTTP:", e)
        return False

# =================================================================
# 📥 PRIMARY RUN WORKFLOW WITH ONE-GO PHASE TRANSITION
# =================================================================
async def main():
    if not FILE_ID: 
        print("Empty File Matrix ID Found")
        return 
        
    tg_bot = Client("WorkerMaster", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, no_updates=True)
    await tg_bot.start()
    
    last_update_time = 0
    
    # Safe Throttled Status Updater to strictly avoid Telegram Rate-limiting
    async def update_status_throttled(status_text):
        nonlocal last_update_time
        now = time.time()
        if now - last_update_time >= 10:
            last_update_time = now
            try:
                await tg_bot.edit_message_text(CHAT_ID, MSG_ID, status_text, parse_mode=pyrogram.enums.ParseMode.MARKDOWN)
            except Exception as e:
                print("Failed to update status:", e)

    await tg_bot.edit_message_text(CHAT_ID, MSG_ID, "⚡ **Status:** Initiating target pull sequence...")

    dl_path = None
    for attempt in range(1, 6):
        try:
            dl_path = await tg_bot.download_media(FILE_ID)
            if dl_path and os.path.exists(dl_path) and os.path.getsize(dl_path) > 1024:
                break
            await asyncio.sleep(2)
        except Exception as e:
            await tg_bot.edit_message_text(CHAT_ID, MSG_ID, f"⚠️ **Network Dropout {attempt}/5:** `{e}`")
            await asyncio.sleep(3)

    if not dl_path or not os.path.exists(dl_path): 
        await tg_bot.edit_message_text(CHAT_ID, MSG_ID, "❌ **Critical Error:** Failed to download manga file from Telegram servers.")
        return await tg_bot.stop()

    ext = os.path.splitext(FNAME)[1].lower() or ".zip"
    ws = os.path.abspath("manga_workspace")
    inp = os.path.join(ws, "input")
    out = os.path.join(ws, "output")
    
    if os.path.exists(ws): shutil.rmtree(ws)
    os.makedirs(inp, exist_ok=True)
    os.makedirs(out, exist_ok=True)

    try:
        if ext in [".zip", ".cbz"]:
            with zipfile.ZipFile(dl_path, 'r') as z: 
                z.extractall(inp)
        elif ext == ".pdf":
            import fitz
            pdf_layer = fitz.open(dl_path)
            for znc_n in range(len(pdf_layer)):
                pdf_pg = pdf_layer.load_page(znc_n)
                pdf_pg.get_pixmap(dpi=150).save(os.path.join(inp, f"page_{znc_n:03d}.png"))
            pdf_layer.close()
        else:
            shutil.copy(dl_path, inp)
    except Exception as e:
        await tg_bot.edit_message_text(CHAT_ID, MSG_ID, f"❌ **Extraction Failed:** `{e}`")
        return await tg_bot.stop()

    pages = sorted([os.path.join(r, f) for r, _, fs in os.walk(inp) for f in fs if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp'))])
    if not pages: 
        await tg_bot.edit_message_text(CHAT_ID, MSG_ID, "❌ **Formatting Error:** No supported images found in your document.")
        return await tg_bot.stop()

    # Clean up results folder for fresh run
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out, exist_ok=True)

    cwd_dir = "manga-image-translator" if os.path.exists("manga-image-translator") else None

    # Pre-clean any leftover translations inside all possible result locations to avoid conflicts
    possible_folders = [
        os.path.join(ws, "output"),
        os.path.join(ws, "input"),
        os.path.abspath("result"),
        os.path.abspath("results"),
        os.path.abspath(os.path.join("manga-image-translator", "result")),
        os.path.abspath(os.path.join("manga-image-translator", "results")),
    ]
    for folder in possible_folders:
        if os.path.exists(folder):
            for f in os.listdir(folder):
                if f.endswith("_translations.txt"):
                    try: os.remove(os.path.join(folder, f))
                    except: pass

    # =================================================================
    # 🔍 PHASE 1: OCR TEXT EXTRACTION FOR ALL PAGES (ONE GO)
    # =================================================================
    # Setting translator to 'original' forces the OCR engine to record actual speech texts
    cli_cmd_p1 = [
        "python", "-m", "manga_translator", 
        "-i", inp, 
        "--dest", out, 
        "--translator", "original",
        "--save-text"
    ]
    
    proc_p1 = await asyncio.create_subprocess_exec(
        *cli_cmd_p1, 
        stdout=asyncio.subprocess.PIPE, 
        stderr=asyncio.subprocess.STDOUT, 
        cwd=cwd_dir
    )
    
    current_ocr_page = 0
    while True:
        line = await proc_p1.stdout.readline()
        if not line:
            break
        decoded = line.decode('utf-8', errors='ignore').strip()
        print(decoded) # Output to Actions Console log
        
        if "Translating:" in decoded:
            current_ocr_page += 1
            percent = int((current_ocr_page / len(pages)) * 100)
            bar = "█" * (percent // 10) + "░" * (10 - (percent // 10))
            ocr_text = (
                f"🔍 **Phase 1/4: Analyzing Speech Frames (OCR)**\n"
                f"Extracting speech bubbles from all images in parallel...\n\n"
                f"**OCR Progress:** Image `{current_ocr_page}` of `{len(pages)}` parsed.\n"
                f"`[{bar}] {percent}%`"
            )
            await update_status_throttled(ocr_text)

    await proc_p1.wait()

    # =================================================================
    # 📝 SCAN ALL POSSIBLE PATHS AND COMPILE EXTRACTED SUBTITLES
    # =================================================================
    translation_files = []
    source_folder = None

    # Search dynamically through possible folders to catch where the engine outputs text files
    for folder in possible_folders:
        if os.path.exists(folder):
            files = [f for f in os.listdir(folder) if f.endswith("_translations.txt")]
            if files:
                translation_files = sorted(files)
                source_folder = folder
                break

    if not translation_files:
        await tg_bot.edit_message_text(CHAT_ID, MSG_ID, "❌ **Parsing Error:** No subtitles detected in any of the pages. Make sure the uploaded images contain readable text bubbles!")
        return await tg_bot.stop()

    print(f"✅ Text files successfully located in: {source_folder}")

    page_to_file = {i: fname for i, fname in enumerate(translation_files, 1)}
    master_lines = []
    
    for page_idx, fname in page_to_file.items():
        base_name = fname.replace("_translations.txt", "")
        master_lines.append(f"[Page {page_idx:02d}: {base_name}]")
        
        file_path = os.path.join(source_folder, fname)
        with open(file_path, "r", encoding="utf-8") as rf:
            content = rf.read()
            
        blocks = content.strip().split("\n\n")
        for block in blocks:
            lines = [l.strip() for l in block.strip().split("\n") if l.strip()]
            if not lines:
                continue
            
            block_idx = lines[0]
            
            # Robust filter to completely bypass any color properties lines
            text_lines = []
            for line in lines[1:]:
                lowered = line.lower()
                if "color:" in lowered or "fg, bg" in lowered:
                    continue
                text_lines.append(line)
                
            if text_lines:
                orig_text = text_lines[0]
                b_num = parse_block_idx(block_idx)
                # Formulate tag cleanly with single curly braces to avoid parsing offsets
                master_lines.append(f"{block_idx}")
                master_lines.append(f"{{{USER_ID}}}tutty_{page_idx}_{b_num}({orig_text})\n")
        master_lines.append("") # Extra spacer between pages

    master_txt_path = os.path.join(ws, f"FrameExtr_{USER_ID}.txt")
    with open(master_txt_path, "w", encoding="utf-8") as wf:
        wf.write("\n".join(master_lines))

    # Clean up old translation files from GitHub so we start fresh
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    delete_url = f"https://api.github.com/repos/{REPO_NAME}/contents/trans_{USER_ID}.txt"
    try:
        r = requests.get(delete_url, headers=headers, timeout=10)
        if r.status_code == 200:
            sha = r.json().get("sha")
            payload = {"message": "Clean old translation file", "sha": sha}
            requests.delete(delete_url, headers=headers, json=payload, timeout=10)
    except Exception as e:
        print("Pre-cleaning old translation file failed:", e)

    # Deliver compiled Master translation file straight to User PM
    caption_pm = (
        f"📝 **Manga Consolidated Translation File Ready!**\n\n"
        f"**Images Extracted:** `{len(pages)}` Pages\n"
        f"**Instructions:**\n"
        f"1️⃣ Translate the dialogues enclosed purely inside brackets `( )`.\n"
        f"2️⃣ DO NOT alter the `{{{USER_ID}}}tutty` tags.\n"
        f"3️⃣ Send this edited file back to the bot in PM.\n\n"
        f"⏳ **Timeout Alarm:** You have exactly **10 minutes** to translate and return this file!"
    )
    
    send_document_via_http(BOT_TOKEN, USER_ID, master_txt_path, caption_pm)

    # =================================================================
    # ⏳ PHASE 2: 10-MINUTE WAIT LOOP WITH REAL-TIME STATUS BAR
    # =================================================================
    timeout_duration = 600 # 10 minutes
    start_time = time.time()
    user_uploaded = False
    data_snapshot = None

    while time.time() - start_time < timeout_duration:
        elapsed = int(time.time() - start_time)
        remaining = timeout_duration - elapsed
        mins, secs = divmod(remaining, 60)
        
        percent = int((elapsed / timeout_duration) * 100)
        bar = "█" * (percent // 10) + "░" * (10 - (percent // 10))
        
        wait_text = (
            f"⏳ **Phase 2/4: Waiting for Manual Translation**\n"
            f"Master subtitle file sent to the user's PM.\n\n"
            f"**Time Remaining Countdown:** `{mins:02d}m {secs:02d}s`\n"
            f"`[{bar}] {percent}% Elapsed`"
        )
        await update_status_throttled(wait_text)
        
        # Poll GitHub REST API directly bypassing all caches
        api_url = f"https://api.github.com/repos/{REPO_NAME}/contents/trans_{USER_ID}.txt?t={int(time.time())}"
        try:
            res = requests.get(api_url, headers=headers, timeout=5)
            if res.status_code == 200:
                user_uploaded = True
                data_snapshot = res.json()
                break
        except Exception as e:
            print("Poller request error:", e)
            
        await asyncio.sleep(5)

    if not user_uploaded:
        # Timeout cleanup routine
        shutil.rmtree(ws, ignore_errors=True)
        try: os.remove(dl_path)
        except: pass
        cancel_text = (
            f"❌ **Task Cancelled (Timeout):**\n"
            f"User failed to return the translated file within the 10-minute limit.\n"
            f"All temporary image files and cache have been successfully deleted."
        )
        await tg_bot.edit_message_text(CHAT_ID, MSG_ID, cancel_text)
        return await tg_bot.stop()

    await tg_bot.edit_message_text(CHAT_ID, MSG_ID, "📥 **Syncing:** Rebuilding local translation models...")

    # =================================================================
    # ⚙️ PARSING BACK MASTER TRANSLATIONS & WRITING BACK TO LOCAL TXT
    # =================================================================
    content_b64 = data_snapshot.get("content", "")
    txt_val = base64.b64decode(content_b64).decode('utf-8', errors='ignore')
    
    # Matches single braces structure correctly without escape faults
    pattern = r"\{(\d+)\}tutty_(\d+)_(\d+)\((.*?)\)"
    translations_map = {}
    
    for line in txt_val.splitlines():
        line = line.strip()
        match = re.search(pattern, line)
        if match:
            _, p_idx, b_idx, text = match.groups()
            translations_map[(int(p_idx), int(b_idx))] = text.strip()

    # Recreate the individual files in source_folder with newly mapped translations
    for page_idx, fname in page_to_file.items():
        file_path = os.path.join(source_folder, fname)
        with open(file_path, "r", encoding="utf-8") as rf:
            content = rf.read()
            
        blocks = content.strip().split("\n\n")
        new_blocks = []
        for block in blocks:
            lines = [l.strip() for l in block.strip().split("\n") if l.strip()]
            if not lines:
                continue
                
            block_idx = lines[0]
            
            # Filter and preserve metadata lines (colors, styles, etc.)
            meta_lines = []
            text_lines = []
            for line in lines[1:]:
                lowered = line.lower()
                if "color:" in lowered or "fg, bg" in lowered:
                    meta_lines.append(line)
                else:
                    text_lines.append(line)
                    
            if text_lines:
                orig_text = text_lines[0]
                
                p_idx = page_idx
                b_idx = parse_block_idx(block_idx)
                key = (p_idx, b_idx)
                
                translation_text = translations_map.get(key, orig_text)
                
                # Assemble block structures preserving custom styles
                reconstructed_lines = [block_idx] + meta_lines + [orig_text, translation_text]
                new_blocks.append("\n".join(reconstructed_lines))
                
        with open(file_path, "w", encoding="utf-8") as wf:
            wf.write("\n\n".join(new_blocks) + "\n\n")

    # Delete translation file from GitHub Actions repo to clean up workspace
    try:
        sha = data_snapshot.get("sha")
        payload = {"message": "Clean processed translation file", "sha": sha}
        requests.delete(delete_url, headers=headers, json=payload, timeout=10)
    except Exception as e:
        print("Cleanup deletion on GitHub failed:", e)

    # =================================================================
    # 🎨 PHASE 3: RENDERING & ADJUSTING COMPLETED TYPESETTING (ONE GO)
    # =================================================================
    # Set translator back to 'original' to force the loader to typeset the text
    # Mask dilation and kernel sizes are set to stable defaults to prevent border bleeding/smudging
    cli_cmd_p2 = [
        "python", "-m", "manga_translator", 
        "-i", inp, 
        "--dest", out, 
        "--translator", "original",
        "--load-text",
        "--manga2eng",
        "--overwrite"
    ]

    proc_p2 = await asyncio.create_subprocess_exec(
        *cli_cmd_p2, 
        stdout=asyncio.subprocess.PIPE, 
        stderr=asyncio.subprocess.STDOUT, 
        cwd=cwd_dir
    )

    current_render_page = 0
    while True:
        line = await proc_p2.stdout.readline()
        if not line:
            break
        decoded = line.decode('utf-8', errors='ignore').strip()
        print(decoded)
        
        if "Translating:" in decoded:
            current_render_page += 1
            percent = int((current_render_page / len(pages)) * 100)
            bar = "█" * (percent // 10) + "░" * (10 - (percent // 10))
            render_text = (
                f"🎨 **Phase 3/4: Rendering Beautiful Typesetting**\n"
                f"Adjusting and wrapping text correctly within bubbles...\n\n"
                f"**Render Progress:** Image `{current_render_page}` of `{len(pages)}` formatted.\n"
                f"`[{bar}] {percent}%`"
            )
            await update_status_throttled(render_text)

    await proc_p2.wait()

    # =================================================================
    # 📦 PHASE 4: COMPILING & DELIVERING THE OUTPUT
    # =================================================================
    await tg_bot.edit_message_text(CHAT_ID, MSG_ID, "📦 **Phase 4/4: Packaging output...**\n`[██████████] 100%`")

    finals_l = sorted([os.path.join(r, f) for r, _, fs in os.walk(out) for f in fs if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')) and not f.endswith("_rearranged.png")])
    zipx_out = "translated_" + FNAME if ext in [".zip", ".cbz", ".pdf"] else finals_l[0]
    
    if ext in [".zip", ".cbz"]:
        with zipfile.ZipFile(zipx_out, 'w', zipfile.ZIP_DEFLATED) as z_enc:
            for fd_c in finals_l: 
                z_enc.write(fd_c, os.path.relpath(fd_c, out))
    elif ext == ".pdf":
        from PIL import Image
        px_i_set = [Image.open(p_z_file).convert('RGB') for p_z_file in finals_l]
        if px_i_set: 
            px_i_set[0].save(zipx_out, save_all=True, append_images=px_i_set[1:])

    endcap_caption = "✅ **Processing Repacked Successfully!**\n⚡ Control Type: Native One-Go Manual Typesetting Core v2"
    
    try:
        await tg_bot.send_document(CHAT_ID, zipx_out, caption=endcap_caption)
        await tg_bot.delete_messages(CHAT_ID, MSG_ID)
    except Exception as e:
        print("Failed to deliver final document:", e)

    # Post execution cleanup
    shutil.rmtree(ws, ignore_errors=True)
    try: os.remove(dl_path)
    except: pass
    try:
        if ext in [".zip", ".cbz", ".pdf"]: os.remove(zipx_out)
    except: pass
    await tg_bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
