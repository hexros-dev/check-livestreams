# ====================== IMPORTS ======================
import json
import os
import shutil
import smtplib
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from hashlib import md5
from pathlib import Path
from uuid import uuid4

import inflect
import pytz
import requests
import yt_dlp
from deep_translator import GoogleTranslator
from dotenv import load_dotenv

# import logging
load_dotenv()
from_lang = "auto"
to_lang = "en"
translator = GoogleTranslator(source=from_lang, target=to_lang)
# ====================== CONSTANTS ======================
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PWD = os.getenv("SENDER_PWD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
ENV = os.getenv("ENV") or "production"
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
LIMIT = 15  # minutes
DB_PATH = "titles.db"

ENV_LIST = {
    "production": "AUTO",
    "development": "DEV",
    "self-host": "HOST",
    "raspberry": "RPI",
    "test": "TEST",
}

UNARCHIVE_FILTERS = [
    "unarchive",
    "unarchived",
    "no archive",
    "no archived",
    "archive",
    "archiving",
    "archived",
    "rebroadcast",
    "アーカイブ無し",
    "アーカイブ",
    "アーカイブはない",
    "アーカイブ済み",
    "アーカイブなし",
    "アーカイブされていない",
    "アーカイブする",
    "アーカイブされた",
    "arsip",
    "belum diarsipkan",
    "diarsipkan",
    "tidak diarsipkan",
]
KARAOKE_FILTERS = [
    "karaoke",
    "sing",
    "singing",
    "歌枠",
    "ヒトカラ",
    "カラ",
    "うたう",
    "歌",
]
# LIARS_BAR_FILTERS = ["liar's bar", "liars bar", "liar bar"]
TEST_FILTERS = ["test"]

FILTERS = {
    "Unarchived": {
        "counter": 0,
        "icon": "🚨",
        "color": "#FF4500",
        "is_true": False,
        "filter": UNARCHIVE_FILTERS,
        "label": '<span style="font-weight: bold; background-color: palevioletred; padding: 1.5px; margin: 4px; border-style: dashed;">UNARCHIVED</span>',
    },
    "Karaoke": {
        "counter": 0,
        "icon": "🎤",
        "color": "#32CD32",
        "is_true": False,
        "filter": KARAOKE_FILTERS,
        "label": '<span style="font-weight: bold; background-color: burlywood; padding: 1.5px; margin: 4px; border-style: dashed;">Karaoke</span>',
    },
    "Test": {
        "counter": 0,
        "icon": "🤖",
        "color": "#6D41BF",
        "is_true": False,
        "filter": TEST_FILTERS,
        "label": '<span style="font-weight: bold; background-color: burlywood; padding: 1.5px; margin: 4px; border-style: dashed;">Test</span>',
    },
    # "Liar's Bar": {
    #     "counter": 0,
    #     "icon": "🤥",
    #     "color": "#8B4513",
    #     "is_true": False,
    #     "filter": LIARS_BAR_FILTERS,
    #     "label": '<span style="font-weight: bold; background-color: #2F131E; padding: 3px; margin: 4px; border-radius: 30%; color: #87F5FB;">Liar</span>'
    # }
}

UPCOMING_SUBJECT = (
    f"[{ENV_LIST.get(ENV, 'UNKNOWN')}] 🗓️ Upcoming Live Streams Notification"
)
LIVE_SUBJECT = f"[{ENV_LIST.get(ENV, 'UNKNOWN')}] 🔴 Live Streams Notification"

SKIP_STREAMS = [
    "VoWHIX4tp5k",  # free chat room Aki
    "INFI9FahPY0",  # free chat room Matsuri
    "L701Sxy3ohw",  # free chat room Polka
    "9vaxfw1qFcY",  # free chat room Lui
    "EdVVFI2oIec", "K2osic0Civk"
]  # video id


# ====================== CLASSES ======================
class Color:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    PURPLE = "\033[94m"
    CYAN = "\033[96m"
    RESET = "\033[0m"


# ====================== HELPER FUNCTIONS ======================
# logging.basicConfig(
#     filename="yt-dlp.log",  # File log
#     level=logging.DEBUG,  # Ghi chi tiết log
#     format="%(asctime)s - %(levelname)s - %(message)s",
# )


def init_db():
    """Khởi tạo cơ sở dữ liệu nếu chưa tồn tại."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS video_titles (
            original_title TEXT PRIMARY KEY,
            translated_title TEXT,
            last_accessed INTEGER
        )
    """
    )
    conn.commit()
    conn.close()


