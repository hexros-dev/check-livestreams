import copy
import json
import time
from pathlib import Path

LIVE_STEAMS_PATH = Path("./live_streams.json").absolute()
UPCOMING_STEAMS_PATH = Path("./upcoming.json").absolute()
IS_TEST = False
if IS_TEST:
    LIVE_STEAMS_PATH = Path("./tests/live_streams_test.json").absolute()
    UPCOMING_STEAMS_PATH = Path("./tests/upcoming_test.json").absolute()


def run():
    print(">>> Loading data...")
    vtuber_data = {}
    data = {}
    with open("./vtuber.json", "r", encoding="utf-8") as file:
        vtuber_data = json.load(file)

    for channel_id, channel_data in vtuber_data.items():
        data[channel_id] = {
            "channel_url": channel_data.get(
                "link", "https://www.youtube.com/@notfound"
            ).get("youtube"),
            "channel_name": channel_data.get("channel_name", "John Doe Ch."),
            "avatar_url": channel_data.get(
                "avatar_url",
                "https://yt3.googleusercontent.com/U3KyLvyQRzOrgRHZYEYPQCc1QS2Jx5LnQF_5H6aYDluVM8AOnAZ90U0tSY3aVobgVNlRccieDA",
            ),
            "videos": [],
        }

    with open(LIVE_STEAMS_PATH, "r", encoding="utf-8") as file:
        live_data = json.load(file)

    with open(UPCOMING_STEAMS_PATH, "r", encoding="utf-8") as file:
        upcoming_data = json.load(file)

    live_streams_result = copy.deepcopy(data)
    for channel_id, l_data in live_data.items():
        if l_data.get("videos", []):
            if channel_id in live_streams_result:
                live_streams_result[channel_id]["videos"] = l_data.get("videos", [])

    upcoming_result = copy.deepcopy(data)
    for channel_id, u_data in upcoming_data.items():
        if u_data.get("videos", []):
            if channel_id in upcoming_result:
                upcoming_result[channel_id]["videos"] = u_data.get("videos", [])

    with open(LIVE_STEAMS_PATH, "w", encoding="utf-8") as file:
        json.dump(live_streams_result, file, ensure_ascii=False, indent=4)

    with open(UPCOMING_STEAMS_PATH, "w", encoding="utf-8") as file:
        json.dump(upcoming_result, file, ensure_ascii=False, indent=4)

    print(">>> Loaded!")
    time.sleep(2)


if __name__ == "__main__":
    run()
