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
from pyrogram import Client
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

FILE_ID = os.getenv("FILE_ID", "").strip()
CHAT_ID = int(os.getenv("CHAT_ID", "0"))
MSG_ID = int(os.getenv("MSG_ID", "0"))
LANG = os.getenv("LANG", "english").strip().lower()
STYLE = os.getenv("STYLE", "style1").strip()
FNAME = os.getenv("FNAME", "translated_manga.zip").strip()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "").strip()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

raw_keys = os.getenv("gemini_keys", "")
GEMINI_KEYS = [k.strip() for k in raw_keys.split(",") if k.strip()]

print(f"=== DEEP-ANNELISE START [LANG: {LANG}] | FILE: {FNAME} ===")
print(f"✅ ACTIVATING AUTO-HEALING BALANCER | LOADED KEYS: {len(GEMINI_KEYS)}\n")

if not BOT_TOKEN or not API_ID:
    print("❌ CRITICAL ERROR: GitHub Secrets missing. Job Aborted!")
    sys.exit(1)

# =================================================================
# ⚙️ 1. RATE LIMITER & KEY ROTATOR 
# =================================================================
class SafeRateLimiter:
    def __init__(self, keys):
        self.keys = keys
        self.lock = threading.Lock()
        self.idx = 0
        self.delay_between_requests = 60.0 / (14 * max(1, len(keys))) 
        self.last_call = 0.0

    def get_key_and_wait(self):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_call
            if elapsed < self.delay_between_requests:
                time.sleep(self.delay_between_requests - elapsed)
            self.last_call = time.time()
            key = self.keys[self.idx]
            self.idx = (self.idx + 1) % len(self.keys)
            return key

api_balancer = SafeRateLimiter(GEMINI_KEYS)

# =================================================================
# 🛡️ 2. AUTO-HEALING PROTOCOL PROXY (BULLETPROOF FIX)
# =================================================================
PROXY_PORT = 11434

# If one model throws a 404, it instantly tests the next one.
MODELS_TO_TEST = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.0-pro"]

class ProxyHTTPRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass 

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"object": "list", "data": [{"id": "gpt-3.5-turbo"}]}).encode('utf-8'))

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            req_data = json.loads(body)
            temperature = req_data.get('temperature', 0.3)
            sys_prompt, user_prompt = "", ""
            
            for m in req_data.get('messages', []):
                if m.get('role') == 'system':
                    sys_prompt += m.get('content', '') + "\n"
                else:
                    user_prompt += m.get('content', '') + "\n"
            
            gemini_payload = {
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": {"temperature": temperature}
            }
            if sys_prompt.strip():
                gemini_payload["system_instruction"] = {"parts": [{"text": sys_prompt.strip()}]}
                
            native_body = json.dumps(gemini_payload).encode('utf-8')
            
            success = False
            last_err_body = b'{}'
            last_http_code = 500
            
            # Auto-Healing Loop: Try different keys and models until one works
            for attempt in range(len(GEMINI_KEYS) * 2):
                primary_key = api_balancer.get_key_and_wait()
                
                for model_name in MODELS_TO_TEST:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={primary_key}"
                    req = urllib.request.Request(url, data=native_body, method='POST')
                    req.add_header('Content-Type', 'application/json')
                    
                    try:
                        with urllib.request.urlopen(req) as resp:
                            gemini_reply = json.loads(resp.read().decode('utf-8'))
                            extraction = gemini_reply.get('candidates', [])[0]['content']['parts'][0]['text']
                            success = True
                            break # Success! Break model loop
                            
                    except urllib.error.HTTPError as h_err:
                        last_http_code = h_err.code
                        last_err_body = h_err.read()
                        
                        if last_http_code in [404, 400]:
                            continue # Model not found, try the next model in the list instantly
                        elif last_http_code in [429, 403]:
                            break # Rate limited or key banned, break model loop, try next API key
                
                if success:
                    break # Break retry loop
            
            if not success:
                self.send_response(last_http_code)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(last_err_body)
                return
               
            reconstructed_op = {
                "id": "chatcmpl-native-gemini-protocol",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "gpt-3.5-turbo",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": extraction}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(reconstructed_op).encode('utf-8'))
            
        except Exception as Ex:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(Ex).encode('utf-8'))

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer): daemon_threads = True

if GEMINI_KEYS:
    proxy_system = ThreadingHTTPServer(('127.0.0.1', PROXY_PORT), ProxyHTTPRequestHandler)
    threading.Thread(target=proxy_system.serve_forever, daemon=True).start()

