import os
import sys
import zipfile
import shutil
import asyncio
from pyrogram import Client
import pyrogram.utils

# Channel Id Bypasser
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

GEMINI_KEYS = [k.strip() for k in os.getenv("gemini_keys", "").split(",") if k.strip()]

print(f"=== DEEP-ANNELISE START [LANG: {LANG}] | FILE: {FNAME} ===")
print(f"✅ NATIVE OVERRIDE INIT | LOADED KEYS: {len(GEMINI_KEYS)}\n")

if not BOT_TOKEN or len(BOT_TOKEN) < 10 or not API_ID:
    print("❌ CRITICAL ERROR: GitHub Secrets (API_ID, BOT_TOKEN) missing. Job Aborted!")
    sys.exit(1)

# =================================================================
# 🧬 1. THE NATIVE PLUGIN OVERRIDE CODE (FORK-SCRIPT INTEGRATION)
# Yeh sidha Manga Library ke system me push/replace hoga.
# =================================================================
NATIVE_LIBRARY_OVERRIDE = """
import os
import asyncio
import aiohttp
from .base import BaseTranslator

class GPT3Translator(BaseTranslator):
    _KEYS = [k.strip() for k in os.getenv("gemini_keys", "").split(",") if k.strip()]
    _KL_IDX = 0

    def __init__(self):
        super().__init__()

    async def _fetch_from_gemini(self, text, session, attempt=0):
        if not self._KEYS:
            return "ERROR_NO_API"
        
        # Max fallback protections
        if attempt > (len(self._KEYS) * 2):
            return text 
            
        active_key = self._KEYS[self._KL_IDX % len(self._KEYS)]
        
        # 100% Validated Stable Model - Locking it down to prevent 'omni-flash Limit 0' Bug
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={active_key}"
        
        # Precise UI injection prompt handling natively inside the function (Bypasses manual confignymys configs)
        lang = os.getenv("LANG", "english").lower().strip()
        if "hienglish" in lang:
            sys_pr = "You are a professional manga translator. Translate everything exactly into HINGLISH. This means Hindi language spoken naturally but written perfectly in ENGLISH ROMAN ALPHABETS ONLY! DO NOT USE DEVANAGARI whatsoever. Example output: 'Bhai, main idhar aa gaya hu'. Keep strictly native structure."
        else:
            sys_pr = "You are a professional manga translator. Accurately translate this image frame Japanese text directly into fluid localized English, returning nothing but the output."

        payload = {
            "systemInstruction": {"parts": [{"text": sys_pr}]},
            "contents": [{"parts": [{"text": str(text)}]}],
            "generationConfig": {"temperature": 0.25}
        }
        
        try:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    try:
                        return data['candidates'][0]['content']['parts'][0]['text'].strip()
                    except: return text
                
                elif resp.status == 429: # THE OFFICIAL INTERNAL AUTO SLEEP
                    print(f"\\n[NATIVE ENGINE] RPM LIMIT HIT: Switching Gemini Auth Keys \\nWait Cycle Starting... (15 sec Quota obey mode)")
                    self._KL_IDX += 1
                    await asyncio.sleep(15.0) 
                    return await self._fetch_from_gemini(text, session, attempt + 1)
                
                else: 
                     # Bad gateway, 500, or invalid param. Next Key 
                     err_data = await resp.text()
                     print(f"\\n[NATIVE ENGINE] Unknown API Error {resp.status}, cycling keys -> {err_data[:200]}")
                     self._KL_IDX += 1
                     await asyncio.sleep(2.0)
                     return await self._fetch_from_gemini(text, session, attempt + 1)
        except Exception as Native_EX:
            print(f"\\n[NATIVE ENGINE AIOHTTP ERROR] Retrying Network {Native_EX}")
            self._KL_IDX += 1
            await asyncio.sleep(4.0)
            return await self._fetch_from_gemini(text, session, attempt + 1)

    async def translate(self, queries, sl, tl, **kwargs):
        print(f"\\n🔥 [NATIVE PLUGIN ACTIVATED] BATCH DISPATCH! Distributing {len(queries)} frames independently to Gemini API Clusters without Proxy...\\n")
        async with aiohttp.ClientSession() as session:
            tasks_list = [self._fetch_from_gemini(tx, session) for tx in queries]
            output_results = await asyncio.gather(*tasks_list)
        return type(queries)(output_results)
"""

