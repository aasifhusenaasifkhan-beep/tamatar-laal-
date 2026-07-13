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
os.environ["VECLIB_MAXIMUM_THREADS"] = "4"
os.environ["NUMEXPR_NUM_THREADS"] = "4"

# Set optimal thread count for PyTorch CPU operations
try:
    import torch
    torch.set_num_threads(4)
except ImportError:
    pass


# =========================================================================================
# 🧬 DYNAMIC OVERWRITE FOR 'chatgpt.py' - COMPLETELY BYPASSES OPENAI/API VALIDATIONS
# ==========================================================================================

ROUTINE_SCRIPT_BYPASSER = """
import os
import asyncio
import time
import json
import base64
import requests
from .common import CommonTranslator

class HumanInterventionTranslator(CommonTranslator):
    supported_src_languages = ['auto', 'ENG', 'JPN', 'CHS', 'CHT', 'KOR', 'FRA', 'DEU', 'RUS', 'SPA', 'ITA', 'POR', 'TRK', 'VIE', 'NLD', 'PLK', 'UKR', 'ARA', 'THA', 'IND', 'FIL']
    supported_target_languages = ['auto', 'ENG', 'JPN', 'CHS', 'CHT', 'KOR', 'FRA', 'DEU', 'RUS', 'SPA', 'ITA', 'POR', 'TRK', 'VIE', 'NLD', 'PLK', 'UKR', 'ARA', 'THA', 'IND', 'FIL']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sys_token = os.environ.get("ENV_BOT_TOKEN")
        self.git_token = os.environ.get("ENV_GITHUB_TOKEN")
        self.cst_uid = int(os.environ.get("ENV_USER_ID", "0"))
        self.chat_id = int(os.environ.get("ENV_CHAT_ID", "0"))
        self.msg_id = int(os.environ.get("ENV_MSG_ID", "0"))
        self.repo_name = os.environ.get("ENV_REPO_NAME", "")
        self.frame_counter = 0
        self.translations_map = {}
        
        # Load translation map dynamically in render mode
        mode = os.environ.get("ENV_TRANSLATE_MODE", "EXTRACT")
        if mode == "RENDER":
            json_path = "../manga_workspace/translations.json"
            if os.path.exists(json_path):
                try:
                    with open(json_path, "r", encoding="utf-8") as rf:
                        data = json.load(rf)
                        for k, v in data.items():
                            p_idx, b_idx = k.split("_", 1)
                            self.translations_map[(int(p_idx), b_idx.strip())] = v
                except Exception as e:
                    print("Error loading translation JSON in bypasser:", e)

    def supports_languages(self, from_lang, to_lang, fatal=False):
        return True

    async def _translate(self, from_lang, to_lang, queries, *args, **kwargs):
        return await self.do_custom_workflow(queries)

    async def translate(self, from_lang, to_lang, queries, *args, **kwargs):
        return await self.do_custom_workflow(queries)

    async def do_custom_workflow(self, queries):
        if not queries: 
            return queries
        
        self.frame_counter += 1
        mode = os.environ.get("ENV_TRANSLATE_MODE", "EXTRACT")
        
        if mode == "EXTRACT":
            # Save raw dialogues for compiling all pages later
            os.makedirs("../manga_workspace", exist_ok=True)
            page_file = f"../manga_workspace/page_{self.frame_counter}_queries.txt"
            with open(page_file, "w", encoding="utf-8") as wf:
                wf.write("\\n".join(queries))
            return queries
            
        elif mode == "RENDER":
            # Fetch translations on the fly
            translated_layer_dump = []
            for idx, qrs in enumerate(queries, 1):
                key = (self.frame_counter, str(idx))
                translated_text = self.translations_map.get(key, qrs)
                translated_layer_dump.append(translated_text)
            return translated_layer_dump

# Mapping all possible classes
class ChatGPTTranslator(HumanInterventionTranslator): pass
class ChatGPT2StageTranslator(HumanInterventionTranslator): pass
class GPT3Translator(HumanInterventionTranslator): pass
class GPT35TurboTranslator(HumanInterventionTranslator): pass
class GPT4Translator(HumanInterventionTranslator): pass
"""


