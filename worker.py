import os
import sys
import json
import zipfile
import shutil
import asyncio
import time
import requests
from pyrogram import Client
import pyrogram.utils

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
REPO_NAME = os.getenv("REPO_NAME", "aasifhusenaasifkhan-beep/tamatar-laal-").strip()

# System tuning: Maximize CPU Multithreading for faster translation & rendering
os.environ["OMP_NUM_THREADS"] = "4"
os.environ["MKL_NUM_THREADS"] = "4"
os.environ["OPENBLAS_NUM_THREADS"] = "4"

print(f"=== DEEP-ANNELISE BATCH OCR ENGINE | USER: {USER_ID} ===")
if not BOT_TOKEN or not API_ID:
    print("❌ CRITICAL ERROR: GitHub Secrets parameters are missing!")
    sys.exit(1)

# Helper to send document directly via HTTP to avoid session conflicts
def send_subtitles_via_http(file_path, caption):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    with open(file_path, 'rb') as doc:
        requests.post(url, data={
            'chat_id': USER_ID,
            'caption': caption,
            'parse_mode': 'Markdown'
        }, files={'document': doc})

# Helper to update status message via HTTP
def update_status_via_http(message, percent):
    filled_length = int(percent // 10)
    bar = "█" * filled_length + "░" * (10 - filled_length)
    text = f"🎨 **Status Update:** {message}\\n`[{bar}] {percent}%`"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "message_id": MSG_ID,
        "text": text,
        "parse_mode": "Markdown"
    })

# =================================================================
# 🛡️ 1. SUBPROCESS RENDERING CONTROLLER (BATCH TRANS MODE)
# =================================================================
async def run_translator_ocr_only(input_dir, json_output_path, cwd_dir):
    # Runs OCR only on all images and saves blocks to single json file
    cli_cmd = ["python", "-m", "manga_translator", "-i", input_dir, "--translator", "none", "--save-text-file", json_output_path]
    proc = await asyncio.create_subprocess_exec(*cli_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=cwd_dir)
    await proc.communicate()
    return proc.returncode == 0

async def run_translator_render_only(input_dir, output_dir, json_input_path, cwd_dir):
    # Renders updated translation json onto images
    style_flags = ["--manga2eng"] if STYLE == "style2" else []
    cli_cmd = ["python", "-m", "manga_translator", "-i", input_dir, "--dest", output_dir, "--load-text", json_input_path] + style_flags
    proc = await asyncio.create_subprocess_exec(*cli_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=cwd_dir)
    await proc.communicate()
    return proc.returncode == 0


