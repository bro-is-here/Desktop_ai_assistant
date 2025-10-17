# robin.py — Robin Ultimate (Complete Laptop Control) - FINAL CLEAN VERSION
# No indentation errors, complete sentences, no flickering, Vosk optimized

import asyncio
import json
import os
import queue
import random
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

import psutil
import speech_recognition as sr
import sounddevice as sd
import soundfile as sf
import tkinter as tk
import vlc
from tkinter import messagebox, scrolledtext

# =============== OPTIONAL IMPORTS ===============
try:
    import pyautogui
    import pyperclip
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.01
    PYAUTOGUI_AVAILABLE = True
except:
    PYAUTOGUI_AVAILABLE = False

try:
    from PIL import ImageGrab, Image
    import pytesseract
    PIL_AVAILABLE = True
    OCR_AVAILABLE = True
except:
    PIL_AVAILABLE = False
    OCR_AVAILABLE = False

try:
    from langdetect import detect as langdetect_detect
    LANGDETECT_AVAILABLE = True
except:
    LANGDETECT_AVAILABLE = False

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except:
    EDGE_TTS_AVAILABLE = False

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except:
    PYTTSX3_AVAILABLE = False

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except:
    GTTS_AVAILABLE = False

try:
    from vosk import Model, KaldiRecognizer
    import wave
    VOSK_AVAILABLE = True
except:
    VOSK_AVAILABLE = False

import config

# =============== OPENAI CLIENT ===============
try:
    from openai import OpenAI
    api_keys = []
    single_key = getattr(config, "OPENAI_API_KEY", None) or getattr(config, "API_KEY", None)
    if single_key:
        api_keys.append(single_key)
    multi_keys = getattr(config, "OPENAI_API_KEYS", None) or getattr(config, "API_KEYS", None)
    if multi_keys and isinstance(multi_keys, list):
        api_keys.extend([k for k in multi_keys if k])
    if api_keys:
        clients = []
        for key in api_keys:
            if key:
                clients.append({"key": key, "client": OpenAI(api_key=key), "active": True})
        if not clients:
            clients = None
    else:
        clients = None
    current_client_idx = 0
    client = None if not clients else clients[0]["client"]
except Exception as e:
    print(f"[OpenAI Error] {e}")
    clients = None
    client = None

# =============== GLOBAL SETTINGS ===============
SAFE_MODE = False
AUTOMATION_DELAY = 0.01
MAX_SCREENSHOT_CONTEXT = 2000
MAX_RETRY_ATTEMPTS = 3
TASK_TIMEOUT = 60

history_lock = threading.Lock()
vlc_lock = threading.Lock()
speech_lock = threading.Lock()
screen_lock = threading.Lock()
tts_lock = threading.Lock()

emotion_lines = {
    "happy": ["Yay!"], "normal": ["Hello!"], "speaking": ["Let me tell you…"],
    "angry": ["Hey!"], "sad": ["Sorry…"], "listening": ["Yes sir?"],
    "excited": ["Wow!"], "thinking": ["Hmm…"], "sleepy": ["*yawn*"]
}

vlc_instance = None
player = None
video_label = None
answer_box = None
status_label = None
input_box = None
tts_model_btn = None
performance_label = None

is_sleeping = False
last_interaction = time.time()
WAKE_WORD = "robin"
listening_mode = "offline"

speech_queue = queue.Queue()
tts_engine = None
edge_voice_en = "en-US-AriaNeural"
edge_voice_hi = "hi-IN-SwaraNeural"

conversation_history = []
MAX_MEMORY = 10
current_personality = "professional"
current_emotion = "normal"

listening_enabled = True
tts_enabled = True
last_spoken_text = ""
tts_model = "pyttsx3"  # Changed default from gtts to pyttsx3 (more reliable)

screen_context_cache = ""
last_screen_read = 0
alarms = []

performance_stats = {
    "tasks_completed": 0,
    "total_execution_time": 0.0,
    "avg_execution_time": 0.0,
    "cpu_usage": 0,
    "memory_usage": 0,
    "monitor_enabled": True
}

# =============== GUI SETUP ===============
root = tk.Tk()
root.title("Robin - Complete Laptop Control AI")
root.geometry("900x1000")
root.minsize(700, 800)
root.configure(bg="#0a0e27")

root.grid_rowconfigure(0, weight=4)
root.grid_rowconfigure(1, weight=0)
root.grid_rowconfigure(2, weight=1)
root.grid_rowconfigure(3, weight=0)
root.grid_rowconfigure(4, weight=0)
root.grid_rowconfigure(5, weight=0)
root.grid_columnconfigure(0, weight=1)

video_frame = tk.Frame(root, bg="#0a0e27", relief="flat")
video_frame.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
video_frame.grid_rowconfigure(0, weight=1)
video_frame.grid_columnconfigure(0, weight=1)

video_label = tk.Label(video_frame, bg="#0a0e27")
video_label.grid(sticky="nsew")

panel_frame = tk.Frame(root, bg="#1a1f3a", relief="ridge", bd=2)
panel_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=8)
panel_frame.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

