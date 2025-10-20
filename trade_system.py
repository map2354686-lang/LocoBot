import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta


# -----------------------------
# 🔰 Widok finalizacji handlu (w prywatnym kanale)
# -----------------------------
class FinalizeTradeView(discord.ui.View):
    def __init__(self, channel, cog, author, partner):
        super().__init__(timeout=None)
        self.channel = channel
        self.cog = cog
        self.author = author
        self.partner = partner

    @discord.ui.button(label="✅ Oferta udana", style=discord.ButtonStyle.green)
    async def success(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🎉 Handel zakończony pomyślnie! Kanał zostanie usunięty za 5 sekund.", ephemeral=True)

        # Powiadom kanał 📣│ogłoszenia
        announce_channel = discord.utils.get(interaction.guild.text_channels, name="📣│ogłoszenia")
        if announce_channel:
            await announce_channel.send(
                f"✅ Handel pomyślnie zakończony między {self.author.mention} a {self.partner.mention} 💎"
            )

        await asyncio.sleep(5)
        await self.channel.delete()

    @discord.ui.button(label="❌ Anuluj handel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Handel anulowany. Kanał zostanie usunięty za 5 sekund.", ephemeral=True)
        announce_channel = discord.utils.get(interaction.guild.text_channels, name="📣│ogłoszenia")
        if announce_channel:
            await announce_channel.send(
                f"🚫 Handel między {self.author.mention} a {self.partner.mention} został anulowany."
            )

        await asyncio.sleep(5)
        await self.channel.delete()


# -----------------------------
# 📩 Widok przycisków ogłoszenia
# -----------------------------
class TradeOfferView(discord.ui.View):
    def __init__(self, cog, author):
        super().__init__(timeout=None)
        self.cog = cog
        self.author = author
        self.active = True
        self.current_trade_user = None  # aktualnie handlujący użytkownik

    @discord.ui.button(label="🟢 Zainteresowany", style=discord.ButtonStyle.green)
    async def interested(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active:
            await interaction.response.send_message("⏳ Ten handel jest już w toku lub zakończony.", ephemeral=True)
            return

        if interaction.user == self.author:
            await interaction.response.send_message("❌ Nie możesz handlować sam ze sobą!", ephemeral=True)
            return

        guild = interaction.guild
        if (self.author.id, interaction.user.id) in self.cog.active_trades:
            await interaction.response.send_message("⚠️ Już handlujesz z tym graczem!", ephemeral=True)
            return

        # Zablokuj inne kliknięcia
        self.cog.active_trades.add((self.author.id, interaction.user.id))
        self.active = False
        self.current_trade_user = interaction.user

        # 🏗️ Tworzenie prywatnego kanału handlu
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            self.author: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        channel_name = f"💸│handel-{self.author.name.lower()}-{interaction.user.name.lower()}"
        trade_channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)

        embed = discord.Embed(
            title="💬 Pokój handlowy",
            description=(f"{self.author.mention} i {interaction.user.mention},\n"
                         f"możecie teraz omówić szczegóły wymiany tutaj.\n\n"
                         f"Gdy zakończycie handel, wybierzcie jedną z opcji poniżej."),
            color=discord.Color.green()
        )
        await trade_channel.send(embed=embed, view=FinalizeTradeView(trade_channel, self.cog, self.author, interaction.user))

        # Zaktualizuj ogłoszenie
        updated_embed = discord.Embed(
            title="🔒 Oferta w trakcie realizacji",
            description=f"Handel pomiędzy {self.author.mention} a {interaction.user.mention} jest w toku!",
            color=discord.Color.orange()
        )
        await interaction.response.edit_message(embed=updated_embed, view=None)

    @discord.ui.button(label="🔴 Anuluj ofertę", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Tylko autor ogłoszenia może je anulować.", ephemeral=True)
            return

        self.active = False
        embed = discord.Embed(
            title="❌ Oferta anulowana",
            description=f"{self.author.mention} anulował swoje ogłoszenie handlowe.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)


# -----------------------------
# 🪙 Główna klasa systemu handlu
# -----------------------------
class TradeSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_trades = set()

    @app_commands.command(name="wystaw", description="Wystaw ofertę handlową na kanale 🧭│handel.")
    async def wystaw(self, interaction: discord.Interaction):
        user = interaction.user
        trade_channel = discord.utils.get(interaction.guild.text_channels, name="🧭│handel")
        announce_channel = discord.utils.get(interaction.guild.text_channels, name="📣│ogłoszenia")

        if not trade_channel or not announce_channel:
            await interaction.response.send_message("⚠️ Brakuje jednego z kanałów: 🧭│handel lub 📣│ogłoszenia.", ephemeral=True)
            return

        await interaction.response.send_message("🧾 Rozpoczynamy tworzenie twojej oferty handlu!", ephemeral=True)
        await user.send("💰 **Krok 1:** Napisz, co oferujesz:")

        def check(m): return m.author == user and isinstance(m.channel, discord.DMChannel)
        offer = await self.bot.wait_for("message", check=check)
        offer_text = offer.content

        await user.send("🎯 **Krok 2:** Napisz, co chciałbyś otrzymać w zamian:")
        want = await self.bot.wait_for("message", check=check)
        want_text = want.content

        await user.send("📝 **Krok 3:** (opcjonalnie) Opis oferty lub wpisz `pomiń`:")
        desc = await self.bot.wait_for("message", check=check)
        desc_text = None if desc.content.lower() == "pomiń" else desc.content

        await user.send("📸 **Krok 4:** Jeśli chcesz, wyślij zdjęcie przedmiotu (lub wpisz `pomiń`):")
        attachment = None
        try:
            img = await self.bot.wait_for("message", check=check, timeout=60)
            if img.attachments:
                attachment = img.attachments[0].url
            elif img.content.lower() == "pomiń":
                attachment = None
        except asyncio.TimeoutError:
            attachment = None

        # 📦 Tworzymy embed oferty
        embed = discord.Embed(
            title="📦 Nowe ogłoszenie handlowe",
            description=f"**👤 Gracz:** {user.mention}\n\n"
                        f"💰 **Oferuje:** {offer_text}\n"
                        f"🎯 **Chce otrzymać:** {want_text}\n\n"
                        f"📝 **Opis:** {desc_text or '_Brak dodatkowych informacji_'}",
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="Kliknij przycisk, aby rozpocząć handel z autorem.")
        if attachment:
            embed.set_image(url=attachment)

        view = TradeOfferView(self, user)
        message = await trade_channel.send(embed=embed, view=view)

        # 📣 Ogłoszenie w kanale 📣│ogłoszenia
        announce_embed = discord.Embed(
            title="🛒 Nowa oferta handlowa!",
            description=f"{user.mention} wystawił nową ofertę handlu na kanale {trade_channel.mention}! 💎",
            color=discord.Color.blurple()
        )
        announce_embed.set_footer(text="Czas trwania oferty: 6 godzin ⏳")
        await announce_channel.send(embed=announce_embed)

        await user.send("✅ Twoja oferta została opublikowana! Wygasa za 6 godzin ⏳")

        # ⏳ Automatyczne wygaśnięcie po 6 godzinach
        await asyncio.sleep(6 * 60 * 60)
        if view.active:
            view.active = False
            expired = discord.Embed(
                title="⌛ Oferta wygasła",
                description=f"Oferta gracza {user.mention} wygasła po 6 godzinach bez zainteresowania.",
                color=discord.Color.dark_grey()
            )
            try:
                await message.edit(embed=expired, view=None)
            except:
                pass
            try:
                await user.send("⌛ Twoja oferta wygasła bez odpowiedzi.")
            except:
                pass


# -----------------------------
# 🔧 Rejestracja rozszerzenia
# -----------------------------
async def setup(bot):
    await bot.add_cog(TradeSystem(bot))