# =================================================================
# 🧬 2. PROCESS CORE & INJECTION SYSTEM 
# =================================================================
async def run_translator_with_fallback(input_dir, output_dir, workspace):
    cwd_dir = "manga-image-translator" if os.path.exists("manga-image-translator") else None
    if not GEMINI_KEYS:
        return False, "Failed", "WARNING! Empty Database Request -> 0 API Keys Supplied! Ensure UI passes it properly."

    # Force ENV Exporting to the internal payload library environment
    os.environ["gemini_keys"] = os.getenv("gemini_keys", "")
    os.environ["LANG"] = LANG

    # GITHUB HACK INJECTION: We replace manga_translator's native GPT logic utilizing OUR script code!
    if cwd_dir:
        library_overwriter = os.path.join(cwd_dir, "manga_translator", "translators", "gpt3.py")
        if os.path.exists(library_overwriter):
            with open(library_overwriter, "w", encoding="utf-8") as writer:
                writer.write(NATIVE_LIBRARY_OVERRIDE)
            print("🚀 Deep Annelise Script Injected Into Github Workflow (Library Fork Achieved Runtime)!")

    # Bypassed style param passing normally. Using our Native GPT3 flag triggers our Plugin Core.  
    style_flags = ["--manga2eng"] if STYLE == "style2" else []
    cli_cmd = ["python", "-m", "manga_translator", "-i", input_dir, "--dest", output_dir, "--translator", "gpt3", "-l", "ENG"] + style_flags
    
    if os.path.exists(output_dir): shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    proc = await asyncio.create_subprocess_exec(*cli_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=cwd_dir)
    out, _ = await proc.communicate()
    log = out.decode('utf-8', errors='ignore')

    cnt_results = 0
    if os.path.exists(output_dir):
        base_results = [f for root, _, fx in os.walk(output_dir) for f in fx if f.lower().endswith(('.png','.jpg','.jpeg','.webp'))]
        cnt_results = len(base_results)

    print(f">> Translation Mode Finalized | Node Result {proc.returncode} | Success Blocks Generated: {cnt_results}")

    if proc.returncode == 0 and cnt_results > 0:
        return True, "SYSTEM FORK - NATIVE GEMINI API", log
    
    return False, "Failed", log

