# cogs/discipline.py
import discord
from discord.ext import commands
from discord import app_commands
import json, asyncio
from pathlib import Path

# CONFIG
LOG_CHANNEL_ID = 1492339928523079792
TARGET_GUILD_ID = 1465423138581123186
AUTH_FILE = Path("authorization_logs.json")

SUSPENSION_ROLE_ID = 1489441783770513491  # replace with actual
DEMOTION_REMOVE_FILE = Path("demotion_remove_roles.json")
DEMOTION_ASSIGN_FILE = Path("demotion_assign_roles.json")

DISCIPLINE_LEVELS = {
    "Written Warning": 1,
    "Suspension": 2,
    "Demotion": 3,
    "Termination": 4,
    "Blacklist": 4,
}

COLOR = discord.Color(int("8a7147", 16))
LOGO_URL = "https://cdn.discordapp.com/attachments/1231290151708131379/1492345476870180936/Untitled.png?ex=69dafe88&is=69d9ad08&hm=72263ac8462f2704f65973f7367dfb37591e9bd84edbc683f2c6f27901d84412&"

# ---------------- Authorization ----------------
def get_user_level(user_id: int) -> int | None:
    if not AUTH_FILE.exists():
        return None
    try:
        with open(AUTH_FILE, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return None
    for entry in data:
        if entry.get("id") == user_id and entry.get("action") == "Accepted":
            return int(entry.get("access_level", 0))
    return None


# ----------------- Discipline Cog -----------------
class Discipline(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="discipline", description="Issue a disciplinary action")
    @app_commands.describe(
        officer="Select the officer to discipline",
        type="Select the type of disciplinary action"
    )
    @app_commands.choices(type=[
        app_commands.Choice(name="Written Warning", value="Written Warning"),
        app_commands.Choice(name="Suspension", value="Suspension"),
        app_commands.Choice(name="Demotion", value="Demotion"),
        app_commands.Choice(name="Termination", value="Termination"),
        app_commands.Choice(name="Blacklist", value="Blacklist"),
    ])
    async def discipline(
        self,
        interaction: discord.Interaction,
        officer: discord.Member,
        type: app_commands.Choice[str]
    ):
        user_level = get_user_level(interaction.user.id)
        if user_level is None:
            return await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)

        discipline_type = type.value
        if user_level < DISCIPLINE_LEVELS[discipline_type]:
            return await interaction.response.send_message(
                f"You do not have the required authorization level to issue a {discipline_type}.",
                ephemeral=True
            )

        # Select modal
        if discipline_type in ["Written Warning", "Termination", "Blacklist"]:
            modal = SimpleDisciplineModal(discipline_type, officer)
        elif discipline_type == "Suspension":
            modal = SuspensionModal(officer)
        elif discipline_type == "Demotion":
            modal = DemotionModal(officer)

        await interaction.response.send_modal(modal)


# ----------------- MODALS -----------------
class SimpleDisciplineModal(discord.ui.Modal, title="Disciplinary Action"):
    def __init__(self, action_type: str, officer: discord.Member):
        super().__init__()
        self.action_type = action_type
        self.officer = officer


        self.reason = discord.ui.TextInput(label="Reason", style=discord.TextStyle.paragraph)
        self.evidence = discord.ui.TextInput(label="Evidence", style=discord.TextStyle.paragraph)

        self.add_item(self.reason)
        self.add_item(self.evidence)

    async def on_submit(self, interaction: discord.Interaction):
        await handle_discipline(
            interaction,
            self.officer,
            self.action_type,
            self.reason.value,
            self.evidence.value,

        )


class SuspensionModal(discord.ui.Modal, title="Suspension Form"):
    def __init__(self, officer: discord.Member):
        super().__init__()
        self.officer = officer


        self.reason = discord.ui.TextInput(label="Reason", style=discord.TextStyle.paragraph)
        self.evidence = discord.ui.TextInput(label="Evidence", style=discord.TextStyle.paragraph)
        self.length = discord.ui.TextInput(label="Length", placeholder="1d, 3d, 7d")


        self.add_item(self.reason)
        self.add_item(self.evidence)
        self.add_item(self.length)

    async def on_submit(self, interaction: discord.Interaction):
        await handle_discipline(
            interaction,
            self.officer,
            "Suspension",
            self.reason.value,
            self.evidence.value,
            length=self.length.value,
        )


class DemotionModal(discord.ui.Modal, title="Demotion Form"):
    def __init__(self, officer: discord.Member):
        super().__init__()
        self.officer = officer


        self.reason = discord.ui.TextInput(label="Reason", style=discord.TextStyle.paragraph)
        self.evidence = discord.ui.TextInput(label="Evidence", style=discord.TextStyle.paragraph)
        self.new_rank = discord.ui.TextInput(label="New Rank", placeholder="Enter new rank name")


        self.add_item(self.reason)
        self.add_item(self.evidence)
        self.add_item(self.new_rank)

    async def on_submit(self, interaction: discord.Interaction):
        await handle_discipline(
            interaction,
            self.officer,
            "Demotion",
            self.reason.value,
            self.evidence.value,
            new_rank=self.new_rank.value,

        )


