import os
import sys
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

print(f"=== DEEP-ANNELISE MANUAL ENGINE ON CPU | USER: {USER_ID} ===")
if not BOT_TOKEN or not API_ID:
    print("❌ CRITICAL ERROR: GitHub Secrets parameters are missing!")
    sys.exit(1)


# =========================================================================================
# 🧬 DYNAMIC OVERWRITE FOR 'chatgpt.py' - COMPLETELY BYPASSES OPENAI/API VALIDATIONS
# ==========================================================================================

ROUTINE_SCRIPT_BYPASSER = """
import os
import asyncio
import time
import requests
from .common import CommonTranslator

class HumanInterventionTranslator(CommonTranslator):
    # Defining standard supported languages list to prevent LanguageUnsupportedException
    supported_src_languages = ['auto', 'ENG', 'JPN', 'CHS', 'CHT', 'KOR', 'FRA', 'DEU', 'RUS', 'SPA', 'ITA', 'POR', 'TRK', 'VIE', 'NLD', 'PLK', 'UKR', 'ARA', 'THA', 'IND', 'FIL']
    supported_target_languages = ['auto', 'ENG', 'JPN', 'CHS', 'CHT', 'KOR', 'FRA', 'DEU', 'RUS', 'SPA', 'ITA', 'POR', 'TRK', 'VIE', 'NLD', 'PLK', 'UKR', 'ARA', 'THA', 'IND', 'FIL']

    def __init__(self, *args, **kwargs):
        # Base constructor initialization without hitting external API triggers
        super().__init__(*args, **kwargs)
        self.sys_token = os.environ.get("ENV_BOT_TOKEN")
        self.cst_uid = int(os.environ.get("ENV_USER_ID", "0"))
        self.chat_id = int(os.environ.get("ENV_CHAT_ID", "0"))
        self.msg_id = int(os.environ.get("ENV_MSG_ID", "0"))
        self.repo_name = os.environ.get("ENV_REPO_NAME", "")
        self.page_counter = 1 # Stateless sequential page counter

    # Forcefully bypass translator level language verification checks
    def supports_languages(self, from_lang, to_lang, fatal=False):
        return True

    async def _translate(self, from_lang, to_lang, queries, *args, **kwargs):
        return await self.do_custom_workflow(queries)

    async def translate(self, from_lang, to_lang, queries, *args, **kwargs):
        return await self.do_custom_workflow(queries)

    def draw_bar(self, percent, step_msg):
        filled_length = int(percent // 10)
        bar = "█" * filled_length + "░" * (10 - filled_length)
        return f"🎨 **Status Update:** {step_msg}\\n`[{bar}] {percent}%`"

    def send_subtitles_via_http(self, file_path, caption):
        url = f"https://api.telegram.org/bot{self.sys_token}/sendDocument"
        with open(file_path, 'rb') as doc:
            requests.post(url, data={
                'chat_id': self.cst_uid,
                'caption': caption,
                'parse_mode': 'Markdown'
            }, files={'document': doc})

    def update_status_via_http(self, message):
        url = f"https://api.telegram.org/bot{self.sys_token}/editMessageText"
        requests.post(url, json={
            "chat_id": self.chat_id,
            "message_id": self.msg_id,
            "text": message,
            "parse_mode": "Markdown"
        })

    async def do_custom_workflow(self, queries):
        if not queries: 
            return queries
        
        print(f"\\n🔥 Frame Interceptor: Processing Page {self.page_counter} ({len(queries)} rows).")
        out_rows = []
        out_rows.append(f"# MSG_ID: {self.msg_id}")
        out_rows.append(f"# PAGE: {self.page_counter}") # Stateless page mapping header
        out_rows.append("# ----------------------------------------")
        
        for nx, qrs in enumerate(queries):
            r_x = nx + 1
            out_rows.append(f"{r_x:02d}")
            qrs_c = str(qrs).replace('\\n', ' ')
            out_rows.append(f"{{{self.cst_uid}}}tutty{r_x:02d}({qrs_c})\\n")
            
        xport_nm = f"FrameExtr_{self.cst_uid}_page_{self.page_counter}.txt"
        with open(xport_nm, "w", encoding="utf-8") as op_w:
            op_w.write("\\n".join(out_rows))
            
        dirctn = (
            f"📝 **Frames Disassembled Fully (Page {self.page_counter})!**\\n\\n"
            "1️⃣ Open & Edit this mapped '.txt' file.\\n"
            "2️⃣ Translate text localized purely enclosed in `( )`.\\n"
            "3️⃣ DO NOT alter specific node tagging formatting loops like `{{{self.cst_uid}}}tutty`.\\n"
            "4️⃣ Resend updated document cleanly back to bot to trigger Engine Continuation Render! (Waiting Timeout ~12 Mins)"
        )
        
        # Send page subtitles directly to User's PM
        self.send_subtitles_via_http(xport_nm, dirctn)
        
        # Update progress bar status
        self.update_status_via_http(self.draw_bar(50, f"Page {self.page_counter} Extracted! Delivered to your PM. Waiting..."))

        translated_layer_dump = [raw for raw in queries] 
        fxd_capture = False
        
        # 12 minutes countdown timer loop (checks every 15 seconds)
        for elapsed in range(0, 720, 15):
            await asyncio.sleep(15) 
            
            # Poll raw GitHub (Fallback support for both main & master branch!)
            github_url = f"https://raw.githubusercontent.com/{self.repo_name}/main/trans_{self.cst_uid}_page_{self.page_counter}.txt?t={time.time()}"
            res = requests.get(github_url)
            
            if res.status_code == 404:
                # master branch fallback
                github_url = f"https://raw.githubusercontent.com/{self.repo_name}/master/trans_{self.cst_uid}_page_{self.page_counter}.txt?t={time.time()}"
                res = requests.get(github_url)
            
            if res.status_code == 200:
                txt_val = res.text
                try:
                    tag = f"{{{self.cst_uid}}}tutty"
                    for line in txt_val.splitlines():
                        line = line.strip()
                        if tag in line:
                            idx_part = line.split(tag)[1]
                            idx_str = "".join([c for c in idx_part if c.isdigit()])
                            idx = int(idx_str) - 1
                            
                            text_part = idx_part[len(idx_str):].strip()
                            if text_part.startswith("(") and text_part.endswith(")"):
                                translated_text = text_part[1:-1]
                            else:
                                translated_text = text_part.strip("()")
                                
                            if 0 <= idx < len(translated_layer_dump):
                                translated_layer_dump[idx] = translated_text.strip()
                                
                    fxd_capture = True
                    break
                except Exception as SysERR:
                    print("Parse error on user formatting structure -> ", SysERR)
                    
        if not fxd_capture:
            print(">> [!] Timeout reached or translation failed. Outputting empty render.")
            
        # Increment page counter for next iteration
        self.page_counter += 1
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

    # Overwrite 'chatgpt.py' because library uses it internally
    if cwd_dir:
        core_lib_node = os.path.join(cwd_dir, "manga_translator", "translators", "chatgpt.py")
        if os.path.exists(os.path.dirname(core_lib_node)):
            with open(core_lib_node, "w", encoding="utf-8") as injectn:
                injectn.write(ROUTINE_SCRIPT_BYPASSER)
            print("💥 CRITICAL: chatgpt.py bypass written correctly!")

    style_flags = ["--manga2eng"] if STYLE == "style2" else []
    
    # FIXED: Added positional subcommand "local" to command array
    # FIXED BYPASS: Change target language from "ENG" to "FRA" (French)
    cli_cmd = ["python", "-m", "manga_translator", "local", "-i", input_dir, "--dest", output_dir, "--translator", "gpt3", "-l", "FRA"] + style_flags
    
    if os.path.exists(output_dir): 
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    await bot_client.edit_message_text(CHAT_ID, MSG_ID, "🔍 **Step 2/4:** Running OCR Engine (Parsing Text bubbles)...\n`[███░░░░░░░] 30%`")

    proc = await asyncio.create_subprocess_exec(*cli_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=cwd_dir)
    
    # Read output log line-by-line dynamically
    log_dump = []
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        decoded = line.decode('utf-8', errors='ignore').strip()
        log_dump.append(decoded)
        print(decoded) # Print to GitHub console

    await proc.wait()
    full_log = "\n".join(log_dump)

    cnt_results = 0
    if os.path.exists(output_dir):
        base_results = [f for r, _, fx in os.walk(output_dir) for f in fx if f.lower().endswith(('.png','.jpg','.jpeg','.webp'))]
        cnt_results = len(base_results)

    if proc.returncode == 0 and cnt_results > 0:
        return True, "Success", full_log
    
    return False, "Failed", full_log


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
        from PIL import Image
        px_i_set = [Image.open(p_z_file).convert('RGB') for p_z_file in finals_l]
        if px_i_set: 
            px_i_set[0].save(zipx_out, save_all=True, append_images=px_i_set[1:])

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
