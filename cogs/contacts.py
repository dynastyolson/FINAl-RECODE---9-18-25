import discord
from discord.ext import commands
from datetime import datetime

# ------------------------------
# CONFIGURATION
# ------------------------------
FORUM_CHANNEL_ID = 1492347637171622018  # Forum channel for contact posts
ROLE_CONTACT_NOTIFY = 1489441770625564734  # Role to ping when ticket created
EMOJI_CONFIRM = 1411408394476322846  # Reaction emoji ID

# Elevation roles
ROLE_HIGH_COMMAND = 1489441757442605328      # High Command
ROLE_DA = 1489441766536118512                # Department Administration
ROLE_MANAGEMENT = 1489441751184707759        # Server Management

# Role hierarchy for staff replies
ROLE_SUPERVISOR = 1489441770625564734        # Supervisor
ROLE_DEPT_ADMIN = 1489441766536118512        # Department Administration
ROLE_SERVER_MANAGEMENT = 1489441751184707759 # Server Management


class ContactSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_tickets = {}
        self.ignore_messages = set()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Handle DMs from users
        if isinstance(message.channel, discord.DMChannel):
            if message.author.id in self.active_tickets:
                thread = self.bot.get_channel(self.active_tickets[message.author.id])
                if thread:
                    embed = discord.Embed(
                        title="New Reply",
                        description=message.content,
                        color=0x8a7147,
                    )
                    embed.set_thumbnail(
                        url="https://cdn.discordapp.com/attachments/1411384487694307349/1411384964133421107/icon_26.png"
                    )
                    sent = await thread.send(embed=embed)
                    try:
                        await sent.add_reaction(self.bot.get_emoji(EMOJI_CONFIRM))
                    except:
                        pass
                return

            # Initial DM prompt if no ticket
            view = discord.ui.View()
            view.add_item(ContactButton(self))
            embed = discord.Embed(
                title="Need Assistance?",
                description=(
                    "If you have a concern or require assistance, please create a support ticket by pressing the button below. "
                    "Your request will be directed to the **Los Angeles Sheriffs Department Supervisory Board**."
                ),
                color=0x8a7147,
            )
            await message.channel.send(embed=embed, view=view)

        # Handle staff replies in ticket threads
        elif message.guild:
            if message.id in self.ignore_messages:
                return

            for user_id, thread_id in self.active_tickets.items():
                if message.channel.id == thread_id:
                    user = await self.bot.fetch_user(user_id)
                    if not user:
                        return

                    rank, color, logo = self.get_rank_info(message.author)
                    embed = discord.Embed(description=message.content, color=color)
                    embed.set_author(name=rank, icon_url=logo)

                    try:
                        sent = await user.send(embed=embed)
                        await sent.add_reaction(self.bot.get_emoji(EMOJI_CONFIRM))
                    except:
                        pass
                    break

    def get_rank_info(self, member: discord.Member):
        """Assigns rank display based on role hierarchy"""
        if any(r.id == ROLE_SERVER_MANAGEMENT for r in member.roles):
            return (
                "Server Management",
                0x8a7147,
                "https://cdn.discordapp.com/attachments/1231290151708131379/1492345476870180936/Untitled.png?ex=69dafe88&is=69d9ad08&hm=72263ac8462f2704f65973f7367dfb37591e9bd84edbc683f2c6f27901d84412&",
            )
        if any(r.id == ROLE_DEPT_ADMIN for r in member.roles):
            return (
                "Department Administration",
                0x8a7147,
                "https://cdn.discordapp.com/attachments/1231290151708131379/1492345476870180936/Untitled.png?ex=69dafe88&is=69d9ad08&hm=72263ac8462f2704f65973f7367dfb37591e9bd84edbc683f2c6f27901d84412&",
            )
        if any(r.id == ROLE_SUPERVISOR for r in member.roles):
            return (
                "Department Supervisor",
                0x8a7147,
                "https://cdn.discordapp.com/attachments/1231290151708131379/1492345476870180936/Untitled.png?ex=69dafe88&is=69d9ad08&hm=72263ac8462f2704f65973f7367dfb37591e9bd84edbc683f2c6f27901d84412&",
            )
        return (
            "Department Supervisor",
            0x8a7147,
            "https://cdn.discordapp.com/attachments/1231290151708131379/1492345476870180936/Untitled.png?ex=69dafe88&is=69d9ad08&hm=72263ac8462f2704f65973f7367dfb37591e9bd84edbc683f2c6f27901d84412&",
        )


# ------------------------------
# BUTTONS / MODALS
# ------------------------------
class ContactButton(discord.ui.Button):
    def __init__(self, cog: ContactSystem):
        super().__init__(label="Contact us here!", style=discord.ButtonStyle.secondary)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ContactModal(self.cog, interaction.user))


