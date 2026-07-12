import os
import sys
import zipfile
import shutil
import asyncio
from pyrogram import Client
import pyrogram.utils

# Pyrogram Core By-Pass
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
GEMINI_KEYS_STR = os.getenv("gemini_keys", "")

GEMINI_KEYS = [k.strip() for k in GEMINI_KEYS_STR.split(",") if k.strip()]

print(f"=== DEEP-ANNELISE START [LANG: {LANG}] | FILE: {FNAME} ===")
print(f"✅ FORK/INJECTION INITIALIZED | ACTIVE KEYS: {len(GEMINI_KEYS)}\n")

if not BOT_TOKEN or len(BOT_TOKEN) < 10 or not API_ID:
    print("❌ CRITICAL ERROR: GitHub Secrets (API_ID, BOT_TOKEN) missing. Translation Terminated!")
    sys.exit(1)

# =================================================================
# 🧬 1. THE NATIVE FORK INJECTOR CODE (HACKS THE LIBRARY AT RUNTIME)
# Yeh Python script runtime pe "manga_translator/translators/gpt3.py" 
# ko poori tarah udaa ke ye naya "Gemini Native" code wahan bitha dega.
# =================================================================

CUSTOM_GEMINI_NATIVE_PLUGIN = """
import os
import asyncio
import aiohttp
import json
from .base import BaseTranslator

class UltimateGeminiFork(BaseTranslator):
    def __init__(self):
        super().__init__()
        # Import keys gracefully mapped from the Worker environment!
        keys_pool = os.getenv("ENV_GEMINI_POOL", "")
        self.keys = [k.strip() for k in keys_pool.split(",") if k.strip()]
        self.target_lang = os.getenv("ENV_LANG_SET", "english").lower()
        self.k_index = 0
        self.thread_lock = asyncio.Lock()
        
    async def request_google(self, text, auth_session, attempt=0):
        # Backup safe exit
        if not self.keys: return text
        if attempt >= max(3, len(self.keys) * 2): return text
        
        # Atomically pulling 1 Key dynamically from available
        async with self.thread_lock:
            active_key = self.keys[self.k_index % len(self.keys)]
            self.k_index += 1
            
        # Target latest highly effective flash versions 
        node_str = "gemini-2.0-flash" if attempt % 2 == 0 else "gemini-1.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{node_str}:generateContent?key={active_key}"
        
        # Hardcoding the prompt logic into the very depth of the library 
        if "hienglish" in self.target_lang:
            instruct = "You are a professional manga translator. Translate everything exactly into HINGLISH. This means Hindi language spoken naturally but written perfectly in ENGLISH ROMAN ALPHABETS ONLY! DO NOT USE DEVANAGARI whatsoever. Example output: 'Bhai, main idhar aa gaya hu'. Only output translated text seamlessly."
        else:
            instruct = "You are a professional manga translator. Accurately translate this extracted text directly into fluid localized English. Return nothing but the translation output."

        payload = {
            "systemInstruction": {"parts": [{"text": instruct}]},
            "contents": [{"parts": [{"text": str(text)}]}],
            "generationConfig": {"temperature": 0.25}
        }
        
        try:
            # We enforce gentle dispatch wait natively so server doesn't 429 
            await asyncio.sleep(0.4)
            async with auth_session.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=aiohttp.ClientTimeout(total=45)) as response:
                if response.status == 200:
                    resp_json = await response.json()
                    try: 
                        return resp_json['candidates'][0]['content']['parts'][0]['text'].strip()
                    except (KeyError, IndexError): return text
                    
                elif response.status == 429: # Proper RPM Exhaustion Check
                    await asyncio.sleep(2.0)
                    return await self.request_google(text, auth_session, attempt + 1)
                    
                else: 
                     await asyncio.sleep(1.0)
                     return await self.request_google(text, auth_session, attempt + 1)
                     
        except Exception as NativeFail:
            await asyncio.sleep(1.2)
            return await self.request_google(text, auth_session, attempt + 1)

    async def translate(self, queries, sl, tl, **kwargs):
        if not self.keys:
            print(">> WARNING! API pool Empty. Translation Skpped.")
            return queries
        print(f"\\n🔥 [DEEP-FORK] Operating direct Gemini Injection on {len(queries)} frame lines! (Mode: {self.target_lang})\\n")
        async with aiohttp.ClientSession() as conn:
            task_list = [self.request_google(req_q, conn) for req_q in queries]
            output_responses = await asyncio.gather(*task_list)
        return output_responses

# MAGIC MAPPING: Whatever GPT version CLI asks for, they ALL point to our Supreme Gemini Fork Engine!
class GPT3Translator(UltimateGeminiFork): pass
class GPT35Translator(UltimateGeminiFork): pass
class GPT35TurboTranslator(UltimateGeminiFork): pass
class GPT4Translator(UltimateGeminiFork): pass
"""