btn_style = {
    "font": ("Segoe UI", 9, "bold"),
    "relief": "flat",
    "bd": 0,
    "bg": "#2d3561",
    "fg": "#e0e7ff",
    "activebackground": "#3d4578",
    "cursor": "hand2"
}

awake_btn = tk.Button(panel_frame, text="⚡ Awake", **btn_style)
silent_btn = tk.Button(panel_frame, text="🔇 Silent", **btn_style)
mute_btn = tk.Button(panel_frame, text="🎤 Mute", **btn_style)
mode_btn = tk.Button(panel_frame, text="🎭 Mode", **btn_style)
tts_model_btn = tk.Button(panel_frame, text="🌐 gTTS", **btn_style)
monitor_btn = tk.Button(panel_frame, text="📊 Monitor", **btn_style)
listen_mode_btn = tk.Button(panel_frame, text="📴 Offline", **btn_style)
restart_btn = tk.Button(panel_frame, text="🔄 Restart", **btn_style)
sleep_btn = tk.Button(panel_frame, text="😴 Sleep", **btn_style)

emoji_style = {k: v for k, v in btn_style.items() if k != 'font'}
emoji_style['font'] = ("Segoe UI Emoji", 11)
smile_btn = tk.Button(panel_frame, text="😊", **emoji_style)
power_btn = tk.Button(panel_frame, text="⏻", **emoji_style)

awake_btn.grid(row=0, column=0, padx=5, pady=7, sticky="ew")
silent_btn.grid(row=0, column=1, padx=5, pady=7, sticky="ew")
mute_btn.grid(row=0, column=2, padx=5, pady=7, sticky="ew")
mode_btn.grid(row=0, column=3, padx=5, pady=7, sticky="ew")
tts_model_btn.grid(row=0, column=4, padx=5, pady=7, sticky="ew")
monitor_btn.grid(row=0, column=5, padx=5, pady=7, sticky="ew")
listen_mode_btn.grid(row=1, column=4, padx=5, pady=7, sticky="ew")
restart_btn.grid(row=1, column=0, padx=5, pady=7, sticky="ew")
sleep_btn.grid(row=1, column=1, padx=5, pady=7, sticky="ew")
smile_btn.grid(row=1, column=2, padx=5, pady=7, sticky="ew")
power_btn.grid(row=1, column=3, padx=5, pady=7, sticky="ew")

answer_box = scrolledtext.ScrolledText(
    root, height=8, bg="#1a1f3a", fg="#e0e7ff",
    wrap="word", font=("Consolas", 9),
    insertbackground="#e0e7ff", relief="flat", bd=0
)
answer_box.grid(row=2, column=0, sticky="nsew", padx=12, pady=(8, 4))

input_frame = tk.Frame(root, bg="#0a0e27")
input_frame.grid(row=3, column=0, sticky="ew", padx=12, pady=4)
input_frame.grid_columnconfigure(0, weight=1)

input_box = tk.Entry(
    input_frame, bg="#1a1f3a", fg="#e0e7ff",
    font=("Segoe UI", 10), relief="flat", bd=2,
    insertbackground="#7dd3fc"
)
input_box.grid(row=0, column=0, sticky="ew", padx=(0, 8))

send_btn = tk.Button(
    input_frame, text="Send ➤",
    font=("Segoe UI", 9, "bold"), relief="flat", bd=0,
    bg="#2d3561", fg="#e0e7ff", activebackground="#3d4578",
    cursor="hand2"
)
send_btn.grid(row=0, column=1)

perf_frame = tk.Frame(root, bg="#1a1f3a", relief="ridge", bd=1)
perf_frame.grid(row=4, column=0, sticky="ew", padx=12, pady=4)
perf_frame.grid_columnconfigure(0, weight=1)

performance_label = tk.Label(
    perf_frame, text="Tasks: 0 | Avg: 0.0s | CPU: 0% | RAM: 0% | WiFi: 0%",
    bg="#1a1f3a", fg="#7dd3fc",
    font=("Segoe UI", 8), anchor="w", padx=10, pady=5
)
performance_label.grid(sticky="ew")

status_label = tk.Label(
    root, text="Status: Initializing...",
    bg="#0a0e27", fg="#7dd3fc",
    font=("Segoe UI", 9), anchor="w"
)
status_label.grid(row=5, column=0, pady=(0, 8), padx=12, sticky="ew")

anim_files = {emo: f"images/emotions/{emo}.mp4" for emo in emotion_lines.keys()}
anim_files.setdefault("normal", "images/emotions/normal.mp4")

# =============== SYSTEM PROMPT ===============
SYSTEM_PROMPT = """You are Robin, an advanced AI with COMPLETE control over a Windows laptop.

CRITICAL: Respond ONLY with valid JSON. NO exceptions.

Response format:
1. TASK (user asks to do something): Return ONLY JSON array of actions
2. CONVERSATION (user asks question): Return ONLY {"response":"answer","emotion":"emotion_name"}

RULES:
- ALWAYS valid JSON only
- Add waits for app loading (2-3 seconds)
- Use read_screen to verify progress
- Never describe actions - execute silently"""

