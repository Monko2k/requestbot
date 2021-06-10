import asyncio
from websocket import create_connection
from osu_sr_calculator import calculateStarRating
import irc
import re
import requests
import json

# https://old.ppy.sh/p/irc
BANCHO_IRC_USERNAME = ""
BANCHO_IRC_PASSWORD = ""

# https://old.ppy.sh/p/api
OSU_API_KEY = ""

# https://twitchapps.com/tmi/
TWITCH_IRC_USERNAME = ""
TWITCH_IRC_PASSWORD = ""


loop = asyncio.get_event_loop()

bancho_client = irc.Client(irc.Endpoint(host="cho.ppy.sh", port=6667, ssl=False))
bancho_credentials = irc.Credentials(username=BANCHO_IRC_USERNAME, password=BANCHO_IRC_PASSWORD)

twitch_client = irc.Client(irc.Endpoint(host="irc.chat.twitch.tv", port=6697, ssl=True))
twitch_credentials = irc.Credentials(username=TWITCH_IRC_USERNAME, password=TWITCH_IRC_PASSWORD)

def connect(client) -> None:
    loop.create_task(client.connect())


def login(client, credentials) -> None:
    client.send(irc.Pass(credentials.password))
    client.send(irc.Nick(credentials.username))


@bancho_client.on("CONNECT")
async def on_bancho_connect() -> None:
    login(bancho_client, bancho_credentials)


@bancho_client.on("PING")
def on_bancho_ping(ping: irc.Ping) -> None:
    pong = irc.Pong(ping.message)
    bancho_client.send(pong)


@bancho_client.on("PRIVMSG")
def on_bancho_privmsg(privmsg: irc.Privmsg) -> None:
    print(
        f"Bancho | User: {privmsg.user} | Target: {privmsg.target} | Message: {privmsg.message}"
    )


@bancho_client.on("CONNECTION_CLOSED")
def on_bancho_connection_closed() -> None:
    print("LOST CONNECTION")
    connect(bancho_client)


@twitch_client.on("CONNECT")
async def on_twitch_connect() -> None:
    login(twitch_client, twitch_credentials)
    twitch_client.send(irc.Join(channel=TWITCH_IRC_USERNAME))


