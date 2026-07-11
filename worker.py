import os
import sys
import zipfile
import shutil
import asyncio
import json
import threading
import time
import urllib.request
import urllib.error
import itertools
from pyrogram import Client
import pyrogram.utils
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

# Safe Channel Bypass
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

# Clean separation of keys extracted from HF Environment payload.
raw_keys = os.getenv("gemini_keys", "")
GEMINI_KEYS = [k.strip() for k in raw_keys.split(",") if k.strip()]

print(f"=== START PROCESS - LANG: {LANG} | ARCHIVE: {FNAME} ===")
print(f"✅ ACTIVATING DEEP ANNELISE LOAD BALANCER | API KEYS LOADED: {len(GEMINI_KEYS)}")

if not BOT_TOKEN or len(BOT_TOKEN) < 10 or not API_ID:
    print("❌ CRITICAL ERROR: GitHub Secrets (API_ID, BOT_TOKEN) are missing. Workflow Aborting!")
    sys.exit(1)

def mask_key(key):
    return f"...{key[-4:]}" if len(key) > 6 else "***"

# =================================================================
# 🚀 1. THREAD-SAFE ROUND ROBIN API KEY DISTRIBUTOR 
# =================================================================
class APIKeyManager:
    """Solves Threading bugs by safely distributing keys round-robin per request."""
    def __init__(self, keys):
        self.keys = keys
        self.lock = threading.Lock()
        self._cycle = itertools.cycle(self.keys) if self.keys else None
    
    def get_key(self):
        with self.lock:
            if not self._cycle: return None
            return next(self._cycle)

key_manager = APIKeyManager(GEMINI_KEYS)

# =================================================================
# 🚀 2. LOCAL API INTERCEPTOR SERVER
# =================================================================
PROXY_PORT = 11434

class ProxyHTTPRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Disabling output noise to prevent HTTP 200 clutter in logs

    def do_GET(self):
        # Mocks 'gpt-3.5-turbo' model schema for validation checks
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        mock_data = {"object": "list", "data": [{"id": "gpt-3.5-turbo", "object": "model", "created": 1234, "owned_by": "openai"}]}
        self.wfile.write(json.dumps(mock_data).encode('utf-8'))

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            req_data = json.loads(body)
            messages = req_data.get('messages', [])
            temperature = req_data.get('temperature', 0.3)
            
            # Separation loop mapping GPT Prompt instructions to strict Google API format
            system_text = ""
            user_text = ""
            for msg in messages:
                if msg.get('role') == 'system':
                    system_text += msg.get('content', '') + "\n"
                else:
                    user_text += msg.get('content', '') + "\n"
            
            gemini_payload = {
                "contents": [{"role": "user", "parts": [{"text": user_text}]}],
                "generationConfig": {"temperature": temperature}
            }
            if system_text.strip():
                # Fixes Gemini strict schema payload rejection formats (Fixes Bug 3)
                gemini_payload["systemInstruction"] = {"parts": [{"text": system_text}]}
            
            gemini_body = json.dumps(gemini_payload).encode('utf-8')
            
            success = False
            last_err_body = b"{}"
            last_code = 500
            
            # 🚀 RAPID-RETRY LOOP (Fixes Issue Bug 2)
            # Total attempts cap to 3x per active Keys 
            max_attempts = min(30, len(GEMINI_KEYS) * 3 + 2)
            
            for attempt in range(max_attempts):
                sys_api = key_manager.get_key()
                if not sys_api:
                    break
                
                # Locked default 1.5-flash for max stability across different region clusters
                url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={sys_api}'
                req = urllib.request.Request(url, data=gemini_body, method='POST')
                req.add_header('Content-Type', 'application/json')
                
                try:
                    with urllib.request.urlopen(req) as response:
                        resp_body = response.read()
                        gemini_resp = json.loads(resp_body)
                        success = True
                        break # Limit and response bypass fully functional, break sequence
                        
                except urllib.error.HTTPError as e:
                    last_code = e.code
                    last_err_body = e.read()
                    
                    if last_code in (429, 500): 
                        # 429 Limits (15 RPM Exceeded) or Google Backend Outages
                        # Instantly loop next assigned key! No massive 60 sec stops saving Library timeout.
                        time.sleep(1.2) 
                        continue
                    elif last_code == 404:
                        # Dead endpoint or deprecated key node. Sleep slightly and loop next request.
                        time.sleep(1.0)
                        continue
                    else:
                        break # Unrecoverable API block

            # If all 30 sub-attempts exhaust and fail
            if not success:
                self.send_response(last_code)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(last_err_body)
                return
            
            # Google Response Content parsing with Safely built Block Checks
            try:
                translated_text = ""
                candidates = gemini_resp.get('candidates', [])
                if candidates:
                    parts = candidates[0].get('content', {}).get('parts', [])
                    if parts:
                        translated_text = parts[0].get('text', '')
            except Exception:
                translated_text = "[SAFETY OR PARSER FAILED]"
            
            # Reconstruction payload compatible natively returning to MTPE library 
            openai_resp = {
                "id": "chatcmpl-native-gemini-bypasser",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "gpt-3.5-turbo",
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": translated_text},
                    "finish_reason": "stop"
                }],
                "usage": {"prompt_tokens": len(user_text), "completion_tokens": len(translated_text), "total_tokens": 0}
            }
            
            final_resp_body = json.dumps(openai_resp).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(final_resp_body)
                
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8'))

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

