import discord
from discord import app_commands, Interaction, Embed
from discord.ext import commands
from discord.ext.commands import CooldownMapping, BucketType

# ------------------------------
# SETTINGS
# ------------------------------
ASSISTANCE_ROLE_ID = 1489441768566161519   # Officers who can request assistance
FORCE_REQUEST_ROLE_ID = 1489441766536118512  # Supervisors who can force request
ADMIN_USER_ID = 1221986685634613338        # Developer override
ASSISTANCE_CHANNEL_ID = 1489442163203768420  # Assistance request channel

DEPARTMENT_LOGO = "https://media.discordapp.net/attachments/1400897643772907640/1424180413076606977/Untitled_design_4.png?ex=69107e9e&is=690f2d1e&hm=74989a85019ed50ac5814b2ce101c204b3f26cfe13a3d62351af0d34c5e76cad&=&format=webp&quality=lossless"
COLOR_SCHEME = 0x8a7147  # Department gray

ASSISTANCE_COOLDOWN = CooldownMapping.from_cooldown(1, 21600, BucketType.user)  # 6 hours


def can_use_assistance_command(user):
    return any(role.id == ASSISTANCE_ROLE_ID for role in user.roles) or user.id == ADMIN_USER_ID


def can_use_force_request(user):
    return any(role.id == FORCE_REQUEST_ROLE_ID for role in user.roles) or user.id == ADMIN_USER_ID


class AssistanceCog(commands.Cog):
    """Handles deputy assistance requests."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="assistance-request", description="Send an assistance request with priority and reason")
    @app_commands.describe(
        priority="Priority level of assistance",
        reason="Reason for the assistance request"
    )
    @app_commands.choices(priority=[
        app_commands.Choice(name="1 - Urgent (Ping @everyone)", value=1),
        app_commands.Choice(name="2 - High (Ping @here)", value=2),
        app_commands.Choice(name="3 - Normal (No ping)", value=3)
    ])
    async def assistance_request(self, interaction: Interaction, priority: app_commands.Choice[int], reason: str):
        if not can_use_assistance_command(interaction.user):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        bucket = ASSISTANCE_COOLDOWN.get_bucket(interaction)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            hours = int(retry_after // 3600)
            minutes = int((retry_after % 3600) // 60)
            await interaction.response.send_message(
                f"You must wait {hours}h {minutes}m before using this command again.",
                ephemeral=True
            )
            return

        await self._send_assistance_embed(interaction, priority.value, reason)
        await interaction.response.send_message(
            f"Assistance request sent with priority {priority.value}.", ephemeral=True
        )

    @app_commands.command(name="force-request", description="Force send an assistance request without cooldown")
    @app_commands.describe(
        priority="Priority level of assistance",
        reason="Reason for the assistance request"
    )
    @app_commands.choices(priority=[
        app_commands.Choice(name="1 - Urgent (Ping @everyone)", value=1),
        app_commands.Choice(name="2 - High (Ping @here)", value=2),
        app_commands.Choice(name="3 - Normal (No ping)", value=3)
    ])
    async def force_request(self, interaction: Interaction, priority: app_commands.Choice[int], reason: str):
        if not can_use_force_request(interaction.user):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        await self._send_assistance_embed(interaction, priority.value, reason)
        await interaction.response.send_message(
            f"Force assistance request sent with priority {priority.value}.", ephemeral=True
        )

    async def _send_assistance_embed(self, interaction: Interaction, priority_value: int, reason: str):
        channel = interaction.guild.get_channel(ASSISTANCE_CHANNEL_ID)
        if channel is None:
            await interaction.response.send_message("Assistance channel not found.", ephemeral=True)
            return

        if priority_value == 1:
            ping = "@everyone"
            desc_text = "is urgently requesting additional deputies."
        elif priority_value == 2:
            ping = "@here"
            desc_text = "is requesting additional deputies."
        else:
            ping = None
            desc_text = "is requesting deputy assistance."

        description = f"The department {desc_text}\n\n**Reason:** {reason}"
        embed = Embed(
            title="Assistance Request",
            description=description,
            color=COLOR_SCHEME
        )
        embed.set_thumbnail(url=DEPARTMENT_LOGO)

        await channel.send(content=ping, embed=embed)


# ------------------------------
# SETUP
# ------------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(AssistanceCog(bot))
