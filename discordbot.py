import os
import discord
from discord.ext import commands, tasks
from discord import Embed
from dotenv import load_dotenv
from mcstatus import JavaServer
from datetime import datetime
import asyncio

# 🔐 Wczytaj token z pliku .env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ⚙️ Ustawienia intencji
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# 🤖 Tworzymy bota
bot = commands.Bot(command_prefix="!", intents=intents)

# 🔧 Ustawienia kanałów
STATUS_CHANNEL_NAME = "💎│status-serwera"

# 🌍 Dane serwera Minecraft
SERVER_ADDRESS = "lococraft.ddns.net"
SERVER_PORT = 25566

# 🧠 Zmienna do zapamiętania ID wiadomości statusu
status_message_id = None


# -----------------------------
# Klasa do wyświetlania stron graczy
# -----------------------------
class PlayerListView(discord.ui.View):
    def __init__(self, pages):
        super().__init__(timeout=None)
        self.pages = pages
        self.current_page = 0

    async def update_embed(self, interaction):
        """Aktualizuje embed przy zmianie strony"""
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @discord.ui.button(label="⬅️ Poprzednia", style=discord.ButtonStyle.gray)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_embed(interaction)

    @discord.ui.button(label="➡️ Następna", style=discord.ButtonStyle.gray)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            await self.update_embed(interaction)


# -----------------------------
# EVENTY
# -----------------------------
@bot.event
async def on_ready():
    print(f"✅ Zalogowano jako {bot.user}")
    await setup_status_message()
    update_status.start()

    # 🔁 Synchronizacja komend z Discordem
    await bot.tree.sync()
    print("🌐 Slash-komendy zsynchronizowane z Discordem!")


async def setup_status_message():
    """Wysyła wiadomość statusową lub odnajduje starą"""
    global status_message_id
    guild = bot.guilds[0]
    channel = discord.utils.get(guild.text_channels, name=STATUS_CHANNEL_NAME)

    if not channel:
        print("⚠️ Nie znaleziono kanału statusowego!")
        return

    async for message in channel.history(limit=10):
        if message.author == bot.user:
            status_message_id = message.id
            return

    embed = discord.Embed(
        title="🌍 Status serwera LocoCraft",
        description="Ładowanie statusu serwera...",
        color=discord.Color.yellow()
    )
    msg = await channel.send(embed=embed)
    status_message_id = msg.id
    print("✅ Utworzono nową wiadomość statusową!")


# -----------------------------
# NOWA WERSJA – ładne animowane odświeżanie statusu
# -----------------------------
@tasks.loop(seconds=30)
async def update_status():
    global status_message_id
    guild = bot.guilds[0]
    channel = discord.utils.get(guild.text_channels, name=STATUS_CHANNEL_NAME)

    if not channel or not status_message_id:
        return

    # 👀 Etap 1 – efekt „odświeżania”
    loading_embed = discord.Embed(
        title="🌍 **Status serwera LocoCraft**",
        description="🔄 **Sprawdzanie statusu serwera...**",
        color=discord.Color.light_grey()
    )
    loading_embed.set_thumbnail(url=bot.user.display_avatar.url)
    msg = await channel.fetch_message(status_message_id)
    await msg.edit(embed=loading_embed)

    await asyncio.sleep(1.2)  # krótkie opóźnienie dla efektu

    try:
        server = JavaServer.lookup(f"{SERVER_ADDRESS}:{SERVER_PORT}")
        status = server.status()
        query = None
        try:
            query = server.query()
        except Exception:
            pass
        online = True
    except Exception:
        online = False
        status = None
        query = None

    if online:
        # Pobierz listę graczy
        player_names = []
        if query and query.players.names:
            player_names = query.players.names
        elif hasattr(status.players, "sample") and status.players.sample:
            player_names = [p.name for p in status.players.sample]

        names = "\n".join([f"• {n}" for n in player_names]) if player_names else "_Brak graczy online_"

        # 👇 Etap 2 – efekt „PUU!” = zmiana koloru i treści
        embed = discord.Embed(
            title="🌍 **Status serwera LocoCraft**",
            description=(
                f"🟢 **Serwer ONLINE!**\n"
                f"👥 Gracze: **{status.players.online}/{status.players.max}**\n\n"
                f"**Lista graczy:**\n{names}\n\n"
                f"🕒 Ostatnia aktualizacja: <t:{int(datetime.now().timestamp())}:T>"
            ),
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        embed.set_footer(text="Powered by LocoCraft | System Statusu", icon_url=bot.user.display_avatar.url)
        await msg.edit(embed=embed)

    else:
        embed = discord.Embed(
            title="🌍 **Status serwera LocoCraft**",
            description=(
                f"🔴 **Serwer OFFLINE!**\n"
                f"🕒 Ostatnia próba: <t:{int(datetime.now().timestamp())}:T>\n"
                f"💡 Serwer może być w trakcie restartu."
            ),
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        embed.set_footer(text="Powered by LocoCraft | System Statusu", icon_url=bot.user.display_avatar.url)
        await msg.edit(embed=embed)


# -----------------------------
# POWITANIE + AUTOROLE
# -----------------------------
@bot.event
async def on_member_join(member):
    """Wysyła wiadomość powitalną i nadaje rolę nowemu użytkownikowi"""
    welcome_channel_name = "🤝│witaj"  # 👈 Twój kanał powitań
    role_name = "🎮 | Gracz"             # 👈 Rola, jaką bot ma nadać

    guild = member.guild
    channel = discord.utils.get(guild.text_channels, name=welcome_channel_name)
    role = discord.utils.get(guild.roles, name=role_name)

    # 📩 Wiadomość powitalna
    if channel:
        embed = discord.Embed(
            title="👋 Witaj na serwerze LocoCraft!",
            description=(
                f"Hej {member.mention}, witamy Cię na **{guild.name}**!\n\n"
                f"💎 Miłej gry, udanych handli i dobrej zabawy z ekipą!"
            ),
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="Powered by LocoCraft", icon_url=bot.user.display_avatar.url)
        await channel.send(embed=embed)

    # 🎭 Nadaj rolę
    if role:
        try:
            await member.add_roles(role)
            print(f"✅ Nadano rolę '{role_name}' użytkownikowi {member.name}")
        except discord.Forbidden:
            print("⚠️ Bot nie ma uprawnień do nadania roli!")
    else:
        print(f"⚠️ Nie znaleziono roli '{role_name}' na serwerze!")

# ---------------------------------
# 🌐 Fake web server for Render (anti-timeout)
# ---------------------------------
from flask import Flask
import threading

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot is running and healthy!"

def run_web():
    app.run(host="0.0.0.0", port=8080)

# Start web server in background thread
threading.Thread(target=run_web).start()


# -----------------------------
# START BOTA (async)
# -----------------------------
async def main():
    async with bot:
        await bot.load_extension("trade_system")  # ⬅️ Ładuje Twój plik handlu
        await bot.start(TOKEN)

asyncio.run(main())




