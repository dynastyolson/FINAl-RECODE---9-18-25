import discord
from discord.ext import commands
from datetime import datetime, timezone

# ------------------------------
# SETTINGS
# ------------------------------
GUILD_ID = 1465423138581123186  # Replace with your department server ID
CHANNEL_ID = 1489753816671981708  # Replace with the channel ID for logs
DEPARTMENT_LOGO = "https://cdn.discordapp.com/attachments/1231290151708131379/1492345476870180936/Untitled.png?ex=69dafe88&is=69d9ad08&hm=72263ac8462f2704f65973f7367dfb37591e9bd84edbc683f2c6f27901d84412&"
COLOR_SCHEME = 0x8a7147  # Department gray


class OfficerLoggerCog(commands.Cog):
    """Logs officer join/leave events for the department."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.guild.id != GUILD_ID:
            return

        channel = member.guild.get_channel(CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                description=(
                    f"{member.mention} has joined the department. "
                    f"We now have **{len(member.guild.members)}** members."
                ),
                color=COLOR_SCHEME,
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_author(name="Los Angeles Sheriffs Department", icon_url=DEPARTMENT_LOGO)
            embed.set_thumbnail(url=DEPARTMENT_LOGO)
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.guild.id != GUILD_ID:
            return

        channel = member.guild.get_channel(CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                description=(
                    f"{member.mention} has left the department. "
                    f"We now have **{len(member.guild.members)}** members."
                ),
                color=COLOR_SCHEME,
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_author(name="Los Angeles Sheriffs Department", icon_url=DEPARTMENT_LOGO)
            embed.set_thumbnail(url=DEPARTMENT_LOGO)
            await channel.send(embed=embed)


# ------------------------------
# SETUP
# ------------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(OfficerLoggerCog(bot))