# =============== HELPERS ===============
def log(text: str):
    try:
        ts = datetime.now().strftime('%H:%M:%S')
        answer_box.insert("end", f"[{ts}] {text}\n")
        answer_box.see("end")
    except:
        pass

def set_status(text: str):
    try:
        status_label.config(text=f"Status: {text}")
    except:
        pass

def read_screen_text():
    global screen_context_cache, last_screen_read
    if not PIL_AVAILABLE or not OCR_AVAILABLE:
        return "Screen reading unavailable"
    try:
        with screen_lock:
            screenshot = ImageGrab.grab()
            text = pytesseract.image_to_string(screenshot)
            screen_context_cache = text[:MAX_SCREENSHOT_CONTEXT]
            last_screen_read = time.time()
            return screen_context_cache
    except Exception as e:
        return f"Error: {e}"

def get_running_processes():
    try:
        processes = []
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                processes.append(proc.info['name'])
            except:
                pass
        return processes[:50]
    except:
        return []

def get_current_time_info():
    now = datetime.now()
    return {
        "time": now.strftime("%I:%M:%S %p"),
        "date": now.strftime("%A, %B %d, %Y"),
        "timestamp": now.isoformat()
    }

def set_alarm(alarm_time: str, message: str = "Alarm"):
    try:
        target_time = datetime.strptime(alarm_time, "%H:%M").time()
        now = datetime.now()
        target_datetime = datetime.combine(now.date(), target_time)
        if target_datetime <= now:
            target_datetime += timedelta(days=1)
        alarm_info = {"time": alarm_time, "message": message, "target": target_datetime, "active": True}
        alarms.append(alarm_info)
        log(f"Alarm set for {alarm_time}: {message}")
        speak(f"Alarm set for {alarm_time}", "happy")
        return True
    except Exception as e:
        log(f"Alarm error: {e}")
        return False

def check_alarms():
    global alarms
    now = datetime.now()
    for alarm in alarms[:]:
        if alarm["active"] and now >= alarm["target"]:
            speak(f"Alarm! {alarm['message']}", "excited")
            log(f"ALARM: {alarm['message']}")
            messagebox.showinfo("Alarm", alarm["message"])
            alarms.remove(alarm)

def alarm_monitor_loop():
    while True:
        try:
            check_alarms()
            time.sleep(10)
        except:
            pass

threading.Thread(target=alarm_monitor_loop, daemon=True).start()

# =============== CMD EXECUTION ===============
def run_cmd_command(command: str, wait_output: bool = True):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout.strip()
        error = result.stderr.strip()
        if wait_output:
            return output if output else error
        return "Command executed"
    except:
        return "Error"

def run_powershell_command(command: str):
    try:
        ps_command = ["powershell", "-Command", command]
        result = subprocess.run(ps_command, capture_output=True, text=True, timeout=30)
        output = result.stdout.strip()
        return output if output else "Command executed"
    except:
        return "Error"

def set_system_volume(level: int):
    try:
        level = max(0, min(100, level))
        run_cmd_command(f"nircmd.exe setsysvolume {int(level * 655.35)}", wait_output=False)
        return True
    except:
        return False

def set_system_brightness(level: int):
    try:
        level = max(0, min(100, level))
        ps_cmd = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})"
        run_powershell_command(ps_cmd)
        return True
    except:
        return False

def control_wifi(state: str):
    try:
        if state.lower() == "on":
            run_cmd_command("netsh interface set interface \"Wi-Fi\" enable", wait_output=False)
        else:
            run_cmd_command("netsh interface set interface \"Wi-Fi\" disable", wait_output=False)
        return True
    except:
        return False

def smart_type(text: str):
    if not PYAUTOGUI_AVAILABLE:
        return
    try:
        if any(c in text for c in ['@', '#', '$', '%', '^', '&', '*', '(', ')', '{', '}', '[', ']', '|', '\\', ':', ';', '"', "'", '<', '>', ',', '.', '?', '/', '~', '`']):
            pyperclip.copy(text)
            pyautogui.hotkey('ctrl', 'v')
        else:
            pyautogui.write(text, interval=0.01)
    except:
        pass

def detect_language(text: str):
    if not text or not text.strip():
        return "en"
    if re.search(r'[\u0900-\u097F]', text):
        return "hi"
    if LANGDETECT_AVAILABLE:
        try:
            return langdetect_detect(text)
        except:
            return "en"
    return "en"

def is_redundant(text: str):
    global last_spoken_text
    with speech_lock:
        t = re.sub(r'\s+', ' ', text.strip()).lower()
        if not t or t == last_spoken_text:
            return True
        last_spoken_text = t
        return False

# =============== TTS FUNCTIONS ===============
def init_pyttsx3():
    global tts_engine
    if tts_engine is None:
        try:
            tts_engine = pyttsx3.init()
            tts_engine.setProperty('rate', 160)
            tts_engine.setProperty('volume', 0.9)
            voices = tts_engine.getProperty('voices')
            if len(voices) > 1:
                tts_engine.setProperty('voice', voices[1].id)
        except:
            pass

