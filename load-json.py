import json
    

def run():
    # load vtuber.json
    vtuber_data = {}
    data = {}
    with open("./vtuber.json", "r", encoding="utf-8") as file:
        vtuber_data = json.load(file)
    
    for channel_id, channel_data in vtuber_data.items():
        data[channel_id] = {
            "channel_url": channel_data.get("link", "https://www.youtube.com/@notfound").get("youtube"),
            "channel_name": channel_data.get("channel_name", "John Doe Ch."),
            "avatar_url": channel_data.get("avatar_url", "https://yt3.googleusercontent.com/U3KyLvyQRzOrgRHZYEYPQCc1QS2Jx5LnQF_5H6aYDluVM8AOnAZ90U0tSY3aVobgVNlRccieDA"),
            "videos": []
        }
    
    with open("./live_streams.json", "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False)

    with open("./upcoming.json", "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False)


if __name__ == "__main__":
    run()