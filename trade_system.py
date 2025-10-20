# trade_system.py
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from datetime import datetime


# -----------------------------
# 🔰 Widok finalizacji handlu (w prywatnym kanale)
# -----------------------------
class FinalizeTradeView(discord.ui.View):
    """
    Przyciski w prywatnym pokoju handlu.
    - ✅ Oferta udana: usuwa pokój, usuwa ogłoszenie w 🧭│handel i wysyła info do 📣│ogłoszenia
    - ❌ Anuluj: usuwa pokój, PRZYWRACA ogłoszenie do stanu aktywnego (bez spamu w 📣│ogłoszenia)
    """
    def __init__(self, channel: discord.TextChannel, cog: "TradeSystem",
                 author: discord.Member, partner: discord.Member,
                 original_message: discord.Message, original_embed: discord.Embed):
        super().__init__(timeout=None)
        self.channel = channel
        self.cog = cog
        self.author = author
        self.partner = partner
        self.original_message = original_message
        self.original_embed = original_embed

    @discord.ui.button(label="✅ Oferta udana", style=discord.ButtonStyle.green)
    async def success(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "🎉 Handel zakończony pomyślnie! Kanał zostanie usunięty za 5 sekund.",
            ephemeral=True
        )

        # 📣 Powiadom o sukcesie
        announce_channel = discord.utils.get(interaction.guild.text_channels, name="📣│ogłoszenia")
        if announce_channel:
            await announce_channel.send(
                f"✅ Handel pomyślnie zakończony pomiędzy {self.author.mention} a {self.partner.mention} 💎"
            )

        # 🧹 Usuń ogłoszenie z 🧭│handel
        try:
            await self.original_message.delete()
        except Exception:
            pass

        # 🗑️ Usuń pokój i zwolnij blokadę pary
        await asyncio.sleep(5)
        try:
            await self.channel.delete()
        finally:
            self.cog.active_trades.discard((self.author.id, self.partner.id))
            self.cog.active_trades.discard((self.partner.id, self.author.id))

    @discord.ui.button(label="❌ Anuluj handel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "❌ Handel anulowany. Kanał zostanie usunięty za 5 sekund.",
            ephemeral=True
        )

        # 🔁 PRZYWRÓĆ ogłoszenie do stanu aktywnego w 🧭│handel (bez ogłoszeń w 📣│ogłoszenia)
        try:
            await self.original_message.edit(
                embed=self.original_embed,
                view=TradeOfferView(self.cog, self.author)  # nowy aktywny view
            )
        except Exception:
            pass

        # 🗑️ Usuń pokój i zwolnij blokadę pary
        await asyncio.sleep(5)
        try:
            await self.channel.delete()
        finally:
            self.cog.active_trades.discard((self.author.id, self.partner.id))
            self.cog.active_trades.discard((self.partner.id, self.author.id))