async def edge_speak_to_wav(text: str, voice: str):
    try:
        comm = edge_tts.Communicate(text, voice)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        await comm.save(wav_path)
        data, rate = sf.read(wav_path, dtype='float32')
        duration = len(data) / rate
        return wav_path, duration
    except Exception as e:
        print(f"[Edge TTS Error] {str(e)[:60]}")
        return None, None

# =============== VIDEO/EMOTION ===============
def play_emotion_video(duration: float, emotion: str):
    global player, vlc_instance
    if not vlc_instance or not player:
        return
    path = anim_files.get(emotion) or anim_files.get("normal")
    if not path or not os.path.exists(path):
        log(f"Video not found: {path}")
        return
    
    try:
        with vlc_lock:
            media = vlc_instance.media_new(path)
            media.add_option('input-repeat=-1')
            player.set_media(media)
            player.play()
            log(f"Playing emotion: {emotion}")
    except Exception as e:
        log(f"Video play error: {e}")
    
    def revert():
        time.sleep(duration + 0.5)
        try:
            with vlc_lock:
                if player and player.is_playing():
                    normal = anim_files.get("normal")
                    if normal and os.path.exists(normal):
                        media = vlc_instance.media_new(normal)
                        media.add_option('input-repeat=-1')
                        player.set_media(media)
                        player.play()
        except Exception as e:
            log(f"Revert error: {e}")
    
    threading.Thread(target=revert, daemon=True).start()

def tts_worker():
    global current_emotion, tts_model
    while True:
        item = speech_queue.get()
        if item is None:
            speech_queue.task_done()
            continue
        text, emotion = item
        if not text or is_redundant(text):
            speech_queue.task_done()
            continue
        
        current_emotion = emotion or "normal"
        log(f"🤖 Speaking ({tts_model}): {text[:60]}")
        
        if not tts_enabled:
            log("Voice disabled - animation only")
            duration = len(text.split()) / 3.0
            play_emotion_video(duration, current_emotion)
            speech_queue.task_done()
            continue
        
        try:
            with tts_lock:
                lang = detect_language(text)
                
                # PRIMARY: PyTTSx3 (OFFLINE, FAST, RELIABLE)
                if tts_model == "pyttsx3":
                    try:
                        log("Using PyTTSx3...")
                        init_pyttsx3()
                        dur = len(text.split()) / 3.5
                        play_emotion_video(dur, emotion)
                        time.sleep(0.3)
                        log("PyTTSx3: Speaking...")
                        tts_engine.say(text)
                        tts_engine.runAndWait()
                        log("PyTTSx3: Complete")
                    except Exception as e:
                        log(f"PyTTSx3 Error: {e}")
                        tts_model = "gtts"
                        speech_queue.put((text, emotion))
                        speech_queue.task_done()
                        continue
                
                # SECONDARY: gTTS (SIMPLIFIED - NO FFMPEG)
                elif tts_model == "gtts" and GTTS_AVAILABLE:
                    lang_code = "hi" if lang == "hi" else "en"
                    try:
                        log(f"Using gTTS ({lang_code})...")
                        mp3_path = os.path.join(tempfile.gettempdir(), f"robin_{int(time.time()*1000)}.mp3")
                        
                        # Generate MP3
                        tts_gtts = gTTS(text=text, lang=lang_code, slow=False)
                        log("Generating MP3...")
                        tts_gtts.save(mp3_path)
                        log(f"MP3 saved: {mp3_path}")
                        
                        duration = max(len(text.split()) / 2.5, 1.5)
                        play_emotion_video(duration, emotion)
                        time.sleep(0.3)
                        
                        # Play directly with VLC (no ffmpeg conversion)
                        if vlc_instance and player:
                            try:
                                log("Playing with VLC...")
                                with vlc_lock:
                                    media = vlc_instance.media_new(mp3_path)
                                    player.set_media(media)
                                    player.play()
                                    log("Waiting for audio to finish...")
                                    total_wait = 0
                                    while player.is_playing() and total_wait < duration + 5:
                                        time.sleep(0.1)
                                        total_wait += 0.1
                                    player.stop()
                                    log("gTTS: Complete")
                            except Exception as e:
                                log(f"VLC playback error: {e}")
                        
                        # Cleanup
                        try:
                            if os.path.exists(mp3_path):
                                os.remove(mp3_path)
                        except:
                            pass
                    
                    except Exception as e:
                        log(f"gTTS Error: {str(e)[:60]}")
                        tts_model = "pyttsx3"
                        speech_queue.put((text, emotion))
                        speech_queue.task_done()
                        continue
                
                # TERTIARY: Edge TTS (OPTIONAL)
                elif tts_model == "edge" and EDGE_TTS_AVAILABLE:
                    voice = edge_voice_hi if lang == "hi" else edge_voice_en
                    try:
                        log(f"Using Edge TTS ({voice})...")
                        wav_path, dur = asyncio.run(edge_speak_to_wav(text, voice))
                        if wav_path and dur:
                            play_emotion_video(dur, emotion)
                            time.sleep(0.3)
                            try:
                                log("Playing Edge TTS audio...")
                                data, rate = sf.read(wav_path, dtype='float32')
                                sd.play(data, rate)
                                sd.wait()
                                log("Edge TTS: Complete")
                                os.remove(wav_path)
                            except Exception as e:
                                log(f"Audio error: {e}")
                    except Exception as e:
                        log(f"Edge TTS Error: {str(e)[:60]}")
                        tts_model = "pyttsx3"
                        speech_queue.put((text, emotion))
                        speech_queue.task_done()
                        continue
            
            set_status(f"{current_emotion.title()} | {current_personality.title()}")
        
        except Exception as e:
            log(f"TTS worker error: {e}")
        
        finally:
            speech_queue.task_done()

