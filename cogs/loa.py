# cogs/loa.py
import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Optional

# ---------------- CONFIG ----------------
LOA_CHANNEL_ID = 1492339763221369094      # <-- set your LOA log channel ID
APPROVER_ROLE_ID = 1489441766536118512    # <-- role allowed to approve/deny
EMBED_COLOR = 0x8a7147
THUMBNAIL_URL = "https://cdn.discordapp.com/attachments/1231290151708131379/1492345476870180936/Untitled.png?ex=69dafe88&is=69d9ad08&hm=72263ac8462f2704f65973f7367dfb37591e9bd84edbc683f2c6f27901d84412&"

# Approve / Deny custom_id templates (you can replace these with your fixed IDs)
# They will include the target user id so interactions are scoped.
APPROVE_CUSTOM_ID = "loa_approve:{uid}"
DENY_CUSTOM_ID = "loa_deny:{uid}"
EXTEND_CUSTOM_ID = "loa_extend:{uid}"

# Persist LOAs here
STORE_FILE = Path("loa_store.json")

# ---------------- Persistence helpers ----------------
def load_store() -> dict:
    if STORE_FILE.exists():
        try:
            return json.loads(STORE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_store(data: dict):
    STORE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

# In-memory store loaded from disk at start; structure:
# { "<user_id>": { "status": "Pending"/"Approved"/"Denied", "begin": "MM/DD/YYYY", "end": "MM/DD/YYYY",
#                  "reason": "...", "message_id": <channel_message_id or null>, "channel_id": <channel id> } }
loa_store = load_store()

# ---------------- Date parsing ----------------
DATE_FORMATS = ["%m/%d/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y"]

def parse_date(text: str) -> Optional[datetime]:
    text = text.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None

def date_to_string(dt: datetime) -> str:
    return dt.strftime("%m/%d/%Y")

# ---------------- Modals ----------------
class LOARequestModal(ui.Modal, title="LOA Request Form"):
    def __init__(self, requester: discord.Member):
        super().__init__(timeout=None)
        self.requester = requester

        self.begin = ui.TextInput(label="Beginning Date", placeholder="MM/DD/YYYY", required=True)
        self.end = ui.TextInput(label="Ending Date", placeholder="MM/DD/YYYY", required=True)
        self.reason = ui.TextInput(label="Reason", style=discord.TextStyle.paragraph, required=True, max_length=1500)

        self.add_item(self.begin)
        self.add_item(self.end)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        # Parse dates
        begin_dt = parse_date(self.begin.value)
        end_dt = parse_date(self.end.value)
        if not begin_dt or not end_dt:
            return await interaction.response.send_message(
                "Unable to parse provided dates. Use MM/DD/YYYY or YYYY-MM-DD or DD-MM-YYYY.", ephemeral=True
            )
        if end_dt < begin_dt:
            return await interaction.response.send_message("End date cannot be before Begin date.", ephemeral=True)

        uid = str(self.requester.id)
        loa_store[uid] = {
            "status": "Pending",
            "begin": date_to_string(begin_dt),
            "end": date_to_string(end_dt),
            "reason": self.reason.value,
            "message_id": None,
            "channel_id": LOA_CHANNEL_ID
        }
        save_store(loa_store)

        # Build embed
        embed = discord.Embed(
            title="LOA Request",
            description=(
                f"**Officer:** {self.requester.mention}\n"
                f"**Begins:** {loa_store[uid]['begin']}\n"
                f"**Ends:** {loa_store[uid]['end']}\n"
                f"**Reason:** {loa_store[uid]['reason']}"
            ),
            color=EMBED_COLOR
        )
        embed.set_thumbnail(url=THUMBNAIL_URL)

        # Build moderation view with Approve/Deny (custom ids include user id)
        view = LOAModerationView(self.requester.id)

        ch = interaction.client.get_channel(LOA_CHANNEL_ID)
        if not ch:
            return await interaction.response.send_message("LOA channel not found. Contact an admin.", ephemeral=True)

        sent = await ch.send(embed=embed, view=view)
        loa_store[uid]["message_id"] = sent.id
        save_store(loa_store)

        await interaction.response.send_message("Your LOA request has been submitted.", ephemeral=True)


class LOAExtendModal(ui.Modal, title="Extend LOA"):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.new_end = ui.TextInput(label="New End Date", placeholder="MM/DD/YYYY", required=True)
        self.add_item(self.new_end)

    async def on_submit(self, interaction: discord.Interaction):
        uid = str(self.user_id)
        if uid not in loa_store:
            return await interaction.response.send_message("You do not have an active LOA.", ephemeral=True)

        new_dt = parse_date(self.new_end.value)
        if not new_dt:
            return await interaction.response.send_message("Unable to parse the new date. Use MM/DD/YYYY.", ephemeral=True)

        # update store
        loa_store[uid]["end"] = date_to_string(new_dt)
        save_store(loa_store)

        # edit channel message if exists
        msg_id = loa_store[uid].get("message_id")
        ch_id = loa_store[uid].get("channel_id", LOA_CHANNEL_ID)
        ch = interaction.client.get_channel(ch_id)
        if ch and msg_id:
            try:
                msg = await ch.fetch_message(msg_id)
                updated = discord.Embed(
                    title="LOA Request",
                    description=(
                        f"**Officer:** <@{uid}>\n"
                        f"**Begins:** {loa_store[uid]['begin']}\n"
                        f"**Ends:** {loa_store[uid]['end']}\n"
                        f"**Reason:** {loa_store[uid]['reason']}\n"
                        f"**Status:** {loa_store[uid]['status']}"
                    ),
                    color=EMBED_COLOR
                )
                updated.set_thumbnail(url=THUMBNAIL_URL)
                await msg.edit(embed=updated)
            except Exception:
                pass

        await interaction.response.send_message("Your LOA end date has been updated.", ephemeral=True)

# ---------------- Views ----------------
class LOAModerationView(ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

        # buttons created here so custom_id contains user id
        approve_id = APPROVE_CUSTOM_ID.format(uid=user_id)
        deny_id = DENY_CUSTOM_ID.format(uid=user_id)
        self.add_item(ui.Button(label="Approve", style=discord.ButtonStyle.success, custom_id=approve_id))
        self.add_item(ui.Button(label="Deny", style=discord.ButtonStyle.danger, custom_id=deny_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # only allow approvers to use the buttons
        if any(r.id == APPROVER_ROLE_ID for r in interaction.user.roles):
            return True
        await interaction.response.send_message("You do not have permission to perform that action.", ephemeral=True)
        return False

    @ui.button(label="Approve", style=discord.ButtonStyle.success, custom_id="__placeholder_approve")
    async def _approve_stub(self, interaction: discord.Interaction, button: ui.Button):
        # This stub is never used; real buttons have custom IDs we handle in bot-wide handler.
        await interaction.response.defer()

    @ui.button(label="Deny", style=discord.ButtonStyle.danger, custom_id="__placeholder_deny")
    async def _deny_stub(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()

class LOAManageView(ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id
        extend_id = EXTEND_CUSTOM_ID.format(uid=user_id)
        self.add_item(ui.Button(label="Extend LOA", style=discord.ButtonStyle.secondary, custom_id=extend_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message("You cannot extend another user's LOA.", ephemeral=True)
        return False

# ---------------- Cog ----------------
class LOACog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_expired_loas.start()

    def cog_unload(self):
        self.check_expired_loas.cancel()

    @tasks.loop(minutes=1)
    async def check_expired_loas(self):
        # Remove expired LOAs and update/remove messages
        to_remove = []
        now = datetime.now(timezone.utc)
        for uid, data in list(loa_store.items()):
            try:
                end_dt = parse_date(data["end"])
                if not end_dt:
                    continue
                if now > end_dt or data.get("status") == "Denied":
                    # try to edit the channel message to indicate expired/cleared or delete it
                    ch = self.bot.get_channel(data.get("channel_id", LOA_CHANNEL_ID))
                    msg_id = data.get("message_id")
                    if ch and msg_id:
                        try:
                            msg = await ch.fetch_message(msg_id)
                            # mark expired
                            expired_embed = discord.Embed(
                                title="LOA Expired / Cleared",
                                description=(
                                    f"**Officer:** <@{uid}>\n"
                                    f"**Begins:** {data.get('begin')}\n"
                                    f"**Ends:** {data.get('end')}\n"
                                    f"**Status:** Cleared"
                                ),
                                color=EMBED_COLOR
                            )
                            expired_embed.set_thumbnail(url=THUMBNAIL_URL)
                            await msg.edit(embed=expired_embed, view=None)
                        except Exception:
                            pass
                    to_remove.append(uid)
            except Exception:
                continue

        for uid in to_remove:
            loa_store.pop(uid, None)
        if to_remove:
            save_store(loa_store)

    # Listen for button interactions globally (because we use dynamic custom_ids)
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        # handle approve/deny and extend by custom_id pattern
        if not interaction.type == discord.InteractionType.component:
            return

        cid = interaction.data.get("custom_id", "")
        # Approve pattern
        if cid.startswith("loa_approve:"):
            try:
                target_id = int(cid.split(":", 1)[1])
            except Exception:
                return
            if not any(r.id == APPROVER_ROLE_ID for r in interaction.user.roles):
                return await interaction.response.send_message("You do not have permission to approve.", ephemeral=True)

            uid = str(target_id)
            if uid not in loa_store:
                return await interaction.response.send_message("No such LOA found.", ephemeral=True)

            loa_store[uid]["status"] = "Approved"
            save_store(loa_store)

            # update channel embed
            ch = self.bot.get_channel(loa_store[uid].get("channel_id", LOA_CHANNEL_ID))
            msg_id = loa_store[uid].get("message_id")
            if ch and msg_id:
                try:
                    msg = await ch.fetch_message(msg_id)
                    updated = discord.Embed(
                        title="LOA Request",
                        description=(
                            f"**Officer:** <@{uid}>\n"
                            f"**Begins:** {loa_store[uid]['begin']}\n"
                            f"**Ends:** {loa_store[uid]['end']}\n"
                            f"**Reason:** {loa_store[uid]['reason']}\n"
                            f"**Status:** {loa_store[uid]['status']}"
                        ),
                        color=EMBED_COLOR
                    )
                    updated.set_thumbnail(url=THUMBNAIL_URL)
                    await msg.edit(embed=updated, view=None)
                except Exception:
                    pass

            # DM the user
            user = self.bot.get_user(int(uid))
            if user:
                dm_embed = discord.Embed(
                    description="Your LOA status has been updated. Use `/loa manage` to view the update.",
                    color=EMBED_COLOR
                )
                try:
                    await user.send(embed=dm_embed)
                except Exception:
                    pass

            await interaction.response.send_message(f"LOA Approved for <@{uid}>", ephemeral=True)
            return

        # Deny pattern
        if cid.startswith("loa_deny:"):
            try:
                target_id = int(cid.split(":", 1)[1])
            except Exception:
                return
            if not any(r.id == APPROVER_ROLE_ID for r in interaction.user.roles):
                return await interaction.response.send_message("You do not have permission to deny.", ephemeral=True)

            uid = str(target_id)
            if uid not in loa_store:
                return await interaction.response.send_message("No such LOA found.", ephemeral=True)

            loa_store[uid]["status"] = "Denied"
            save_store(loa_store)

            # update channel embed
            ch = self.bot.get_channel(loa_store[uid].get("channel_id", LOA_CHANNEL_ID))
            msg_id = loa_store[uid].get("message_id")
            if ch and msg_id:
                try:
                    msg = await ch.fetch_message(msg_id)
                    updated = discord.Embed(
                        title="LOA Request",
                        description=(
                            f"**Officer:** <@{uid}>\n"
                            f"**Begins:** {loa_store[uid]['begin']}\n"
                            f"**Ends:** {loa_store[uid]['end']}\n"
                            f"**Reason:** {loa_store[uid]['reason']}\n"
                            f"**Status:** {loa_store[uid]['status']}"
                        ),
                        color=EMBED_COLOR
                    )
                    updated.set_thumbnail(url=THUMBNAIL_URL)
                    await msg.edit(embed=updated, view=None)
                except Exception:
                    pass

            # DM the user
            user = self.bot.get_user(int(uid))
            if user:
                dm_embed = discord.Embed(
                    description="Your LOA status has been updated. Use `/loa manage` to view the update.",
                    color=EMBED_COLOR
                )
                try:
                    await user.send(embed=dm_embed)
                except Exception:
                    pass

            await interaction.response.send_message(f"LOA Denied for <@{uid}>", ephemeral=True)
            return

        # Extend pattern (user button)
        if cid.startswith("loa_extend:"):
            try:
                target_id = int(cid.split(":", 1)[1])
            except Exception:
                return
            # only allow the owner to open the extend modal
            if interaction.user.id != target_id:
                return await interaction.response.send_message("You cannot extend another user's LOA.", ephemeral=True)
            modal = LOAExtendModal(target_id)
            return await interaction.response.send_modal(modal)

    # app_commands group
    loa = app_commands.Group(name="loa", description="Manage your Leave of Absence")

    @loa.command(name="request")
    async def request(self, interaction: discord.Interaction):
        """Request a leave of absence (opens a form)."""
        modal = LOARequestModal(interaction.user)
        await interaction.response.send_modal(modal)

    @loa.command(name="manage")
    async def manage(self, interaction: discord.Interaction):
        """View/manage your LOA (ephemeral)."""
        uid = str(interaction.user.id)
        data = loa_store.get(uid)
        if not data:
            embed = discord.Embed(description="You do not have an active leave of absence.", color=EMBED_COLOR)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        embed = discord.Embed(
            title=f"Manage LOA | {interaction.user}",
            description=(
                "Your LOA information is displayed below:\n\n"
                f"**Status:** {data['status']}\n"
                f"**Beginning Date:** {data['begin']}\n"
                f"**Ending Date:** {data['end']}\n"
                f"**Reason:** {data['reason']}"
            ),
            color=EMBED_COLOR
        )
        await interaction.response.send_message(embed=embed, view=LOAManageView(interaction.user.id), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(LOACog(bot))