def translate_title(title: str) -> str:
    trans_title = translator.translate(title)
    if trans_title is None:
        trans_title = translator.translate(title)
    elif "Error 500 (Server Error)!!1500.That’s an error.There was an error. Please try again later.That’s all we know." in trans_title:
        trans_title = translator.translate(title)
    return trans_title


def get_translated_title(original_title, translate_func):
    """
    Lấy tiêu đề đã dịch hoặc dịch nếu chưa tồn tại.
    :param original_title: Tiêu đề gốc
    :param translate_func: Hàm dịch tiêu đề
    :return: Tiêu đề đã dịch
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    current_time = int(time.time())

    # Kiểm tra trong cơ sở dữ liệu
    cursor.execute(
        "SELECT translated_title FROM video_titles WHERE original_title = ?",
        (original_title,),
    )
    row = cursor.fetchone()

    if row:
        # Cập nhật thời gian truy cập
        row_0 = ""
        if row[0] is None:
            row_0 = original_title
        else:
            row_0 = row[0]
        if "Error 500 (Server Error)!!1500.That’s an error.There was an error. Please try again later.That’s all we know." in row_0:
            translated_title = translate_func(original_title)
            cursor.execute(
                "UPDATE video_titles SET translated_title = ?, last_accessed = ? WHERE original_title = ?",
                (translated_title, current_time, original_title),
            )
            conn.commit()
            conn.close()
            return translated_title
        else:
            cursor.execute(
                "UPDATE video_titles SET last_accessed = ? WHERE original_title = ?",
                (current_time, original_title),
            )
            conn.commit()
            conn.close()
            return row_0
    else:
        # Dịch và lưu lại
        translated_title = translate_func(original_title)
        cursor.execute(
            "INSERT INTO video_titles (original_title, translated_title, last_accessed) VALUES (?, ?, ?)",
            (original_title, translated_title, current_time),
        )
        conn.commit()
        conn.close()
        return translated_title


def clean_up_old_titles(days=1):
    """Xóa các tiêu đề không được truy cập trong N ngày qua."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cutoff_time = int((datetime.now() - timedelta(days=days)).timestamp())
    cursor.execute("DELETE FROM video_titles WHERE last_accessed < ?", (cutoff_time,))
    conn.commit()
    conn.close()


def get_clock_emoji(dt: datetime) -> str:
    emojis = [
        "🕛",
        "🕧",
        "🕐",
        "🕜",
        "🕑",
        "🕝",
        "🕒",
        "🕞",
        "🕓",
        "🕟",
        "🕔",
        "🕠",
        "🕕",
        "🕡",
        "🕖",
        "🕢",
        "🕗",
        "🕣",
        "🕘",
        "🕤",
        "🕙",
        "🕥",
        "🕚",
        "🕦",
    ]

    index = (
        dt.hour % 12 * 2 + (1 if dt.minute >= 15 else 0) + (1 if dt.minute >= 45 else 0)
    ) % len(emojis)
    return emojis[index]


def print_text(text: str, prefix: str = "I", suffix: str = "\n") -> None:
    _type = prefix.upper()
    match (_type):
        case "I":
            print(f"{Color.CYAN}", end="")
        case "S":
            print(f"{Color.GREEN}", end="")
        case "W":
            print(f"{Color.YELLOW}", end="")
        case "E":
            print(f"{Color.RED}", end="")
        case "Q":
            print(f"{Color.PURPLE}", end="")
        case _:
            pass
    print(f"<{prefix if prefix else '?'}> {text}{Color.RESET}", end=suffix)


