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

# Safe Channel Bypass Fix
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

raw_keys = os.getenv("gemini_keys", "")
GEMINI_KEYS = [k.strip() for k in raw_keys.split(",") if k.strip()]

print(f"=== DEEP-ANNELISE START [LANG: {LANG}] | FILE: {FNAME} ===")
print(f"✅ ACTIVATING BALANCER | LOADED KEYS: {len(GEMINI_KEYS)}\n")

if not BOT_TOKEN or len(BOT_TOKEN) < 10 or not API_ID:
    print("❌ CRITICAL ERROR: GitHub Secrets (API_ID, BOT_TOKEN) missing. Job Aborted!")
    sys.exit(1)

# =================================================================
# ⚙️ 1. THREAD-SAFE ROUND-ROBIN DISTRIBUTOR (THE 429 MANAGER)
# =================================================================
class SafekeyManager:
    """Multi-Threading Safe Distributor - Prevents API key corruption overlapping"""
    def __init__(self, keys):
        self.lock = threading.Lock()
        self.cycle = itertools.cycle(keys) if keys else None

    def pop_key(self):
        with self.lock:
            return next(self.cycle) if self.cycle else None

api_balancers = SafekeyManager(GEMINI_KEYS)

# =================================================================
# 🧠 2. DYNAMIC MODEL RESOLVER DATABASE (THE 404 DESTROYER)
# =================================================================
MODEL_CACHE = {} 
MODEL_LOCK = threading.Lock()

def grab_certified_gemini_model(api_key):
    """Dynamically asks Google exactly which Model exists on YOUR key to prevent 404 Discontinuity."""
    with MODEL_LOCK:
        if api_key in MODEL_CACHE:
            return MODEL_CACHE[api_key]
            
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    target = "gemini-2.0-flash" # Safe default constraint
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            # Find all model nodes capable of native structural content execution:
            active_clusters = [ m['name'].replace('models/', '') for m in data.get('models', []) 
                                if 'generateContent' in m.get('supportedGenerationMethods', [])]
            
            if active_clusters:
                # Always grab Top Tier active Flash, ignores Deprecated Pro
                flashes = [c for c in active_clusters if 'flash' in c.lower() and 'lite' not in c.lower()]
                flashes.sort(reverse=True)
                target = flashes[0] if flashes else active_clusters[-1]
                
    except Exception as e:
        print(f"⚠️ Dynamic Modeler Warning! Assuming latest node endpoint. Err: {e}")
        
    with MODEL_LOCK:
        MODEL_CACHE[api_key] = target
    return target

# =================================================================
# 🛡️ 3. LOCAL PROTOCOL PROXY SYSTEM (ROUTING MTPE INTO GEMINI NATIVE)
# =================================================================
PROXY_PORT = 11434

class ProxyHTTPRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Disabling default Webserver Log Print Triggers 

    def do_GET(self):
        # Keeps MTPE Library thinking its verifying GPT-3.
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
            
            sys_prompt = ""
            user_prompt = ""
            for m in req_data.get('messages', []):
                if m.get('role') == 'system':
                    sys_prompt += m.get('content', '') + "\n"
                else:
                    user_prompt += m.get('content', '') + "\n"
            
            # Formally Built 100% Google Gemini Native Payload Specification
            gemini_payload = {
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": {"temperature": temperature}
            }
            if sys_prompt.strip():
                # BUGFIX: Changed schema into Valid REST representation 'system_instruction' 
                gemini_payload["system_instruction"] = {"parts": [{"text": sys_prompt}]}
                
            native_body = json.dumps(gemini_payload).encode('utf-8')
            
            success = False
            last_err_body = b'{}'
            last_http_code = 500
            
            # Attempt Recovery Network: Swaps 10 Keys multiple times 
            max_pings = (len(GEMINI_KEYS) * 2) + 2 
            
            for index in range(max_pings):
                primary_key = api_balancers.pop_key() 
                if not primary_key: break
                
                # Fetch EXACT model verified existing for THIS assigned api_key. No guessing!
                verified_modelstr = grab_certified_gemini_model(primary_key)
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{verified_modelstr}:generateContent?key={primary_key}"
                req = urllib.request.Request(url, data=native_body, method='POST')
                req.add_header('Content-Type', 'application/json')
                
                try:
                    with urllib.request.urlopen(req) as resp:
                        gemini_reply = json.loads(resp.read().decode('utf-8'))
                        success = True
                        break # Node Translate confirmed OK!
                        
                except urllib.error.HTTPError as h_err:
                    last_http_code = h_err.code
                    last_err_body = h_err.read()
                    
                    if last_http_code == 429: # Resource Load Empty Request
                        time.sleep(2) # Give proxy a sec before sweeping keys
                        continue 
                    elif last_http_code in (404, 400):  
                        # Hard Deprecated / Model Flaw. Reset cache block and try swap!
                        if primary_key in MODEL_CACHE: del MODEL_CACHE[primary_key]
                        continue
                    else:
                        time.sleep(1) # E.g 500 Internals Breakage limits
                        continue
            
            if not success:
               self.send_response(last_http_code)
               self.send_header('Content-Type', 'application/json')
               self.end_headers()
               self.wfile.write(last_err_body)
               return
               
            # Final Output Formatter
            try:
                extraction = gemini_reply.get('candidates', [])[0]['content']['parts'][0]['text']
            except (KeyError, IndexError):
                extraction = "[DeepAnnelise: Format Parse Corrupted]"
                
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
    # Wake up Protocol Environment Network Node 
    proxy_system = ThreadingHTTPServer(('127.0.0.1', PROXY_PORT), ProxyHTTPRequestHandler)
    threading.Thread(target=proxy_system.serve_forever, daemon=True).start()