# =================================================================
# 📥 3. PRIMARY ENDPOINT FRAME (TELEGRAM BOT DOWNLOAD MANAGER)
# =================================================================
async def main():
    if not FILE_ID: 
        print("Empty File ID")
        return
        
    tg_bot = Client("Worker", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, no_updates=True)
    await tg_bot.start()
    async def e_msg(s_t):
        try: await tg_bot.edit_message_text(CHAT_ID, MSG_ID, s_t)
        except: pass

    await e_msg(f"⏳ **Local Node Frame Pull: {FNAME}...**")

    dl_path = None
    for attempt_seq in range(1, 6):
        try:
            dl_path = await tg_bot.download_media(FILE_ID)
            if dl_path and os.path.exists(dl_path) and os.path.getsize(dl_path) > 1024:
                break
            await asyncio.sleep(2)
        except BaseException as B_EX:
            await e_msg(f"⚠️ **Network Dropout Phase {attempt_seq}/5** | Recovering...")
            await asyncio.sleep(3)

    if not dl_path or not os.path.exists(dl_path):
        return await tg_bot.stop()

    ext = os.path.splitext(FNAME)[1].lower() or ".zip"
    ws = os.path.abspath("manga_workspace")
    inp = os.path.join(ws,"input")
    out = os.path.join(ws,"output")
    if os.path.exists(ws): shutil.rmtree(ws)
    os.makedirs(inp, exist_ok=True); os.makedirs(out, exist_ok=True)

    try:
        if ext in [".zip",".cbz"]:
            with zipfile.ZipFile(dl_path,'r') as z: z.extractall(inp)
        elif ext == ".pdf":
            import fitz
            pdf_layer = fitz.open(dl_path)
            for znc_n in range(len(pdf_layer)):
                pdf_pg = pdf_layer.load_page(znc_n)
                pdf_pg.get_pixmap(dpi=150).save(os.path.join(inp, f"page_{znc_n:03d}.png"))
            pdf_layer.close()
        else:
            shutil.copy(dl_path, inp)
    except zipfile.BadZipFile:
        await e_msg("❌ **Core Error | Archive Data Corrupted, Rejecting Format Protocol.** (Send valid format)")
        return await tg_bot.stop()

    pages = [os.path.join(r,f) for r,_,fs in os.walk(inp) for f in fs if f.lower().endswith(('.png','.jpg','.jpeg','.webp','.bmp'))]
    if not pages:
        return await tg_bot.stop()

    lang_ux = "HiEng Official Native Frame" if LANG == "hienglish" else "ENG Vector NLP Base"
    await e_msg(f"🔄 **AI Processing Network Hooked | UI Node Units: {len(pages)}** [Model: {lang_ux}] ✨\n_Native 'Forked-Runtime Script' Loaded._")

    success_bool, prvd_ui, full_core_log = await run_translator_with_fallback(inp, out, ws)

    if not success_bool:
        err_out = f"⚠️ **Hard Crash Encountered**\nReview output dump format for failures.\n\n_Logs:_ `{full_core_log[-450:]}`"
        await e_msg(err_out)
        return await tg_bot.stop()

    await e_msg(f"🎨 **Compilation Finished.** | Rendering Network Zip Processors...")

    finals_l = sorted([os.path.join(r,f) for r,_,fs in os.walk(out) for f in fs if f.lower().endswith(('.png','.jpg','.jpeg','.webp'))])
    zipx_out = "translated_" + FNAME if ext in [".zip",".cbz",".pdf"] else finals_l[0]
    
    if ext in [".zip",".cbz"]:
        with zipfile.ZipFile(zipx_out,'w',zipfile.ZIP_DEFLATED) as z_enc:
            for fd_c in finals_l: z_enc.write(fd_c, os.path.relpath(fd_c, out))
    elif ext == ".pdf":
        from PIL import Image
        px_i_set = [Image.open(p_z_file).convert('RGB') for p_z_file in finals_l]
        if px_i_set: px_i_set[0].save(zipx_out, save_all=True, append_images=px_i_set[1:])

    sbslmt_zpb = os.path.getsize(zipx_out) / (1024*1024)
    if sbslmt_zpb > 1900:
        await e_msg(f"❌ **Package Maxed Payload -> {sbslmt_zpb:.1f} MB** | Bot limit threshold compromised.")
        return await tg_bot.stop()

    endcap_caption = f"✅ **Processing Operation Completed!**\n🌐 Language Structure: {lang_ux}\n⚡ Execution Engine: Native Gemini Override Plugin\n"
    try:
        await tg_bot.send_document(CHAT_ID, zipx_out, caption=endcap_caption)
        try: await tg_bot.delete_messages(CHAT_ID, MSG_ID)
        except: pass
    except Exception:
        pass

    shutil.rmtree(ws, ignore_errors=True)
    try: os.remove(dl_path)
    except: pass
    try:
        if ext in [".zip",".cbz",".pdf"]: os.remove(zipx_out)
    except: pass
    await tg_bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