def get_channel_url(file_path: str) -> list[str] | None:
    is_exists = Path(file_path).exists()
    if not is_exists:
        print_text(
            f"File {file_path} is not exist. Please create file and try again!",
            prefix="E",
        )
        exit(1)
    with open(file_path, mode="r", encoding="utf-8") as file:
        lines = file.readlines()
        result = [line.strip() for line in lines]

    return result


def counter(num: int, text: str = "", filter: list[str] = None, is_true: bool = False):
    f_text = text.lower()
    if filter is None:
        num += 1
        return num

    for i_filter in filter:
        if i_filter in f_text:
            num += 1
            is_true = True
            break

    return num, is_true


def count_title_description(
    num: int, title: str = "", description: str = "", filter: list[str] = None
):
    f_title = title.lower() if title else ""
    f_description = description.lower() if description else ""

    is_true = False

    for i_filter in filter:
        if i_filter in f_title or i_filter in f_description:
            num += 1
            is_true = True
            break

    return num, is_true


def send_email(subject: str, body: str) -> None:
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PWD)
        text = msg.as_string()
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, text)
        server.quit()
        print_text("Email sent successfully!", "S")
    except Exception as e:
        print_text(f"Failed to send email: {e}", "E")


def sort_obj(obj):
    obj = dict(sorted(obj.items(), key=lambda item: item[0]))

    for id_obj in obj.values():
        id_obj["videos"] = sorted(id_obj["videos"], key=lambda video: video["video_id"])

    return obj


def pretty_time_delta(delta, lang=inflect.engine()):
    seconds = delta.total_seconds()
    if not seconds:
        return "0 seconds"
    seconds = abs(int(seconds))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    _, seconds_decimal = divmod(delta.total_seconds(), 1)
    milliseconds = "%.2f" % float(seconds_decimal * 1000)
    measures = (
        (days, "day"),
        (hours, "hour"),
        (minutes, "minute"),
        (seconds, "second"),
        (milliseconds, "millisecond"),
    )
    return lang.join(
        [f"{count} {lang.plural(noun, count)}" for (count, noun) in measures if count]
    )


def send_discord_message(webhook_url, message):
    headers = {"Content-Type": "application/json"}
    data = {"content": message}
    response = requests.post(webhook_url, json=data, headers=headers)
    if response.status_code == 204:
        print("Message sent successfully!")
    else:
        print(
            f"Failed to send message. Status code: {response.status_code}, Response: {response.text}"
        )


