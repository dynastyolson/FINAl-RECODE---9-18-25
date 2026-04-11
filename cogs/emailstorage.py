# cogs/supervisory_board.py
import discord
from discord.ext import commands
from discord import ui
import json
from pathlib import Path

# CONFIG
TARGET_CHANNEL_ID = 1489442235664699484   # replace with your channel ID
SUPERVISORY_ROLE_ID = 1489441770625564734  # replace with your Supervisory Board role ID
EMAIL_FILE = Path("supervisory_emails.json")

COLOR = discord.Color(int("8a7147", 16))
GREEN = discord.ButtonStyle.success
EMAIL_EMOJI = "<:image_20250915_213226179:1417337282700120166>"  # replace with your emoji

# ---------------- Persistence ----------------
def load_emails():
    if EMAIL_FILE.exists():
        try:
            with open(EMAIL_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_emails(data):
    with open(EMAIL_FILE, "w") as f:
        json.dump(data, f, indent=4)

emails_data = load_emails()

# ---------------- Views ----------------
class EmailButton(ui.View):
    def __init__(self, member: discord.Member):
        super().__init__(timeout=None)
        self.add_item(AddEmailButton(member))

class AddEmailButton(ui.Button):
    def __init__(self, member: discord.Member):
        super().__init__(label="Add E-mail", style=GREEN, emoji=EMAIL_EMOJI, custom_id=f"email_{member.id}")
        self.member = member

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.member.id:
            return await interaction.response.send_message("This button isn’t for you.", ephemeral=True)

        if str(self.member.id) in emails_data and emails_data[str(self.member.id)]["email"] != "N/A":
            return await interaction.response.send_message("You have already submitted your email.", ephemeral=True)

        await interaction.response.send_modal(AddEmailModal(self.member))

class AddEmailModal(ui.Modal, title="Add Your Email"):
    def __init__(self, member: discord.Member):
        super().__init__()
        self.member = member
        self.email = ui.TextInput(label="E-mail", placeholder="Enter your e-mail address", required=True)
        self.add_item(self.email)

    async def on_submit(self, interaction: discord.Interaction):
        email_value = self.email.value.strip()
        user_id_str = str(self.member.id)

        # Fetch target channel
        channel = interaction.client.get_channel(TARGET_CHANNEL_ID)
        if not channel:
            return await interaction.response.send_message("Target channel not found.", ephemeral=True)

        # Delete old message if exists
        old_msg_id = emails_data.get(user_id_str, {}).get("message_id")
        if old_msg_id:
            try:
                old_msg = await channel.fetch_message(old_msg_id)
                await old_msg.delete()
            except:
                pass

        # Save email persistently
        emails_data[user_id_str] = {
            "email": email_value,
            "guild_id": self.member.guild.id
        }

        # Repost updated embed with button
        embed = build_embed(self.member, email_value)
        new_msg = await channel.send(embed=embed, view=None)
        emails_data[user_id_str]["message_id"] = new_msg.id
        save_emails(emails_data)

        await interaction.response.send_message(
            "Your email has been saved and your profile updated.", ephemeral=True
        )

# ---------------- Embed Builder ----------------
def build_embed(member: discord.Member, email: str = "N/A"):
    embed = discord.Embed(
        title=f"{member.name} | {member.id}",
        description=(
            f"Discord: {member.mention} | {member.name} ({member.id})\n"
            f"Role: Supervisory Board\n"
            f"E-mail: {email}"
        ),
        color=COLOR
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    return embed

# ---------------- Cog ----------------
class SupervisoryBoard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def send_initial_embed(self, member: discord.Member):
        """Helper to send the initial embed if member doesn't already have one."""
        user_id_str = str(member.id)
        if user_id_str in emails_data:
            # Already exists, maybe just add view if email missing
            if emails_data[user_id_str].get("email", "N/A") == "N/A":
                self.bot.add_view(EmailButton(member))
            return

        channel = member.guild.get_channel(TARGET_CHANNEL_ID)
        if not channel:
            return

        embed = build_embed(member)
        msg = await channel.send(embed=embed, view=EmailButton(member))
        emails_data[user_id_str] = {
            "email": "N/A",
            "message_id": msg.id,
            "guild_id": member.guild.id
        }
        save_emails(emails_data)

    @commands.Cog.listener()
    async def on_ready(self):
        print("SupervisoryBoard cog ready. Initializing existing members...")
        for guild in self.bot.guilds:
            for member in guild.members:
                if any(r.id == SUPERVISORY_ROLE_ID for r in member.roles):
                    await self.send_initial_embed(member)
        print("SupervisoryBoard initialization complete.")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Detect role changes for Supervisory Board"""
        before_roles = {r.id for r in before.roles}
        after_roles = {r.id for r in after.roles}

        gained_role = SUPERVISORY_ROLE_ID not in before_roles and SUPERVISORY_ROLE_ID in after_roles
        if gained_role:
            await self.send_initial_embed(after)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Covers if member rejoins with role already present"""
        if any(r.id == SUPERVISORY_ROLE_ID for r in member.roles):
            await self.send_initial_embed(member)

async def setup(bot: commands.Bot):
    await bot.add_cog(SupervisoryBoard(bot))