# =================================================================
# 🛡️ 2. SUBPROCESS RENDERING CONTROLLER
# =================================================================
async def run_translator_with_fallback(input_dir, output_dir, ws, bot_client):
    cwd_dir = "manga-image-translator" if os.path.exists("manga-image-translator") else None

    # Forwarding parameters safely inside the sub-process container
    os.environ["ENV_USER_ID"] = str(USER_ID)
    os.environ["ENV_API_HASH"] = str(API_HASH)
    os.environ["ENV_API_ID"] = str(API_ID)
    os.environ["ENV_BOT_TOKEN"] = str(BOT_TOKEN)
    os.environ["ENV_CHAT_ID"] = str(CHAT_ID)
    os.environ["ENV_MSG_ID"] = str(MSG_ID)
    os.environ["ENV_REPO_NAME"] = str(REPO_NAME)
    os.environ["ENV_GITHUB_TOKEN"] = os.getenv("GITHUB_TOKEN", "").strip()

    # Overwrite 'chatgpt.py' because library uses it internally
    if cwd_dir:
        core_lib_node = os.path.join(cwd_dir, "manga_translator", "translators", "chatgpt.py")
        if os.path.exists(os.path.dirname(core_lib_node)):
            with open(core_lib_node, "w", encoding="utf-8") as injectn:
                injectn.write(ROUTINE_SCRIPT_BYPASSER)
            print("💥 CRITICAL: chatgpt.py bypass written correctly!")

    # Added '--manga2eng' to prevent speech overflow in all styles
    style_flags = ["--manga2eng"]
    
    # -----------------------------------------------------------------
    # PHASE 1: OCR & DIALOGUE EXTRACTION (FAST RUN)
    # -----------------------------------------------------------------
    os.environ["ENV_TRANSLATE_MODE"] = "EXTRACT"
    cli_cmd = ["python", "-m", "manga_translator", "-i", input_dir, "--dest", output_dir, "--translator", "gpt3", "-l", "FRA"] + style_flags
    
    await bot_client.edit_message_text(CHAT_ID, MSG_ID, "🔍 **Phase 1/3: Extracting speech bubbles (OCR)...\n`[████░░░░░░] 40%`**")
    
    proc = await asyncio.create_subprocess_exec(*cli_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=cwd_dir)
    
    pages = sorted([os.path.join(r, f) for r, _, fs in os.walk(input_dir) for f in fs if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp'))])
    
    current_page = 0
    start_time = time.time()
    
    while True:
        line = await proc.stdout.readline()
        if not line: break
        decoded = line.decode('utf-8', errors='ignore').strip()
        print(decoded) # Capture system logs
        
        if "Translating:" in decoded:
            current_page += 1
            elapsed = time.time() - start_time
            speed = current_page / elapsed if elapsed > 0 else 0
            percent = int((current_page / len(pages)) * 100)
            bar = "█" * (percent // 10) + "░" * (10 - (percent // 10))
            
            speed_str = f"{speed:.2f} pages/sec"
            if speed > 0:
                speed_str += f" ({1/speed:.1f} sec/page)"
                
            status_text = (
                f"🔍 **Phase 1/3: Extracting speech frames (OCR)**\n"
                f"Analyzing page structures to map dialogue bubbles...\n\n"
                f"**Extraction Progress:** Page `{current_page}` of `{len(pages)}` finished.\n"
                f"**Speed:** `{speed_str}` | **Percentage:** `{percent}%`\n"
                f"`[{bar}]`"
            )
            try:
                await bot_client.edit_message_text(CHAT_ID, MSG_ID, status_text)
            except:
                pass
                
    await proc.wait()

    # Compile the consolidated Master subtitle file
    master_lines = []
    for i in range(1, 1000):
        page_file = os.path.join(ws, f"page_{i}_queries.txt")
        if os.path.exists(page_file):
            master_lines.append(f"[Page {i:02d}]")
            with open(page_file, "r", encoding="utf-8") as rf:
                queries = rf.read().splitlines()
            for idx, q in enumerate(queries, 1):
                # Clean Tag formatting with single braces to strictly avoid parsing offsets
                master_lines.append(f"{idx}")
                master_lines.append(f"{{{USER_ID}}}tutty_{i}_{idx} ==> {q}\n")
            master_lines.append("")
        else:
            # Safe boundary check to stop parsing when frame files end
            if i > 1 and not any(os.path.exists(os.path.join(ws, f"page_{k}_queries.txt")) for k in range(i, i+10)):
                break
                
    master_txt_path = os.path.join(ws, f"FrameExtr_{USER_ID}.txt")
    with open(master_txt_path, "w", encoding="utf-8") as wf:
        wf.write("\n".join(master_lines))

    # Deliver compiled Master translation file straight to User PM
    caption_pm = (
        f"📝 **Manga Consolidated Translation File Ready!**\n\n"
        f"**Images Extracted:** `{len(pages)}` Pages\n"
        f"**Instructions:**\n"
        f"1️⃣ Translate the dialogues written after the `==>` arrow.\n"
        f"2️⃣ DO NOT alter the `{{{USER_ID}}}tutty` tags or the `==>` arrow.\n"
        f"3️⃣ Send this edited file back to the bot in PM.\n\n"
        f"⏳ **Timeout Alarm:** You have exactly **10 minutes** to translate and return this file!"
    )
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    try:
        with open(master_txt_path, 'rb') as doc:
            requests.post(url, data={'chat_id': USER_ID, 'caption': caption_pm, 'parse_mode': 'Markdown'}, files={'document': doc}, timeout=15)
    except Exception as e:
        print("Failed to deliver document via HTTP:", e)

    # -----------------------------------------------------------------
    # PHASE 2: WAIT LOOP WITH PROGRESS COUNTDOWN (10 MINUTES)
    # -----------------------------------------------------------------
    timeout_duration = 600
    start_time = time.time()
    user_uploaded = False
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {os.getenv('GITHUB_TOKEN', '').strip()}"
    }
    
    while time.time() - start_time < timeout_duration:
        elapsed = int(time.time() - start_time)
        remaining = timeout_duration - elapsed
        mins, secs = divmod(remaining, 60)
        
        percent = int((elapsed / timeout_duration) * 100)
        filled_length = int(percent // 10)
        bar = "█" * filled_length + "░" * (10 - filled_length)
        
        wait_text = (
            f"⏳ **Phase 2/3: Waiting for translation file...**\n"
            f"Consolidated file delivered to user PM.\n\n"
            f"**Time Remaining Countdown:** `{mins:02d}m {secs:02d}s`\n"
            f"`[{bar}] {percent}% elapsed`"
        )
        try:
            await bot_client.edit_message_text(CHAT_ID, MSG_ID, wait_text)
        except:
            pass
            
        # Poll GitHub REST API directly bypassing all caches
        api_url = f"https://api.github.com/repos/{REPO_NAME}/contents/trans_{USER_ID}.txt?t={int(time.time())}"
        try:
            res = requests.get(api_url, headers=headers, timeout=10)
            if res.status_code == 200:
                user_uploaded = True
                data = res.json()
                content_b64 = data.get("content", "")
                txt_val = base64.b64decode(content_b64).decode('utf-8', errors='ignore')
                
                # Parsing the compiled translations cleanly via Regex
                pattern = r"\{(\d+)\}tutty_(\d+)_(\d+) ==> (.*)"
                translations = {}
                for line in txt_val.splitlines():
                    line = line.strip()
                    match = re.search(pattern, line)
                    if match:
                        _, p_idx, b_idx, text = match.groups()
                        translations[f"{p_idx}_{b_idx}"] = text.strip()
                        
                # Save translations map to shared JSON file
                with open(os.path.join(ws, "translations.json"), "w", encoding="utf-8") as wf:
                    import json
                    json.dump(translations, wf, ensure_ascii=False, indent=4)
                    
                # Safe cleanup of parsed translation from GitHub
                sha = data.get("sha")
                requests.delete(api_url.split("?")[0], headers=headers, json={"message": "Clean trans file", "sha": sha}, timeout=10)
                break
        except Exception as e:
            print("Poller network error:", e)
            
        await asyncio.sleep(10)

    if not user_uploaded:
        await bot_client.edit_message_text(CHAT_ID, MSG_ID, "❌ **Timeout:** Task cancelled. Cache has been cleared.")
        return False, "Timeout", ""

    # -----------------------------------------------------------------
    # PHASE 3: RENDERING & COMPILING TRANSLATIONS (FAST RUN)
    # -----------------------------------------------------------------
    os.environ["ENV_TRANSLATE_MODE"] = "RENDER"
    await bot_client.edit_message_text(CHAT_ID, MSG_ID, "🎨 **Phase 3/3: Typesetting & Rendering manga...\n`[████████░░] 80%`**")
    
    if os.path.exists(output_dir): 
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    proc2 = await asyncio.create_subprocess_exec(*cli_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=cwd_dir)
    
    current_render_page = 0
    start_render_time = time.time()
    
    while True:
        line = await proc2.stdout.readline()
        if not line: break
        decoded = line.decode('utf-8', errors='ignore').strip()
        print(decoded)
        
        if "Translating:" in decoded:
            current_render_page += 1
            elapsed_render = time.time() - start_render_time
            speed_render = current_render_page / elapsed_render if elapsed_render > 0 else 0
            percent_render = int((current_render_page / len(pages)) * 100)
            bar_render = "█" * (percent_render // 10) + "░" * (10 - (percent_render // 10))
            
            speed_render_str = f"{speed_render:.2f} pages/sec"
            if speed_render > 0:
                speed_render_str += f" ({1/speed_render:.1f} sec/page)"
                
            render_text = (
                f"🎨 **Phase 3/3: Rendering completed typesetting**\n"
                f"Erasing bubbles and adjusting fonts with automatic fitting...\n\n"
                f"**Render Progress:** Page `{current_render_page}` of `{len(pages)}` finished.\n"
                f"**Speed:** `{speed_render_str}` | **Percentage:** `{percent_render}%`\n"
                f"`[{bar_render}]`"
            )
            try:
                await bot_client.edit_message_text(CHAT_ID, MSG_ID, render_text)
            except:
                pass
                
    await proc2.wait()
    
    cnt_results = 0
    if os.path.exists(output_dir):
        base_results = [f for r, _, fx in os.walk(output_dir) for f in fx if f.lower().endswith(('.png','.jpg','.jpeg','.webp'))]
        cnt_results = len(base_results)

    if proc2.returncode == 0 and cnt_results > 0:
        return True, "Success", ""
    return False, "Failed", ""


# =================================================================
# 📥 3. PRIMARY RUN WORKFLOW
# =================================================================
async def main():
    if not FILE_ID: 
        print("Empty File Matrix ID Found")
        return 
        
    tg_bot = Client("WorkerMaster", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, no_updates=True)
    await tg_bot.start()
    
    def get_progress_bar(percent, status):
        filled_length = int(percent // 10)
        bar = "█" * filled_length + "░" * (10 - filled_length)
        return f"⚡ **Status:** {status}\n`[{bar}] {percent}%`"

    await tg_bot.edit_message_text(CHAT_ID, MSG_ID, get_progress_bar(10, "Target pull sequence initiated..."))

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

    await tg_bot.edit_message_text(CHAT_ID, MSG_ID, get_progress_bar(20, "Extracting layouts & images..."))

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

    pages = [os.path.join(r, f) for r, _, fs in os.walk(inp) for f in fs if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp'))]
    if not pages: 
        await tg_bot.edit_message_text(CHAT_ID, MSG_ID, "❌ **Formatting Error:** No supported images found in your document.")
        return await tg_bot.stop()

    success_bool, prvd_ui, full_core_log = await run_translator_with_fallback(inp, out, ws, tg_bot)

    if not success_bool:
        err_out = (
            f"❌ **FATAL SYSTEM FAIL / DENIAL LOOP**\n"
            f"Processes crashed during generation blocks.\n\n"
            f"**Error Diagnostics:**\n"
            f"`{full_core_log[-450:]}`"
        )
        await tg_bot.edit_message_text(CHAT_ID, MSG_ID, err_out)
        return await tg_bot.stop()

    await tg_bot.edit_message_text(CHAT_ID, MSG_ID, get_progress_bar(90, "Rebuilding completed typesetting output..."))

    finals_l = sorted([os.path.join(r, f) for r, _, fs in os.walk(out) for f in fs if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))])
    zipx_out = "translated_" + FNAME if ext in [".zip", ".cbz", ".pdf"] else finals_l[0]
    
    if ext in [".zip", ".cbz"]:
        with zipfile.ZipFile(zipx_out, 'w', zipfile.ZIP_DEFLATED) as z_enc:
            for fd_c in finals_l: 
                z_enc.write(fd_c, os.path.relpath(fd_c, out))
    elif ext == ".pdf":
        # Highly optimized PyMuPDF (fitz) engine to prevent Pillow memory leaks/freezes
        import fitz
        doc = fitz.open()
        for img_path in finals_l:
            img = fitz.open(img_path)
            rect = img[0].rect
            page = doc.new_page(width=rect.width, height=rect.height)
            page.insert_image(rect, filename=img_path)
            img.close()
        doc.save(zipx_out)
        doc.close()

    endcap_caption = "✅ **Processing Repacked Successfully!**\n⚡ Control Type: Manual Human Output Render Logic MTPE"
    
    try:
        await tg_bot.send_document(CHAT_ID, zipx_out, caption=endcap_caption)
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
