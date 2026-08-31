import os
import json
import re
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is missing from your .env file."
    )


# ============================================================
# TEST SERVER
# ============================================================

TEST_GUILD_ID = 1543964932200996914

CONFIG_FILE = "config.json"


# ============================================================
# CONFIG SYSTEM
# ============================================================

def load_config():

    if not os.path.exists(CONFIG_FILE):
        return {}

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            return json.load(file)

    except (json.JSONDecodeError, OSError):
        return {}


def save_config(config):

    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=4)


config = load_config()


# ============================================================
# BOT
# ============================================================

class SDBSTBot(commands.Bot):

    def __init__(self):

        intents = discord.Intents.default()

        super().__init__(
            command_prefix="!",
            intents=intents
        )

    async def setup_hook(self):

        guild = discord.Object(id=TEST_GUILD_ID)

        # Copy our commands to the test server.
        self.tree.copy_global_to(guild=guild)

        synced = await self.tree.sync(guild=guild)

        print(
            f"Synced {len(synced)} slash command(s) "
            f"to test server."
        )

    async def on_ready(self):

        print(f"Logged in as {self.user}")
        print(f"Bot ID: {self.user.id}")


bot = SDBSTBot()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_server_config(guild_id):

    guild_id = str(guild_id)

    if guild_id not in config:
        config[guild_id] = {}

    return config[guild_id]


def channel_mention(guild, channel_id):

    if not channel_id:
        return "❌ Not configured"

    channel = guild.get_channel(channel_id)

    if channel:
        return channel.mention

    return "⚠️ Channel not found"


def safe_channel_name(user1, user2):

    name1 = re.sub(
        r"[^a-z0-9]",
        "",
        user1.name.lower()
    )[:12]

    name2 = re.sub(
        r"[^a-z0-9]",
        "",
        user2.name.lower()
    )[:12]

    return f"ticket-{name1}-{name2}"[:100]


# ============================================================
# AD EMBED
# ============================================================

def create_ad_embed(
    interaction,
    item,
    price,
    ad_type,
    image=None
):

    if ad_type == "WTB":

        title = "🟢  WANT TO BUY"
        color = discord.Color.green()
        action = "is looking to buy"

    else:

        title = "🔵  WANT TO SELL"
        color = discord.Color.blue()
        action = "is looking to sell"

    embed = discord.Embed(
        title=title,
        color=color,
        timestamp=datetime.now(timezone.utc)
    )

    embed.description = (
        f"**{interaction.user.mention}** "
        f"{action}\n\n"

        f"🏷️ **Item**\n"
        f"{item}\n\n"

        f"💵 **Price**\n"
        f"${price:,.2f} USD"
    )

    embed.set_author(
        name=str(interaction.user),
        icon_url=interaction.user.display_avatar.url
    )

    if image:

        embed.set_image(
            url=image
        )

    embed.set_footer(
        text=(
            "SDBST Marketplace • "
            "Use the buttons below to interact"
        )
    )

    return embed


# ============================================================
# SETUP COMMAND
# ============================================================

