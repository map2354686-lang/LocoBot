import discord
from discord import app_commands
from discord.ext import commands
import asyncio

# -----------------------------
# KLASA TradeView – przyciski Akceptuj / Odrzuć
# -----------------------------
class TradeView(discord.ui.View):
    def __init__(self, author, target):
        super().__init__(timeout=None)
        self.author = author
        self.target = target

    # ✅ Akceptacja oferty
    @discord.ui.button(label="✅ Akceptuj", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.target:
            await interaction.response.send_message(
                "❌ Nie możesz zaakceptować tej oferty — nie jesteś jej odbiorcą.",
                ephemeral=True
            )
            return

        guild = interaction.guild

        # 🔒 Ustawienia uprawnień dla kanału handlu
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            self.author: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            self.target: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }

        # 🏗️ Tworzenie prywatnego kanału handlu
        trade_channel_name = f"💸│handel-{self.author.name.lower()}-{self.target.name.lower()}"
        trade_channel = await guild.create_text_channel(
            name=trade_channel_name,
            overwrites=overwrites,
            reason="Automatycznie utworzony kanał handlu"
        )

        # 💬 Wiadomość powitalna w kanale
        welcome_embed = discord.Embed(
            title="💸 Pokój handlu",
            description=(
                f"Witajcie {self.author.mention} i {self.target.mention}!\n\n"
                "Ten kanał został utworzony, abyście mogli spokojnie przeprowadzić wymianę.\n"
                "Gdy zakończycie handel, napiszcie **`!zakoncz`**, aby kanał został usunięty. 💎"
            ),
            color=discord.Color.green()
        )
        await trade_channel.send(embed=welcome_embed)

        # ✏️ Zaktualizuj starą wiadomość
        embed = discord.Embed(
            title="✅ Handel zaakceptowany!",
            description=(
                f"{self.target.mention} zaakceptował ofertę handlu od {self.author.mention}.\n\n"
                f"🔗 Kanał handlu: {trade_channel.mention}"
            ),
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=None)

        # (opcjonalnie) usuń starą wiadomość po 10s
        await asyncio.sleep(10)
        try:
            await interaction.message.delete()
        except:
            pass

    # ❌ Odrzucenie oferty
    @discord.ui.button(label="❌ Odrzuć", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.target:
            await interaction.response.send_message(
                "❌ Nie możesz odrzucić tej oferty — nie jesteś jej odbiorcą.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="❌ Handel odrzucony",
            description=f"{self.target.mention} odrzucił ofertę handlu od {self.author.mention}.",
            color=discord.Color.red()
        )

        await interaction.response.edit_message(embed=embed, view=None)

        # (opcjonalnie) usuń wiadomość po 10 sekundach
        await asyncio.sleep(10)
        try:
            await interaction.message.delete()
        except:
            pass


# -----------------------------
# GŁÓWNA KLASA SYSTEMU HANDLU
# -----------------------------
class TradeSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Slash-komenda /trade
    @app_commands.command(name="trade", description="Wyślij ofertę handlu do innego gracza.")
    async def trade(self, interaction: discord.Interaction, user: discord.User):
        if user == interaction.user:
            await interaction.response.send_message(
                "❌ Nie możesz wysłać oferty handlu samemu sobie!",
                ephemeral=True
            )
            return

        # Znajdź kanał handlu
        channel = discord.utils.get(interaction.guild.text_channels, name="🧭│handel")
        if not channel:
            await interaction.response.send_message(
                "⚠️ Nie znaleziono kanału `🧭│handel`!",
                ephemeral=True
            )
            return

        # Utwórz embed oferty
        embed = discord.Embed(
            title="💰 Nowa oferta handlu!",
            description=f"{interaction.user.mention} chce się z Tobą wymienić!",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Kliknij przycisk, aby zaakceptować lub odrzucić ofertę.")

        view = TradeView(author=interaction.user, target=user)

        await channel.send(content=f"{user.mention}", embed=embed, view=view)
        await interaction.response.send_message(
            f"✅ Wysłano ofertę handlu do {user.mention}!",
            ephemeral=True
        )

    # Komenda !zakoncz do usuwania kanału po zakończeniu handlu
    @commands.command(name="zakoncz")
    async def zakoncz(self, ctx):
        """Usuwa aktualny kanał handlu po zakończeniu"""
        if ctx.channel.name.startswith("💸│handel-"):
            await ctx.send("🧹 Kanał handlu zostanie usunięty za 5 sekund...")
            await asyncio.sleep(5)
            await ctx.channel.delete()
        else:
            await ctx.send("❌ To nie jest kanał handlu!")


# -----------------------------
# Rejestracja rozszerzenia
# -----------------------------
async def setup(bot):
    await bot.add_cog(TradeSystem(bot))


