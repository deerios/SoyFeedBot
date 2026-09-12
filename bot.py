import discord
import aiohttp
import json
import os
import asyncio

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
DISCORD_CHANNEL_ID = int(os.environ["DISCORD_CHANNEL_ID"])
YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]

YOUTUBE_CHANNELS = [
    "@DannyIshay",
    "@VirtuePostMortem",
    "@iloveveganpvssy",
    "@jadeforjustice",
    "@chrisbryantphd",
    "@plantgeezer",
    "@ThatChipGuy",
    "@jakeastonfta",
    "@VeganStonerLady",
    "@jemlettuce",
    "@forindividuals",
    "@vegangaze",
    "@AxelBertilDahlström",
    "@VeganHeretic",
    "@dr.matthewnagra",
    "@loebjeremy",
    "@JasonGutt",
    "@MehtaEthics",
    "@TheTallestMunchkin",
    "@earthtomanar",
    "@NoInjusticeLastsForever"
]

STATE_FILE = "youtube_state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)


def get_cached_playlist_id(state, channel_identifier):
    return state.get("_playlist_ids", {}).get(channel_identifier)


def cache_playlist_id(state, channel_identifier, playlist_id):
    state.setdefault("_playlist_ids", {})[channel_identifier] = playlist_id


async def get_uploads_playlist_id(session, channel_identifier):
    if channel_identifier.startswith("UC"):
        return channel_identifier.replace("UC", "UU", 1)

    if channel_identifier.startswith("@"):
        url = f"https://www.googleapis.com/youtube/v3/channels?part=contentDetails&forHandle={channel_identifier}&key={YOUTUBE_API_KEY}"
        async with session.get(url) as response:
            data = await response.json()
            items = data.get("items", [])
            if items:
                return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
            return None

    return None


async def get_broadcast_statuses(session, video_ids):
    if not video_ids:
        return {}
    ids_param = ",".join(video_ids)
    url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={ids_param}&key={YOUTUBE_API_KEY}"
    async with session.get(url) as response:
        if response.status != 200:
            print(f"YouTube API returned status {response.status} for videos.list")
            return {}
        data = await response.json()
        return {item["id"]: item["snippet"]["liveBroadcastContent"] for item in data.get("items", [])}


async def check_youtube_videos(discord_channel):
    state = load_state()

    async with aiohttp.ClientSession() as session:
        for yt_channel in YOUTUBE_CHANNELS:
            playlist_id = get_cached_playlist_id(state, yt_channel)
            if not playlist_id:
                playlist_id = await get_uploads_playlist_id(session, yt_channel)
                if not playlist_id:
                    print(f"Could not resolve playlist ID for {yt_channel}")
                    continue
                cache_playlist_id(state, yt_channel, playlist_id)
                save_state(state)

            url = f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&playlistId={playlist_id}&maxResults=5&key={YOUTUBE_API_KEY}"
            async with session.get(url) as response:
                if response.status != 200:
                    print(f"YouTube API returned status {response.status} for {yt_channel}")
                    continue

                data = await response.json()
                items = data.get("items", [])

                if yt_channel not in state:
                    state[yt_channel] = [item["snippet"]["resourceId"]["videoId"] for item in items]
                    save_state(state)
                    continue

                new_videos = []
                for item in reversed(items):
                    video_id = item["snippet"]["resourceId"]["videoId"]
                    if video_id not in state[yt_channel]:
                        new_videos.append(item)

                broadcast_statuses = await get_broadcast_statuses(
                    session, [item["snippet"]["resourceId"]["videoId"] for item in new_videos]
                )

                for item in new_videos:
                    video_id = item["snippet"]["resourceId"]["videoId"]
                    channel_name = item["snippet"]["videoOwnerChannelTitle"]

                    if broadcast_statuses.get(video_id) == "live":
                        action = "started a livestream now!"
                    else:
                        action = "uploaded a new YouTube video!"

                    message = f"Hey <@&1399648272125267978> **{channel_name}** {action}\nhttps://www.youtube.com/watch?v={video_id}"

                    try:
                        await discord_channel.send(message)
                        state[yt_channel].append(video_id)

                        if len(state[yt_channel]) > 20:
                            state[yt_channel] = state[yt_channel][-20:]

                        save_state(state)
                        await asyncio.sleep(2.0)
                    except Exception as e:
                        print(f"Failed to send Discord message: {e}")

            await asyncio.sleep(0.5)


class OneShotClient(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}. Running single check pass...")
        channel = self.get_channel(DISCORD_CHANNEL_ID)
        if channel is None:
            channel = await self.fetch_channel(DISCORD_CHANNEL_ID)

        try:
            await check_youtube_videos(channel)
        finally:
            await self.close()


def main():
    intents = discord.Intents.default()
    client = OneShotClient(intents=intents)
    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