@twitch_client.on("PRIVMSG")
def on_twitch_privmsg(privmsg: irc.Privmsg) -> None:
    print(
        f"Twitch | User: {privmsg.user} | Target: {privmsg.target} | Message: {privmsg.message}"
    )

    is_link = re.search("https:\S+", privmsg.message)    
    if (is_link):
        beatmap_link = is_link.group(0)
        undetermined_link = re.match("^https:\/\/osu.ppy.sh\/beatmapsets", beatmap_link)
        if (undetermined_link):
            if (re.search("#osu", beatmap_link)):
                is_b_link = True
                is_s_link = False
            else:
                is_b_link = False
                is_s_link = True

        else:
            is_b_link = bool(re.match("(^https:\/\/osu.ppy.sh\/b\/)|(^https:\/\/old.ppy.sh\/b\/)|(^https:\/\/osu.ppy.sh\/beatmaps)", beatmap_link))
            is_s_link = bool(re.match("(^https:\/\/osu.ppy.sh\/s\/)|(^https:\/\/old.ppy.sh\/s\/)", beatmap_link))

        # This should capture every possible beatmap link 

        if (is_b_link | is_s_link):
            beatmapmessage = privmsg.user + " > [" 
            responsemessage = privmsg.user + " > " 
            is_beatmap_id = re.search("\d+$", beatmap_link)
            if(is_beatmap_id): 
                mods_hd = bool(re.search("(?i)(hd)|(hidden)",privmsg.message))
                mods_hr = bool(re.search("(?i)(hr)|(hardrock)|(hard rock)",privmsg.message))
                mods_dt = bool(re.search("(?i)(dt)|(nc)|(doubletime)|(double time)|(nightcore)|(night core)",privmsg.message)) # Nobody should request nightcore 
                mods_ez = bool(re.search("(?i)(ez)",privmsg.message)) # Ignoring the word "easy", since the case where its just used as an adjective when requesting is probably more common (and you're insane if you use it to request the mod)
                mods_fl = bool(re.search("(?i)(fl)",privmsg.message))
                mods_ht = bool(re.search("(?i)(?!https)(ht)|(halftime)|(half time)",privmsg.message))

                # If you request any other mod you're really strange

                mod_string = ""

                diff_mods = []
                mods_dict = "" # SR calculator returns a dictionary, so need to do this even though the dictionary will only have one value (surely there is a better way to do this)

                if(mods_hd):
                    mod_string += "HD,"
                if(mods_hr):
                    mod_string += "HR,"
                    diff_mods.append('HR')
                    mods_dict += "HR"
                if(mods_ez):
                    mod_string += "EZ,"
                    diff_mods.append('EZ')
                    mods_dict += "EZ"
                if(mods_dt):
                    mod_string += "DT,"
                    diff_mods.append('DT')
                    mods_dict += "DT"
                if(mods_fl):
                    mod_string += "FL,"
                if(mods_ht):
                    mod_string += "HT,"
                    diff_mods.append('HT')
                    mods_dict += "HT"

                if(len(mod_string) != 0):
                    mod_string = "+" + mod_string[:-1]

                beatmap_id = is_beatmap_id.group(0)
                param = '&b=' if is_b_link else '&s='
                beatmap_info = json.loads(requests.get('https://osu.ppy.sh/api/get_beatmaps?k=' + OSU_API_KEY + param + beatmap_id).text)

                if(len(diff_mods) > 0):
                    mod_sr = calculateStarRating(map_id=int(beatmap_info[0]["beatmap_id"]), mods=diff_mods)
                    truncated_sr = str(round(mod_sr[mods_dict], 2))
                else:
                    truncated_sr = str(round(float(beatmap_info[0]["difficultyrating"]), 2))

                if(mods_dt):
                    hit_length = int(int(beatmap_info[0]["hit_length"]) / 1.5)
                elif(mods_ht):
                    hit_length = int(int(beatmap_info[0]["hit_length"]) * 1.5)
                else:
                    hit_length = int(beatmap_info[0]["hit_length"])
                formatted_length = str(hit_length//60) + ":" + str(hit_length%60).zfill(2)

                metadata_string = beatmap_info[0]["artist"] + " - " + beatmap_info[0]["title"] + " [" + beatmap_info[0]["version"] + "] " + mod_string + " (" + truncated_sr + "\u2605, " + formatted_length + " drain length)"
                beatmapmessage += "https://osu.ppy.sh/b/" + beatmap_info[0]["beatmap_id"] + " " + metadata_string + "]" 
                responsemessage += metadata_string
                bancho_client.send(irc.Privmsg(target=BANCHO_IRC_USERNAME, message=beatmapmessage))
                twitch_client.send(irc.Privmsg(target="#" + TWITCH_IRC_USERNAME, message=responsemessage))
    
    elif (re.match("!np", privmsg.message)):
        try:
            ws = create_connection("ws://127.0.0.1:24050/ws")
        except:
            print("Connection to the websocket could not be established")
            return;
        clientdata = json.loads(ws.recv())
        npmessage = privmsg.user + " > "
        npmessage += clientdata["menu"]["bm"]["metadata"]["artist"] + " - " + clientdata["menu"]["bm"]["metadata"]["title"] + " [" + clientdata["menu"]["bm"]["metadata"]["difficulty"] + "] (https://osu.ppy.sh/b/" + str(clientdata["menu"]["bm"]["id"]) + ")"
        ws.close()
        twitch_client.send(irc.Privmsg(target="#" + TWITCH_IRC_USERNAME, message=npmessage))

    elif (re.match("!skin", privmsg.message)):
        try:
            ws = create_connection("ws://127.0.0.1:24050/ws")
        except:
            print("Connection to the websocket could not be established")
            return;
        clientdata = json.loads(ws.recv())
        skinmessage = privmsg.user + " > Current Skin: " + clientdata["settings"]["folders"]["skin"]
        ws.close()
        twitch_client.send(irc.Privmsg(target="#" + TWITCH_IRC_USERNAME, message=skinmessage))


@twitch_client.on("PING")
def on_twitch_ping(ping: irc.Ping) -> None:
    pong = irc.Pong(ping.message)
    twitch_client.send(pong)

@twitch_client.on("CONNECTION_CLOSED")
def on_twitch_connection_closed() -> None:
    print("LOST CONNECTION")
    connect(twitch_client)



connect(bancho_client)
connect(twitch_client)
loop.run_forever()