# =================================================================
# 🧬 4. BATCH TRIGGER AND MTPE EXECUTION CORE
# =================================================================
async def run_translator_with_fallback(input_dir, output_dir, workspace):
    cwd_dir = "manga-image-translator" if os.path.exists("manga-image-translator") else None
    if not GEMINI_KEYS:
        return False, "Failed", "WARNING! Empty Database Request -> 0 Keys Supplied! Please inject keys via /addapi"

    style_flags = ["--manga2eng"] if STYLE == "style2" else []
    
    # Force injection parameter redirector over localhost Protocol
    os.environ["OPENAI_API_KEY"] = "sk-interception.system"
    os.environ["OPENAI_API_BASE"] = f"http://127.0.0.1:{PROXY_PORT}/v1"
    os.environ["OPENAI_BASE_URL"] = f"http://127.0.0.1:{PROXY_PORT}/v1"

    gpt_config_path = os.path.join(workspace, "gpt_config.yml")
    
    # Internal Framework NLP Processing 
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

    # Boot the sequence utilizing fake "GPT3.5" to trigger the trap. 
    cli_cmd = ["python", "-m", "manga_translator", "-i", input_dir, "--dest", output_dir, "--translator", "gpt3.5", "-l", "ENG", "--gpt-config", gpt_config_path] + style_flags
    if os.path.exists(output_dir): shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    proc = await asyncio.create_subprocess_exec(*cli_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=cwd_dir)
    out, _ = await proc.communicate()
    log = out.decode('utf-8', errors='ignore')

    cnt_results = 0
    if os.path.exists(output_dir):
        base_results = [f for root, _, fx in os.walk(output_dir) for f in fx if f.lower().endswith(('.png','.jpg','.jpeg','.webp'))]
        cnt_results = len(base_results)

    print(f">> Translation Yield Finalised -> ReturnCode {proc.returncode} | Output Matrices Generated: {cnt_results}")

    if proc.returncode == 0 and cnt_results > 0:
        return True, "DEEP ANNELISE GEMINI NATIVE ENGINE", log
    
    return False, "Failed", log

# =================================================================
# 📥 5. PRIMARY ENDPOINT FRAME (TELEGRAM BOT DOWNLOAD MANAGER)
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
    for attempt_seq in range(1, 6):
        try:
            dl_path = await tg_bot.download_media(FILE_ID)
            if dl_path and os.path.exists(dl_path) and os.path.getsize(dl_path) > 1024:
                break
            await asyncio.sleep(2)
        except BaseException as B_EX:
            await e_msg(f"⚠️ **Transmission Frame Dropout {attempt_seq}/5** Relaying Request...")
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

    lang_ux = "Hinglish NLP Interface Target" if LANG == "hienglish" else "English Vector Standardize"
    await e_msg(f"🔄 **Engine Routing Initialised | Visual Nodes: {len(pages)}** [NLP Protocol: {lang_ux}] ✨\n_Utilizing Dynamic Network Node Balancing Mode._")

    success_bool, prvd_ui, full_core_log = await run_translator_with_fallback(inp, out, ws)

    if not success_bool:
        err_out = f"⚠️ **ALL KEYS CRASHED (Limit Complete Exhaustion) / Model Denied Server Error:**\n\n😔 Diagnostics Output Dump\n\n_Logs:_ `{full_core_log[-450:]}`"
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
        await e_msg(f"❌ **Package Maxed Overweight Payload -> {sbslmt_zpb:.1f} MB** | 2GB Over MTProto Threshold limit broken.")
        return await tg_bot.stop()

    endcap_caption = f"✅ **Processing Operation Completed**\n🌐 Network Node Format: {lang_ux}\n⚡ Execution Handler Node: [Auto Balance Keys & Models Native]\n"
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