class ContactModal(discord.ui.Modal, title="Contact Form"):
    def __init__(self, cog: ContactSystem, user: discord.User):
        super().__init__(timeout=None)
        self.cog = cog
        self.user = user
        self.inquiry = discord.ui.TextInput(
            label="Inquiry", style=discord.TextStyle.paragraph, required=True
        )
        self.add_item(self.inquiry)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            forum = interaction.client.get_channel(FORUM_CHANNEL_ID)
            if not isinstance(forum, discord.ForumChannel):
                return await interaction.response.send_message(
                    "Forum channel not found.", ephemeral=True
                )

            safe_name = f"Contact-{self.user.name}".replace(" ", "-")[:100]
            role_notify = forum.guild.get_role(ROLE_CONTACT_NOTIFY)
            role_mention = role_notify.mention if role_notify else "\u200b"

            thread, starter_msg = await forum.create_thread(
                name=safe_name,
                content=role_mention,
                auto_archive_duration=1440,
                reason=f"Contact ticket created by {self.user}",
            )

            self.cog.active_tickets[self.user.id] = thread.id

            now = datetime.now().strftime("%m/%d/%Y %H:%M")
            embed_staff = discord.Embed(
                title=f"Ticket Information: {now} EST",
                description=(
                    f"**Details:** {self.inquiry.value}\n"
                    f"**User:** {self.user.mention}\n"
                    f"**Date Submitted:** {now}"
                ),
                color=0x8a7147,
            )

            view = TicketControls(self.cog, self.user)
            await starter_msg.edit(content=role_mention, embed=embed_staff, view=view)

            # DM confirmation for user
            embed_dm = discord.Embed(
                description=(
                    "Your contact request has been created. Please wait up to 24 hours for a reply "
                    "before contacting a department manager.\n\n"
                    f"{self.inquiry.value}"
                ),
                color=0x8a7147,
            )
            embed_dm.set_thumbnail(
                url="https://cdn.discordapp.com/attachments/1231290151708131379/1492345476870180936/Untitled.png?ex=69dafe88&is=69d9ad08&hm=72263ac8462f2704f65973f7367dfb37591e9bd84edbc683f2c6f27901d84412&"
            )
            try:
                await self.user.send(embed=embed_dm)
            except discord.Forbidden:
                pass

            await interaction.response.send_message(
                "Your contact has been submitted successfully.", ephemeral=True
            )

        except Exception as e:
            print(f"ContactModal error: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Something went wrong while creating your ticket.", ephemeral=True
                )


# ------------------------------
# TICKET CONTROLS
# ------------------------------
class TicketControls(discord.ui.View):
    def __init__(self, cog: ContactSystem, opener: discord.User):
        super().__init__(timeout=None)
        self.cog = cog
        self.opener = opener

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        thread = interaction.channel
        embed_thread = discord.Embed(description="This ticket has been closed.", color=0x8A8A8A)
        msg = await thread.send(content="\u200b", embed=embed_thread)
        self.cog.ignore_messages.add(msg.id)

        try:
            await self.opener.send(embed=embed_thread)
        except discord.Forbidden:
            pass

        self.cog.active_tickets.pop(self.opener.id, None)
        self.stop()

    @discord.ui.button(label="Elevate Contact", style=discord.ButtonStyle.secondary)
    async def elevate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            ephemeral=True, view=ElevateDropdown(self.cog, self.opener)
        )


class ElevateDropdown(discord.ui.View):
    def __init__(self, cog: ContactSystem, opener: discord.User):
        super().__init__(timeout=60)
        self.cog = cog
        self.opener = opener

        select = discord.ui.Select(
            placeholder="Select elevation level",
            options=[
                discord.SelectOption(label="Department Administration", value="high"),
                discord.SelectOption(label="Department Executive", value="admin"),
                discord.SelectOption(label="Server Management", value="server"),
            ],
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        choice = interaction.data["values"][0]

        if choice == "high":
            role_ping, text_name = f"<@&{ROLE_HIGH_COMMAND}>", "High Command"
        elif choice == "admin":
            role_ping, text_name = f"<@&{ROLE_DA}>", "Department Administration"
        else:
            role_ping, text_name = f"<@&{ROLE_MANAGEMENT}>", "Server Management"

        embed_thread = discord.Embed(
            description=f"This ticket has been elevated to {role_ping}.", color=0x8A8A8A
        )
        msg = await interaction.channel.send(content="\u200b", embed=embed_thread)
        self.cog.ignore_messages.add(msg.id)

        embed_user = discord.Embed(description=f"Your ticket has been elevated to {text_name}.", color=0x8A8A8A)
        try:
            await self.opener.send(embed=embed_user)
        except discord.Forbidden:
            pass

        await interaction.response.edit_message(view=None)


# ------------------------------
# SETUP
# ------------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(ContactSystem(bot))