@bot.tree.command(
    name="setup",
    description="Configure SDBST Marketplace for this server."
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def setup(
    interaction: discord.Interaction
):

    guild = interaction.guild

    if guild is None:
        await interaction.response.send_message(
            "❌ This command must be used inside a server.",
            ephemeral=True
        )
        return

    server_config = get_server_config(
        guild.id
    )

    buying_id = server_config.get(
        "buying_channel"
    )

    selling_id = server_config.get(
        "selling_channel"
    )

    ticket_id = server_config.get(
        "ticket_category"
    )

    mm_id = server_config.get(
        "mm_channel"
    )

    embed = discord.Embed(
        title="⚙️ SDBST Marketplace Setup",
        description=(
            "Configure the marketplace using "
            "the selectors below.\n\n"

            f"🟢 **Buying Channel:** "
            f"{channel_mention(guild, buying_id)}\n"

            f"🔵 **Selling Channel:** "
            f"{channel_mention(guild, selling_id)}\n"

            f"🎫 **Ticket Category:** "
            f"{channel_mention(guild, ticket_id)}\n"

            f"🤝 **MM Channel:** "
            f"{channel_mention(guild, mm_id)}"
        ),
        color=discord.Color.blurple()
    )

    embed.set_footer(
        text=(
            "Only server administrators "
            "can change these settings."
        )
    )

    await interaction.response.send_message(
        embed=embed,
        view=SetupView(),
        ephemeral=True
    )


# ============================================================
# SETUP VIEW
# ============================================================

class SetupView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=300
        )


    # --------------------------------------------------------
    # BUYING CHANNEL
    # --------------------------------------------------------

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[
            discord.ChannelType.text
        ],
        placeholder="🟢 Select the Buying Channel",
        custom_id="setup:buying"
    )
    async def buying_channel(
        self,
        interaction,
        select
    ):

        if not interaction.user.guild_permissions.administrator:

            await interaction.response.send_message(
                "❌ Administrator permissions required.",
                ephemeral=True
            )

            return

        channel = select.values[0]

        server_config = get_server_config(
            interaction.guild.id
        )

        server_config[
            "buying_channel"
        ] = channel.id

        save_config(config)

        await interaction.response.send_message(
            f"🟢 Buying channel set to "
            f"{channel.mention}.",
            ephemeral=True
        )


    # --------------------------------------------------------
    # SELLING CHANNEL
    # --------------------------------------------------------

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[
            discord.ChannelType.text
        ],
        placeholder="🔵 Select the Selling Channel",
        custom_id="setup:selling"
    )
    async def selling_channel(
        self,
        interaction,
        select
    ):

        if not interaction.user.guild_permissions.administrator:

            await interaction.response.send_message(
                "❌ Administrator permissions required.",
                ephemeral=True
            )

            return

        channel = select.values[0]

        server_config = get_server_config(
            interaction.guild.id
        )

        server_config[
            "selling_channel"
        ] = channel.id

        save_config(config)

        await interaction.response.send_message(
            f"🔵 Selling channel set to "
            f"{channel.mention}.",
            ephemeral=True
        )


    # --------------------------------------------------------
    # TICKET CATEGORY
    # --------------------------------------------------------

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[
            discord.ChannelType.category
        ],
        placeholder="🎫 Select the Ticket Category",
        custom_id="setup:tickets"
    )
    async def ticket_category(
        self,
        interaction,
        select
    ):

        if not interaction.user.guild_permissions.administrator:

            await interaction.response.send_message(
                "❌ Administrator permissions required.",
                ephemeral=True
            )

            return

        category = select.values[0]

        server_config = get_server_config(
            interaction.guild.id
        )

        server_config[
            "ticket_category"
        ] = category.id

        save_config(config)

        await interaction.response.send_message(
            f"🎫 Ticket category set to "
            f"**{category.name}**.",
            ephemeral=True
        )


    # --------------------------------------------------------
    # MM CHANNEL
    # --------------------------------------------------------

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[
            discord.ChannelType.text
        ],
        placeholder="🤝 Select the MM Channel",
        custom_id="setup:mm"
    )
    async def mm_channel(
        self,
        interaction,
        select
    ):

        if not interaction.user.guild_permissions.administrator:

            await interaction.response.send_message(
                "❌ Administrator permissions required.",
                ephemeral=True
            )

            return

        channel = select.values[0]

        server_config = get_server_config(
            interaction.guild.id
        )

        server_config[
            "mm_channel"
        ] = channel.id

        save_config(config)

        await interaction.response.send_message(
            f"🤝 MM channel set to "
            f"{channel.mention}.",
            ephemeral=True
        )


# ============================================================
# AD BUTTONS
# ============================================================

