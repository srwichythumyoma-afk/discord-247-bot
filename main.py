import os
import asyncio
import logging

import discord
from discord.ext import commands, tasks
from aiohttp import web

# ---------- ตั้งค่า Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("voice-bot")

# ---------- อ่านค่าจาก Environment Variable ----------
TOKEN = os.environ.get("DISCORD_TOKEN")
CHANNEL_ID_RAW = os.environ.get("CHANNEL_ID")
PORT = int(os.environ.get("PORT", 8080))

if not TOKEN:
    raise RuntimeError("ไม่พบ DISCORD_TOKEN ใน Environment Variable")
if not CHANNEL_ID_RAW:
    raise RuntimeError("ไม่พบ CHANNEL_ID ใน Environment Variable")

CHANNEL_ID = int(CHANNEL_ID_RAW)

# ---------- ตั้งค่า Intents ----------
intents = discord.Intents.default()
intents.voice_states = True     # จำเป็นสำหรับการเชื่อมต่อ/รักษาสถานะ Voice Channel
intents.members = True          # ตามที่เปิดไว้ใน Developer Portal
intents.message_content = True  # ตามที่เปิดไว้ใน Developer Portal

bot = commands.Bot(command_prefix="!", intents=intents)


async def join_voice_channel() -> None:
    """เชื่อมต่อบอทเข้า Voice Channel ตาม CHANNEL_ID (ถ้ายังไม่ได้เชื่อมต่ออยู่)"""
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(CHANNEL_ID)
        except discord.HTTPException as e:
            log.error("หา Channel ID %s ไม่เจอ: %s", CHANNEL_ID, e)
            return

    if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
        log.error("Channel ID %s ไม่ใช่ Voice/Stage Channel", CHANNEL_ID)
        return

    voice_client = channel.guild.voice_client

    # ถ้าเชื่อมต่ออยู่แล้วและอยู่ห้องที่ถูกต้อง ไม่ต้องทำอะไรซ้ำ
    if voice_client and voice_client.is_connected():
        if voice_client.channel.id != CHANNEL_ID:
            await voice_client.move_to(channel)
            log.info("ย้ายไปที่ Voice Channel: %s", channel.name)
        return

    try:
        await channel.connect(self_deaf=True, self_mute=True, reconnect=True)
        log.info("เชื่อมต่อ Voice Channel สำเร็จ: %s", channel.name)
    except Exception as e:
        log.error("เชื่อมต่อ Voice Channel ไม่สำเร็จ: %s", e)


@bot.event
async def on_ready():
    log.info("บอทออนไลน์แล้วในชื่อ %s (ID: %s)", bot.user, bot.user.id)
    await join_voice_channel()
    if not voice_watchdog.is_running():
        voice_watchdog.start()


@bot.event
async def on_voice_state_update(member: discord.Member, before, after):
    # ถ้าบอทเองถูกเตะ/หลุดออกจาก Voice Channel (เช่น แอดมินกดเตะ, Discord รีสตาร์ทวอยซ์
    # เซิร์ฟเวอร์) ให้พยายามเชื่อมต่อกลับทันที
    if member.id == bot.user.id and after.channel is None:
        log.warning("บอทหลุดออกจาก Voice Channel กำลังเชื่อมต่อใหม่...")
        await asyncio.sleep(5)
        await join_voice_channel()


@tasks.loop(minutes=5)
async def voice_watchdog():
    """ตรวจสอบเป็นระยะว่าบอทยังอยู่ใน Voice Channel ที่ถูกต้องหรือไม่
    (กันเคส event หลุดไม่ทำงาน เช่น เครือข่ายมีปัญหาแวบเดียวตอนบอทกำลังจะหลุด)"""
    await join_voice_channel()


# ---------- Web Server สำหรับ Health Check (Render ต้องการให้แอปฟัง Port ที่กำหนด) ----------
async def health_check(request: web.Request) -> web.Response:
    return web.Response(text="Bot is alive")


async def start_web_server() -> None:
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    log.info("Web Server (Health Check) เริ่มทำงานที่พอร์ต %s", PORT)


async def main() -> None:
    await start_web_server()
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except discord.LoginFailure:
        log.error("DISCORD_TOKEN ไม่ถูกต้อง กรุณาตรวจสอบค่าใน Environment Variable")
    except KeyboardInterrupt:
        log.info("ปิดบอท...")
