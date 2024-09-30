from datetime import datetime
from pathlib import Path
import yt_dlp
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from hashlib import md5
import pytz
from concurrent.futures import ThreadPoolExecutor, as_completed

SENDER_EMAIL = os.getenv('SENDER_EMAIL')
SENDER_PWD = os.getenv('SENDER_PWD')
RECEIVER_EMAIL = os.getenv('RECEIVER_EMAIL')
LIMIT = 15 # minutes

class Color:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    PURPLE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'

def get_clock_emoji(dt: datetime) -> str:
    emojis = ["🕛","🕧","🕐","🕜","🕑","🕝","🕒","🕞","🕓","🕟","🕔","🕠","🕕","🕡","🕖","🕢","🕗","🕣","🕘","🕤","🕙","🕥","🕚","🕦"]

    index = (dt.hour % 12 * 2 + (1 if dt.minute >= 15 else 0) + (1 if dt.minute >= 45 else 0)) % len(emojis)
    return emojis[index]

def print_text(text: str, prefix: str = 'I', suffix: str = '\n') -> None:
    _type = prefix.upper()
    match(_type):
        case 'I':
            print(f"{Color.CYAN}", end='')
        case 'S':
            print(f"{Color.GREEN}", end='')
        case 'W':
            print(f"{Color.YELLOW}", end='')
        case 'E':
            print(f"{Color.RED}", end='')
        case 'Q':
            print(f"{Color.PURPLE}", end='')
        case _:
            pass
    print(f"<{prefix if prefix else '?'}> {text}{Color.RESET}", end=suffix)

def get_channel_url(file_path: str) -> list[str] | None:
    is_exists = Path(file_path).exists()
    if not is_exists:
        print_text(f"File {file_path} is not exist. Please create file and try again!", prefix='E')
        exit(1)
    with open(file_path, mode='r', encoding='utf-8') as file:
        lines = file.readlines()
        result = [line.strip() for line in lines]
    
    return result

def send_email(subject: str, body: str) -> None:
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PWD)
        text = msg.as_string()
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, text)
        server.quit()
        print_text("Email sent successfully!", 'S')
    except Exception as e:
        print_text(f"Failed to send email: {e}", 'E')

def send_email_upcoming(live_streams: str) -> None:
    now_ = datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')).strftime("%d/%m/%Y %H:%M:%S")
    subject = f"🗓️ Upcoming YouTube Live Streams Notification {now_}"
    now_ = datetime.strptime(now_, "%d/%m/%Y %H:%M:%S")
    flag = False
    need_red = False
    is_bold = False
    is_unarchived = False
    body = ""
    for channel_id, info in live_streams.items():
        if info['videos']:
            body += f'''
                        <li>
                            <strong style="font-size: 18px;">{info['channel_name']} ({channel_id})</strong> - <a href="{info['channel_url']}"><strong>Visit Channel</strong></a>
                            <ul>
                    '''
            for video in info['videos']:
                schedule_date = datetime.strptime(video['date'].split(" (GMT+7)")[0], "%d/%m/%Y %H:%M:%S")
                delta = schedule_date - now_
                seconds = delta.total_seconds()
                if "free" in video['title'].lower():
                    is_bold = True
                    need_red = True
                    is_unarchived = True
                if seconds <= LIMIT * 60:
                    flag = True
                    need_red = True
                    
                emoji = get_clock_emoji(schedule_date)
                body += f'''
                            <hr />
                            <li style="list-style-type: none; {"color:red;" if need_red else ""} {"font-weight: bold; font-style: oblique;" if is_bold else ""} ">
                                <strong>🏷️ Title: </strong> <span>{video['title']}</span>
                                <br />
                                <span><strong>🖼️ Thumbnail: </strong> <img src='{video['thumbnail']}'/></span>
                                <br />
                                <strong>{emoji} Scheduled for: </strong> <span>{video['date']} ({str(delta)} from now)</span>
                                <br />
                                <a href="https://www.youtube.com/watch?v={video['video_id']}"><strong>▶️ Open Video</strong></a>
                            </li>
                        '''
                need_red = False
                is_bold = False
            body += '</ul></li>'

    body += '</ul></html>'
    body_first = f'''<html>
                <h1>📹 Upcoming YouTube Live Streams</h1>
                {"<h2> Have Unarchived Live Streams</h2>" if is_unarchived else ""}
                <br />
                <ul>
            '''
    body = body_first + body
    current_hash = md5(str(live_streams).encode('utf-8')).hexdigest()
    
    is_exists = Path('./prev_hash_upcoming.md5').exists()
    if not is_exists:
        print("create file")
        with open("./prev_hash_upcoming.md5", mode='w', encoding='utf-8') as file:
            pass

    with open("./prev_hash_upcoming.md5", mode='r+', encoding='utf-8') as file:
        prev_hash = file.readline().strip()
        print_text(f"prev_upcoming_hash: {prev_hash}")
        print_text(f"curr_upcoming_hash: {current_hash}")
        if prev_hash != current_hash:
            file.seek(0, 0)
            file.write(current_hash)
            send_email(subject, body)
        else:
            if flag:
                send_email(subject, body)
            else:
                print_text("Nothing changed!", "S")

