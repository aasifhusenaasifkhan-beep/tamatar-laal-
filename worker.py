import os
import sys
import zipfile
import shutil
import asyncio
import json
import threading
import urllib.request
import urllib.error
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

GEMINI_KEYS = [k.strip() for k in os.getenv("gemini_keys", "").split(",") if k.strip()]

print(f"=== START LANG:{LANG} FILE:{FNAME} ===")
print(f"KEYS RECEIVED FROM HF DB: {len(GEMINI_KEYS)}")

# Error Catching Logic
if not BOT_TOKEN or len(BOT_TOKEN) < 10:
    print("❌ CRITICAL ERROR: BOT_TOKEN is missing or invalid in GitHub Secrets!")
    sys.exit(1)
if not API_ID or API_ID == 0:
    print("❌ CRITICAL ERROR: API_ID is missing in GitHub Secrets!")
    sys.exit(1)

LIMIT_KEYWORDS = ["429", "rate limit", "quota", "limit exceeded", "resource exhausted", "too many requests", "billing", "free quota", "missingapikey"]

def is_limit_error(text):
    return any(k in text.lower() for k in LIMIT_KEYWORDS)

def mask_key(key):
    return f"...{key[-4:]}" if len(key) > 6 else "***"

# =================================================================
# 🚀 LOCAL PROXY INTERCEPTOR (THE ULTIMATE FIX FOR 404 NOT_FOUND)
# =================================================================
PROXY_PORT = 11434
CURRENT_GEMINI_KEY = ""

class ProxyHTTPRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Logs hide karega taaki output clean rahe

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            data = json.loads(body)
            # MAGIC PATCH: Payload me model name ko forcefully Gemini bana dega
            data['model'] = 'gemini-1.5-flash'
            # Gemini jo arguments support nahi karta unhe hata dega
            data.pop('frequency_penalty', None)
            data.pop('presence_penalty', None)
            data.pop('user', None)
            data.pop('seed', None)
            body = json.dumps(data).encode('utf-8')
        except Exception:
            pass
        
        # Route directly to Google Gemini's endpoint
        url = 'https://generativelanguage.googleapis.com/v1beta/openai/v1/chat/completions'
        req = urllib.request.Request(url, data=body, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', f'Bearer {CURRENT_GEMINI_KEY}')
        
        try:
            with urllib.request.urlopen(req) as response:
                resp_body = response.read()
                self.send_response(response.status)
                for k, v in response.headers.items():
                    if k.lower() not in ['transfer-encoding', 'content-encoding']:
                        self.send_header(k, v)
                self.end_headers()
                self.wfile.write(resp_body)
        except urllib.error.HTTPError as e:
            resp_body = e.read()
            self.send_response(e.code)
            for k, v in e.headers.items():
                if k.lower() not in ['transfer-encoding', 'content-encoding']:
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(resp_body)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8'))

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

# Start local proxy in background
server = ThreadingHTTPServer(('127.0.0.1', PROXY_PORT), ProxyHTTPRequestHandler)
threading.Thread(target=server.serve_forever, daemon=True).start()
# =================================================================

async def run_translator_with_fallback(input_dir, output_dir, workspace):
    global CURRENT_GEMINI_KEY
    cwd_dir = "manga-image-translator" if os.path.exists("manga-image-translator") else None

    if not GEMINI_KEYS:
        return False, "Failed", "No API left in Database, please add using /addapi."

    style_flags = ["--manga2eng"] if STYLE == "style2" else []
    last_log = ""

    for idx, api_key in enumerate(GEMINI_KEYS):
        print(f"[{idx+1}/{len(GEMINI_KEYS)}] Trying GEMINI API (Key: {mask_key(api_key)})")
        
        CURRENT_GEMINI_KEY = api_key
        
        # Traffic ko Local Proxy pe bhejna (jo theek se rewrite karke Gemini pe bhej dega)
        os.environ["OPENAI_API_KEY"] = "sk-fake-key"
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

        cli_cmd = ["python", "-m", "manga_translator", "-i", input_dir, "--dest", output_dir, "--translator", "gpt3.5", "-l", "ENG", "--gpt-config", gpt_config_path] + style_flags

        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        proc = await asyncio.create_subprocess_exec(*cli_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=cwd_dir)
        out, _ = await proc.communicate()
        log = out.decode('utf-8', errors='ignore')
        last_log = log

        cnt = 0
        if os.path.exists(output_dir):
            for r,_,fs in os.walk(output_dir):
                cnt += len([f for f in fs if f.lower().endswith(('.png','.jpg','.jpeg','.webp'))])

        print(f"Return code {proc.returncode}, images generated: {cnt}")

        if proc.returncode == 0 and cnt > 0:
            return True, "GEMINI", log
        else:
            if is_limit_error(log) or "invalid" in log.lower() or "unauthorized" in log.lower() or "not_found" in log.lower():
                print(f"Key LIMIT / DEAD / 404 Error. Shifting to next API key...")
                continue
            else:
                print(f"Translation Error. Shifting anyway... \n{log[-400:]}")
                continue

    return False, "Failed", last_log

async def main():
    if not FILE_ID: return
    bot = Client("Worker", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, no_updates=True)
    await bot.start()
    async def edit(t):
        try: await bot.edit_message_text(CHAT_ID, MSG_ID, t)
        except: pass

    await edit(f"⏳ **Downloading {FNAME}...**")

    dl_path = None
    for i in range(1,6):
        try:
            dl_path = await bot.download_media(FILE_ID)
            if dl_path and os.path.exists(dl_path) and os.path.getsize(dl_path) > 1024:
                break
            await asyncio.sleep(3)
        except Exception as e:
            await edit(f"⚠️ **Retry {i}/5** downloading...")
            await asyncio.sleep(5)

    if not dl_path or not os.path.exists(dl_path):
        await edit("❌ **Download failed after 5 retries.**")
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
                doc.load_page(n).get_pixmap(dpi=150).save(os.path.join(inp, f"page_{n:03d}.png"))
            doc.close()
        else:
            shutil.copy(dl_path, inp)
    except zipfile.BadZipFile:
        await edit("❌ **BadZipFile** - Download corrupt. Dubara bhejo.")
        return await bot.stop()

    pages = [os.path.join(r,f) for r,_,fs in os.walk(inp) for f in fs if f.lower().endswith(('.png','.jpg','.jpeg','.webp','.bmp'))]
    if not pages:
        await edit("❌ No images inside zip")
        return await bot.stop()

    lang_display = "Hindi (Roman / Hinglish)" if LANG == "hienglish" else "English"
    await edit(f"🔄 **AI Translating** {len(pages)} panels | {lang_display} | Gemini API")

    ok, provider_msg, full_log = await run_translator_with_fallback(inp, out, ws)

    if not ok:
        fail_msg = f"⚠️ **Translation / API Error:**\n\n😔 System ne koshish ki par translate nahi ho paya.\n\n_Logs:_ `{full_log[-300:]}`"
        await edit(fail_msg)
        return await bot.stop()

    await edit(f"🎨 **Done with {provider_msg}** - Uploading...")

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
        await edit(f"❌ **File too big {file_size_mb:.1f} MB** > 2GB Telegram limit")
        return await bot.stop()

    caption = f"✅ **Done! [Gemini]** 🌐 {lang_display} | {STYLE}"
    try:
        await bot.send_document(CHAT_ID, final_file, caption=caption)
        try: await bot.delete_messages(CHAT_ID, MSG_ID)
        except: pass
    except Exception as e:
        await edit(f"❌ Upload failed: {e}")

    shutil.rmtree(ws, ignore_errors=True)
    try: os.remove(dl_path)
    except: pass
    try:
        if ext in [".zip",".cbz",".pdf"]: os.remove(final_file)
    except: pass
    await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