# Spawning Threaded Backdoor Protocol Server
if GEMINI_KEYS:
    server = ThreadingHTTPServer(('127.0.0.1', PROXY_PORT), ProxyHTTPRequestHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

# =================================================================
# 🚀 3. THE DISPATCH WORKER CORE 
# =================================================================
async def run_translator_with_fallback(input_dir, output_dir, workspace):
    cwd_dir = "manga-image-translator" if os.path.exists("manga-image-translator") else None

    if not GEMINI_KEYS:
        return False, "Failed", "0 API Keys found inside processing system. Apply using /addapi."

    style_flags = ["--manga2eng"] if STYLE == "style2" else []
    
    # Rerouting Official Application Base environment toward internal 3D protocol script mapping
    os.environ["OPENAI_API_KEY"] = "sk-fake-interceptor-bypass"
    os.environ["OPENAI_API_BASE"] = f"http://127.0.0.1:{PROXY_PORT}/v1"
    os.environ["OPENAI_BASE_URL"] = f"http://127.0.0.1:{PROXY_PORT}/v1"

    gpt_config_path = os.path.join(workspace, "gpt_config.yml")
    
    if LANG == "hienglish":
        cfg = """gpt3.5:
  temperature: 0.3
  prompt_template: "Translate to Hinglish: "
  chat_system_template: "You are a professional manga translator. You MUST translate the text into Hinglish (Hindi written in Roman English alphabet). For example, translate 'I am talking to you' to 'Main abhi tumse baat kar raha hu'. Do NOT use the Devanagari script (like 'मैं', 'तुम'). Only output the translated Hinglish text and nothing else."
"""
    else:
        cfg = """gpt3.5:
  temperature: 0.3
  prompt_template: "Translate to English: "
  chat_system_template: "You are a professional manga translator. Accurately translate the text to natural-sounding English."
"""
        
    with open(gpt_config_path, "w", encoding="utf-8") as f:
        f.write(cfg)

    # Note the CLI injection using 'gpt3.5' translator, seamlessly intercepted by localhost protocol
    cli_cmd = ["python", "-m", "manga_translator", "-i", input_dir, "--dest", output_dir, "--translator", "gpt3.5", "-l", "ENG", "--gpt-config", gpt_config_path] + style_flags

    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    proc = await asyncio.create_subprocess_exec(*cli_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=cwd_dir)
    out, _ = await proc.communicate()
    log = out.decode('utf-8', errors='ignore')

    cnt = 0
    if os.path.exists(output_dir):
        for r,_,fs in os.walk(output_dir):
            cnt += len([f for f in fs if f.lower().endswith(('.png','.jpg','.jpeg','.webp'))])

    print(f"Translation Output | Return Code {proc.returncode} | Generative Archivals Saved: {cnt}")

    if proc.returncode == 0 and cnt > 0:
        return True, "GEMINI FLUX ENGINE", log
    
    return False, "Failed", log

# =================================================================
# 🚀 4. MAIN TELEGRAM INTERFACE & WRAPPER
# =================================================================
async def main():
    if not FILE_ID: return
    bot = Client("Worker", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, no_updates=True)
    await bot.start()
    async def edit(t):
        try: await bot.edit_message_text(CHAT_ID, MSG_ID, t)
        except: pass

    await edit(f"⏳ **Extraction Layer Processing Archive {FNAME}...**")

    dl_path = None
    for i in range(1,6):
        try:
            dl_path = await bot.download_media(FILE_ID)
            if dl_path and os.path.exists(dl_path) and os.path.getsize(dl_path) > 1024:
                break
            await asyncio.sleep(2)
        except Exception as e:
            await edit(f"⚠️ **Transmission Frame Dropout {i}/5** Relaying Request...")
            await asyncio.sleep(3)

    if not dl_path or not os.path.exists(dl_path):
        await edit("❌ **Subsystem Corrupted Error | Media Not Extractable.**")
        return await bot.stop()

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
            doc = fitz.open(dl_path)
            for n in range(len(doc)):
                pg = doc.load_page(n)
                pg.get_pixmap(dpi=150).save(os.path.join(inp, f"page_{n:03d}.png"))
            doc.close()
        else:
            shutil.copy(dl_path, inp)
    except zipfile.BadZipFile:
        await edit("❌ **Subsystem Corrupted Error | Unrecognized ZIP format detected.**")
        return await bot.stop()

    pages = [os.path.join(r,f) for r,_,fs in os.walk(inp) for f in fs if f.lower().endswith(('.png','.jpg','.jpeg','.webp','.bmp'))]
    if not pages:
        await edit("❌ Unrecognized graphical frames (Ensure structural paths enclose images).")
        return await bot.stop()

    lang_display = "Hinglish NLP Model" if LANG == "hienglish" else "English Vector NLP"
    await edit(f"🔄 **Engine Routing Initialized** {len(pages)} Sequence Units | {lang_display} | Utilizing Dynamic {len(GEMINI_KEYS)} APIs Load Balancer! ✨")

    ok, provider_msg, full_log = await run_translator_with_fallback(inp, out, ws)

    if not ok:
        fail_msg = f"⚠️ **FATAL FRAME ERROR | Internal Request Crash:**\n\n😔 Diagnostics Output Dump\n\n_Logs:_ `{full_log[-350:]}`"
        await edit(fail_msg)
        return await bot.stop()

    await edit(f"🎨 **Visual Output Sequence Complete | Rendering Archive Format Mode...**")

    files = sorted([os.path.join(r,f) for r,_,fs in os.walk(out) for f in fs if f.lower().endswith(('.png','.jpg','.jpeg','.webp'))])
    
    final_file = "translated_" + FNAME if ext in [".zip",".cbz",".pdf"] else files[0]
    
    if ext in [".zip",".cbz"]:
        with zipfile.ZipFile(final_file,'w',zipfile.ZIP_DEFLATED) as z:
            for f in files: z.write(f, os.path.relpath(f,out))
    elif ext == ".pdf":
        from PIL import Image
        imgs = [Image.open(f).convert('RGB') for f in files]
        if imgs: imgs[0].save(final_file, save_all=True, append_images=imgs[1:])

    file_size_mb = os.path.getsize(final_file) / (1024*1024)
    if file_size_mb > 1900:
        await edit(f"❌ **File too big {file_size_mb:.1f} MB** Transmission Payload Aborted.")
        return await bot.stop()

    caption = f"✅ **Processed Sequence Engine: [{provider_msg}]**\n🌐 Network Node: {lang_display}  \n⚙️ Protocol Structure: {STYLE}"
    try:
        await bot.send_document(CHAT_ID, final_file, caption=caption)
        try: await bot.delete_messages(CHAT_ID, MSG_ID)
        except: pass
    except Exception as e:
        await edit(f"❌ Telegram MTProto Client Upload Failure: {e}")

    shutil.rmtree(ws, ignore_errors=True)
    try: os.remove(dl_path)
    except: pass
    try:
        if ext in [".zip",".cbz",".pdf"]: os.remove(final_file)
    except: pass
    await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