# ====================== UTILITY FUNCTIONS ======================
def send_email_upcoming(live_streams: str) -> None:
    # format time (now)
    now_ = datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")).strftime("%Y/%m/%d %H:%M:%S")
    message = "# 📹 Upcoming Unarchived YouTube Live Streams\n"
    channel_lst = []
    is_send = False
    # subject and body when send email
    subject = f"{UPCOMING_SUBJECT} {now_}"
    body = ""

    now_ = datetime.strptime(now_, "%Y/%m/%d %H:%M:%S")
    # variables
    need_red = False  # change text to red
    prev_upcoming_streams = {}

    # count variables
    upcoming_counter = 0
    for filters in FILTERS.items():
        filters[1]["counter"] = 0
    new_counter = 0
    total_streams = 0

    # label template
    new_label = '<span style="font-weight: bold; background-color: greenyellow; padding: 3px; margin: 4px; border-radius: 30%;">New!</span>'

    # load previous upcoming streams save in file json
    with open("./upcoming.json", "r", encoding="utf-8") as file:
        prev_upcoming_streams = json.load(file)

    for channel_id, info in live_streams.items():
        if info["videos"]:
            body += f"""
                        <li style="list-style-type: none;">
                            <img src="{info.get("avatar_url")}=s900-c-k-c0x00ffffff-no-rj" style="width: 60px; height: 60px; border-radius: 50%; margin-right: 4px; display: inline-block;" />
                            <strong style="font-size: 18px;">{info['channel_name']} ({channel_id})</strong> - <a href="{info['channel_url']}"><strong>Visit Channel</strong></a>
                            <ul>
                    """
            for video in info["videos"]:
                # Check new streams
                exists = True
                try:
                    if prev_upcoming_streams.get(channel_id).get("videos") == []:
                        exists = False
                    else:
                        exists = any(
                            item["video_id"] == video["video_id"]
                            for item in prev_upcoming_streams.get(channel_id).get(
                                "videos"
                            )
                        )
                except TypeError as e:
                    print(f"ERROR: {e}")
                    print(f"Channel_id at upcoming: {channel_id}")
                new_counter = new_counter if exists else new_counter + 1
                # Get delta time
                schedule_date = datetime.strptime(
                    video.get("date", "4444/04/04 04:04:04"), "%Y/%m/%d %H:%M:%S"
                )
                delta = schedule_date - now_
                seconds = delta.total_seconds()

                # Check delta if time smaller limit
                if seconds <= LIMIT * 60:
                    upcoming_counter += 1
                    need_red = True

                for filters in FILTERS.items():
                    _filter = filters[1].get("filter", [])
                    filters[1]["counter"], filters[1]["is_true"] = (
                        count_title_description(
                            filters[1]["counter"],
                            video["title"],
                            video["description"],
                            _filter,
                        )
                    )

                # Get emoji
                emoji = get_clock_emoji(schedule_date)
                total_streams += 1
                if FILTERS["Unarchived"].get("is_true"):
                    is_send = True
                    if channel_id not in channel_lst:
                        message += f"## {info['channel_name']} ({channel_id})\n---\n"
                        channel_lst.append(channel_id)
                    message += f"- Title: {video['title']}\n- Stream ID: [{video['video_id']}](https://www.youtube.com/watch?v={video['video_id']})\n- Scheduled for: {video['date']}\n---\n"

                body += f"""
                            <hr />
                            <li style="list-style-type: none; {"color:red;" if need_red else ""} {"color: blue; font-weight: bold; font-style: oblique;" if FILTERS["Unarchived"].get("is_true") else ""} ">
                                <span><strong>🏷️ Title: </strong>{video['title']}</span> {"".join(filters[1].get("label", "") if filters[1].get("is_true", False) else "" for filters in FILTERS.items())} {"" if exists else new_label}
                                <br />
                                <span><strong>📝 Translated Title: </strong>{get_translated_title(video['title'], translate_title)}</span>
                                <br />
                                <span><strong>🆔 Stream ID: </strong><span style="font-weight: bold; font-family: consolas, 'Times New Roman', tahoma; font-size:x-large;">{video['video_id']}</span></span>
                                <br />
                                <span><strong>🖼️ Thumbnail: </strong> <img src="{video['thumbnail']}"/></span>
                                <br />
                                <span><strong>{emoji} Scheduled for: </strong>{video['date']} ({str(delta)} from now)</span>
                                <br />
                                <a href="https://www.youtube.com/watch?v={video['video_id']}"><strong>▶️ Open Stream</strong></a>
                            </li>
                        """
                need_red = False
                for filters in FILTERS.items():
                    filters[1]["is_true"] = False
                    # print(filters)
            body += "</ul></li>"

    body += "</ul></body></html>"
    body_first = f"""<!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                </head>
                <body>
                <h1>📹 Upcoming YouTube Live Streams</h1>
                <br />
                {''.join(f'<h2 style="color: {filters[1].get("color", "green")}; font-weight: bold;">{filters[1].get("icon", "📣")} {filters[1].get("counter")} {filters[0]} Live Streams</h2>' if filters[1].get("counter") > 0 else "" for filters in FILTERS.items())}
                {f'<h2 style="color: blue; font-weight: bold;">🆕 {new_counter} New Live Streams</h2>' if new_counter > 0 else ""}
                {f'<h2 style="color: orange; font-weight: bold;">💠 {upcoming_counter} Live Streams will live soon!</h2>' if upcoming_counter > 0 else ""}
                {f'<h2 style="color: #4B0082; font-weight: bold;">📊 {total_streams} Live Streams in total.</h2>'}
                <ul>
            """
    body = body_first + body
    current_hash = md5(str(live_streams).encode("utf-8")).hexdigest()

    message = f"# `Total {FILTERS['Unarchived'].get('counter')} Unarchived Live Streams.\n` {message}"

    is_exists = Path("./prev_hash_upcoming.md5").exists()
    if not is_exists:
        print("create file")
        with open("./prev_hash_upcoming.md5", mode="w", encoding="utf-8") as file:
            pass

    with open("./prev_hash_upcoming.md5", mode="r+", encoding="utf-8") as file:
        prev_hash = file.readline().strip()
        print_text(f"prev_upcoming_hash: {prev_hash}")
        print_text(f"curr_upcoming_hash: {current_hash}")
        if prev_hash != current_hash:
            if is_send:
                send_discord_message(DISCORD_WEBHOOK_URL, message=message)
            file.seek(0, 0)
            file.write(current_hash)
            send_email(subject, body)
        else:
            if upcoming_counter:
                if is_send:
                    send_discord_message(DISCORD_WEBHOOK_URL, message=message)
                send_email(subject, body)
            else:
                print_text("Nothing changed!", "S")