def speak(text: str, emotion: str = "normal"):
    if text:
        speech_queue.put((text, emotion))

threading.Thread(target=tts_worker, daemon=True).start()

# =============== VLC FUNCTIONS ===============
def init_vlc():
    global vlc_instance, player
    if vlc_instance is None:
        try:
            vlc_instance = vlc.Instance("--quiet")
            player = vlc_instance.media_player_new()
            if sys.platform.startswith("win"):
                player.set_hwnd(video_label.winfo_id())
        except Exception as e:
            print(f"[VLC error] {e}")
    return vlc_instance

def start_normal_loop():
    global player, vlc_instance
    normal = anim_files.get("normal")
    if not normal or not os.path.exists(normal):
        return
    with vlc_lock:
        try:
            media = vlc_instance.media_new(normal)
            media.add_option('input-repeat=-1')
            player.set_media(media)
            player.play()
        except:
            pass

# =============== AUTOMATION ENGINE ===============
def execute_automation_steps(steps):
    if not PYAUTOGUI_AVAILABLE:
        speak("Automation requires pyautogui", "sad")
        return False, ""

    task_start_time = time.time()
    log(f"Executing automation...")
    set_status("Automating...")
    screen_data = ""

    for i, step in enumerate(steps):
        try:
            action = step.get("action", "").lower()

            if action == "press":
                key = step.get("key", "")
                if key:
                    pyautogui.press(key)
            elif action == "hotkey":
                keys = step.get("keys", [])
                if keys:
                    pyautogui.hotkey(*keys)
            elif action == "type":
                text = step.get("text", "")
                if text:
                    smart_type(text)
            elif action == "click":
                x = step.get("x", 0)
                y = step.get("y", 0)
                if x and y:
                    screen_width, screen_height = pyautogui.size()
                    x = max(10, min(x, screen_width - 10))
                    y = max(10, min(y, screen_height - 10))
                    pyautogui.click(x, y)
                    time.sleep(0.2)
            elif action == "moveto":
                x = step.get("x", 0)
                y = step.get("y", 0)
                if x and y:
                    pyautogui.moveTo(x, y, duration=0.2)
            elif action == "drag":
                x1, y1 = step.get("x1", 0), step.get("y1", 0)
                x2, y2 = step.get("x2", 0), step.get("y2", 0)
                if all([x1, y1, x2, y2]):
                    pyautogui.moveTo(x1, y1)
                    pyautogui.drag(x2 - x1, y2 - y1, duration=0.3)
            elif action == "scroll":
                amount = step.get("amount", -3)
                pyautogui.scroll(amount)
            elif action == "wait":
                seconds = step.get("seconds", 0.5)
                time.sleep(seconds)
            elif action == "clipboard_copy":
                text = step.get("text", "")
                if text:
                    pyperclip.copy(text)
            elif action == "clipboard_paste":
                pyautogui.hotkey('ctrl', 'v')
                time.sleep(0.2)
            elif action == "read_screen":
                screen_data = read_screen_text()
            elif action == "screenshot":
                if PIL_AVAILABLE:
                    try:
                        img = ImageGrab.grab()
                        path = f"screenshots/screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                        os.makedirs("screenshots", exist_ok=True)
                        img.save(path)
                    except:
                        pass
            elif action == "get_current_time":
                time_info = get_current_time_info()
                screen_data = f"Time: {time_info['time']}, Date: {time_info['date']}"
            elif action == "set_alarm":
                alarm_time = step.get("time", "")
                message = step.get("message", "Alarm")
                if alarm_time:
                    set_alarm(alarm_time, message)
            elif action == "run_cmd":
                command = step.get("command", "")
                wait_output = step.get("wait_output", False)
                if command:
                    output = run_cmd_command(command, wait_output)
                    if wait_output:
                        screen_data = output
            elif action == "run_powershell":
                command = step.get("command", "")
                if command:
                    output = run_powershell_command(command)
                    screen_data = output
            elif action == "set_volume":
                level = step.get("level", 50)
                set_system_volume(level)
            elif action == "set_brightness":
                level = step.get("level", 70)
                set_system_brightness(level)
            elif action == "wifi_control":
                state = step.get("state", "on")
                control_wifi(state)
            elif action == "shutdown":
                delay = step.get("delay", 60)
                run_cmd_command(f"shutdown /s /t {delay}", wait_output=False)
            elif action == "restart_system":
                delay = step.get("delay", 60)
                run_cmd_command(f"shutdown /r /t {delay}", wait_output=False)
            elif action == "confirm":
                message = step.get("message", "Continue?")
                if not messagebox.askyesno("Confirm", message):
                    log("Task cancelled")
                    return False

            time.sleep(AUTOMATION_DELAY)

        except Exception as e:
            log(f"Step error: {e}")

    task_end_time = time.time()
    execution_time = task_end_time - task_start_time

    performance_stats["tasks_completed"] += 1
    performance_stats["total_execution_time"] += execution_time
    performance_stats["avg_execution_time"] = performance_stats["total_execution_time"] / performance_stats["tasks_completed"]

    update_performance_display()

    log(f"Task completed in {execution_time:.2f}s")
    set_status("Ready")

    return True, screen_data

