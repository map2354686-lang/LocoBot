import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from datetime import datetime


# -----------------------------
# 🔰 Widok finalizacji handlu (w prywatnym kanale)
# -----------------------------
class FinalizeTradeView(discord.ui.View):
    def __init__(self, channel, cog, author, partner, announce_message):
        super().__init__(timeout=None)
        self.channel = channel
        self.cog = cog
        self.author = author
        self.partner = partner
        self.announce_message = announce_message

    @discord.ui.button(label="✅ Oferta udana", style=discord.ButtonStyle.green)
    async def success(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in [self.author, self.partner]:
            await interaction.response.send_message("❌ Nie możesz tego zrobić.", ephemeral=True)
            return

        await interaction.response.send_message("🎉 Handel zakończony pomyślnie! Kanał zostanie usunięty za 5 sekund.", ephemeral=True)

        # ✅ Aktualizacja ogłoszenia
        success_embed = discord.Embed(
            title="✅ Oferta zakończona pomyślnie!",
            description=(
                f"Wymiana pomiędzy {self.author.mention} a {self.partner.mention} zakończyła się sukcesem 💎"
            ),
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        await self.announce_message.edit(embed=success_embed)

        # 📩 DM do autora
        try:
            await self.author.send("✅ Twoja oferta zakończyła się pomyślnie! 💎")
        except:
            pass

        await asyncio.sleep(5)
        await self.channel.delete()

    @discord.ui.button(label="❌ Anuluj handel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in [self.author, self.partner]:
            await interaction.response.send_message("❌ Nie możesz anulować tego handlu.", ephemeral=True)
            return

        await interaction.response.send_message("🚫 Handel został anulowany. Kanał zostanie usunięty za 5 sekund.", ephemeral=True)

        # 🔁 Przywrócenie oferty jako aktywnej
        for view in self.cog.active_offers:
            if view.author == self.author:
                view.active = True
                break

        try:
            await self.author.send("❌ Twój handel został anulowany. Twoja oferta jest ponownie aktywna.")
        except:
            pass

        await asyncio.sleep(5)
        await self.channel.delete()


# -----------------------------
# 📩 Widok przycisków ogłoszenia
# -----------------------------
class TradeOfferView(discord.ui.View):
    def __init__(self, cog, author, announce_message=None):
        super().__init__(timeout=None)
        self.cog = cog
        self.author = author
        self.announce_message = announce_message
        self.active = True
        self.current_trade_user = None

    @discord.ui.button(label="🟢 Zainteresowany", style=discord.ButtonStyle.green)
    async def interested(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active:
            await interaction.response.send_message("⏳ Ten handel jest już w toku lub zakończony.", ephemeral=True)
            return
        if interaction.user == self.author:
            await interaction.response.send_message("❌ Nie możesz handlować sam ze sobą!", ephemeral=True)
            return

        guild = interaction.guild
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

        # 💬 Wiadomość w kanale handlu
        embed = discord.Embed(
            title="💬 Pokój handlowy",
            description=(
                f"{self.author.mention} i {interaction.user.mention},\n"
                f"możecie teraz omówić szczegóły wymiany tutaj.\n\n"
                f"Gdy zakończycie handel, wybierzcie jedną z opcji poniżej."
            ),
            color=discord.Color.green()
        )
        await trade_channel.send(embed=embed, view=FinalizeTradeView(trade_channel, self.cog, self.author, interaction.user, self.announce_message))

        # 🔒 Zaktualizuj ofertę w kanale 🧭│handel
        updated_embed = discord.Embed(
            title="🔒 Oferta w trakcie realizacji",
            description=f"Handel pomiędzy {self.author.mention} a {interaction.user.mention} jest w toku!",
            color=discord.Color.orange()
        )
        await interaction.response.edit_message(embed=updated_embed, view=None)

    @discord.ui.button(label="🔴 Anuluj ofertę", style=discord.ButtonStyle.red)
    async def cancel_offer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Tylko autor może anulować swoją ofertę.", ephemeral=True)
            return

        self.active = False

        # Usuń ogłoszenie + ofertę
        try:
            if self.announce_message:
                await self.announce_message.delete()
        except:
            pass
        try:
            await interaction.message.delete()
        except:
            pass

        try:
            await interaction.user.send("❌ Twoja oferta została anulowana i usunięta z ogłoszeń.")
        except:
            pass


# -----------------------------
# 🪙 Główna klasa systemu handlu
# -----------------------------
class TradeSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_trades = set()
        self.active_offers = []

    @app_commands.command(name="wystaw", description="Wystaw ofertę handlową na kanale 🧭│handel.")
    async def wystaw(self, interaction: discord.Interaction):
        user = interaction.user
        trade_channel = discord.utils.get(interaction.guild.text_channels, name="🧭│handel")
        announce_channel = discord.utils.get(interaction.guild.text_channels, name="📣│ogłoszenia")

        if not trade_channel or not announce_channel:
            await interaction.response.send_message("⚠️ Brakuje kanału `🧭│handel` lub `📣│ogłoszenia`.", ephemeral=True)
            return

        await interaction.response.send_message("🧾 Rozpoczynamy tworzenie oferty!", ephemeral=True)
        await user.send("💰 **Krok 1:** Co oferujesz?")

        def check(m): return m.author == user and isinstance(m.channel, discord.DMChannel)
        offer = await self.bot.wait_for("message", check=check)
        offer_text = offer.content

        await user.send("🎯 **Krok 2:** Co chciałbyś otrzymać w zamian?")
        want = await self.bot.wait_for("message", check=check)
        want_text = want.content

        await user.send("📝 **Krok 3:** Dodatkowy opis (lub napisz `pomiń`):")
        desc = await self.bot.wait_for("message", check=check)
        desc_text = None if desc.content.lower() == "pomiń" else desc.content

        await user.send("📸 **Krok 4:** Wyślij zdjęcie przedmiotu (lub napisz `pomiń`):")
        attachment = None
        try:
            img = await self.bot.wait_for("message", check=check, timeout=60)
            if img.attachments:
                attachment = img.attachments[0].url
            elif img.content.lower() == "pomiń":
                attachment = None
        except asyncio.TimeoutError:
            attachment = None

        # 📦 Embed oferty
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

        # 📣 Ogłoszenie
        announce_embed = discord.Embed(
            title="🛒 Nowa oferta handlowa!",
            description=f"{user.mention} wystawił nową ofertę na kanale {trade_channel.mention}! 💎",
            color=discord.Color.blurple()
        )
        announce_embed.set_footer(text="Czas trwania oferty: 6 godzin ⏳")
        announce_message = await announce_channel.send(embed=announce_embed)

        view = TradeOfferView(self, user, announce_message)
        offer_message = await trade_channel.send(embed=embed, view=view)
        self.active_offers.append(view)

        await user.send("✅ Twoja oferta została opublikowana i wygasa za 6 godzin ⏳")

        # ⏳ Automatyczne wygaśnięcie
        await asyncio.sleep(6 * 60 * 60)
        if view.active:
            view.active = False
            try:
                await offer_message.delete()
                await announce_message.delete()
            except:
                pass
            try:
                await user.send("⌛ Twoja oferta wygasła po 6 godzinach bez zainteresowania.")
            except:
                pass


# -----------------------------
# 🔧 Rejestracja rozszerzenia
# -----------------------------
async def setup(bot):
    await bot.add_cog(TradeSystem(bot))







