import os
import re
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import httpx


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MARKETPLACE_API_URL = os.getenv("MARKETPLACE_API_URL")
MARKETPLACE_API_KEY = os.getenv("MARKETPLACE_API_KEY")

if not DISCORD_TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is missing from .env"
    )

if not MARKETPLACE_API_URL:
    raise RuntimeError(
        "MARKETPLACE_API_URL is missing from .env"
    )

if not MARKETPLACE_API_KEY:
    raise RuntimeError(
        "MARKETPLACE_API_KEY is missing from .env"
    )

MARKETPLACE_API_URL = MARKETPLACE_API_URL.rstrip("/")


# ============================================================
# TEST SERVER
# ============================================================

TEST_GUILD_ID = 1543964932200996914


# ============================================================
# API CLIENT
# ============================================================

class MarketplaceAPI:

    def __init__(self):

        self.client = httpx.AsyncClient(
            base_url=MARKETPLACE_API_URL,
            headers={
                "X-API-Key": MARKETPLACE_API_KEY
            },
            timeout=httpx.Timeout(
                15.0,
                connect=10.0
            )
        )

    async def close(self):

        if not self.client.is_closed:
            await self.client.aclose()


    async def health(self):

        response = await self.client.get(
            "/api/public/bot/health"
        )

        response.raise_for_status()

        return response.json()


    async def get_config(self, server_id):

        response = await self.client.get(
            f"/api/public/bot/config/{server_id}"
        )

        if response.status_code == 404:
            return {}

        response.raise_for_status()

        data = response.json()

        if isinstance(data, dict):

            # Some APIs return:
            # {"config": {...}}
            if isinstance(data.get("config"), dict):
                return data["config"]

            return data

        return {}


    async def save_config(self, server_id, data):

        response = await self.client.put(
            f"/api/public/bot/config/{server_id}",
            json=data
        )

        response.raise_for_status()

        return response.json()


    async def patch_config(self, server_id, data):

        response = await self.client.patch(
            f"/api/public/bot/config/{server_id}",
            json=data
        )

        response.raise_for_status()

        return response.json()


    async def list_ads(self, server_id, limit=100):

        response = await self.client.get(
            "/api/public/bot/ads",
            params={
                "server_id": str(server_id),
                "limit": limit
            }
        )

        response.raise_for_status()

        data = response.json()

        if isinstance(data, dict):
            return data.get("ads", [])

        if isinstance(data, list):
            return data

        return []


    async def create_ad(self, data):

        response = await self.client.post(
            "/api/public/bot/ads",
            json=data
        )

        response.raise_for_status()

        return response.json()


    async def get_ad(self, ad_id):

        response = await self.client.get(
            f"/api/public/bot/ads/{ad_id}"
        )

        if response.status_code == 404:
            return None

        response.raise_for_status()

        return response.json()


    async def update_ad(self, ad_id, data):

        response = await self.client.patch(
            f"/api/public/bot/ads/{ad_id}",
            json=data
        )

        response.raise_for_status()

        return response.json()


    async def complete_ad(self, ad_id):

        response = await self.client.post(
            f"/api/public/bot/ads/{ad_id}/complete"
        )

        response.raise_for_status()

        return response.json()


    async def delete_ad(self, ad_id):

        response = await self.client.delete(
            f"/api/public/bot/ads/{ad_id}"
        )

        response.raise_for_status()


    async def list_tickets(self, server_id):

        response = await self.client.get(
            "/api/public/bot/tickets",
            params={
                "server_id": str(server_id)
            }
        )

        response.raise_for_status()

        data = response.json()

        if isinstance(data, dict):
            return data.get("tickets", [])

        if isinstance(data, list):
            return data

        return []


    async def create_ticket(self, data):

        response = await self.client.post(
            "/api/public/bot/tickets",
            json=data
        )

        response.raise_for_status()

        return response.json()


    async def get_ticket(self, ticket_id):

        response = await self.client.get(
            f"/api/public/bot/tickets/{ticket_id}"
        )

        if response.status_code == 404:
            return None

        response.raise_for_status()

        return response.json()


    async def update_ticket(self, ticket_id, data):

        response = await self.client.patch(
            f"/api/public/bot/tickets/{ticket_id}",
            json=data
        )

        response.raise_for_status()

        return response.json()


    async def close_ticket(self, ticket_id):

        response = await self.client.post(
            f"/api/public/bot/tickets/{ticket_id}/close"
        )

        response.raise_for_status()

        return response.json()


