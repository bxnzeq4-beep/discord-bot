import os
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="/", intents=intents)

queue = {}
volume = {}
loop_mode = {}

ydl_opts = {
    'format': 'bestaudio',
    'noplaylist': True,
    'quiet': True
}


def get_audio_source(url):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if 'entries' in info:
            info = info['entries'][0]
        return info['url'], info['title']


async def play_next(guild):
    guild_id = guild.id

    if guild_id not in volume:
        volume[guild_id] = 0.5

    if guild_id not in loop_mode:
        loop_mode[guild_id] = False

    if queue[guild_id]:
        url = queue[guild_id][0] if loop_mode[guild_id] else queue[guild_id].pop(0)

        stream_url, title = get_audio_source(url)
        vc = guild.voice_client

        source = discord.FFmpegPCMAudio(
            stream_url,
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            options="-vn"
        )

        source = discord.PCMVolumeTransformer(source, volume=volume[guild_id])

        def after_play(error):
            fut = asyncio.run_coroutine_threadsafe(
                play_next(guild),
                bot.loop
            )
            try:
                fut.result()
            except:
                pass

        vc.play(source, after=after_play)
        print(f"▶ 재생 시작: {title}")

    else:
        print("대기열 끝. 채널 유지 중...")


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")


# 🔁 자동 재접속
@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id:
        if before.channel and not after.channel:
            await asyncio.sleep(2)
            try:
                await before.channel.connect()
                print("🔁 자동 재접속 성공")
            except Exception as e:
                print("재접속 실패:", e)


# 🎵 재생
@bot.tree.command(name="재생", description="노래 재생")
@app_commands.describe(검색="유튜브 제목 또는 링크")
async def play(interaction: discord.Interaction, 검색: str):

    await interaction.response.defer()

    if not interaction.user.voice:
        await interaction.followup.send("먼저 음성채널에 들어가주세요!", ephemeral=True)
        return

    guild_id = interaction.guild.id

    if guild_id not in queue:
        queue[guild_id] = []

    if not interaction.guild.voice_client:
        await interaction.user.voice.channel.connect()

    if "http" not in 검색:
        검색 = f"ytsearch:{검색}"

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(검색, download=False)
        if 'entries' in info:
            info = info['entries'][0]
        url = info['webpage_url']
        title = info['title']

    queue[guild_id].append(url)

    await interaction.followup.send(f"🎵 대기열 추가됨: {title}")

    vc = interaction.guild.voice_client
    if not vc.is_playing():
        await play_next(interaction.guild)


# ⏭ 넘기기
@bot.tree.command(name="넘기기", description="다음 곡으로")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.stop()
        await interaction.response.send_message("⏭ 다음 곡으로 넘어갑니다.")
    else:
        await interaction.response.send_message("재생 중인 노래가 없습니다.")


# 🔊 볼륨
@bot.tree.command(name="볼륨", description="볼륨 설정 (0~100)")
async def set_volume(interaction: discord.Interaction, 값: int):

    if 값 < 0 or 값 > 100:
        await interaction.response.send_message("0~100 사이 값 입력")
        return

    guild_id = interaction.guild.id
    volume[guild_id] = 값 / 100

    vc = interaction.guild.voice_client
    if vc and vc.source:
        vc.source.volume = volume[guild_id]

    await interaction.response.send_message(f"🔊 볼륨 {값}% 로 설정")


# 📜 대기열
@bot.tree.command(name="대기열", description="현재 대기열 확인")
async def show_queue(interaction: discord.Interaction):

    guild_id = interaction.guild.id

    if guild_id not in queue or not queue[guild_id]:
        await interaction.response.send_message("대기열이 비어있습니다.")
        return

    msg = ""
    for i, url in enumerate(queue[guild_id], 1):
        msg += f"{i}. {url}\n"

    await interaction.response.send_message(f"📜 현재 대기열:\n{msg}")


# 🔁 반복
@bot.tree.command(name="반복", description="현재 곡 반복 ON/OFF")
async def toggle_loop(interaction: discord.Interaction):

    guild_id = interaction.guild.id

    if guild_id not in loop_mode:
        loop_mode[guild_id] = False

    loop_mode[guild_id] = not loop_mode[guild_id]

    상태 = "ON 🔁" if loop_mode[guild_id] else "OFF ❌"

    await interaction.response.send_message(f"반복 모드: {상태}")


bot.run(TOKEN)