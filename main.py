import json
import sys
import os

import discord
from discord import Thread
from discord.abc import GuildChannel, PrivateChannel

DEFAULT_WEBHOOK_NAME = 'Portal'
MAX_MESSAGE_HISTORY = 100

if len(sys.argv) != 2:
    print(f'Incorrect number of arguments ({len(sys.argv) - 1})')
    print('Expected 1')
    quit()

CONFIG_PATH = sys.argv[1]
if not os.path.exists(CONFIG_PATH):
    print(f'"{CONFIG_PATH}" is not a valid path')
    quit()

with open(CONFIG_PATH) as file:
    DATA = json.load(file)

async def send_message(webhook, message):
    return await webhook.send(
        content = message.content,
        wait = True,
        username = message.author.name,
        avatar_url = message.author.avatar.url,
        files = [await x.to_file() for x in message.attachments]
    )

class PortalBot(discord.Client):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.portals = {}
        self.message_history = []

    async def on_ready(self) -> None:
        for channel_id in DATA['channel_ids']:
            channel = self.get_channel(channel_id)

            if not isinstance(channel, GuildChannel):
                match channel:
                    case Thread():
                        print(f'Channel with ID {channel_id} is a thread')
                    case PrivateChannel():
                        print(f'Channel with ID {channel_id} is a direct message')
                    case None:
                        print(f'Channel with ID {channel_id} not found')
                continue
            elif channel.type is not discord.ChannelType.text:
                continue

            webhooks = await channel.webhooks()

            try:
                index = [x.name for x in webhooks].index(DEFAULT_WEBHOOK_NAME)
                webhook = webhooks[index]
            except ValueError:
                print(f'No webhook with default name found in channel with ID {channel_id}')
                print('Creating webhook for this channel')
                webhook = await channel.create_webhook(name = DEFAULT_WEBHOOK_NAME)

            print(f'{channel.guild.name}: #{channel.name}')
            self.portals[channel_id] = webhook

        print('Ready')

    def is_valid_message(self, message):
        return not message.author.bot and message.channel.id in self.portals.keys()

    async def on_message(self, message) -> None:
        if not self.is_valid_message(message):
            return

        sent_messages = []

        webhooks = [y for x, y in self.portals.items() if x != message.channel.id]
        for webhook in webhooks:
            sent_message = await send_message(webhook, message)
            if sent_message is not None:
                sent_messages.append(sent_message)

        self.message_history.append((message.id, sent_messages))
        if len(self.message_history) > MAX_MESSAGE_HISTORY:
            self.message_history = self.message_history[:1]

    async def on_message_edit(self, before, after):
        if not self.is_valid_message(before):
            return

        index = [x[0] for x in self.message_history].index(before.id)
        sent_messages = [x[1] for x in self.message_history][index]

        for message in sent_messages:
            await message.edit(
                content = after.content,
                attachments = after.attachments
            )

    async def on_message_delete(self, message):
        if not self.is_valid_message(message):
            return

        index = [x[0] for x in self.message_history].index(message.id)
        sent_messages = [x[1] for x in self.message_history][index]

        for message in sent_messages:
            await message.delete()

        del self.message_history[index]

token = DATA['token']

intents = discord.Intents.default()
intents.message_content = True

portal_bot = PortalBot(intents = intents)
portal_bot.run(token)
