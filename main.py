import json

import aiohttp
import discord
from discord import Thread, Webhook
from discord.abc import GuildChannel, PrivateChannel

async def send_message(url, message):
    async with aiohttp.ClientSession() as session:
        webhook = Webhook.from_url(url, session = session)
        await webhook.send(
            content = message.content,
            username = message.author.name,
            avatar_url = message.author.avatar.url,
            files = [await x.to_file() for x in message.attachments]
        )

class PortalBot(discord.Client):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.portals = []

    async def on_ready(self) -> None:
        with open('config.json') as file:
            data = json.load(file)

        for portal in data['portals']:
            channel_id = int(portal['channel_id'])
            webhook_url = portal['webhook_url']

            channel = self.get_channel(channel_id)

            match channel:
                case GuildChannel():
                    self.portals.append((channel, webhook_url))
                case Thread():
                    print(f'Channel with ID {channel_id} is a thread')
                case PrivateChannel():
                    print(f'Channel with ID {channel_id} is a direct message')
                case None:
                    print(f'Channel with ID {channel_id} not found')

        print(f'Portal count: {len(self.portals)}')
        for portal in self.portals:
            print(f'{portal[0].guild.name}: #{portal[0].name}')
        print('Ready')

    async def on_message(self, message) -> None:
        if message.author.bot:
            return

        try:
            index = [x[0] for x in self.portals].index(message.channel)
        except ValueError:
            return

        urls = [x[1] for x in self.portals]
        for url in urls[:index] + urls[index+1:]:
            await send_message(url, message)

with open('config.json') as file:
    data = json.load(file)
token = data['token']

intents = discord.Intents.default()
intents.message_content = True

portal_bot = PortalBot(intents = intents)
portal_bot.run(token)