# =============== API KEY MANAGEMENT ===============
def switch_api_key():
    global current_client_idx, client, clients
    if not clients or len(clients) < 2:
        return False
    if current_client_idx < len(clients):
        clients[current_client_idx]["active"] = False
    for i in range(len(clients)):
        idx = (current_client_idx + 1 + i) % len(clients)
        if clients[idx]["active"]:
            current_client_idx = idx
            client = clients[idx]["client"]
            log(f"Switched to API Key #{idx+1}")
            speak(f"Switched to backup API key", "normal")
            return True
    return False

# =============== AI DECISION ENGINE ===============
def process_user_command(query: str):
    global last_interaction, conversation_history, screen_context_cache, client, clients, current_client_idx

    if not client or not clients:
        speak("Cannot connect to AI. Check API keys in config.py", "sad")
        return

    last_interaction = time.time()
    log(f"You: {query}")
    set_status("Thinking...")

    try:
        time_keywords = ['time', 'date', 'clock', 'day', 'today', 'what time']
        if any(keyword in query.lower() for keyword in time_keywords):
            time_info = get_current_time_info()
            response_text = f"It's {time_info['time']} on {time_info['date']}"
            speak(response_text, "normal")
            with history_lock:
                conversation_history.append({"role": "user", "content": query})
                conversation_history.append({"role": "assistant", "content": response_text})
            set_status("Ready")
            return

        context_info = f"\n\nTime: {get_current_time_info()['time']}\nDate: {get_current_time_info()['date']}"

        if screen_context_cache and (time.time() - last_screen_read) < 30:
            context_info += f"\n\nScreen: {screen_context_cache[:300]}"

        procs = get_running_processes()
        if procs:
            context_info += f"\n\nApps: {', '.join(procs[:10])}"

        with history_lock:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT + context_info},
                *conversation_history[-MAX_MEMORY:],
                {"role": "user", "content": query}
            ]

        max_retries = len(clients) if clients else 1
        retry_count = 0
        result = None

        while retry_count < max_retries:
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.2,
                    max_tokens=2000,
                    timeout=30
                )
                result = response.choices[0].message.content.strip()
                break
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "rate_limit" in error_str.lower():
                    log(f"Rate limit on Key #{current_client_idx+1}")
                    if switch_api_key():
                        retry_count += 1
                        time.sleep(1)
                        continue
                    else:
                        speak("All API keys rate limited. Please wait.", "sad")
                        set_status("Rate Limited")
                        return
                else:
                    raise e

        if not result:
            speak("No response from AI", "sad")
            return

        try:
            parsed = json.loads(result)
            
            if isinstance(parsed, list):
                log("Executing automation...")
                execution_result = execute_automation_steps(parsed)
                if isinstance(execution_result, tuple):
                    success, screen_data = execution_result
                    speak("Task completed successfully", "happy")
            
            elif isinstance(parsed, dict) and "response" in parsed:
                response_text = parsed.get("response", "")
                emotion = parsed.get("emotion", "normal")
                if response_text and not response_text.endswith(('.', '!', '?')):
                    response_text += "."
                if response_text:
                    speak(response_text, emotion)
            
            else:
                if result and not result.endswith(('.', '!', '?')):
                    result += "."
                speak(result, "normal")
        
        except json.JSONDecodeError:
            if result and not result.endswith(('.', '!', '?')):
                result += "."
            speak(result, "normal")

        with history_lock:
            conversation_history.append({"role": "user", "content": query})
            conversation_history.append({"role": "assistant", "content": result[:500]})

    except Exception as e:
        print(f"[AI Error] {e}")
        speak("Error occurred", "sad")
        set_status("Error")

# =============== VOICE LISTENING ===============
recognizer = sr.Recognizer()
recognizer.pause_threshold = 0.6
recognizer.non_speaking_duration = 0.4