class AdButtons(discord.ui.View):

    def __init__(
        self,
        seller_id,
        item,
        price
    ):

        super().__init__(
            timeout=None
        )

        self.seller_id = seller_id
        self.item = item
        self.price = price


    # ========================================================
    # OFFER
    # ========================================================

    @discord.ui.button(
        label="Offer",
        emoji="🟢",
        style=discord.ButtonStyle.success
    )
    async def offer(
        self,
        interaction,
        button
    ):

        guild = interaction.guild

        if guild is None:

            await interaction.response.send_message(
                "❌ This can only be used inside a server.",
                ephemeral=True
            )

            return


        # ----------------------------------------------------
        # Prevent seller from offering on own ad
        # ----------------------------------------------------

        if interaction.user.id == self.seller_id:

            await interaction.response.send_message(
                "❌ You can't offer on your own ad.",
                ephemeral=True
            )

            return


        server_config = get_server_config(
            guild.id
        )

        ticket_category_id = server_config.get(
            "ticket_category"
        )

        if not ticket_category_id:

            await interaction.response.send_message(
                "❌ Tickets aren't configured yet. "
                "An administrator needs to run `/setup`.",
                ephemeral=True
            )

            return


        category = guild.get_channel(
            ticket_category_id
        )

        if not isinstance(
            category,
            discord.CategoryChannel
        ):

            await interaction.response.send_message(
                "❌ The configured ticket category "
                "is invalid.",
                ephemeral=True
            )

            return


        # ----------------------------------------------------
        # Fetch seller directly from Discord
        # ----------------------------------------------------

        try:

            seller = await guild.fetch_member(
                self.seller_id
            )

        except discord.NotFound:

            await interaction.response.send_message(
                "❌ I couldn't find the ad owner.",
                ephemeral=True
            )

            return


        # ----------------------------------------------------
        # Ticket name
        # ----------------------------------------------------

        ticket_name = safe_channel_name(
            seller,
            interaction.user
        )


        # ----------------------------------------------------
        # Prevent duplicate ticket
        # ----------------------------------------------------

        for channel in category.channels:

            if channel.name == ticket_name:

                await interaction.response.send_message(
                    f"❌ You already have a ticket: "
                    f"{channel.mention}",
                    ephemeral=True
                )

                return


        # ----------------------------------------------------
        # Ticket permissions
        # ----------------------------------------------------

        overwrites = {

            guild.default_role:
                discord.PermissionOverwrite(
                    view_channel=False
                ),

            seller:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                ),

            interaction.user:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                ),

            guild.me:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_channels=True
                )
        }


        # ----------------------------------------------------
        # Create ticket
        # ----------------------------------------------------

        try:

            ticket = await guild.create_text_channel(
                name=ticket_name,
                category=category,
                overwrites=overwrites,
                topic=(
                    f"SDBST ticket • "
                    f"{self.item} • "
                    f"${self.price:,.2f}"
                )
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ I don't have permission to create "
                "ticket channels.",
                ephemeral=True
            )

            return


        # ----------------------------------------------------
        # Ticket embed
        # ----------------------------------------------------

        embed = discord.Embed(
            title="🎫 SDBST Trade Ticket",
            description=(

                f"**Buyer:** "
                f"{interaction.user.mention}\n"

                f"**Seller:** "
                f"{seller.mention}\n\n"

                f"🏷️ **Item**\n"
                f"{self.item}\n\n"

                f"💵 **Price**\n"
                f"${self.price:,.2f} USD"
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.set_footer(
            text="SDBST Marketplace • Trade safely"
        )


        await ticket.send(

            content=(
                f"{seller.mention} "
                f"{interaction.user.mention}\n\n"
                f"🎫 **Trade ticket created!**"
            ),

            embed=embed,

            view=TicketButtons(
                seller_id=self.seller_id,
                buyer_id=interaction.user.id
            )
        )


        await interaction.response.send_message(
            f"✅ Your ticket has been created: "
            f"{ticket.mention}",
            ephemeral=True
        )


    # ========================================================
    # MARK DONE
    # ========================================================

    @discord.ui.button(
        label="Mark Done",
        emoji="✅",
        style=discord.ButtonStyle.secondary
    )
    async def mark_done(
        self,
        interaction,
        button
    ):

        if interaction.user.id != self.seller_id:

            await interaction.response.send_message(
                "❌ Only the person who created this ad "
                "can mark it as done.",
                ephemeral=True
            )

            return


        await interaction.response.send_message(
            "✅ Ad marked as completed. Deleting...",
            ephemeral=True
        )

        await interaction.message.delete()


    # ========================================================
    # EDIT
    # ========================================================

    @discord.ui.button(
        label="Edit Ad",
        emoji="✏️",
        style=discord.ButtonStyle.primary
    )
    async def edit_ad(
        self,
        interaction,
        button
    ):

        if interaction.user.id != self.seller_id:

            await interaction.response.send_message(
                "❌ Only the person who created this ad "
                "can edit it.",
                ephemeral=True
            )

            return


        await interaction.response.send_message(
            "✏️ Ad editing is coming next.",
            ephemeral=True
        )


# ============================================================
# TICKET BUTTONS
# ============================================================

class TicketButtons(discord.ui.View):

    def __init__(
        self,
        seller_id,
        buyer_id
    ):

        super().__init__(
            timeout=None
        )

        self.seller_id = seller_id
        self.buyer_id = buyer_id


    # ========================================================
    # CLOSE
    # ========================================================

    @discord.ui.button(
        label="Close Ticket",
        emoji="🔒",
        style=discord.ButtonStyle.danger
    )
    async def close_ticket(
        self,
        interaction,
        button
    ):

        if interaction.user.id not in {
            self.seller_id,
            self.buyer_id
        }:

            await interaction.response.send_message(
                "❌ You aren't part of this ticket.",
                ephemeral=True
            )

            return


        await interaction.response.send_message(
            "🔒 Closing ticket...",
            ephemeral=True
        )

        await interaction.channel.delete(
            reason=(
                f"Ticket closed by "
                f"{interaction.user}"
            )
        )


    # ========================================================
    # REQUEST MM
    # ========================================================

    @discord.ui.button(
        label="Request MM",
        emoji="🤝",
        style=discord.ButtonStyle.primary
    )
    async def request_mm(
        self,
        interaction,
        button
    ):

        guild_id = str(
            interaction.guild.id
        )

        server_config = config.get(
            guild_id,
            {}
        )

        mm_channel_id = server_config.get(
            "mm_channel"
        )

        if not mm_channel_id:

            await interaction.response.send_message(
                "❌ MM channel hasn't been configured yet.",
                ephemeral=True
            )

            return


        mm_channel = interaction.guild.get_channel(
            mm_channel_id
        )

        if not mm_channel:

            await interaction.response.send_message(
                "❌ The configured MM channel "
                "couldn't be found.",
                ephemeral=True
            )

            return


        await interaction.response.send_message(
            (
                f"🤝 Please go to "
                f"{mm_channel.mention} "
                f"to request a middleman."
            ),
            ephemeral=True
        )


# ============================================================
# /WTB
# ============================================================

@bot.tree.command(
    name="wtb",
    description="Create a Want To Buy ad."
)
@app_commands.describe(
    item="The item you want to buy",
    price="The price in USD",
    image="Optional image URL"
)
async def wtb(
    interaction,
    item: str,
    price: float,
    image: str | None = None
):

    if price <= 0:

        await interaction.response.send_message(
            "❌ Price must be greater than $0.",
            ephemeral=True
        )

        return


    server_config = get_server_config(
        interaction.guild.id
    )

    buying_channel_id = server_config.get(
        "buying_channel"
    )

    if not buying_channel_id:

        await interaction.response.send_message(
            (
                "❌ Buying channel hasn't been "
                "configured.\n\n"
                "Ask an administrator to run `/setup`."
            ),
            ephemeral=True
        )

        return


    channel = interaction.guild.get_channel(
        buying_channel_id
    )

    if not channel:

        await interaction.response.send_message(
            "❌ The configured buying channel "
            "couldn't be found.",
            ephemeral=True
        )

        return


    embed = create_ad_embed(
        interaction,
        item,
        price,
        "WTB",
        image
    )

    view = AdButtons(
        seller_id=interaction.user.id,
        item=item,
        price=price
    )


    await channel.send(
        embed=embed,
        view=view
    )


    await interaction.response.send_message(
        (
            f"✅ Your WTB ad was posted in "
            f"{channel.mention}."
        ),
        ephemeral=True
    )


# ============================================================
# /WTS
# ============================================================

@bot.tree.command(
    name="wts",
    description="Create a Want To Sell ad."
)
@app_commands.describe(
    item="The item you want to sell",
    price="The price in USD",
    image="Optional image URL"
)
async def wts(
    interaction,
    item: str,
    price: float,
    image: str | None = None
):

    if price <= 0:

        await interaction.response.send_message(
            "❌ Price must be greater than $0.",
            ephemeral=True
        )

        return


    server_config = get_server_config(
        interaction.guild.id
    )

    selling_channel_id = server_config.get(
        "selling_channel"
    )

    if not selling_channel_id:

        await interaction.response.send_message(
            (
                "❌ Selling channel hasn't been "
                "configured.\n\n"
                "Ask an administrator to run `/setup`."
            ),
            ephemeral=True
        )

        return


    channel = interaction.guild.get_channel(
        selling_channel_id
    )

    if not channel:

        await interaction.response.send_message(
            "❌ The configured selling channel "
            "couldn't be found.",
            ephemeral=True
        )

        return


    embed = create_ad_embed(
        interaction,
        item,
        price,
        "WTS",
        image
    )

    view = AdButtons(
        seller_id=interaction.user.id,
        item=item,
        price=price
    )


    await channel.send(
        embed=embed,
        view=view
    )


    await interaction.response.send_message(
        (
            f"✅ Your WTS ad was posted in "
            f"{channel.mention}."
        ),
        ephemeral=True
    )


# ============================================================
# RUN
# ============================================================

bot.run(TOKEN)