import json
import os
import sys

import discord
from discord import Thread
from discord.abc import GuildChannel, PrivateChannel

DEFAULT_WEBHOOK_NAME = "Portal"
MAX_MESSAGE_HISTORY = 3

if len(sys.argv) != 2:
    print(f"Incorrect number of arguments ({len(sys.argv) - 1})")
    print("Expected 1")
    quit()

CONFIG_PATH = sys.argv[1]
if not os.path.exists(CONFIG_PATH):
    print(f'"{CONFIG_PATH}" is not a valid path')
    quit()

with open(CONFIG_PATH) as file:
    DATA = json.load(file)


def flatten_list_of_dicts(list_of_dicts):
    return {key: value for dict in list_of_dicts for key, value in dict.items()}


async def send_message(webhook, message):
    return await webhook.send(
        content=message.content,
        wait=True,
        username=message.author.name,
        avatar_url=message.author.avatar.url,
        files=[await x.to_file() for x in message.attachments],
    )


class Portal:
    def __init__(self, name) -> None:
        self.name = name
        self.map = {}
        self.message_history = []

    def add_channel(self, channel_id, webhook) -> None:
        self.map[channel_id] = webhook


class PortalBot(discord.Client):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.portals = []

    async def on_ready(self) -> None:
        for portal_data in DATA["portals"]:
            name = portal_data["name"]
            print(f'Creating portal "{name}"')
            portal = Portal(name)

            for channel_id in portal_data["channel_ids"]:
                channel = self.get_channel(channel_id)

                if not isinstance(channel, GuildChannel):
                    match channel:
                        case Thread():
                            print(f"Channel with ID {channel_id} is a thread")
                        case PrivateChannel():
                            print(f"Channel with ID {channel_id} is a direct message")
                        case None:
                            print(f"Channel with ID {channel_id} not found")
                    continue

                if channel.type is not discord.ChannelType.text:
                    print(f'Channel "{channel.name}" is not a text channel')
                    continue

                print(f"{channel.guild.name}: #{channel.name}")

                webhooks = await channel.webhooks()

                try:
                    index = [x.name for x in webhooks].index(DEFAULT_WEBHOOK_NAME)
                    webhook = webhooks[index]
                except ValueError:
                    print(
                        f"No webhook with default name found in channel #{channel.name}"
                    )
                    print("Creating webhook for this channel")
                    webhook = await channel.create_webhook(name=DEFAULT_WEBHOOK_NAME)

                portal.add_channel(channel_id, webhook)

            self.portals.append(portal)

        print("Ready")

    def is_valid_message(self, message):
        return not message.author.bot and message.channel.id in flatten_list_of_dicts(
            [portal.map for portal in self.portals]
        )

    async def on_message(self, message) -> None:
        if not self.is_valid_message(message):
            return

        channel_id = message.channel.id
        for p in self.portals:
            if channel_id in p.map:
                portal = p
                break

        sent_messages = []

        webhooks = [y for x, y in portal.map.items() if x != channel_id]
        for webhook in webhooks:
            sent_message = await send_message(webhook, message)
            if sent_message is not None:
                sent_messages.append(sent_message)

        portal.message_history.append((message.id, sent_messages))
        if len(portal.message_history) > MAX_MESSAGE_HISTORY:
            portal.message_history = portal.message_history[:1]

    async def on_message_edit(self, before, after) -> None:
        if not self.is_valid_message(before):
            return

        channel_id = before.channel.id
        for p in self.portals:
            if channel_id in p.map:
                portal = p
                break

        index = [x[0] for x in portal.message_history].index(before.id)
        sent_messages = [x[1] for x in portal.message_history][index]

        for message in sent_messages:
            await message.edit(content=after.content, attachments=after.attachments)

    async def on_message_delete(self, message) -> None:
        if not self.is_valid_message(message):
            return

        channel_id = message.channel.id
        for p in self.portals:
            if channel_id in p.map:
                portal = p
                break

        index = [x[0] for x in portal.message_history].index(message.id)
        sent_messages = [x[1] for x in portal.message_history][index]

        for message in sent_messages:
            await message.delete()

        del portal.message_history[index]


token = DATA["token"]

intents = discord.Intents.default()
intents.message_content = True

portal_bot = PortalBot(intents=intents)
portal_bot.run(token)