def send_email_live(live_streams: str) -> None:
    subject = f"🔴 YouTube Live Streams Notification {datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')).strftime("%d/%m/%Y %H:%M:%S")}"
    body = f'''<html>
                <h1>🔴 YouTube Live Streams</h1>
                <br />
                <ul>
            '''
    for channel_id, info in live_streams.items():
        if info['videos']:
            body += f'''
                        <li>
                            <strong style="font-size: 18px;">{info['channel_name']} ({channel_id})</strong> - <a href="{info['channel_url']}"><strong>Visit Channel</strong></a>
                            <ul>
                    '''
            for video in info['videos']:
                body += f'''
                            <hr />
                            <li style="list-style-type: none;">
                                <strong>🏷️ Title: </strong> <span>{video['title']}</span>
                                <br />
                                <span><strong>🖼️ Thumbnail: </strong> <img src='{video["thumbnail"]}'/></span>
                                <br />
                                <a href="https://www.youtube.com/watch?v={video['video_id']}"><strong>▶️ Open Video</strong></a>
                            </li>
                        '''
        
            body += '</ul></li>'

    body += '</ul></html>'

    current_hash = md5(str(live_streams).encode('utf-8')).hexdigest()
    
    is_exists = Path('./prev_hash_live.md5').exists()
    if not is_exists:
        print("create file")
        with open("./prev_hash_live.md5", mode='w', encoding='utf-8') as file:
            pass

    with open("./prev_hash_live.md5", mode='r+', encoding='utf-8') as file:
        prev_hash = file.readline().strip()
        print_text(f"prev_live_hash: {prev_hash}")
        print_text(f"curr_live_hash: {current_hash}")
        if prev_hash != current_hash:
            file.seek(0, 0)
            file.write(current_hash)
            send_email(subject, body)
        else:
            print_text("Nothing changed!", "S")

def sort_obj(obj):
    obj = dict(sorted(obj.items(), key=lambda item:item[0]))

    for id_obj in obj.values():
        id_obj["videos"] = sorted(id_obj["videos"], key=lambda video:video["video_id"])
        
    return obj

def get_info_livestream(channel_url: str):
    yt_opts = {
        'extract_flat': True,
        'skip_download': True,
        'quiet': True
    }
    upcoming = {}
    live_streams = {}
    with yt_dlp.YoutubeDL(yt_opts) as ydl:
        try:
            if not channel_url.endswith('streams'):
                live_url = channel_url + '/streams'
            result = ydl.extract_info(live_url, download=False)
            channel_id = result.get('uploader_id')
            print_text(f'Searching from channel: {channel_id}')
            channel_name = result.get('channel')
            videos_upcoming = []
            videos_live = []
            count = 0
            for entry in result.get('entries', []):
                if count > 10:
                    break
                title = entry.get('title', '')
                status = entry.get('live_status', '')
                thumbnail = entry.get('thumbnails')[-1].get('url')
                if status == 'is_upcoming':
                    print_text('Found upcoming live stream!', prefix='S')
                    print_text(f"Title: {title}", "T")
                    video_id = entry.get('id')
                    scheduled_time = entry.get('release_timestamp')
                    tz = pytz.timezone('Asia/Ho_Chi_Minh')
                    scheduled_time_readable = datetime.fromtimestamp(scheduled_time, tz).strftime('%d/%m/%Y %H:%M:%S (GMT+7)')
                    scheduled_date = datetime.fromtimestamp(scheduled_time)
                    current = datetime.now()
                    delta = scheduled_date - current
                    if delta.days > 50:
                        continue
                    videos_upcoming.append({
                        "video_id": video_id,
                        "title": title,
                        "date": scheduled_time_readable,
                        "thumbnail": thumbnail
                    })
                elif status == 'is_live':
                    print_text('Found live stream!', prefix='S')
                    print_text(f"Title: {title}")
                    video_id = entry.get('id')
                    videos_live.append({
                        "video_id": video_id,
                        "title": title,
                        "thumbnail": thumbnail
                    })
                else:
                    continue
                count += 1
            upcoming[channel_id] = {
                "channel_url": channel_url,
                "channel_name": channel_name,
                "videos": videos_upcoming
            }
            live_streams[channel_id] = {
                "channel_url": channel_url,
                "channel_name": channel_name,
                "videos": videos_live
            }
        except Exception as e:
            print_text(f"Failed to fetch data for {channel_url}: {e}", prefix='E')

    upcoming = sort_obj(upcoming)
    live_streams = sort_obj(live_streams)
    
    return upcoming, live_streams

def process_channels(channel_urls: list[str], max_workers=5):
    upcoming_all = {}
    live_streams_all = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(get_info_livestream, url): url for url in channel_urls}

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



if __name__ == '__main__':
    os.system('cls' if os.name=='nt' else 'clear')
    channel_urls = get_channel_url("channel_url.txt")
    upcoming, live_streams = process_channels(channel_urls, 15)

    send_email_upcoming(upcoming)
    send_email_live(live_streams)
    with open('./live_streams.json', mode='w', encoding='utf-8') as file:
        file.write(json.dumps(live_streams, ensure_ascii=False))

    with open('./upcoming.json', mode='w', encoding='utf-8') as file:
        file.write(json.dumps(upcoming, ensure_ascii=False))
    
    print_text("Done!", prefix='S')
