import json
import os
import sys

import discord
from discord import Forbidden, HTTPException, Thread
from discord.abc import GuildChannel, PrivateChannel

DEFAULT_WEBHOOK_NAME = "Portal"
MAX_MESSAGE_HISTORY = 100

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


async def send_message(webhook, message):
    return await webhook.send(
        content=message.content,
        wait=True,
        username=message.author.name,
        avatar_url=message.author.avatar.url,
        files=[await x.to_file() for x in message.attachments],
    )


class Portal:
    def __init__(self, name, channel_ids, webhooks) -> None:
        self.name = name
        self.map = {}
        self.message_history = []

        for i, channel_id in enumerate(channel_ids):
            self.map[channel_id] = webhooks[:i] + webhooks[i + 1 :]


class PortalBot(discord.Client):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.portal_map = {}

    async def on_ready(self) -> None:
        for portal_data in DATA["portals"]:
            name = portal_data["name"]
            print(f'Creating portal "{name}"')

            buffer = []

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

                try:
                    channel_webhooks = await channel.webhooks()
                except Forbidden:
                    print("I do not have permission to create a webhook")
                    continue

                webhook = next(
                    (w for w in channel_webhooks if w.name == DEFAULT_WEBHOOK_NAME),
                    None,
                )

                if webhook is not None:
                    buffer.append((channel_id, webhook))
                    continue

                print(f"No webhook with default name found in channel #{channel.name}")
                print("Creating webhook for this channel")

                try:
                    webhook = await channel.create_webhook(name=DEFAULT_WEBHOOK_NAME)
                except Forbidden:
                    print("I do not have permissions to create a webhook")
                except HTTPException:
                    print("Failed to create webhook")
                else:
                    buffer.append((channel_id, webhook))

            channel_ids, webhooks = zip(*buffer)
            portal = Portal(name, channel_ids, webhooks)

            for id in channel_ids:
                self.portal_map[id] = portal

        print("Ready")

    def is_valid_message(self, message):
        return not message.author.bot and message.channel.id in self.portal_map

    async def on_message(self, message) -> None:
        if not self.is_valid_message(message):
            return

        portal = self.portal_map[message.channel.id]
        sent_messages = []

        for webhook in portal.map[message.channel.id]:
            sent_message = await send_message(webhook, message)
            if sent_message is not None:
                sent_messages.append(sent_message)

        portal.message_history.append((message.id, sent_messages))
        if len(portal.message_history) > MAX_MESSAGE_HISTORY:
            portal.message_history = portal.message_history[:1]

    async def on_message_edit(self, before, after) -> None:
        if not self.is_valid_message(before):
            return

        portal = self.portal_map[before.channel.id]
        index = [x[0] for x in portal.message_history].index(before.id)
        sent_messages = [x[1] for x in portal.message_history][index]

        for message in sent_messages:
            try:
                await message.edit(content=after.content, attachments=after.attachments)
            except HTTPException:
                print("Failed to edit message")

    async def on_message_delete(self, message) -> None:
        if not self.is_valid_message(message):
            return

        portal = self.portal_map[message.channel.id]
        index = [x[0] for x in portal.message_history].index(message.id)
        sent_messages = [x[1] for x in portal.message_history][index]

        for message in sent_messages:
            try:
                await message.delete()
            except HTTPException:
                print("Failed to delete message")

        del portal.message_history[index]


token = DATA["token"]

intents = discord.Intents.default()
intents.message_content = True

portal_bot = PortalBot(intents=intents)
portal_bot.run(token)