api = MarketplaceAPI()


# ============================================================
# HELPERS
# ============================================================

def money(value):

    try:
        return f"${float(value):,.2f} USD"

    except (TypeError, ValueError):
        return str(value)


def safe_name(value):

    value = re.sub(
        r"[^a-z0-9]",
        "",
        str(value).lower()
    )

    return value[:12] or "user"


def ticket_channel_name(buyer, seller):

    return (
        f"ticket-{safe_name(buyer)}-{safe_name(seller)}"
    )[:100]


async def get_server_config(guild_id):

    try:

        return await api.get_config(
            guild_id
        )

    except Exception as e:

        print(
            f"[API] Failed to get config: {e}"
        )

        return {}


def configured_channel(guild, channel_id):

    if not channel_id:
        return "❌ Not configured"

    try:

        channel_id = int(channel_id)

    except (TypeError, ValueError):

        return "⚠️ Invalid channel ID"

    channel = guild.get_channel(
        channel_id
    )

    if channel:
        return channel.mention

    return "⚠️ Channel not found"


async def safe_error(
    interaction,
    message
):

    try:

        if interaction.response.is_done():

            await interaction.followup.send(
                message,
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                message,
                ephemeral=True
            )

    except Exception as e:

        print(
            f"[ERROR RESPONSE] {e}"
        )


# ============================================================
# AD EMBEDS
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
        f"{money(price)}"
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