def send_email_live(live_streams: str) -> None:
    subject = f"{LIVE_SUBJECT} {datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')).strftime('%Y/%m/%d %H:%M:%S')}"
    body = ""

    message = "# 🔴 Unarchived YouTube Live Streams\n"
    channel_lst = []
    is_send = False

    new_label = '<span style="font-weight: bold; background-color: greenyellow; padding: 3px; margin: 4px; border-radius: 30%;">New!</span>'

    prev_live_streams = {}

    total_streams = 0

    new_counter = 0
    for filters in FILTERS.items():
        filters[1]["counter"] = 0
    new_counter = 0
    with open("./live_streams.json", "r", encoding="utf-8") as file:
        prev_live_streams = json.load(file)

    for channel_id, info in live_streams.items():
        if info["videos"]:
            body += f"""
                        <li style="list-style-type: none;">
                            <img src="{info.get("avatar_url")}=s900-c-k-c0x00ffffff-no-rj" style="width: 60px; height: 60px; border-radius: 50%; margin-right: 4px;  display: inline-block;" />
                            <strong style="font-size: 18px;">{info['channel_name']} ({channel_id})</strong> - <a href="{info['channel_url']}"><strong>Visit Channel</strong></a>
                            <ul>
                    """
            for video in info["videos"]:
                exists = True
                if prev_live_streams != {}:
                    try:
                        if prev_live_streams.get(channel_id).get("videos") == []:
                            exists = False
                        else:
                            exists = any(
                                item["video_id"] == video["video_id"]
                                for item in prev_live_streams.get(channel_id).get(
                                    "videos", []
                                )
                            )
                    except TypeError as e:
                        print(f"ERROR: {e}")
                        print(f"Channel_id at live: {channel_id}")

                    new_counter = new_counter if exists else new_counter + 1

                for filters in FILTERS.items():
                    _filter = filters[1].get("filter", [])
                    filters[1]["counter"], filters[1]["is_true"] = (
                        count_title_description(
                            filters[1]["counter"],
                            video["title"],
                            video["description"],
                            _filter,
                        )
                    )

                total_streams += 1

                if FILTERS["Unarchived"].get("is_true"):
                    is_send = True
                    if channel_id not in channel_lst:
                        message += f"## {info['channel_name']} ({channel_id})\n---\n"
                        channel_lst.append(channel_id)
                    message += f"- Title: {video['title']}\n- Stream ID: [{video['video_id']}](https://www.youtube.com/watch?v={video['video_id']})\n---\n"

                body += f"""
                            <hr />
                            <li style="list-style-type: none; {'color: red; font-weight: bold; font-style: oblique;' if FILTERS["Unarchived"].get("is_true") else ''}">
                                <span><strong>🏷️ Title: </strong>{video['title']}</span> {"".join(filters[1].get("label", "") if filters[1].get("is_true", False) else "" for filters in FILTERS.items())} {"" if exists else new_label}
                                <br />
                                <span><strong>📝 Translated Title: </strong>{get_translated_title(video['title'], translate_title)}</span>
                                <br />
                                <span><strong>🆔 Stream ID: </strong><span style="font-weight: bold; font-family: consolas, 'Times New Roman', tahoma; font-size:x-large;">{video['video_id']}</span></span>
                                <br />
                                <span><strong>🖼️ Thumbnail: </strong> <img src="{video['thumbnail']}"/></span>
                                <br />
                                <a href="https://www.youtube.com/watch?v={video['video_id']}"><strong>▶️ Watch Stream</strong></a>
                            </li>
                        """
                for filters in FILTERS.items():
                    filters[1]["is_true"] = False
            body += "</ul></li>"

    body += "</ul></body></html>"
    body_first = f"""<!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                </head>
                <body>
                <h1>🔴 YouTube Live Streams</h1>
                <br />
                {''.join(f'<h2 style="color: {filters[1].get("color", "green")}; font-weight: bold;">{filters[1].get("icon", "📣")} {filters[1].get("counter")} {filters[0]} Live Streams</h2>' if filters[1].get("counter") > 0 else "" for filters in FILTERS.items())}
                {f'<h2 style="color: blue; font-weight: bold;">🆕 {new_counter} New Live Streams</h2>' if new_counter > 0 else ""}
                {f'<h2 style="color: #4B0082; font-weight: bold;">📊 {total_streams} Live Streams in total.</h2>'}
                <ul>
            """
    body = body_first + body
    current_hash = md5(str(live_streams).encode("utf-8")).hexdigest()

    message = f"# `Total {FILTERS['Unarchived'].get('counter')} Unarchived Live Streams.`\n {message}"

    is_exists = Path("./prev_hash_live.md5").exists()
    if not is_exists:
        print("create file")
        with open("./prev_hash_live.md5", mode="w", encoding="utf-8") as file:
            pass

    with open("./prev_hash_live.md5", mode="r+", encoding="utf-8") as file:
        prev_hash = file.readline().strip()
        print_text(f"prev_live_hash: {prev_hash}")
        print_text(f"curr_live_hash: {current_hash}")
        if prev_hash != current_hash:
            file.seek(0, 0)
            file.write(current_hash)
            send_email(subject, body)
            if is_send:
                send_discord_message(DISCORD_WEBHOOK_URL, message=message)
        else:
            print_text("Nothing changed!", "S")