def listen_loop():
    global is_sleeping, listening_mode

    vosk_model = None
    if listening_mode == "offline" and VOSK_AVAILABLE:
        try:
            model_path = "vosk-model-en-us-0.22-lgraph"
            if os.path.exists(model_path):
                vosk_model = Model(model_path)
                log("Vosk model loaded")
            else:
                log("Vosk model not found - using online")
                listening_mode = "online"
        except Exception as e:
            print(f"[Vosk init error] {e}")
            listening_mode = "online"

    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
            log("Microphone ready")
    except:
        log("Mic calibration failed")

    while True:
        try:
            if not listening_enabled:
                time.sleep(0.2)
                continue

            if listening_mode == "offline" and vosk_model and VOSK_AVAILABLE:
                try:
                    rec = KaldiRecognizer(vosk_model, 16000)
                    rec.SetWords(["robin", "open", "close", "hello", "yes", "no"])

                    with sr.Microphone(sample_rate=16000) as source:
                        source.dynamic_energy_threshold = False
                        while listening_mode == "offline" and listening_enabled:
                            try:
                                audio_data = recognizer.listen(source, timeout=8, phrase_time_limit=10)
                                
                                if rec.AcceptWaveform(audio_data.get_raw_data()):
                                    result = json.loads(rec.Result())
                                    query = result.get("text", "").strip().lower()

                                    if not query or len(query) < 2:
                                        continue

                                    log(f"[VOSK] {query}")

                                    if is_sleeping:
                                        if WAKE_WORD in query:
                                            is_sleeping = False
                                            speak("I'm awake!", "excited")
                                        continue

                                    if WAKE_WORD not in query:
                                        continue

                                    query = re.sub(rf'\b{WAKE_WORD}\b', '', query, flags=re.IGNORECASE).strip()
                                    if query:
                                        threading.Thread(target=process_user_command, args=(query,), daemon=True).start()
                                
                                else:
                                    partial = json.loads(rec.PartialResult())
                                    partial_text = partial.get("partial", "").strip().lower()
                                    if partial_text and len(partial_text) > 3:
                                        pass
                            
                            except sr.WaitTimeoutError:
                                rec = KaldiRecognizer(vosk_model, 16000)
                                continue

                except Exception as e:
                    print(f"[Vosk error] {e}")
                    listening_mode = "online"
                    log("Switching to online")

            elif listening_mode == "online":
                with sr.Microphone() as source:
                    try:
                        audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                        try:
                            query = recognizer.recognize_google(audio).strip().lower()
                        except sr.UnknownValueValue:
                            continue
                        except sr.RequestError as e:
                            log(f"Google API error: {e}")
                            continue

                        if not query or len(query) < 2:
                            continue

                        log(f"[GOOGLE] {query}")

                        if is_sleeping:
                            if WAKE_WORD in query:
                                is_sleeping = False
                                speak("I'm awake!", "excited")
                            continue

                        if WAKE_WORD not in query:
                            continue

                        query = re.sub(rf'\b{WAKE_WORD}\b', '', query, flags=re.IGNORECASE).strip()
                        if query:
                            threading.Thread(target=process_user_command, args=(query,), daemon=True).start()

                    except sr.WaitTimeoutError:
                        continue
                    except Exception as e:
                        print(f"[Google listen error] {e}")

        except Exception as e:
            print(f"[Listen error] {e}")
            time.sleep(0.5)

