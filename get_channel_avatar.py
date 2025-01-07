import json
import re

import requests


def get_channel_avatar(channel_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
    }
    print(f">>> Getting data from: {channel_url}")
    response = requests.get(channel_url, headers=headers)

    if response.status_code == 200:
        match = re.search(
            r"https://yt3\.googleusercontent\.com/(ytc/)?([a-zA-Z0-9_-]+)",
            response.text,
        )  # =s{size}-c-k-c0x00ffffff-no-rj

        if match:
            return match.group(0).strip()
        else:
            print("Not found the avatar URL for this channel!")
            return None
    else:
        print(f"Unable to access the channel: {response.status_code}")
        return None


if __name__ == "__main__":
    vtuber_data = {}
    with open("./vtuber.json", "r", encoding="utf-8") as file:
        vtuber_data = json.load(file)

    for channel_id, channel_data in vtuber_data.items():
        channel_url = channel_data.get("link", "").get("youtube")
        avatar_url = get_channel_avatar(channel_url)
        channel_data["avatar_url"] = avatar_url

    with open("./vtuber.json", "w", encoding="utf-8") as file:
        json.dump(vtuber_data, file, ensure_ascii=False, indent=4)