def get_info_livestream(channel_url: str):
    Path("./temp").mkdir(parents=True, exist_ok=True)
    original_cookies = Path("cookies.txt").absolute()
    src_dir = original_cookies.parent
    temp_dir = src_dir / "temp"
    temp_dir = temp_dir.resolve()
    temp_cookies_name = f"{uuid4().hex}.txt"
    temp_cookies_path = temp_dir / temp_cookies_name
    temp_cookies_path = temp_cookies_path.resolve()
    shutil.copy(original_cookies, temp_cookies_path)
    yt_opts = {
        "extract_flat": True,
        "skip_download": True,
        "quiet": True,
        "cookiefile": temp_cookies_path,
        "verbose": False,
    }
    # "logger": logging.getLogger(), # in yt_opts
    upcoming = {}
    live_streams = {}
    avatar_url = ""
    with yt_dlp.YoutubeDL(yt_opts) as ydl:
        try:
            if not channel_url.endswith("streams"):
                live_url = channel_url + "/streams"
            result = ydl.extract_info(live_url, download=False)
            channel_id = result.get("uploader_id", channel_url.split("/")[-1])
            print_text(f"Searching from channel: {channel_id}")
            channel_name = result.get("channel")
            videos_upcoming = []
            videos_live = []
            count = 0
            for entry in result.get("entries", []):
                if count > 10:
                    break
                title = entry.get("title", "")
                status = entry.get("live_status", "")
                thumbnail = entry.get("thumbnails")[-1].get("url")
                description = entry.get("description")
                if status == "is_upcoming":
                    print_text("Found upcoming live stream!", prefix="S")
                    print_text(f"Title: {title}", "T")
                    video_id = entry.get("id")
                    if video_id in SKIP_STREAMS:
                        continue
                    scheduled_time = entry.get("release_timestamp")
                    tz = pytz.timezone("Asia/Ho_Chi_Minh")
                    scheduled_time_readable = datetime.fromtimestamp(
                        scheduled_time, tz
                    ).strftime("%Y/%m/%d %H:%M:%S")
                    scheduled_date = datetime.fromtimestamp(scheduled_time)
                    current = datetime.now()
                    delta = scheduled_date - current
                    if delta.days > 10:
                        continue
                    videos_upcoming.append(
                        {
                            "video_id": video_id,
                            "title": title,
                            "date": scheduled_time_readable,
                            "thumbnail": thumbnail,
                            "description": description,
                        }
                    )
                elif status == "is_live":
                    print_text("Found live stream!", prefix="S")
                    print_text(f"Title: {title}", "T")
                    video_id = entry.get("id")
                    if video_id in SKIP_STREAMS:
                        continue
                    videos_live.append(
                        {
                            "video_id": video_id,
                            "title": title,
                            "thumbnail": thumbnail,
                            "description": description,
                        }
                    )
                else:
                    continue
                count += 1

            with open("./vtuber.json", "r", encoding="utf-8") as file:
                raw_data = json.load(file)
                avatar_url = raw_data.get(channel_id, "@dooby3d").get(
                    "avatar_url",
                    "https://yt3.googleusercontent.com/U3KyLvyQRzOrgRHZYEYPQCc1QS2Jx5LnQF_5H6aYDluVM8AOnAZ90U0tSY3aVobgVNlRccieDA",
                )

            upcoming[channel_id] = {
                "channel_url": channel_url,
                "channel_name": channel_name,
                "avatar_url": avatar_url,
                "videos": videos_upcoming,
            }
            live_streams[channel_id] = {
                "channel_url": channel_url,
                "channel_name": channel_name,
                "avatar_url": avatar_url,
                "videos": videos_live,
            }
        except Exception as e:
            print_text(f"Failed to fetch data for {channel_url}: {e}", prefix="E")

    upcoming = sort_obj(upcoming)
    live_streams = sort_obj(live_streams)

    return upcoming, live_streams