# =================================================================
# 🛡️ 2. DEPLOYMENT CORE (WHERE FORK HAPPENS IN REAL-TIME)
# =================================================================
async def run_translator_with_fallback(input_dir, output_dir, workspace):
    cwd_dir = "manga-image-translator" if os.path.exists("manga-image-translator") else None
    
    if not GEMINI_KEYS:
        return False, "Failed", "Empty 0 Keys Setup - Terminated!"

    # System parameters transfer to Hack Custom script environments
    os.environ["ENV_GEMINI_POOL"] = GEMINI_KEYS_STR
    os.environ["ENV_LANG_SET"] = LANG

    # GITHUB HACK OVERRIDE EXECUTION 
    # Library file .> manga_translator/translators/gpt3.py
    if cwd_dir:
        library_overwriter = os.path.join(cwd_dir, "manga_translator", "translators", "gpt3.py")
        if os.path.exists(library_overwriter):
            with open(library_overwriter, "w", encoding="utf-8") as writer:
                writer.write(CUSTOM_GEMINI_NATIVE_PLUGIN)
            print("🚀 Deep Annelise Custom Library Overwriter Executed: Perfect Fork Achieved!")

    style_flags = ["--manga2eng"] if STYLE == "style2" else []
    
    # Observe we are asking library for 'gpt3', BUT under the hood, we wiped it 
    # entirely so it executes UltimateGeminiFork instead without errors! 
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

    print(f">> Execution Phase Concluded | Returns {proc.returncode} | Node Generated Assets: {cnt_results}")

    if proc.returncode == 0 and cnt_results > 0:
        return True, "DEEP FORK CORE - NATIVE GEMINI ✨", log
    
    return False, "Failed", log

# =================================================================
# 📥 3. PRIMARY ENDPOINT TELEGRAM GATEWAY
# =================================================================
async def main():
    if not FILE_ID: return
    tg_bot = Client("Worker", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, no_updates=True)
    await tg_bot.start()
    async def e_msg(s_t):
        try: await tg_bot.edit_message_text(CHAT_ID, MSG_ID, s_t)
        except: pass

    await e_msg(f"⏳ **Archiving Payload Access Phase: {FNAME}...**")

    dl_path = None
    for attempt_seq in range(1, 6):
        try:
            dl_path = await tg_bot.download_media(FILE_ID)
            if dl_path and os.path.exists(dl_path) and os.path.getsize(dl_path) > 1024:
                break
            await asyncio.sleep(2)
        except BaseException:
            await e_msg(f"⚠️ **Telegram Connectivity Phase {attempt_seq}/5** | Recovering Link...")
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
        await e_msg("❌ **Core Error | Archive Validation Sequence Format Fault.**")
        return await tg_bot.stop()

    pages = [os.path.join(r,f) for r,_,fs in os.walk(inp) for f in fs if f.lower().endswith(('.png','.jpg','.jpeg','.webp','.bmp'))]
    if not pages:
        return await tg_bot.stop()

    lang_ux = "Hi-English (HQA Prompt)" if LANG == "hienglish" else "ENG Base Language NLP"
    await e_msg(f"🔄 **Hacking Overriding Subsystems Activated | Visual Extracted Units: {len(pages)}** [Model Mode: {lang_ux}] ✨\n_Utilizing Raw Network Injection for pure operations._")

    success_bool, prvd_ui, full_core_log = await run_translator_with_fallback(inp, out, ws)

    if not success_bool:
        err_out = f"⚠️ **FATAL OVERRIDE FAILURE**\nProcess hit an unconditional block node in Translation Stage.\n\n_System Diagnostics:_ `{full_core_log[-450:]}`"
        await e_msg(err_out)
        return await tg_bot.stop()

    await e_msg(f"🎨 **Pipeline Synthesis Achieved.** | Rendering Architecture Processors...")

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
        await e_msg(f"❌ **Package Data Threshold Met -> {sbslmt_zpb:.1f} MB** | 2GB Upload Restriction Trigerred.")
        return await tg_bot.stop()

    endcap_caption = f"✅ **Extraction Operation Finalised Natively!**\n🌐 Model Output Setup: {lang_ux}\n⚡ Architecture Status: Direct Native Gemini Integrated\n"
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
