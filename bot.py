import discord
import aiohttp
import json
import os
import time
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
    "@NoInjusticeLastsForever",
    "@John.AR.Activism",
    "@HazVegan",
    "@DebugYourBrain",
    "@VeganFelek",
    "@BrianLovesBeans",
    "@ChaseAvior",
    "@foolproofmastery",
    "@VeganTableTalks",
    "@CarnistWordSaLAD",
    "@theVegan47",
    "@The40yearoldVegan",
    "@SoyDaddy1",
    "@imjesperbtw",
    "@tessasaves",
    "@standbesidejordan"
]

STATE_FILE = "youtube_state.json"
MAX_CONCURRENT_CHECKS = 5
SHORTS_CHECK_INTERVAL_SECONDS = 1800


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


def get_cached_channel_title(state, channel_identifier):
    return state.get("_channel_titles", {}).get(channel_identifier)


def cache_channel_title(state, channel_identifier, title):
    state.setdefault("_channel_titles", {})[channel_identifier] = title


def get_shorts_playlist_id(playlist_id):
    return "UUSH" + playlist_id[2:]


def get_seen_shorts(state, channel_identifier):
    return state.get("_shorts", {}).get(channel_identifier)


def cache_seen_shorts(state, channel_identifier, video_ids):
    state.setdefault("_shorts", {})[channel_identifier] = video_ids


async def get_channel_details(session, channel_identifier):
    if channel_identifier.startswith("UC"):
        url = f"https://www.googleapis.com/youtube/v3/channels?part=snippet,contentDetails&id={channel_identifier}&key={YOUTUBE_API_KEY}"
    elif channel_identifier.startswith("@"):
        url = f"https://www.googleapis.com/youtube/v3/channels?part=snippet,contentDetails&forHandle={channel_identifier}&key={YOUTUBE_API_KEY}"
    else:
        return None, None

    async with session.get(url) as response:
        data = await response.json()
        items = data.get("items", [])
        if not items:
            return None, None
        playlist_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
        title = items[0]["snippet"]["title"]
        return playlist_id, title


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


async def process_channel(session, yt_channel, state, discord_channel, semaphore):
    async with semaphore:
        playlist_id = get_cached_playlist_id(state, yt_channel)
        channel_title = get_cached_channel_title(state, yt_channel)
        if not playlist_id or not channel_title:
            playlist_id, channel_title = await get_channel_details(session, yt_channel)
            if not playlist_id:
                print(f"Could not resolve playlist ID for {yt_channel}")
                return
            cache_playlist_id(state, yt_channel, playlist_id)
            cache_channel_title(state, yt_channel, channel_title)
            save_state(state)

        url = f"https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails&playlistId={playlist_id}&maxResults=5&key={YOUTUBE_API_KEY}"
        async with session.get(url) as response:
            if response.status != 200:
                print(f"YouTube API returned status {response.status} for {yt_channel}")
                return

            data = await response.json()
            items = data.get("items", [])

            if yt_channel not in state:
                state[yt_channel] = [item["contentDetails"]["videoId"] for item in items]
                save_state(state)
                return

            new_videos = []
            for item in reversed(items):
                video_id = item["contentDetails"]["videoId"]
                if video_id not in state[yt_channel]:
                    new_videos.append(video_id)

            broadcast_statuses = await get_broadcast_statuses(session, new_videos)

            for video_id in new_videos:
                status = broadcast_statuses.get(video_id)
                if status == "live":
                    action = "started a livestream now!"
                elif status == "upcoming":
                    action = "is going to be live soon!"
                else:
                    action = "uploaded a new YouTube video!"

                message = f"Hey <@&1399648272125267978> **{channel_title}** {action}\nhttps://www.youtube.com/watch?v={video_id}"

                try:
                    await discord_channel.send(message)
                    state[yt_channel].append(video_id)

                    if len(state[yt_channel]) > 20:
                        state[yt_channel] = state[yt_channel][-20:]

                    save_state(state)
                    await asyncio.sleep(2.0)
                except Exception as e:
                    print(f"Failed to send Discord message: {e}")


async def process_channel_shorts(session, yt_channel, state, discord_channel, semaphore, channel_title, playlist_id):
    async with semaphore:
        shorts_playlist_id = get_shorts_playlist_id(playlist_id)
        url = f"https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails&playlistId={shorts_playlist_id}&maxResults=5&key={YOUTUBE_API_KEY}"
        async with session.get(url) as response:
            if response.status != 200:
                print(f"YouTube API returned status {response.status} for {yt_channel} shorts playlist")
                return

            data = await response.json()
            items = data.get("items", [])

            seen_shorts = get_seen_shorts(state, yt_channel)
            if seen_shorts is None:
                cache_seen_shorts(state, yt_channel, [item["contentDetails"]["videoId"] for item in items])
                save_state(state)
                return

            already_posted = set(seen_shorts) | set(state.get(yt_channel, []))

            new_shorts = [
                item["contentDetails"]["videoId"]
                for item in reversed(items)
                if item["contentDetails"]["videoId"] not in already_posted
            ]

            for video_id in new_shorts:
                message = f"Hey <@&1399648272125267978> **{channel_title}** uploaded a new YouTube Short!\nhttps://www.youtube.com/watch?v={video_id}"

                try:
                    await discord_channel.send(message)
                    seen_shorts.append(video_id)

                    if len(seen_shorts) > 20:
                        seen_shorts = seen_shorts[-20:]

                    cache_seen_shorts(state, yt_channel, seen_shorts)
                    save_state(state)
                    await asyncio.sleep(2.0)
                except Exception as e:
                    print(f"Failed to send Discord message: {e}")


async def check_youtube_videos(discord_channel):
    state = load_state()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHECKS)

    async with aiohttp.ClientSession() as session:
        await asyncio.gather(
            *(
                process_channel(session, yt_channel, state, discord_channel, semaphore)
                for yt_channel in YOUTUBE_CHANNELS
            )
        )

        last_shorts_check = state.get("_last_shorts_check", 0)
        if time.time() - last_shorts_check >= SHORTS_CHECK_INTERVAL_SECONDS:
            await asyncio.gather(
                *(
                    process_channel_shorts(
                        session,
                        yt_channel,
                        state,
                        discord_channel,
                        semaphore,
                        get_cached_channel_title(state, yt_channel),
                        get_cached_playlist_id(state, yt_channel),
                    )
                    for yt_channel in YOUTUBE_CHANNELS
                    if get_cached_playlist_id(state, yt_channel)
                )
            )
            state["_last_shorts_check"] = time.time()
            save_state(state)


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
