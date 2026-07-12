 import os
import sys
import zipfile
import shutil
import asyncio
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

print(f"=== DEEP-ANNELISE MANUAL MTPE [LANG: {LANG}] | USER MAPPED: {USER_ID} ===")
if not BOT_TOKEN or not API_ID:
    print("❌ CRITICAL ERROR: GitHub Secrets parameters missing!")
    sys.exit(1)


# =========================================================================================
# 🧬 1. HUMAN INTERVENTION INJECTION SHELL 
# Humare python Github Environment mein yeh script "manga_translator" k under bypass chipkayga
# ==========================================================================================

ROUTINE_SCRIPT_BYPASSER = """
import os
import re
import asyncio
import time
from pyrogram import Client
from .base import BaseTranslator

class HumanInterventionTranslator(BaseTranslator):
    def __init__(self):
        super().__init__()
        self.sys_token = os.environ.get("ENV_BOT_TOKEN")
        self.a_idx = int(os.environ.get("ENV_API_ID"))
        self.a_hash = os.environ.get("ENV_API_HASH")
        self.cst_uid = int(os.environ.get("ENV_USER_ID"))
        self.chk_chn = -1003700822969

    async def translate(self, queries, sl, tl, **kwargs):
        if not queries: return queries
        
        print(f"\\n🔥 [Deep-Annelise] Frame Interceptor triggered! Intersecting {len(queries)} dialogue rows.")
        out_rows = []
        for nx, qrs in enumerate(queries):
            r_x = nx + 1
            out_rows.append(f"{r_x:02d}")
            qrs_c = str(qrs).replace('\\n', ' ')
            out_rows.append(f"{{{self.cst_uid}}}tutty{r_x:02d}({qrs_c})\\n")
            
        xport_nm = f"FrameExtr_{self.cst_uid}.txt"
        with open(xport_nm, "w", encoding="utf-8") as op_w:
            op_w.write("\\n".join(out_rows))
            
        print(">> Launching Independent Relay client connecting directly toward End-User interface...")
        MT_Agent = Client(f"Agnt_{time.time()}", api_id=self.a_idx, api_hash=self.a_hash, bot_token=self.sys_token, in_memory=True, no_updates=True)
        await MT_Agent.start()
        
        dirctn = f"📝 **Frames Disassembled Fully!**\\n\\n1️⃣ Open & Edit this mapped '.txt' file.\\n2️⃣ Translate text localized purely enclosed in `( )`.\\n3️⃣ DO NOT alter specific node tagging formatting loops like `{{..}}tutty`.\\n4️⃣ Resend updated document cleanly back to bot to trigger Engine Continuation Render! (Upto ~12 Mins Timer)"
        await MT_Agent.send_document(self.cst_uid, xport_nm, caption=dirctn)
        
        # Establishing Wait Engine Protocol Frame Limits
        translated_layer_dump = [raw for raw in queries] 
        fxd_capture = False
        
        print(">> Suspending active GitHub workflow processes & Awaiting Return Packets.....")
        
        # Loop Check runs approx intervals of 15 seconds up to 12 mins. (GitHub limit 360m safe)
        for interval in range(50):
            await asyncio.sleep(15) 
            target_hit = None
            async for dm in MT_Agent.search_messages(self.chk_chn, query=f"#TXTDONE_{self.cst_uid}", limit=1):
                target_hit = dm
                break
                
            if target_hit and target_hit.document:
                downl = await MT_Agent.download_media(target_hit)
                try:
                    with open(downl, "r", encoding="utf-8") as rf:
                        txt_val = rf.read()
                        
                    ptn = r"\\{" + str(self.cst_uid) + r"\\}tutty(\d+)\((.*?)\)"
                    matched = re.findall(ptn, txt_val, re.DOTALL)
                    
                    for (mcr_s, passd) in matched:
                        loc_i = int(mcr_s) - 1
                        if 0 <= loc_i < len(translated_layer_dump):
                            translated_layer_dump[loc_i] = passd.strip()
                            
                    await target_hit.delete()
                    fxd_capture = True
                    print("\\n>> [YES] External Load Accepted. Realigning rendering engine formats.")
                    break
                except Exception as SysERR:
                    print("Parse error on user formatting structure -> ", SysERR)
                    
        await MT_Agent.stop()
        
        if not fxd_capture:
            print(f">> [!] CRITICAL | Human Protocol Timed-Out after 12 Mins! Passing blank translations sequence to complete safely...")
            
        return translated_layer_dump

# MAGIC MAPPING (Destroy external APIs defaults routing our Script Node internally overriding engine)
class GPT3Translator(HumanInterventionTranslator): pass
class GPT35Translator(HumanInterventionTranslator): pass
class GPT4Translator(HumanInterventionTranslator): pass
"""