# =============== PERFORMANCE MONITORING ===============
def get_wifi_speed():
    try:
        result = subprocess.run(['netsh', 'wlan', 'show', 'interface'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'Signal' in line and '%' in line:
                match = re.search(r'(\d+)%', line)
                if match:
                    return int(match.group(1))
        return 0
    except:
        return 0

def update_performance_display():
    try:
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
        wifi = get_wifi_speed()
        text = f"Tasks: {performance_stats['tasks_completed']} | Avg: {performance_stats['avg_execution_time']:.2f}s | CPU: {cpu}% | RAM: {mem:.1f}% | WiFi: {wifi}%"
        performance_label.config(text=text)
    except:
        pass

def monitor_performance_loop():
    while True:
        try:
            if performance_stats["monitor_enabled"]:
                update_performance_display()
            time.sleep(1)
        except:
            pass

threading.Thread(target=monitor_performance_loop, daemon=True).start()

# =============== UI BUTTON HANDLERS ===============
def btn_awake():
    global is_sleeping
    is_sleeping = False
    speak("I'm awake!", "excited")
    set_status("Awake")

def btn_mute():
    global listening_enabled
    listening_enabled = not listening_enabled
    status = "Muted" if not listening_enabled else "Listening"
    log(f"Microphone: {status}")
    mute_btn.config(bg="#ef4444" if not listening_enabled else "#2d3561")

def btn_silent():
    global tts_enabled
    tts_enabled = not tts_enabled
    status = "Silent" if not tts_enabled else "Voice On"
    log(f"Voice: {status}")
    silent_btn.config(bg="#ef4444" if not tts_enabled else "#2d3561")

def btn_mode():
    global current_personality
    modes = ["professional", "friendly", "playful"]
    idx = modes.index(current_personality)
    current_personality = modes[(idx + 1) % len(modes)]
    speak(f"Mode: {current_personality}", "normal")
    mode_btn.config(text=f"🎭 {current_personality.title()}")

def btn_tts_model():
    global tts_model
    models = ["gtts", "pyttsx3", "edge"]
    idx = models.index(tts_model)
    tts_model = models[(idx + 1) % len(models)]
    emoji_map = {"gtts": "🌐 gTTS", "pyttsx3": "🎤 PyTTSx3", "edge": "🔊 Edge"}
    tts_model_btn.config(text=emoji_map.get(tts_model, "TTS"))
    speak(f"Switched to {tts_model}", "normal")

def btn_listen_mode():
    global listening_mode
    if listening_mode == "online":
        if VOSK_AVAILABLE:
            listening_mode = "offline"
            speak("Offline mode enabled", "normal")
            listen_mode_btn.config(text="📴 Offline")
        else:
            speak("Vosk not installed", "sad")
    else:
        listening_mode = "online"
        speak("Online mode enabled", "normal")
        listen_mode_btn.config(text="🌐 Online")

def btn_monitor():
    performance_stats["monitor_enabled"] = not performance_stats["monitor_enabled"]
    status = "Enabled" if performance_stats["monitor_enabled"] else "Disabled"
    monitor_btn.config(bg="#ef4444" if not performance_stats["monitor_enabled"] else "#2d3561")

def btn_restart():
    if messagebox.askyesno("Restart", "Restart Robin?"):
        speak("Restarting...", "normal")
        time.sleep(0.5)
        python = sys.executable
        os.execv(python, [python] + sys.argv)

def btn_sleep():
    global is_sleeping
    is_sleeping = True
    speak("Going to sleep", "sleepy")
    set_status("Sleeping")

def btn_quit():
    if messagebox.askyesno("Quit", "Close Robin?"):
        speak("Goodbye!", "sad")
        time.sleep(0.5)
        root.quit()
        os._exit(0)

def send_text_command():
    query = input_box.get().strip()
    if not query:
        return
    input_box.delete(0, tk.END)
    threading.Thread(target=process_user_command, args=(query,), daemon=True).start()

def on_enter_key(event):
    send_text_command()
    return "break"

awake_btn.config(command=btn_awake)
mute_btn.config(command=btn_mute)
silent_btn.config(command=btn_silent)
mode_btn.config(command=btn_mode)
tts_model_btn.config(command=btn_tts_model)
listen_mode_btn.config(command=btn_listen_mode)
monitor_btn.config(command=btn_monitor)
restart_btn.config(command=btn_restart)
sleep_btn.config(command=btn_sleep)
smile_btn.config(command=btn_awake)
power_btn.config(command=btn_quit)
send_btn.config(command=send_text_command)
input_box.bind("<Return>", on_enter_key)
input_box.bind("<KP_Enter>", on_enter_key)

# =============== STARTUP ===============
def startup():
    log("=" * 70)
    log("ROBIN - Complete Laptop Control AI")
    log("=" * 70)
    
    # Check animation files
    log("\nChecking animation files...")
    for emotion, path in anim_files.items():
        if os.path.exists(path):
            log(f"✓ {emotion}: {path}")
        else:
            log(f"✗ MISSING: {emotion}: {path}")
    
    log("\nCreating images/emotions folder if missing...")
    os.makedirs("images/emotions", exist_ok=True)
    log("✓ Folder ready at: images/emotions/")
    
    caps = [
        ("Keyboard/Mouse", PYAUTOGUI_AVAILABLE),
        ("Screenshots", PIL_AVAILABLE),
        ("Screen OCR", OCR_AVAILABLE),
        ("PyTTSx3", PYTTSX3_AVAILABLE),
        ("gTTS", GTTS_AVAILABLE),
        ("Edge TTS", EDGE_TTS_AVAILABLE),
        ("Vosk (Offline)", VOSK_AVAILABLE)
    ]
    
    log("\nCapabilities:")
    for name, available in caps:
        status = "✓" if available else "✗"
        log(f"{status} {name}")
    
    log("-" * 70)
    if clients:
        log(f"API Keys: {len(clients)} loaded ✓")
    else:
        log("✗ No API keys in config.py")
    log("-" * 70)
    
    try:
        init_vlc()
        log("✓ VLC initialized")
        start_normal_loop()
        log("✓ Animation system ready")
    except Exception as e:
        log(f"⚠ Animation error: {e}")
    
    log("\n" + "=" * 70)
    speak("Hello! I'm Robin. Ready for action!", "happy")
    set_status("Ready")
    
    threading.Thread(target=listen_loop, daemon=True).start()
    log("✓ Listening for commands...")
    log("=" * 70 + "\n")
    log("INSTRUCTIONS:")
    log("1. Place MP4 files in: images/emotions/")
    log("2. Say 'robin' to wake up and give commands")
    log("3. Type commands in the input box below")
    log("=" * 70)

# =============== MAIN ===============
if __name__ == "__main__":
    try:
        startup()
        root.mainloop()
    except KeyboardInterrupt:
        print("\nRobin shutting down...")
        root.quit()
        os._exit(0)
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        os._exit(1)