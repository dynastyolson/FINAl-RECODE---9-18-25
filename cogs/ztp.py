# cogs/ztp.py
import discord
from discord import app_commands, Interaction
from discord.ext import commands
import datetime
import json, os

# Config
ZTP_ROLE_ID = 1489441785611817071
ZTP_LOG_CHANNEL_ID = 1492339724956860531
ZTP_STORAGE_FILE = 'ztp.json'
THUMBNAIL_URL = "https://cdn.discordapp.com/attachments/1231290151708131379/1492345476870180936/Untitled.png?ex=69dafe88&is=69d9ad08&hm=72263ac8462f2704f65973f7367dfb37591e9bd84edbc683f2c6f27901d84412&"
ADMIN_ID = 1221986685634613338
SUPERVISOR_ROLE_ID = 1489441770625564734

# Helpers
def load_json(file):
    if not os.path.exists(file):
        return {}
    with open(file, 'r') as f:
        return json.load(f)

def save_json(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=4)

def add_log_entry(message):
    print(f"[ZTP LOG] {message}")

class ZTPCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ztp", description="Add or check an Officer's Zero Tolerance Policy")
    @app_commands.describe(
        officer="Mention or ID of Officer",
        length="Length in days (ignored for check)",
        action="Add or Check"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Add", value="add"),
        app_commands.Choice(name="Check", value="check")
    ])
    async def ztp_command(
        self,
        interaction: Interaction,
        officer: str,
        length: int = 0,
        action: app_commands.Choice[str] = None
    ):
        # Permission check
        if not (
            interaction.user.id == ADMIN_ID
            or any(r.id == SUPERVISOR_ROLE_ID for r in interaction.user.roles)
        ):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return

        guild = interaction.guild
        target = None
        try:
            user_id = int(officer.strip("<@!>"))
            target = guild.get_member(user_id) or await guild.fetch_member(user_id)
        except Exception:
            await interaction.response.send_message(
                "Invalid Officer mention or ID.",
                ephemeral=True
            )
            return

        # Add a ZTP
        if action.value.lower() == "add":
            if length <= 0:
                await interaction.response.send_message(
                    "Please provide a positive number of days for length.",
                    ephemeral=True
                )
                return

            ztp_data = load_json(ZTP_STORAGE_FILE)
            issued_time = datetime.datetime.utcnow()
            ztp_data[str(target.id)] = {
                "issued": issued_time.timestamp(),
                "length_days": length
            }
            save_json(ZTP_STORAGE_FILE, ztp_data)

            role = guild.get_role(ZTP_ROLE_ID)
            if role:
                await target.add_roles(role)

            embed_log = discord.Embed(
                title=f"Zero Tolerance Policy Issued | {target.id}",
                description=(
                    f"{target.mention} has been issued a Zero Tolerance Policy within the Senora Valley Police Department by the Supervisory Board.\n\n"
                    f"- `Length:` {length} day(s)"
                ),
                color=0xE7BB19
            )
            embed_log.set_thumbnail(url=THUMBNAIL_URL)

            log_channel = guild.get_channel(ZTP_LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(embed=embed_log)

            embed_dm = discord.Embed(
                title="LASD | Zero-Tolerance Policy Update",
                description=(
                    f"Hello {target.mention}, your Zero-Tolerance Policy has been updated.\n\n"
                    "- ZTP added\n\n"
                    "You can use the `/ztp` command (set type to Check) to check your ZTP status at any time."
                ),
                color=0x8a7147
            )
            embed_dm.set_thumbnail(url=THUMBNAIL_URL)

            try:
                await target.send(embed=embed_dm)
            except:
                pass

            add_log_entry(f"{interaction.user} added ZTP to {target} for {length} day(s).")
            await interaction.response.send_message(
                f"Zero Tolerance Policy added to {target.mention} for {length} day(s).",
                ephemeral=True
            )

        # Check a ZTP
        elif action.value.lower() == "check":
            ztp_data = load_json(ZTP_STORAGE_FILE)
            user_data = ztp_data.get(str(target.id))
            if not user_data:
                embed_dm = discord.Embed(
                    title="LASD | Zero-Tolerance Policy Status",
                    description=f"{target.mention} currently has **no active Zero-Tolerance Policy**.",
                    color=0x8a7147
                )
                embed_dm.set_thumbnail(url=THUMBNAIL_URL)
                try:
                    await target.send(embed=embed_dm)
                except:
                    pass
                await interaction.response.send_message(
                    f"{target.mention} has no active Zero Tolerance Policy.",
                    ephemeral=True
                )
                return

            issued_ts = user_data["issued"]
            length_days = user_data["length_days"]
            issued_dt = datetime.datetime.utcfromtimestamp(issued_ts)
            expire_dt = issued_dt + datetime.timedelta(days=length_days)
            now = datetime.datetime.utcnow()

            if now > expire_dt:
                # Expired → remove role + delete record
                del ztp_data[str(target.id)]
                save_json(ZTP_STORAGE_FILE, ztp_data)

                role = guild.get_role(ZTP_ROLE_ID)
                if role in target.roles:
                    await target.remove_roles(role)

                embed_dm = discord.Embed(
                    title="LASD | Zero-Tolerance Policy Status",
                    description=f"{target.mention} previously had a Zero-Tolerance Policy which has now expired.",
                    color=0x8a7147
                )
                embed_dm.set_thumbnail(url=THUMBNAIL_URL)
                try:
                    await target.send(embed=embed_dm)
                except:
                    pass
                await interaction.response.send_message(
                    f"{target.mention}'s Zero Tolerance Policy has expired and been removed.",
                    ephemeral=True
                )
                add_log_entry(f"Expired ZTP removed for {target}.")
                return

            days_left = (expire_dt - now).days
            embed_dm = discord.Embed(
                title="LASD | Zero-Tolerance Policy Status",
                description=(
                    f"{target.mention} currently has an active Zero-Tolerance Policy.\n\n"
                    f"- `Issued:` {issued_dt.strftime('%d-%m-%Y %H:%M:%S UTC')}\n"
                    f"- `Days Left:` {days_left} day(s)"
                ),
                color=0x8a7147
            )
            embed_dm.set_thumbnail(url=THUMBNAIL_URL)
            try:
                await target.send(embed=embed_dm)
            except:
                pass

            await interaction.response.send_message(
                f"{target.mention} has an active Zero Tolerance Policy. DM sent.",
                ephemeral=True
            )

        else:
            await interaction.response.send_message(
                "Invalid action. Please select Add or Check.",
                ephemeral=True
            )


# ------------------------------
# SETUP
# ------------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(ZTPCog(bot))
