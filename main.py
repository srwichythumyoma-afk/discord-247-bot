import os
import asyncio
import discord
from discord.ext import commands
from aiohttp import web

TOKEN = os.environ.get('DISCORD_TOKEN')
CHANNEL_ID = int(os.environ.get('CHANNEL_ID', 0))

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

async def handle(request):
    return web.Response(text="Bot is alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await start_web_server()
    
    if CHANNEL_ID:
        channel = bot.get_channel(CHANNEL_ID)
        if channel and isinstance(channel, discord.VoiceChannel):
            try:
                await channel.connect()
                print(f"Connected to {channel.name}")
            except Exception as e:
                print(f"Error connecting to voice channel: {e}")

bot.run(TOKEN)