# -----------------------------
# 📩 Widok przycisków ogłoszenia
# -----------------------------
class TradeOfferView(discord.ui.View):
    """
    View na ogłoszeniu w 🧭│handel:
    - 🟢 Zainteresowany: tworzy prywatny pokój, blokuje dalsze kliknięcia i ustawia "w trakcie"
    - 🔴 Anuluj ofertę: TYLKO autor, usuwa ogłoszenie całkowicie
    """
    def __init__(self, cog: "TradeSystem", author: discord.Member):
        super().__init__(timeout=None)
        self.cog = cog
        self.author = author
        self.active = True
        self.current_trade_user: discord.Member | None = None

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

        # 🔒 Zablokuj dalsze kliknięcia dla tej oferty + zapisz parę
        self.cog.active_trades.add((self.author.id, interaction.user.id))
        self.active = False
        self.current_trade_user = interaction.user

        # 🏗️ Pokój prywatny handlu
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            self.author: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        channel_name = f"💸│handel-{self.author.name.lower()}-{interaction.user.name.lower()}"
        trade_channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)

        # ✍️ Zapamiętaj oryginalny embed (żeby móc przywrócić po anulowaniu)
        try:
            original_embed = interaction.message.embeds[0]
        except Exception:
            original_embed = discord.Embed(title="📦 Oferta handlowa", color=discord.Color.gold())

        # 🔒 Zmień ogłoszenie na "w trakcie"
        inprogress_embed = discord.Embed(
            title="🔒 Oferta w trakcie realizacji",
            description=f"Handel pomiędzy {self.author.mention} a {interaction.user.mention} jest w toku!",
            color=discord.Color.orange()
        )
        await interaction.response.edit_message(embed=inprogress_embed, view=None)

        # 💬 Wiadomość w pokoju
        room_intro = discord.Embed(
            title="💬 Pokój handlowy",
            description=(
                f"{self.author.mention} i {interaction.user.mention}, możecie teraz omówić szczegóły wymiany.\n\n"
                f"Gdy zakończycie handel, wybierzcie jedną z opcji poniżej."
            ),
            color=discord.Color.green()
        )
        await trade_channel.send(
            embed=room_intro,
            view=FinalizeTradeView(
                trade_channel, self.cog, self.author, interaction.user,
                original_message=interaction.message,
                original_embed=original_embed
            )
        )

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
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # para (author_id, partner_id), żeby nie mieć dwóch pokoi z tą samą parą
        self.active_trades: set[tuple[int, int]] = set()

    @app_commands.command(name="wystaw", description="Wystaw ofertę handlową na kanale 🧭│handel.")
    async def wystaw(self, interaction: discord.Interaction):
        user = interaction.user
        trade_channel = discord.utils.get(interaction.guild.text_channels, name="🧭│handel")
        announce_channel = discord.utils.get(interaction.guild.text_channels, name="📣│ogłoszenia")

        if not trade_channel or not announce_channel:
            await interaction.response.send_message(
                "⚠️ Brakuje jednego z kanałów: 🧭│handel lub 📣│ogłoszenia.",
                ephemeral=True
            )
            return

        # Start DM flow
        await interaction.response.send_message("🧾 Rozpoczynamy tworzenie Twojej oferty handlu! Sprawdź DM.", ephemeral=True)
        try:
            await user.send("💰 **Krok 1:** Napisz, co oferujesz:")
        except discord.Forbidden:
            await interaction.followup.send("❌ Nie mogę wysłać Ci wiadomości na DM. Otwórz DM i spróbuj ponownie.", ephemeral=True)
            return

        def dm_check(m: discord.Message):
            return m.author == user and isinstance(m.channel, discord.DMChannel)

        offer = await self.bot.wait_for("message", check=dm_check)
        offer_text = offer.content

        await user.send("🎯 **Krok 2:** Napisz, co chciałbyś otrzymać w zamian:")
        want = await self.bot.wait_for("message", check=dm_check)
        want_text = want.content

        await user.send("📝 **Krok 3:** (opcjonalnie) Opis oferty lub wpisz `pomiń`:")
        desc = await self.bot.wait_for("message", check=dm_check)
        desc_text = None if desc.content.lower() == "pomiń" else desc.content

        await user.send("📸 **Krok 4:** Jeśli chcesz, wyślij **jedno zdjęcie** przedmiotu (lub wpisz `pomiń`). Masz 60 sekund:")
        attachment_url = None
        try:
            img_msg = await self.bot.wait_for("message", check=dm_check, timeout=60)
            if img_msg.attachments:
                attachment_url = img_msg.attachments[0].url
            elif img_msg.content.lower() == "pomiń":
                attachment_url = None
        except asyncio.TimeoutError:
            attachment_url = None

        # 📦 Embed oferty
        base_embed = discord.Embed(
            title="📦 Nowe ogłoszenie handlowe",
            description=(
                f"**👤 Gracz:** {user.mention}\n\n"
                f"💰 **Oferuje:** {offer_text}\n"
                f"🎯 **Chce otrzymać:** {want_text}\n\n"
                f"📝 **Opis:** {desc_text or '_Brak dodatkowych informacji_'}"
            ),
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )
        base_embed.set_footer(text="Kliknij przycisk, aby rozpocząć handel z autorem.")
        if attachment_url:
            base_embed.set_image(url=attachment_url)

        view = TradeOfferView(self, user)
        trade_message = await trade_channel.send(embed=base_embed, view=view)

        # 📣 Powiadom w ogłoszeniach (tylko info o nowym ogłoszeniu)
        announce_embed = discord.Embed(
            title="🛒 Nowa oferta handlowa!",
            description=f"{user.mention} wystawił nową ofertę handlu na kanale {trade_channel.mention}! 💎",
            color=discord.Color.blurple()
        )
        announce_embed.set_footer(text="Czas trwania oferty: 6 godzin ⏳")
        await announce_channel.send(embed=announce_embed)

        try:
            await user.send("✅ Twoja oferta została opublikowana! Wygasa za 6 godzin ⏳")
        except Exception:
            pass

        # ⏳ Wygaśnięcie po 6 godzinach, jeśli nikt nie kliknął
        await asyncio.sleep(6 * 60 * 60)
        if view.active:  # nikt nie rozpoczął handlu
            view.active = False
            expired_embed = discord.Embed(
                title="⌛ Oferta wygasła",
                description=f"Oferta gracza {user.mention} wygasła po 6 godzinach bez zainteresowania.",
                color=discord.Color.dark_grey()
            )
            try:
                await trade_message.edit(embed=expired_embed, view=None)
            except Exception:
                pass
            try:
                await user.send("⌛ Twoja oferta wygasła bez odpowiedzi.")
            except Exception:
                pass


# -----------------------------
# 🔧 Rejestracja rozszerzenia
# -----------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(TradeSystem(bot))