# =================================================================
# 📥 2. PRIMARY RUN WORKFLOW
# =================================================================
async def main():
    if not FILE_ID: 
        print("Empty File Matrix ID Found")
        return 
        
    tg_bot = Client("WorkerMaster", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, no_updates=True)
    await tg_bot.start()
    
    update_status_via_http("Target pull sequence initiated...", 10)

    dl_path = None
    for attempt in range(1, 6):
        try:
            dl_path = await tg_bot.download_media(FILE_ID)
            if dl_path and os.path.exists(dl_path) and os.path.getsize(dl_path) > 1024:
                break
            await asyncio.sleep(2)
        except Exception as e:
            update_status_via_http(f"⚠️ Network Dropout {attempt}/5: `{e}`", 15)
            await asyncio.sleep(3)

    if not dl_path or not os.path.exists(dl_path): 
        update_status_via_http("❌ **Critical Error:** Failed to download manga file from Telegram servers.", 15)
        return await tg_bot.stop()

    update_status_via_http("Extracting layouts & images...", 20)

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
        update_status_via_http(f"❌ **Extraction Failed:** `{e}`", 25)
        return await tg_bot.stop()

    pages = [os.path.join(r, f) for r, _, fs in os.walk(inp) for f in fs if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp'))]
    if not pages: 
        update_status_via_http("❌ **Formatting Error:** No supported images found in your document.", 25)
        return await tg_bot.stop()

    cwd_dir = "manga-image-translator" if os.path.exists("manga-image-translator") else None

    # ------------------ STEP 1: RUN BATCH OCR ------------------
    update_status_via_http(f"Running OCR Engine across all {len(pages)} pages...", 30)
    json_path = os.path.join(ws, "texts.json")
    
    ocr_ok = await run_translator_ocr_only(inp, json_path, cwd_dir)
    if not ocr_ok or not os.path.exists(json_path):
        update_status_via_http("❌ **OCR Stage Failed!** Engine crashed.", 35)
        return await tg_bot.stop()

    # ------------------ STEP 2: COMPILE USER-FRIENDLY TXT FILE ------------------
    update_status_via_http("Compiling all subtitle frames into single file...", 40)
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        out_rows = []
        out_rows.append(f"# MSG_ID: {MSG_ID}")
        out_rows.append("# ----------------------------------------")
        
        # Parse blocks file by file
        for filename, blocks in data.items():
            out_rows.append(f"\\n# FILE: {filename}")
            for idx, block in enumerate(blocks):
                original_text = block.get("text", "").replace("\n", " ")
                # Format: index (0-based block ID)
                out_rows.append(f"{idx:02d}")
                out_rows.append(f"{{{USER_ID}}}tutty{idx:02d}({original_text})\\n")
                
        export_txt_path = os.path.join(ws, f"FrameExtr_{USER_ID}.txt")
        with open(export_txt_path, "w", encoding="utf-8") as op_w:
            op_w.write("\\n".join(out_rows))
            
        dirctn = (
            "📝 **Frames Disassembled Fully (Batch)!**\\n\\n"
            "1️⃣ Open & Edit this mapped '.txt' file.\\n"
            "2️⃣ Translate text localized purely enclosed in `( )`.\\n"
            "3️⃣ DO NOT alter specific node tagging formatting loops.\\n"
            "4️⃣ Resend updated document back to bot inside Group!"
        )
        send_subtitles_via_http(export_txt_path, dirctn)
        update_status_via_http("Extracted! Text file delivered to user's PM. Waiting for translation...", 50)

    except Exception as e:
        update_status_via_http(f"❌ **Subtitle Parsing Failed:** `{e}`", 45)
        return await tg_bot.stop()

    # ------------------ STEP 3: POLLING ON GITHUB RAW FOR TRANSLATION ------------------
    fxd_capture = False
    translated_content = None
    
    # 12 minutes countdown timer loop (checks every 15 seconds)
    for elapsed in range(0, 720, 15):
        await asyncio.sleep(15) 
        
        # Polling: Try main branch, fallback to master if main gives 404 (Bypasses branch mismatch issues!)
        github_url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/trans_{USER_ID}.txt?t={time.time()}"
        res = requests.get(github_url)
        
        if res.status_code == 404:
            # Fallback to master
            github_url = f"https://raw.githubusercontent.com/{REPO_NAME}/master/trans_{USER_ID}.txt?t={time.time()}"
            res = requests.get(github_url)
            
        if res.status_code == 200:
            translated_content = res.text
            fxd_capture = True
            break

    if not fxd_capture or not translated_content:
        update_status_via_http("❌ **Timeout Error:** Manual translation period expired (12 Mins limit reached).", 55)
        return await tg_bot.stop()

    update_status_via_http("Translating Payload Received! Re-aligning layout blocks...", 70)
    
    # ------------------ STEP 4: UPDATE JSON WITH TRANSLATION ------------------
    try:
        current_file = None
        for line in translated_content.splitlines():
            line = line.strip()
            if line.startswith("# FILE:"):
                current_file = line.split("# FILE:")[1].strip()
            elif f"{{{USER_ID}}}tutty" in line:
                tag = f"{{{USER_ID}}}tutty"
                idx_part = line.split(tag)[1]
                idx_str = "".join([c for c in idx_part if c.isdigit()])
                idx = int(idx_str)
                
                text_part = idx_part[len(idx_str):].strip()
                if text_part.startswith("(") and text_part.endswith(")"):
                    translated_text = text_part[1:-1]
                else:
                    translated_text = text_part.strip("()")
                    
                # Update translations inside json memory
                if current_file in data and idx < len(data[current_file]):
                    data[current_file][idx]["translation"] = translated_text.strip()
                    
        # Write back updated json
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        update_status_via_http(f"❌ **Rebuilding JSON Failed:** `{e}`", 75)
        return await tg_bot.stop()

    # ------------------ STEP 5: RENDER PAGES ------------------
    update_status_via_http("Inpainting & Typesetting Hinglish layout onto frames...", 80)
    
    render_ok = await run_translator_render_only(inp, out, json_path, cwd_dir)
    if not render_ok:
        update_status_via_http("❌ **Render Engine Failed!** Crash occurred during drawing.", 85)
        return await tg_bot.stop()

    update_status_via_http("Rebuilding completed typesetting output...", 90)

    finals_l = sorted([os.path.join(r, f) for r, _, fs in os.walk(out) for f in fs if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))])
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

    endcap_caption = "✅ **Processing Completed! Your Translated Manga is Ready!**"
    
    try:
        # Deliver final output directly to user's PM
        await tg_bot.send_document(USER_ID, zipx_out, caption=endcap_caption)
        # Delete status message in Group chat to keep it clean
        await tg_bot.delete_messages(CHAT_ID, MSG_ID)
    except Exception as e:
        print("Failed to deliver final document:", e)

    # Post cleanup of local temporary variables
    shutil.rmtree(ws, ignore_errors=True)
    try: os.remove(dl_path)
    except: pass
    try:
        if ext in [".zip", ".cbz", ".pdf"]: os.remove(zipx_out)
    except: pass
    await tg_bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