def process_channels(channel_urls: list[str], max_workers=5):
    upcoming_all = {}
    live_streams_all = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(get_info_livestream, url): url for url in channel_urls
        }

        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                upcoming, live_streams = future.result()
                for channel_id, data in upcoming.items():
                    upcoming_all[channel_id] = data
                for channel_id, data in live_streams.items():
                    live_streams_all[channel_id] = data
            except Exception as e:
                print_text(f"Error processing {url}: {e}", "E")

    upcoming_all = sort_obj(upcoming_all)
    live_streams_all = sort_obj(live_streams_all)

    return upcoming_all, live_streams_all


def main():
    # os.system('cls' if os.name=='nt' else 'clear')
    print(f"You are in {ENV} environment!")
    start = datetime.now(pytz.timezone("Asia/Ho_Chi_Minh"))
    channel_urls = get_channel_url("channel_url.txt")
    upcoming, live_streams = process_channels(channel_urls, 10)

    send_email_upcoming(upcoming)
    send_email_live(live_streams)

    with open("./live_streams.json", mode="w", encoding="utf-8") as file:
        json.dump(live_streams, file, ensure_ascii=False, indent=4)
        print_text("Saved in to live_streams.json", "S")

    with open("./upcoming.json", mode="w", encoding="utf-8") as file:
        json.dump(upcoming, file, ensure_ascii=False, indent=4)
        print_text("Saved in to upcoming.json", "S")

    end = datetime.now(pytz.timezone("Asia/Ho_Chi_Minh"))
    delta = end - start
    with open("./time-run.txt", "a", encoding="utf-8") as file:
        file.write(
            f"{start.strftime('%Y/%m/%d-%H:%M:%S')} ::: Script ran {pretty_time_delta(delta)} ({delta.total_seconds()} seconds)\n"
        )
    print_text(
        f"Done at {datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')).strftime('%d/%m/%Y %H:%M:%S')}",
        prefix="S",
    )
    time.sleep(5)


if __name__ == "__main__":
    init_db()
    main()
    clean_up_old_titles()
    try:
        shutil.rmtree("./temp")
    except OSError as e:
        print("Error: %s - %s." % (e.filename, e.strerror))