# =================================================================
# 🛡️ 2. EXECUTOR LOGIC ENGINE 
# =================================================================
async def run_translator_with_fallback(input_dir, output_dir, workspace):
    cwd_dir = "manga-image-translator" if os.path.exists("manga-image-translator") else None

    # Sending required isolated variables direct access layer inside subprocess
    os.environ["ENV_USER_ID"] = str(USER_ID)
    os.environ["ENV_API_HASH"] = str(API_HASH)
    os.environ["ENV_API_ID"] = str(API_ID)
    os.environ["ENV_BOT_TOKEN"] = str(BOT_TOKEN)

    # Injector Runtime
    if cwd_dir:
        core_lib_node = os.path.join(cwd_dir, "manga_translator", "translators", "gpt3.py")
        if os.path.exists(core_lib_node):
            with open(core_lib_node, "w", encoding="utf-8") as injectn:
                injectn.write(ROUTINE_SCRIPT_BYPASSER)
            print("💥 DEEP-ANNELISE V-2 FRAME INJECTOR Executed Correctly!")

    style_flags = ["--manga2eng"] if STYLE == "style2" else []
    
    # Observe '--translator gpt3' argument. Since Lib relies on it it intercepts ours Native Module script Code directly!! No internet needed!
    cli_cmd = ["python", "-m", "manga_translator", "-i", input_dir, "--dest", output_dir, "--translator", "gpt3", "-l", "ENG"] + style_flags
    
    if os.path.exists(output_dir): shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    proc = await asyncio.create_subprocess_exec(*cli_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=cwd_dir)
    out, _ = await proc.communicate()
    log = out.decode('utf-8', errors='ignore')

    cnt_results = 0
    if os.path.exists(output_dir):
        base_results = [f for r, _, fx in os.walk(output_dir) for f in fx if f.lower().endswith(('.png','.jpg','.jpeg','.webp'))]
        cnt_results = len(base_results)

    print(f">> Subprocess Operation Status Check | RtnCode {proc.returncode} | Output Asssts Loaded: {cnt_results}")

    if proc.returncode == 0 and cnt_results > 0:
        return True, "DEEP ANNELISE IN-LOOP SYSTEM ✨", log
    
    return False, "Failed", log

# =================================================================
# 📥 3. PRIMARY TELEGRAM OUTPUT ARCHIVER 
# =================================================================
async def main():
    if not FILE_ID: 
        print("Empty File Matrix ID Found") return 
    tg_bot = Client("WorkerMaster", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, no_updates=True)
    await tg_bot.start()
    async def e_msg(s_t):
        try: await tg_bot.edit_message_text(CHAT_ID, MSG_ID, s_t)
        except: pass

    await e_msg(f"⏳ **Sequence Target Acquired** Format Init Pull...")

    dl_path = None
    for attempt in range(1, 6):
        try:
            dl_path = await tg_bot.download_media(FILE_ID)
            if dl_path and os.path.exists(dl_path) and os.path.getsize(dl_path) > 1024:
                break
            await asyncio.sleep(2)
        except BaseException:
            await e_msg(f"⚠️ **Network Dropout Phase {attempt}/5** | Retrying Target Link...")
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
                pdf_pg = pdf_layer.load_page(znc_n)
                pdf_pg.get_pixmap(dpi=150).save(os.path.join(inp, f"page_{znc_n:03d}.png"))
            pdf_layer.close()
        else:
            shutil.copy(dl_path, inp)
    except zipfile.BadZipFile:
        await e_msg("❌ **Format File Internal Structure Protocol Rejection Dump.**")
        return await tg_bot.stop()

    pages = [os.path.join(r,f) for r,_,fs in os.walk(inp) for f in fs if f.lower().endswith(('.png','.jpg','.jpeg','.webp','.bmp'))]
    if not pages: return await tg_bot.stop()

    await e_msg(f"🔄 **Optical Layer Injection Stand-By:** {len(pages)} Extracting... Engine has handed Control to Human External Protocol Matrix.")

    success_bool, prvd_ui, full_core_log = await run_translator_with_fallback(inp, out, ws)

    if not success_bool:
        err_out = f"⚠️ **FATAL COMPILER DENIAL LOOP TIMEOUT**\nRender system force halted sequences.\n\n_System Diagnostics:_ `{full_core_log[-450:]}`"
        await e_msg(err_out)
        return await tg_bot.stop()

    await e_msg(f"🎨 **Translation Input Render Alignment Started.** Creating ZIP Layout...")

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
        await e_msg(f"❌ **Package Data Threshold Met -> {sbslmt_zpb:.1f} MB** Limited Access Payload Blocked.")
        return await tg_bot.stop()

    endcap_caption = f"✅ **Processing Repacked Success!**\n⚡ Control Type: Manual Human Output Render Logic MTPE\n"
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