# ----------------- HANDLER -----------------
async def handle_discipline(
    interaction,
    officer,
    action_type,
    reason,
    evidence,
    case_code=None,
    length=None,
    new_rank=None
):
    punishment = action_type
    if action_type == "Suspension" and length:
        punishment += f" ({length})"
    if action_type == "Demotion" and new_rank:
        punishment += f" → {new_rank}"

    await interaction.response.send_message(
        f"Disciplinary action issued against {officer.mention}: **{punishment}**",
        ephemeral=True
    )

    # DM Embed
    embed_dm = discord.Embed(
        title="Los Angeles Sheriffs Department | Disciplinary Action",
        description=(
            f"- **Reason:** {reason}\n"
            f"- **Evidence:** {evidence}\n"
            f"- **Action:** {punishment}\n\n"
            f"Greetings, {officer.mention}. You've been issued a disciplinary action within the department by the Discipline Management team.\n\n"
            f"This action has been logged as a `{action_type}`. Continued violations may result in further consequences."
        ),
        color=COLOR
    )
    embed_dm.set_thumbnail(url=LOGO_URL)

    try:
        await officer.send(embed=embed_dm)
    except:
        pass

    # Log channel
    log_channel = interaction.client.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        embed_log = discord.Embed(
            title="Discipline Log",
            description=(
                f"- **Officer:** {officer.mention}\n"
                f"- **Supervisor:** {interaction.user.mention}\n"
                f"- **Reason:** {reason}\n"
                f"- **Evidence:** {evidence}\n"
                f"- **Action:** {punishment}\n"
            ),
            color=COLOR
        )
        embed_log.set_thumbnail(url=LOGO_URL)
        embed_log.set_footer(text=f"Issued on {discord.utils.format_dt(discord.utils.utcnow(), style='F')}")
        await log_channel.send(embed=embed_log)

    guild = interaction.client.get_guild(TARGET_GUILD_ID)
    if not guild:
        return

    member = guild.get_member(officer.id)
    if not member:
        return

    # Special Actions
    if action_type == "Termination":
        await member.kick(reason=reason)
    elif action_type == "Blacklist":
        await member.ban(reason=reason)
    elif action_type == "Suspension" and length:
        suspension_role = guild.get_role(SUSPENSION_ROLE_ID)
        if suspension_role:
            await member.add_roles(suspension_role, reason=f"Suspended for {length}")

            dur_map = {"1d": 86400, "3d": 86400 * 3, "7d": 86400 * 7}
            duration_seconds = dur_map.get(length.lower(), 86400)

            async def remove_suspension():
                await asyncio.sleep(duration_seconds)
                try:
                    await member.remove_roles(suspension_role, reason="Suspension expired")
                except:
                    pass

            asyncio.create_task(remove_suspension())

    elif action_type == "Demotion" and new_rank:
        if DEMOTION_REMOVE_FILE.exists():
            try:
                with open(DEMOTION_REMOVE_FILE, "r") as f:
                    remove_roles = json.load(f)
                for role_id in remove_roles:
                    role = guild.get_role(int(role_id))
                    if role in member.roles:
                        await member.remove_roles(role, reason="Demotion role removal")
            except:
                pass

        if DEMOTION_ASSIGN_FILE.exists():
            try:
                with open(DEMOTION_ASSIGN_FILE, "r") as f:
                    assign_roles = json.load(f)
                role_id = assign_roles.get(new_rank)
                if role_id:
                    role = guild.get_role(int(role_id))
                    if role:
                        await member.add_roles(role, reason="Demotion role assignment")
            except:
                pass
# ----------------- Authorization Command -----------------
class Authorization(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="authorization", description="Authorize or deny a user's access level")
    @app_commands.describe(
        user="The user to authorize or deny",
        action="Choose whether to accept or deny",
        access_level="Numeric level of access (1-4)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Accept", value="Accepted"),
        app_commands.Choice(name="Deny", value="Denied"),
    ])
    async def authorization(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        action: app_commands.Choice[str],
        access_level: int
    ):
        if access_level < 1 or access_level > 4:
            return await interaction.response.send_message(
                "Access level must be between 1 and 4.", ephemeral=True
            )

        log_entry = {
            "id": user.id,
            "action": action.value,
            "access_level": access_level,
            "authorized_by": interaction.user.id,
            "timestamp": str(discord.utils.utcnow())
        }

        # Load existing data
        data = []
        if AUTH_FILE.exists():
            try:
                with open(AUTH_FILE, "r") as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                data = []

        # Remove previous authorizations for this user
        data = [entry for entry in data if entry.get("id") != user.id]
        data.append(log_entry)

        with open(AUTH_FILE, "w") as f:
            json.dump(data, f, indent=4)

        # Confirmation embed
        embed = discord.Embed(
            title="Authorization Update",
            description=(
                f"- **User:** {user.mention}\n"
                f"- **Action:** {action.value}\n"
                f"- **Access Level:** {access_level}\n"
                f"- **Authorized By:** {interaction.user.mention}\n"
            ),
            color=COLOR
        )
        embed.set_thumbnail(url=LOGO_URL)
        embed.set_footer(text=f"Updated on {discord.utils.format_dt(discord.utils.utcnow(), style='F')}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Log it publicly
        log_channel = interaction.client.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Discipline(bot))
    await bot.add_cog(Authorization(bot))

