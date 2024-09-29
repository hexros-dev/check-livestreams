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
    body = f'''
                <h1>📹 Upcoming YouTube Live Streams</h1>
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
                schedule_date = datetime.strptime(video['date'].split(" (GMT+7)")[0], "%d/%m/%Y %H:%M:%S")
                delta = schedule_date - now_
                seconds = delta.total_seconds()

                if seconds <= LIMIT * 60:
                    flag = True
                    
                emoji = get_clock_emoji(schedule_date)
                body += f'''
                            <hr />
                            <li style="list-style-type: none;">
                                <strong>🏷️ Title: </strong> <span>{video['title']}</span>
                                <br />
                                <strong>{emoji} Scheduled for: </strong> <span>{video['date']} ({str(delta)} from now)</span>
                                <br />
                                <a href="https://www.youtube.com/watch?v={video['video_id']}"><strong>▶️ Open Video</strong></a>
                            </li>
                        '''
        
            body += '</ul></li>'

    body += '</ul>'

    current_hash = md5(str(live_streams).encode('utf-8')).hexdigest()
    
    is_exists = Path('./prev_hash_upcoming.md5').exists()
    if not is_exists:
        print("create file")
        with open("./prev_hash_upcoming.md5", mode='w', encoding='utf-8') as file:
            pass

    with open("./prev_hash_upcoming.md5", mode='r+', encoding='utf-8') as file:
        prev_hash = file.readline().strip()
        print_text(f"prev_hash: {prev_hash}")
        print_text(f"curr_hash: {current_hash}")
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
    body = f'''
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
                                <a href="https://www.youtube.com/watch?v={video['video_id']}"><strong>Open Video</strong></a>
                            </li>
                        '''
        
            body += '</ul></li>'

    body += '</ul>'

    current_hash = md5(str(live_streams).encode('utf-8')).hexdigest()
    
    is_exists = Path('./prev_hash_live.md5').exists()
    if not is_exists:
        print("create file")
        with open("./prev_hash_live.md5", mode='w', encoding='utf-8') as file:
            pass

    with open("./prev_hash_live.md5", mode='r+', encoding='utf-8') as file:
        prev_hash = file.readline().strip()
        print_text(f"prev_hash: {prev_hash}")
        print_text(f"curr_hash: {current_hash}")
        if prev_hash != current_hash:
            file.seek(0, 0)
            file.write(current_hash)
            send_email(subject, body)
        else:
            print_text("Nothing changed!", "S")

def get_info_livestream(channel_urls: list[str]):
    yt_opts = {
        'extract_flat': True,
        'skip_download': True,
        'quiet': True
    }
    upcoming = {}
    live_streams = {}
    with yt_dlp.YoutubeDL(yt_opts) as ydl:
        for channel_url in channel_urls:
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
                    status = entry.get('live_status')
                    if status == 'is_upcoming':
                        print_text('Found upcoming live stream!', prefix='S')
                        print_text(f"Title: {title}")
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
                            "date": scheduled_time_readable
                        })
                    elif status == 'is_live':
                        print_text('Found live stream!', prefix='S')
                        print_text(f"Title: {title}")
                        video_id = entry.get('id')
                        videos_live.append({
                            "video_id": video_id,
                            "title": title,
                        })
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
    
    return upcoming, live_streams

if __name__ == '__main__':
    os.system('cls' if os.name=='nt' else 'clear')
    channel_urls = get_channel_url("channel_url.txt")
    upcoming, live_streams = get_info_livestream(channel_urls)

    send_email_upcoming(upcoming)
    send_email_live(live_streams)
    with open('./live_streams.json', mode='w', encoding='utf-8') as file:
        file.write(json.dumps(live_streams, ensure_ascii=False))

    with open('./upcoming.json', mode='w', encoding='utf-8') as file:
        file.write(json.dumps(upcoming, ensure_ascii=False))
    
    print_text("Done!", prefix='S')
