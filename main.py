import json

import discord
from discord import Thread
from discord.abc import GuildChannel, PrivateChannel

DEFAULT_WEBHOOK_NAME = 'Portal'
MAX_MESSAGE_HISTORY = 5

async def send_message(webhook, message):
    return await webhook.send(
        content = message.content,
        wait = True,
        username = message.author.name,
        avatar_url = message.author.avatar.url,
        files = [await x.to_file() for x in message.attachments]
    )

async def edit_message(before, after):
    return await before.edit(
        content = after.content,
        attachments = after.attachments
    )

async def delete_message(message):
    return await message.delete()

class PortalBot(discord.Client):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.portals = []
        self.channel_id_set = set()
        self.message_history = []

    async def on_ready(self) -> None:
        with open('config.json') as file:
            data = json.load(file)

        for channel_id in data['channel_ids']:
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
                print(f'No webhook with default name found in channel with with ID {channel_id}')
                print('Creating webhook for this channel')
                webhook = await channel.create_webhook(name = DEFAULT_WEBHOOK_NAME)

            self.portals.append((channel, webhook))

        self.channel_id_set = set([x[0].id for x in self.portals])

        print(f'Portal count: {len(self.portals)}')
        for portal in self.portals:
            print(f'{portal[0].guild.name}: #{portal[0].name}')
        print('Ready')

    async def on_message(self, message) -> None:
        if message.author.bot:
            return

        if message.channel.id not in self.channel_id_set:
            return

        try:
            index = [x[0] for x in self.portals].index(message.channel)
        except ValueError:
            return

        webhooks = [x[1] for x in self.portals]
        sent_messages = []

        for webhook in webhooks[:index] + webhooks[index+1:]:
            sent_message = await send_message(webhook, message)
            if sent_message is not None:
                sent_messages.append(sent_message)

        self.message_history.append((message.id, sent_messages))
        if len(self.message_history) > MAX_MESSAGE_HISTORY:
            self.message_history = self.message_history[:1]

    async def on_message_edit(self, before, after):
        if before.author.bot:
            return

        if before.channel.id not in self.channel_id_set:
            return

        try:
            index = [x[0] for x in self.message_history].index(before.id)
        except ValueError:
            return

        sent_messages = [x[1] for x in self.message_history][index]
        for message in sent_messages:
            await edit_message(message, after)

    async def on_message_delete(self, message):
        if message.author.bot:
            return

        if message.channel.id not in self.channel_id_set:
            return

        try:
            index = [x[0] for x in self.message_history].index(message.id)
        except ValueError:
            return

        sent_messages = [x[1] for x in self.message_history][index]
        for message in sent_messages:
            await delete_message(message)

        del self.message_history[index]

with open('config.json') as file:
    data = json.load(file)
token = data['token']

intents = discord.Intents.default()
intents.message_content = True

portal_bot = PortalBot(intents = intents)
portal_bot.run(token)