# =================================================================
# 🧬 3. MTPE EXECUTION CORE
# =================================================================
async def run_translator_with_fallback(input_dir, output_dir, workspace):
    cwd_dir = "manga-image-translator" if os.path.exists("manga-image-translator") else None
    style_flags = ["--manga2eng"] if STYLE == "style2" else []
    
    os.environ["OPENAI_API_KEY"] = "sk-interception.system"
    os.environ["OPENAI_API_BASE"] = f"http://127.0.0.1:{PROXY_PORT}/v1"
    os.environ["OPENAI_BASE_URL"] = f"http://127.0.0.1:{PROXY_PORT}/v1"

    gpt_config_path = os.path.join(workspace, "gpt_config.yml")
    
    if LANG == "hienglish":
        cfg = """gpt3.5:
  temperature: 0.3
  prompt_template: "Translate to Hinglish: "
  chat_system_template: "You are a professional manga translator. You MUST translate the text into Hinglish (Hindi written using English alphabets). Example: 'What are you doing?' -> 'Tum kya kar rahe ho?'. DO NOT use Devanagari script (like 'मैं'). Only output the translated Hinglish text."
"""
    else:
        cfg = """gpt3.5:
  temperature: 0.3
  prompt_template: "Translate to English: "
  chat_system_template: "You are a professional manga translator. Accurately translate the text to natural-sounding English. Only output the translated text."
"""
    with open(gpt_config_path, "w", encoding="utf-8") as f: f.write(cfg)

    cli_cmd = ["python", "-m", "manga_translator", "-i", input_dir, "--dest", output_dir, "--translator", "gpt3.5", "-l", "ENG", "--gpt-config", gpt_config_path] + style_flags
    if os.path.exists(output_dir): shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    proc = await asyncio.create_subprocess_exec(*cli_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=cwd_dir)
    out, _ = await proc.communicate()
    log = out.decode('utf-8', errors='ignore')

    cnt_results = len([f for root, _, fx in os.walk(output_dir) for f in fx if f.lower().endswith(('.png','.jpg','.jpeg','.webp'))]) if os.path.exists(output_dir) else 0

    if proc.returncode == 0 and cnt_results > 0:
        return True, "DEEP ANNELISE ENGINE", log
    return False, "Failed", log

# =================================================================
# 📥 4. TELEGRAM BOT DOWNLOAD MANAGER
# =================================================================
async def main():
    if not FILE_ID: return
    tg_bot = Client("Worker", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, no_updates=True)
    await tg_bot.start()
    
    async def e_msg(s_t):
        try: await tg_bot.edit_message_text(CHAT_ID, MSG_ID, s_t)
        except: pass

    await e_msg(f"⏳ **Extraction Layer Processing Archive: {FNAME}...**")

    dl_path = None
    for attempt_seq in range(1, 4):
        try:
            dl_path = await tg_bot.download_media(FILE_ID)
            if dl_path and os.path.exists(dl_path) and os.path.getsize(dl_path) > 1024: break
            await asyncio.sleep(2)
        except BaseException:
            await e_msg(f"⚠️ **Download retry {attempt_seq}/3**")
            await asyncio.sleep(3)

    if not dl_path or not os.path.exists(dl_path): return await tg_bot.stop()

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
                pdf_layer.load_page(znc_n).get_pixmap(dpi=150).save(os.path.join(inp, f"page_{znc_n:03d}.png"))
            pdf_layer.close()
        else: shutil.copy(dl_path, inp)
    except zipfile.BadZipFile:
        await e_msg("❌ **Core Error | Archive Data Corrupted.**")
        return await tg_bot.stop()

    pages = [os.path.join(r,f) for r,_,fs in os.walk(inp) for f in fs if f.lower().endswith(('.png','.jpg','.jpeg','.webp','.bmp'))]
    if not pages: return await tg_bot.stop()

    await e_msg(f"🔄 **Translating {len(pages)} Pages...**\n_Auto-Healing Proxy Active (Bypassing 404s)_ ✨")

    success_bool, prvd_ui, full_core_log = await run_translator_with_fallback(inp, out, ws)

    if not success_bool:
        await e_msg(f"⚠️ **TRANSLATION FAILED:**\n`{full_core_log[-450:]}`")
        return await tg_bot.stop()

    await e_msg("🎨 **Compilation Finished.** | Zipping file...")

    finals_l = sorted([os.path.join(r,f) for r,_,fs in os.walk(out) for f in fs if f.lower().endswith(('.png','.jpg','.jpeg','.webp'))])
    zipx_out = "translated_" + FNAME if ext in [".zip",".cbz",".pdf"] else finals_l[0]
    
    if ext in [".zip",".cbz"]:
        with zipfile.ZipFile(zipx_out,'w',zipfile.ZIP_DEFLATED) as z_enc:
            for fd_c in finals_l: z_enc.write(fd_c, os.path.relpath(fd_c, out))
    elif ext == ".pdf":
        from PIL import Image
        px_i_set = [Image.open(p).convert('RGB') for p in finals_l]
        if px_i_set: px_i_set[0].save(zipx_out, save_all=True, append_images=px_i_set[1:])

    sbslmt_zpb = os.path.getsize(zipx_out) / (1024*1024)
    if sbslmt_zpb > 1900:
        await e_msg("❌ **File exceeds Telegram 2GB limit.**")
        return await tg_bot.stop()

    try:
        await tg_bot.send_document(CHAT_ID, zipx_out, caption="✅ **Processing Completed**\nPowered by Deep Annelise Auto-Healer")
        try: await tg_bot.delete_messages(CHAT_ID, MSG_ID)
        except: pass
    except Exception: pass

    shutil.rmtree(ws, ignore_errors=True)
    for cleanup in [dl_path, zipx_out]:
        try: os.remove(cleanup) 
        except: pass
    await tg_bot.stop()

if __name__ == "__main__": asyncio.run(main())