def create_ad_embed_from_data(
    guild,
    ad
):

    owner_id = ad.get(
        "owner_id"
    )

    member = None

    if owner_id:

        try:

            member = guild.get_member(
                int(owner_id)
            )

        except (TypeError, ValueError):

            pass

    if ad.get("ad_type") == "WTB":

        title = "🟢  WANT TO BUY"
        color = discord.Color.green()
        action = "is looking to buy"

    else:

        title = "🔵  WANT TO SELL"
        color = discord.Color.blue()
        action = "is looking to sell"

    if member:

        author_name = str(member)
        mention = member.mention

    else:

        author_name = f"User {owner_id}"
        mention = f"<@{owner_id}>"

    embed = discord.Embed(
        title=title,
        color=color,
        timestamp=datetime.now(timezone.utc)
    )

    embed.description = (
        f"**{mention}** {action}\n\n"

        f"🏷️ **Item**\n"
        f"{ad.get('item', 'Unknown')}\n\n"

        f"💵 **Price**\n"
        f"{money(ad.get('price'))}"
    )

    if member:

        embed.set_author(
            name=author_name,
            icon_url=member.display_avatar.url
        )

    else:

        embed.set_author(
            name=author_name
        )

    image = ad.get(
        "image_url"
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
# BOT
# ============================================================

class SDBSTBot(commands.Bot):

    def __init__(self):

        intents = discord.Intents.default()

        super().__init__(
            command_prefix="!",
            intents=intents
        )

        self.views_restored = False


    async def setup_hook(self):

        guild = discord.Object(
            id=TEST_GUILD_ID
        )

        # Copy global commands to test guild.
        self.tree.copy_global_to(
            guild=guild
        )

        synced = await self.tree.sync(
            guild=guild
        )

        print(
            f"Synced {len(synced)} slash command(s) "
            f"to test server."
        )

        # IMPORTANT:
        # Do NOT call wait_until_ready() here.
        #
        # setup_hook runs BEFORE the Discord gateway
        # becomes ready. Waiting for ready here causes
        # a startup deadlock.
        #
        # Persistent views are restored from on_ready().


    async def on_ready(self):

        print(
            f"Logged in as {self.user}"
        )

        print(
            f"Bot ID: {self.user.id}"
        )

        # Test backend connection.

        try:

            health = await api.health()

            print(
                "Lovable backend: ONLINE"
            )

            print(
                f"Backend response: {health}"
            )

        except Exception as e:

            print(
                f"Lovable backend: OFFLINE ({e})"
            )

        # Restore persistent views only once.

        if not self.views_restored:

            self.views_restored = True

            await restore_persistent_views()


    async def close(self):

        print(
            "Shutting down..."
        )

        await api.close()

        await super().close()


bot = SDBSTBot()


# ============================================================
# SETUP VIEW
# ============================================================

class SetupView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=300
        )


    async def save(
        self,
        interaction,
        key,
        value
    ):

        try:

            await api.patch_config(
                interaction.guild.id,
                {
                    key: str(value)
                }
            )

            await interaction.response.send_message(
                (
                    f"✅ **"
                    f"{key.replace('_', ' ').title()}"
                    f"** updated."
                ),
                ephemeral=True
            )

        except Exception as e:

            print(
                f"[SETUP] {e}"
            )

            await safe_error(
                interaction,
                "❌ Couldn't save that setting to the backend."
            )


    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[
            discord.ChannelType.text
        ],
        placeholder="🟢 Select Buying Channel",
        custom_id="setup:buying"
    )
    async def buying_channel(
        self,
        interaction,
        select
    ):

        if not interaction.user.guild_permissions.administrator:

            await safe_error(
                interaction,
                "❌ Administrator permissions required."
            )

            return

        await self.save(
            interaction,
            "buying_channel_id",
            select.values[0].id
        )


    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[
            discord.ChannelType.text
        ],
        placeholder="🔵 Select Selling Channel",
        custom_id="setup:selling"
    )
    async def selling_channel(
        self,
        interaction,
        select
    ):

        if not interaction.user.guild_permissions.administrator:

            await safe_error(
                interaction,
                "❌ Administrator permissions required."
            )

            return

        await self.save(
            interaction,
            "selling_channel_id",
            select.values[0].id
        )


    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[
            discord.ChannelType.category
        ],
        placeholder="🎫 Select Ticket Category",
        custom_id="setup:tickets"
    )
    async def ticket_category(
        self,
        interaction,
        select
    ):

        if not interaction.user.guild_permissions.administrator:

            await safe_error(
                interaction,
                "❌ Administrator permissions required."
            )

            return

        await self.save(
            interaction,
            "ticket_category_id",
            select.values[0].id
        )


    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[
            discord.ChannelType.text
        ],
        placeholder="🤝 Select MM Channel",
        custom_id="setup:mm"
    )
    async def mm_channel(
        self,
        interaction,
        select
    ):

        if not interaction.user.guild_permissions.administrator:

            await safe_error(
                interaction,
                "❌ Administrator permissions required."
            )

            return

        await self.save(
            interaction,
            "mm_channel_id",
            select.values[0].id
        )


# ============================================================
# /SETUP
# ============================================================

@bot.tree.command(
    name="setup",
    description="Configure SDBST Marketplace."
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def setup(
    interaction: discord.Interaction
):

    if interaction.guild is None:

        await interaction.response.send_message(
            "❌ This command must be used inside a server.",
            ephemeral=True
        )

        return

    await interaction.response.defer(
        ephemeral=True
    )

    server_config = await get_server_config(
        interaction.guild.id
    )

    buying_ch = configured_channel(
        interaction.guild,
        server_config.get(
            "buying_channel_id"
        )
    )

    selling_ch = configured_channel(
        interaction.guild,
        server_config.get(
            "selling_channel_id"
        )
    )

    ticket_cat = configured_channel(
        interaction.guild,
        server_config.get(
            "ticket_category_id"
        )
    )

    mm_ch = configured_channel(
        interaction.guild,
        server_config.get(
            "mm_channel_id"
        )
    )

    embed = discord.Embed(
        title="⚙️ SDBST Marketplace Setup",
        description=(
            "Use the selectors below to configure "
            "your marketplace.\n\n"

            f"🟢 **Buying Channel:** "
            f"{buying_ch}\n"

            f"🔵 **Selling Channel:** "
            f"{selling_ch}\n"

            f"🎫 **Ticket Category:** "
            f"{ticket_cat}\n"

            f"🤝 **MM Channel:** "
            f"{mm_ch}"
        ),
        color=discord.Color.blurple()
    )

    embed.set_footer(
        text=(
            "Only server administrators "
            "can configure the bot."
        )
    )

    await interaction.followup.send(
        embed=embed,
        view=SetupView(),
        ephemeral=True
    )


# ============================================================
# EDIT AD MODAL
# ============================================================

class EditAdModal(discord.ui.Modal):

    def __init__(self, ad):

        super().__init__(
            title="✏️ Edit Advertisement"
        )

        self.ad = ad

        self.item_input = discord.ui.TextInput(
            label="Item",
            default=str(
                ad.get("item", "")
            ),
            max_length=100,
            required=True
        )

        self.price_input = discord.ui.TextInput(
            label="Price (USD)",
            default=str(
                ad.get("price", "")
            ),
            max_length=20,
            required=True
        )

        self.image_input = discord.ui.TextInput(
            label="Image URL (optional)",
            default=str(
                ad.get("image_url") or ""
            ),
            required=False
        )

        self.add_item(
            self.item_input
        )

        self.add_item(
            self.price_input
        )

        self.add_item(
            self.image_input
        )


    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        try:

            price = float(
                self.price_input.value
            )

            if price <= 0:
                raise ValueError

        except ValueError:

            await interaction.response.send_message(
                (
                    "❌ Price must be a valid "
                    "number greater than $0."
                ),
                ephemeral=True
            )

            return

        item = self.item_input.value.strip()

        image = self.image_input.value.strip()

        data = {
            "item": item,
            "price": str(price),
            "image_url": image or None
        }

        try:

            await api.update_ad(
                self.ad["ad_id"],
                data
            )

            channel = interaction.guild.get_channel(
                int(self.ad["channel_id"])
            )

            if channel:

                try:

                    message = await channel.fetch_message(
                        int(self.ad["message_id"])
                    )

                    updated_ad = dict(
                        self.ad
                    )

                    updated_ad.update(
                        data
                    )

                    embed = create_ad_embed_from_data(
                        interaction.guild,
                        updated_ad
                    )

                    await message.edit(
                        embed=embed,
                        view=AdButtons(
                            updated_ad
                        )
                    )

                except discord.NotFound:

                    pass

            await interaction.response.send_message(
                "✅ Advertisement updated.",
                ephemeral=True
            )

        except Exception as e:

            print(
                f"[EDIT] {e}"
            )

            await safe_error(
                interaction,
                "❌ Failed to update the advertisement."
            )


# ============================================================
# AD BUTTONS
# ============================================================

class AdButtons(discord.ui.View):

    def __init__(self, ad):

        super().__init__(
            timeout=None
        )

        self.ad = ad


    # ========================================================
    # OFFER
    # ========================================================

    @discord.ui.button(
        label="Offer",
        emoji="🟢",
        style=discord.ButtonStyle.success,
        custom_id="ad:offer"
    )
    async def offer(
        self,
        interaction,
        button
    ):

        guild = interaction.guild

        if guild is None:

            await safe_error(
                interaction,
                "❌ This can only be used inside a server."
            )

            return

        try:

            owner_id = int(
                self.ad["owner_id"]
            )

        except (TypeError, ValueError, KeyError):

            await safe_error(
                interaction,
                "❌ This advertisement has invalid owner data."
            )

            return

        if interaction.user.id == owner_id:

            await safe_error(
                interaction,
                "❌ You can't offer on your own ad."
            )

            return

        config = await get_server_config(
            guild.id
        )

        category_id = config.get(
            "ticket_category_id"
        )

        if not category_id:

            await safe_error(
                interaction,
                (
                    "❌ Tickets aren't configured. "
                    "Ask an administrator to run `/setup`."
                )
            )

            return

        try:

            category_id = int(
                category_id
            )

        except (TypeError, ValueError):

            await safe_error(
                interaction,
                "❌ Ticket category configuration is invalid."
            )

            return

        category = guild.get_channel(
            category_id
        )

        if not isinstance(
            category,
            discord.CategoryChannel
        ):

            await safe_error(
                interaction,
                (
                    "❌ The configured ticket "
                    "category doesn't exist."
                )
            )

            return

        try:

            seller = await guild.fetch_member(
                owner_id
            )

        except discord.NotFound:

            await safe_error(
                interaction,
                "❌ I couldn't find the ad owner."
            )

            return

        except discord.HTTPException as e:

            print(
                f"[FETCH SELLER] {e}"
            )

            await safe_error(
                interaction,
                "❌ Discord couldn't find the ad owner."
            )

            return

        # ----------------------------------------------------
        # Duplicate ticket check
        # ----------------------------------------------------

        try:

            tickets = await api.list_tickets(
                guild.id
            )

            for ticket in tickets:

                if ticket.get("status") != "open":
                    continue

                buyer = str(
                    ticket.get("buyer_id")
                )

                seller_db = str(
                    ticket.get("seller_id")
                )

                if (
                    buyer == str(interaction.user.id)
                    and seller_db == str(owner_id)
                ):

                    existing_channel_id = ticket.get(
                        "channel_id"
                    )

                    if existing_channel_id:

                        try:

                            existing = guild.get_channel(
                                int(existing_channel_id)
                            )

                        except (
                            TypeError,
                            ValueError
                        ):

                            existing = None

                        if existing:

                            await safe_error(
                                interaction,
                                (
                                    "❌ You already have "
                                    f"a ticket: {existing.mention}"
                                )
                            )

                            return

        except Exception as e:

            print(
                f"[TICKET CHECK] {e}"
            )

        # ----------------------------------------------------
        # Create Discord ticket
        # ----------------------------------------------------

        ticket_name = ticket_channel_name(
            interaction.user,
            seller
        )

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

        try:

            ticket_channel = await guild.create_text_channel(
                name=ticket_name,
                category=category,
                overwrites=overwrites,
                topic=(
                    f"SDBST Trade • "
                    f"{self.ad.get('item')} • "
                    f"{money(self.ad.get('price'))}"
                )
            )

        except discord.Forbidden:

            await safe_error(
                interaction,
                (
                    "❌ I don't have permission "
                    "to create ticket channels."
                )
            )

            return

        except discord.HTTPException as e:

            print(
                f"[CHANNEL CREATE] {e}"
            )

            await safe_error(
                interaction,
                "❌ Discord failed to create the ticket."
            )

            return

        # ----------------------------------------------------
        # Save ticket to backend
        # ----------------------------------------------------

        ticket_data = {

            "server_id":
                str(guild.id),

            "ad_id":
                str(self.ad["ad_id"]),

            "channel_id":
                str(ticket_channel.id),

            "buyer_id":
                str(interaction.user.id),

            "seller_id":
                str(owner_id)
        }

        try:

            ticket_record = await api.create_ticket(
                ticket_data
            )

        except Exception as e:

            print(
                f"[TICKET API] {e}"
            )

            try:

                await ticket_channel.delete(
                    reason=(
                        "Backend ticket creation failed"
                    )
                )

            except Exception:
                pass

            await safe_error(
                interaction,
                (
                    "❌ The ticket couldn't be "
                    "saved to the backend. "
                    "Please try again."
                )
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
                f"{self.ad.get('item')}\n\n"

                f"💵 **Price**\n"
                f"{money(self.ad.get('price'))}"
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.set_footer(
            text="SDBST Marketplace • Trade safely"
        )

        try:

            await ticket_channel.send(
                content=(
                    f"{seller.mention} "
                    f"{interaction.user.mention}\n\n"
                    f"🎫 **Trade ticket created!**"
                ),
                embed=embed,
                view=TicketButtons(
                    ticket_record
                )
            )

        except Exception as e:

            print(
                f"[TICKET MESSAGE] {e}"
            )

        await interaction.response.send_message(
            (
                f"✅ Your ticket has been created: "
                f"{ticket_channel.mention}"
            ),
            ephemeral=True
        )


    # ========================================================
    # MARK DONE
    # ========================================================

    @discord.ui.button(
        label="Mark Done",
        emoji="✅",
        style=discord.ButtonStyle.secondary,
        custom_id="ad:done"
    )
    async def mark_done(
        self,
        interaction,
        button
    ):

        try:

            owner_id = int(
                self.ad["owner_id"]
            )

        except (TypeError, ValueError, KeyError):

            await safe_error(
                interaction,
                "❌ Invalid advertisement owner."
            )

            return

        if interaction.user.id != owner_id:

            await safe_error(
                interaction,
                (
                    "❌ Only the person who created "
                    "this ad can mark it as done."
                )
            )

            return

        await interaction.response.send_message(
            (
                "✅ Marking advertisement "
                "as completed..."
            ),
            ephemeral=True
        )

        try:

            await api.complete_ad(
                self.ad["ad_id"]
            )

        except Exception as e:

            print(
                f"[COMPLETE AD] {e}"
            )

        try:

            await interaction.message.delete()

        except Exception as e:

            print(
                f"[DELETE AD MESSAGE] {e}"
            )


    # ========================================================
    # EDIT
    # ========================================================

    @discord.ui.button(
        label="Edit Ad",
        emoji="✏️",
        style=discord.ButtonStyle.primary,
        custom_id="ad:edit"
    )
    async def edit_ad(
        self,
        interaction,
        button
    ):

        try:

            owner_id = int(
                self.ad["owner_id"]
            )

        except (TypeError, ValueError, KeyError):

            await safe_error(
                interaction,
                "❌ Invalid advertisement owner."
            )

            return

        if interaction.user.id != owner_id:

            await safe_error(
                interaction,
                (
                    "❌ Only the person who created "
                    "this ad can edit it."
                )
            )

            return

        await interaction.response.send_modal(
            EditAdModal(
                self.ad
            )
        )


# ============================================================
# TICKET BUTTONS
# ============================================================

class TicketButtons(discord.ui.View):

    def __init__(self, ticket):

        super().__init__(
            timeout=None
        )

        self.ticket = ticket


    # ========================================================
    # CLOSE
    # ========================================================

    @discord.ui.button(
        label="Close Ticket",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="ticket:close"
    )
    async def close_ticket(
        self,
        interaction,
        button
    ):

        try:

            buyer_id = int(
                self.ticket["buyer_id"]
            )

            seller_id = int(
                self.ticket["seller_id"]
            )

        except (TypeError, ValueError, KeyError):

            await safe_error(
                interaction,
                "❌ Invalid ticket data."
            )

            return

        if interaction.user.id not in {
            buyer_id,
            seller_id
        }:

            await safe_error(
                interaction,
                "❌ You aren't part of this ticket."
            )

            return

        await interaction.response.send_message(
            "🔒 Closing ticket...",
            ephemeral=True
        )

        try:

            await api.close_ticket(
                self.ticket["ticket_id"]
            )

        except Exception as e:

            print(
                f"[CLOSE TICKET API] {e}"
            )

        try:

            await interaction.channel.delete(
                reason=(
                    f"Ticket closed by "
                    f"{interaction.user}"
                )
            )

        except discord.Forbidden:

            print(
                "[CLOSE TICKET] "
                "Bot cannot delete ticket channel."
            )

        except discord.HTTPException as e:

            print(
                f"[CLOSE TICKET DELETE] {e}"
            )


    # ========================================================
    # REQUEST MM
    # ========================================================

    @discord.ui.button(
        label="Request MM",
        emoji="🤝",
        style=discord.ButtonStyle.primary,
        custom_id="ticket:mm"
    )
    async def request_mm(
        self,
        interaction,
        button
    ):

        if interaction.guild is None:

            await safe_error(
                interaction,
                "❌ This can only be used inside a server."
            )

            return

        config = await get_server_config(
            interaction.guild.id
        )

        mm_channel_id = config.get(
            "mm_channel_id"
        )

        if not mm_channel_id:

            await safe_error(
                interaction,
                (
                    "❌ MM channel hasn't "
                    "been configured yet."
                )
            )

            return

        try:

            mm_channel = interaction.guild.get_channel(
                int(mm_channel_id)
            )

        except (TypeError, ValueError):

            mm_channel = None

        if not mm_channel:

            await safe_error(
                interaction,
                (
                    "❌ The configured MM channel "
                    "couldn't be found."
                )
            )

            return

        await interaction.response.send_message(
            (
                f"🤝 **Middleman Request**\n\n"
                f"Please go to "
                f"{mm_channel.mention} "
                f"and request a middleman there."
            ),
            ephemeral=True
        )


# ============================================================
# WTB / WTS MODAL
# ============================================================

class AdModal(discord.ui.Modal):

    def __init__(
        self,
        ad_type
    ):

        super().__init__(
            title=(
                "🟢 Want To Buy"
                if ad_type == "WTB"
                else
                "🔵 Want To Sell"
            )
        )

        self.ad_type = ad_type

        self.item_input = discord.ui.TextInput(
            label="Item",
            placeholder="Example: Dark Matter Katana",
            max_length=100,
            required=True
        )

        self.price_input = discord.ui.TextInput(
            label="Price (USD)",
            placeholder="Example: 15.50",
            max_length=20,
            required=True
        )

        self.image_input = discord.ui.TextInput(
            label="Image URL (optional)",
            placeholder="https://...",
            required=False
        )

        self.add_item(
            self.item_input
        )

        self.add_item(
            self.price_input
        )

        self.add_item(
            self.image_input
        )


    async def on_submit(
        self,
        interaction
    ):

        try:

            price = float(
                self.price_input.value
            )

            if price <= 0:
                raise ValueError

        except ValueError:

            await interaction.response.send_message(
                (
                    "❌ Enter a valid price "
                    "greater than $0."
                ),
                ephemeral=True
            )

            return

        await interaction.response.defer(
            ephemeral=True
        )

        if interaction.guild is None:

            await interaction.followup.send(
                (
                    "❌ This command must be "
                    "used inside a server."
                ),
                ephemeral=True
            )

            return

        config = await get_server_config(
            interaction.guild.id
        )

        if self.ad_type == "WTB":

            channel_id = config.get(
                "buying_channel_id"
            )

        else:

            channel_id = config.get(
                "selling_channel_id"
            )

        if not channel_id:

            await interaction.followup.send(
                (
                    "❌ This marketplace channel "
                    "isn't configured.\n"
                    "Ask an administrator to "
                    "run `/setup`."
                ),
                ephemeral=True
            )

            return

        try:

            channel = interaction.guild.get_channel(
                int(channel_id)
            )

        except (TypeError, ValueError):

            channel = None

        if not channel:

            await interaction.followup.send(
                (
                    "❌ The configured marketplace "
                    "channel couldn't be found."
                ),
                ephemeral=True
            )

            return

        item = self.item_input.value.strip()

        image = self.image_input.value.strip()

        embed = create_ad_embed(
            interaction,
            item,
            price,
            self.ad_type,
            image or None
        )

        # ----------------------------------------------------
        # Send message first so we get its Discord ID.
        # ----------------------------------------------------

        try:

            message = await channel.send(
                embed=embed
            )

        except discord.Forbidden:

            await interaction.followup.send(
                (
                    "❌ I don't have permission "
                    "to send messages in that channel."
                ),
                ephemeral=True
            )

            return

        except discord.HTTPException as e:

            print(
                f"[AD MESSAGE] {e}"
            )

            await interaction.followup.send(
                "❌ Discord failed to post the advertisement.",
                ephemeral=True
            )

            return

        # ----------------------------------------------------
        # Save ad to backend.
        # ----------------------------------------------------

        try:

            ad_record = await api.create_ad(
                {

                    "server_id":
                        str(interaction.guild.id),

                    "owner_id":
                        str(interaction.user.id),

                    "ad_type":
                        self.ad_type,

                    "item":
                        item,

                    "price":
                        str(price),

                    "message_id":
                        str(message.id),

                    "channel_id":
                        str(channel.id),

                    "image_url":
                        image or None
                }
            )

        except Exception as e:

            print(
                f"[CREATE AD API] {e}"
            )

            try:

                await message.delete()

            except Exception:
                pass

            await interaction.followup.send(
                (
                    "❌ The advertisement couldn't "
                    "be saved to the backend."
                ),
                ephemeral=True
            )

            return

        # ----------------------------------------------------
        # Attach persistent buttons.
        # ----------------------------------------------------

        try:

            await message.edit(
                view=AdButtons(
                    ad_record
                )
            )

        except Exception as e:

            print(
                f"[AD BUTTONS] {e}"
            )

        await interaction.followup.send(
            (
                f"✅ Your **{self.ad_type}** ad "
                f"was posted in {channel.mention}."
            ),
            ephemeral=True
        )


# ============================================================
# /WTB
# ============================================================

@bot.tree.command(
    name="wtb",
    description="Create a Want To Buy advertisement."
)
async def wtb(
    interaction: discord.Interaction
):

    await interaction.response.send_modal(
        AdModal("WTB")
    )


# ============================================================
# /WTS
# ============================================================

@bot.tree.command(
    name="wts",
    description="Create a Want To Sell advertisement."
)
async def wts(
    interaction: discord.Interaction
):

    await interaction.response.send_modal(
        AdModal("WTS")
    )


# ============================================================
# RESTORE PERSISTENT VIEWS
# ============================================================

async def restore_persistent_views():

    guild = bot.get_guild(
        TEST_GUILD_ID
    )

    if guild is None:

        print(
            "[RESTORE] Test guild not found."
        )

        return

    # --------------------------------------------------------
    # Restore advertisements
    # --------------------------------------------------------

    try:

        ads = await api.list_ads(
            guild.id,
            limit=100
        )

        restored_ads = 0

        for ad in ads:

            if ad.get("status") == "completed":
                continue

            channel_id = ad.get(
                "channel_id"
            )

            message_id = ad.get(
                "message_id"
            )

            if not channel_id or not message_id:
                continue

            try:

                channel = guild.get_channel(
                    int(channel_id)
                )

                if channel is None:
                    continue

                message = await channel.fetch_message(
                    int(message_id)
                )

                bot.add_view(
                    AdButtons(ad),
                    message_id=message.id
                )

                restored_ads += 1

            except discord.NotFound:

                print(
                    f"[RESTORE AD] Message "
                    f"{message_id} no longer exists."
                )

            except Exception as e:

                print(
                    f"[RESTORE AD] {e}"
                )

        print(
            f"Restored {restored_ads} "
            f"persistent ad view(s)."
        )

    except Exception as e:

        print(
            f"[RESTORE ADS] {e}"
        )


    # --------------------------------------------------------
    # Restore tickets
    # --------------------------------------------------------

    try:

        tickets = await api.list_tickets(
            guild.id
        )

        restored_tickets = 0

        for ticket in tickets:

            if ticket.get("status") == "closed":
                continue

            channel_id = ticket.get(
                "channel_id"
            )

            ticket_id = ticket.get(
                "ticket_id"
            )

            if not channel_id or not ticket_id:
                continue

            try:

                channel = guild.get_channel(
                    int(channel_id)
                )

            except (TypeError, ValueError):

                channel = None

            if channel is None:
                continue

            try:

                async for message in channel.history(
                    limit=20
                ):

                    if message.author.id != bot.user.id:
                        continue

                    bot.add_view(
                        TicketButtons(ticket),
                        message_id=message.id
                    )

                    restored_tickets += 1

                    break

            except Exception as e:

                print(
                    f"[RESTORE TICKET] {e}"
                )

        print(
            f"Restored {restored_tickets} "
            f"persistent ticket view(s)."
        )

    except Exception as e:

        print(
            f"[RESTORE TICKETS] {e}"
        )


# ============================================================
# COMMAND ERROR HANDLER
# ============================================================

@bot.tree.error
async def on_app_command_error(
    interaction,
    error
):

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        await safe_error(
            interaction,
            (
                "❌ You need administrator "
                "permissions to use this command."
            )
        )

        return

    print(
        f"[COMMAND ERROR] {repr(error)}"
    )

    await safe_error(
        interaction,
        (
            "❌ Something went wrong "
            "while running that command."
        )
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    print(
        "============================================"
    )

    print(
        "SDBST Marketplace Bot starting..."
    )

    print(
        "============================================"
    )

    try:

        bot.run(
            DISCORD_TOKEN
        )

    except KeyboardInterrupt:

        print(
            "Bot stopped."
        )

    except Exception as e:

        print(
            f"[FATAL] {repr(e)}"
        )

    finally:

        print(
            "Bot shutdown complete."
        )
