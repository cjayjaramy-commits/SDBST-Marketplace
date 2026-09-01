import os
import re
from datetime import datetime, timezone

import time
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

# Azo's main server
MAIN_GUILD_ID = 1470611899065565480

# Guilds that get an instant slash-command sync.
# Any guild the bot can't reach is skipped with a
# warning instead of crashing startup.
COMMAND_GUILD_IDS = (
    TEST_GUILD_ID,
    MAIN_GUILD_ID,
)


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
# AD TEXT (plain, searchable messages)
# ============================================================

NEGOTIATE_LINE = (
    "💬 You can negotiate the deal privately "
    "here in this ticket."
)


def ad_action_words(ad_type):

    if ad_type == "WTB":
        return "wants to buy"

    return "wants to sell"


def format_ad_text(
    mention,
    item,
    price,
    ad_type
):
    """
    Plain-text ad so the item name is searchable in Discord.

    Example:
        @Azo wants to buy Inverted AWP at $105.00
    """

    return (
        f"{mention} "
        f"{ad_action_words(ad_type)} "
        f"{item} at {money(price)}"
    )


def create_ad_text(
    interaction,
    item,
    price,
    ad_type
):

    return format_ad_text(
        interaction.user.mention,
        item,
        price,
        ad_type
    )


def create_ad_text_from_data(
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

    if member:
        mention = member.mention

    else:
        mention = f"<@{owner_id}>"

    return format_ad_text(
        mention,
        ad.get("item", "Unknown"),
        ad.get("price"),
        ad.get("ad_type")
    )


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

        # Copy global commands to the configured guilds
        # so slash commands update instantly there.
        #
        # A guild the bot isn't in (or was invited to
        # without the applications.commands scope) will
        # raise 403 Missing Access. That must NOT kill
        # startup, so each guild is handled separately.

        # Commands are published GLOBALLY only.
        #
        # Previously they were ALSO copied into each
        # guild, which made Discord show every command
        # twice (2x /wtb, 2x /wts, 2x /setup).
        #
        # Clear any leftover guild-scoped copies so only
        # the single global set remains.

        for guild_id in COMMAND_GUILD_IDS:

            guild = discord.Object(
                id=guild_id
            )

            try:

                self.tree.clear_commands(
                    guild=guild
                )

                await self.tree.sync(
                    guild=guild
                )

                print(
                    f"[SYNC] Cleared duplicate guild "
                    f"commands in {guild_id}."
                )

            except discord.Forbidden:

                print(
                    f"[SYNC] Missing access to guild "
                    f"{guild_id}. Skipping."
                )

            except Exception as e:

                print(
                    f"[SYNC] Cleanup failed for guild "
                    f"{guild_id}: {e}"
                )

        # Publish commands globally so ANY server the bot
        # joins gets them automatically.

        try:

            global_synced = await self.tree.sync()

            print(
                f"Synced {len(global_synced)} slash "
                f"command(s) globally."
            )

        except Exception as e:

            print(
                f"[SYNC] Global sync failed: {e}"
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
# STICKY NOTE CONFIG
# ============================================================

# Defaults used when the server hasn't written its own text.
DEFAULT_STICKY_TEXTS = {
    "buying_channel_id": (
        "📌 **/wtb** — USE THIS COMMAND TO POST BUYING ADS"
    ),
    "selling_channel_id": (
        "📌 **/wts** — USE THIS COMMAND TO POST SELLING ADS"
    ),
    "sticky_channel_id": (
        "📌 **Stickied Message:** use the marketplace "
        "commands to post your ad."
    ),
}

# Which config keys can hold a sticky channel.
STICKY_CHANNEL_KEYS = (
    "buying_channel_id",
    "selling_channel_id",
    "sticky_channel_id",
)

# Per-channel custom text keys.
STICKY_TEXT_KEYS = {
    "buying_channel_id": "sticky_text_buying",
    "selling_channel_id": "sticky_text_selling",
    "sticky_channel_id": "sticky_text_custom",
}


def sticky_enabled(config):

    value = (config or {}).get(
        "sticky_enabled",
        "true"
    )

    return str(value).strip().lower() in (
        "1",
        "true",
        "yes",
        "on"
    )


def sticky_text_for_key(config, key):

    custom = (config or {}).get(
        STICKY_TEXT_KEYS[key]
    )

    if custom and str(custom).strip():
        return str(custom).strip()

    return DEFAULT_STICKY_TEXTS[key]


def sticky_text_for_channel(config, channel_id):
    """
    Returns the sticky text for this channel,
    or None if the channel has no sticky.
    """

    if not sticky_enabled(config):
        return None

    for key in STICKY_CHANNEL_KEYS:

        raw = (config or {}).get(key)

        if not raw:
            continue

        try:

            if int(raw) == int(channel_id):
                return sticky_text_for_key(config, key)

        except (TypeError, ValueError):
            continue

    return None


# ============================================================
# SETUP VIEW
# ============================================================

def channel_default(guild, channel_id):
    """
    Turn a saved channel ID into a Discord default value
    so the selector shows what's already configured.
    """

    if not channel_id:
        return []

    try:

        channel_id = int(channel_id)

    except (TypeError, ValueError):

        return []

    channel = guild.get_channel(
        channel_id
    )

    if channel is None:
        return []

    try:

        return [
            discord.SelectDefaultValue.from_channel(
                channel
            )
        ]

    except Exception:

        return []


class ConfigChannelSelect(discord.ui.ChannelSelect):

    def __init__(
        self,
        parent,
        key,
        placeholder,
        channel_types
    ):

        self.parent_view = parent
        self.config_key = key

        super().__init__(
            placeholder=placeholder,
            channel_types=channel_types,
            min_values=1,
            max_values=1,
            default_values=channel_default(
                parent.guild,
                parent.config.get(key)
            )
        )


    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if not interaction.user.guild_permissions.administrator:

            await safe_error(
                interaction,
                "❌ Administrator permissions required."
            )

            return

        await self.parent_view.save(
            interaction,
            self.config_key,
            self.values[0].id
        )


class StickyTextModal(discord.ui.Modal):

    def __init__(self, parent, key, label):

        super().__init__(
            title="📌 Sticky Message"
        )

        self.parent_view = parent
        self.config_key = STICKY_TEXT_KEYS[key]

        self.text_input = discord.ui.TextInput(
            label=label,
            style=discord.TextStyle.paragraph,
            default=sticky_text_for_key(
                parent.config,
                key
            ),
            max_length=1800,
            required=True
        )

        self.add_item(
            self.text_input
        )


    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        await self.parent_view.save(
            interaction,
            self.config_key,
            self.text_input.value.strip()
        )


class StickyTextButton(discord.ui.Button):

    def __init__(self, parent, key, label, emoji):

        self.parent_view = parent
        self.sticky_key = key

        super().__init__(
            label=label,
            emoji=emoji,
            style=discord.ButtonStyle.secondary,
            row=2
        )


    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if not interaction.user.guild_permissions.administrator:

            await safe_error(
                interaction,
                "❌ Administrator permissions required."
            )

            return

        await interaction.response.send_modal(
            StickyTextModal(
                self.parent_view,
                self.sticky_key,
                self.label
            )
        )


class StickyToggleButton(discord.ui.Button):

    def __init__(self, parent):

        self.parent_view = parent

        on = sticky_enabled(parent.config)

        super().__init__(
            label=(
                "Sticky Notes: ON"
                if on
                else "Sticky Notes: OFF"
            ),
            emoji="📌",
            style=(
                discord.ButtonStyle.success
                if on
                else discord.ButtonStyle.danger
            ),
            row=1
        )


    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if not interaction.user.guild_permissions.administrator:

            await safe_error(
                interaction,
                "❌ Administrator permissions required."
            )

            return

        new_value = (
            "false"
            if sticky_enabled(self.parent_view.config)
            else "true"
        )

        await self.parent_view.save(
            interaction,
            "sticky_enabled",
            new_value
        )


class StickyBackButton(discord.ui.Button):

    def __init__(self, parent):

        self.parent_view = parent

        super().__init__(
            label="Back to Setup",
            emoji="⬅️",
            style=discord.ButtonStyle.primary,
            row=3
        )


    async def callback(
        self,
        interaction: discord.Interaction
    ):

        view = SetupView(
            self.parent_view.guild,
            self.parent_view.config
        )

        await interaction.response.edit_message(
            embed=view.build_embed(),
            view=view
        )


class StickyView(discord.ui.View):
    """
    Sticky note settings: enable/disable, what to say,
    and which extra channel gets one.
    """

    def __init__(self, guild, config):

        super().__init__(
            timeout=300
        )

        self.guild = guild

        self.config = dict(
            config or {}
        )

        self.add_item(
            ConfigChannelSelect(
                self,
                "sticky_channel_id",
                "📌 Extra Sticky Channel (optional)",
                [discord.ChannelType.text]
            )
        )

        self.add_item(
            StickyToggleButton(self)
        )

        self.add_item(
            StickyTextButton(
                self,
                "buying_channel_id",
                "Buying Text",
                "🟢"
            )
        )

        self.add_item(
            StickyTextButton(
                self,
                "selling_channel_id",
                "Selling Text",
                "🔵"
            )
        )

        self.add_item(
            StickyTextButton(
                self,
                "sticky_channel_id",
                "Custom Text",
                "📌"
            )
        )

        self.add_item(
            StickyBackButton(self)
        )


    def build_embed(self):

        status = (
            "🟢 Enabled"
            if sticky_enabled(self.config)
            else "🔴 Disabled"
        )

        custom_ch = configured_channel(
            self.guild,
            self.config.get("sticky_channel_id")
        )

        def preview(key):

            text = sticky_text_for_key(
                self.config,
                key
            )

            text = text.replace("\n", " ")

            if len(text) > 90:
                text = text[:87] + "..."

            return text

        embed = discord.Embed(
            title="📌 Sticky Note Settings",
            description=(
                "A sticky note is re-posted at the "
                "bottom of the channel every time "
                "someone talks, so it always stays "
                "visible under the last ad.\n\n"

                f"**Status:** {status}\n"
                f"**Buying Channel:** "
                f"{configured_channel(self.guild, self.config.get('buying_channel_id'))}\n"
                f"**Selling Channel:** "
                f"{configured_channel(self.guild, self.config.get('selling_channel_id'))}\n"
                f"**Extra Sticky Channel:** {custom_ch}\n\n"

                f"🟢 **Buying text:** {preview('buying_channel_id')}\n"
                f"🔵 **Selling text:** {preview('selling_channel_id')}\n"
                f"📌 **Custom text:** {preview('sticky_channel_id')}"
            ),
            color=discord.Color.gold()
        )

        embed.set_footer(
            text=(
                "Only server administrators "
                "can configure the bot."
            )
        )

        return embed


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

        except Exception as e:

            print(
                f"[STICKY SETUP] {e}"
            )

            await safe_error(
                interaction,
                "❌ Couldn't save that setting to the backend."
            )

            return

        self.config[key] = str(value)

        invalidate_config_cache(interaction.guild.id)

        refreshed = StickyView(
            self.guild,
            self.config
        )

        try:

            await interaction.response.edit_message(
                embed=refreshed.build_embed(),
                view=refreshed
            )

        except Exception as e:

            print(
                f"[STICKY REFRESH] {e}"
            )

            await safe_error(
                interaction,
                "✅ Sticky settings updated."
            )


class StickySettingsButton(discord.ui.Button):

    def __init__(self, parent):

        self.parent_view = parent

        super().__init__(
            label="Sticky Notes",
            emoji="📌",
            style=discord.ButtonStyle.secondary,
            row=4
        )


    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if not interaction.user.guild_permissions.administrator:

            await safe_error(
                interaction,
                "❌ Administrator permissions required."
            )

            return

        view = StickyView(
            self.parent_view.guild,
            self.parent_view.config
        )

        await interaction.response.edit_message(
            embed=view.build_embed(),
            view=view
        )


class SetupView(discord.ui.View):

    def __init__(
        self,
        guild,
        config
    ):

        super().__init__(
            timeout=300
        )

        self.guild = guild

        # Existing saved settings, so nothing feels
        # like starting from scratch.
        self.config = dict(
            config or {}
        )

        self.add_item(
            ConfigChannelSelect(
                self,
                "buying_channel_id",
                "🟢 Buying Channel",
                [discord.ChannelType.text]
            )
        )

        self.add_item(
            ConfigChannelSelect(
                self,
                "selling_channel_id",
                "🔵 Selling Channel",
                [discord.ChannelType.text]
            )
        )

        self.add_item(
            ConfigChannelSelect(
                self,
                "ticket_category_id",
                "🎫 Ticket Category",
                [discord.ChannelType.category]
            )
        )

        self.add_item(
            ConfigChannelSelect(
                self,
                "mm_channel_id",
                "🤝 Middleman Channel",
                [discord.ChannelType.text]
            )
        )

        self.add_item(
            StickySettingsButton(self)
        )


    def build_embed(self):

        return setup_embed(
            self.guild,
            self.config
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

        except Exception as e:

            print(
                f"[SETUP] {e}"
            )

            await safe_error(
                interaction,
                "❌ Couldn't save that setting to the backend."
            )

            return

        # Keep the local copy in sync and rebuild the panel
        # so the saved selections stay visible.

        self.config[key] = str(value)

        invalidate_config_cache(interaction.guild.id)

        refreshed = SetupView(
            self.guild,
            self.config
        )

        try:

            await interaction.response.edit_message(
                embed=refreshed.build_embed(),
                view=refreshed
            )

        except Exception as e:

            print(
                f"[SETUP REFRESH] {e}"
            )

            await safe_error(
                interaction,
                (
                    f"✅ **"
                    f"{key.replace('_', ' ').title()}"
                    f"** updated."
                )
            )


def setup_embed(guild, server_config):

    buying_ch = configured_channel(
        guild,
        server_config.get(
            "buying_channel_id"
        )
    )

    selling_ch = configured_channel(
        guild,
        server_config.get(
            "selling_channel_id"
        )
    )

    ticket_cat = configured_channel(
        guild,
        server_config.get(
            "ticket_category_id"
        )
    )

    mm_ch = configured_channel(
        guild,
        server_config.get(
            "mm_channel_id"
        )
    )

    sticky_status = (
        "🟢 Enabled"
        if sticky_enabled(server_config)
        else "🔴 Disabled"
    )

    embed = discord.Embed(
        title="⚙️ SDBST Marketplace Setup",
        description=(
            "Here's your current configuration. "
            "Change anything you like below — "
            "everything else stays as it is.\n\n"

            f"🟢 **Buying Channel:** "
            f"{buying_ch}\n"

            f"🔵 **Selling Channel:** "
            f"{selling_ch}\n"

            f"🎫 **Ticket Category:** "
            f"{ticket_cat}\n"

            f"🤝 **MM Channel:** "
            f"{mm_ch}\n"

            f"📌 **Sticky Notes:** "
            f"{sticky_status}"
        ),
        color=discord.Color.blurple()
    )

    embed.set_footer(
        text=(
            "Only server administrators "
            "can configure the bot."
        )
    )

    return embed


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

    view = SetupView(
        interaction.guild,
        server_config
    )

    await interaction.followup.send(
        embed=view.build_embed(),
        view=view,
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

        self.add_item(
            self.item_input
        )

        self.add_item(
            self.price_input
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

        data = {
            "item": item,
            "price": str(price)
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

                    await message.edit(
                        content=create_ad_text_from_data(
                            interaction.guild,
                            updated_ad
                        ),
                        embed=None,
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
        # Ticket opening message
        # ----------------------------------------------------

        ticket_message = None

        try:

            ticket_message = await ticket_channel.send(
                content=(
                    f"{seller.mention} "
                    f"{interaction.user.mention}\n\n"

                    f"🎫 **Trade ticket opened**\n"

                    f"**Item:** "
                    f"{self.ad.get('item')}\n"

                    f"**Price:** "
                    f"{money(self.ad.get('price'))}\n"

                    f"**Buyer:** "
                    f"{interaction.user.mention}\n"

                    f"**Seller:** "
                    f"{seller.mention}\n\n"

                    f"{NEGOTIATE_LINE}"
                ),
                view=TicketButtons(
                    ticket_record
                )
            )

        except Exception as e:

            print(
                f"[TICKET MESSAGE] {e}"
            )

        # A clean clickable link straight to the ticket.

        if ticket_message is not None:
            ticket_link = ticket_message.jump_url

        else:
            ticket_link = (
                f"https://discord.com/channels/"
                f"{guild.id}/{ticket_channel.id}"
            )

        await interaction.response.send_message(
            (
                f"[Click here to open a ticket ✔️]"
                f"({ticket_link})\n"
                f"💬 You can negotiate the deal "
                f"separately in the opened ticket."
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

        mm_link = (
            f"https://discord.com/channels/"
            f"{interaction.guild.id}/{mm_channel.id}"
        )

        await interaction.response.send_message(
            (
                f"🤝 **Middleman Request**\n"
                f"[Click here to open a ticket "
                f"and request MM]({mm_link})"
            )
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
            placeholder="Example: Inverted AWP",
            max_length=100,
            required=True
        )

        self.price_input = discord.ui.TextInput(
            label="Price (USD)",
            placeholder="Example: 105.00",
            max_length=20,
            required=True
        )

        self.add_item(
            self.item_input
        )

        self.add_item(
            self.price_input
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

        content = create_ad_text(
            interaction,
            item,
            price,
            self.ad_type
        )

        # ----------------------------------------------------
        # Send message first so we get its Discord ID.
        # ----------------------------------------------------

        try:

            message = await channel.send(
                content=content
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

    total_ads = 0

    total_tickets = 0

    # Restore views in EVERY guild the bot is in,
    # not just the test server.

    for guild in bot.guilds:

        print(
            f"[RESTORE] Checking "
            f"{guild.name} ({guild.id})"
        )

        # --------------------------------------------------------
        # Restore advertisements
        # --------------------------------------------------------

        try:

            ads = await api.list_ads(
                guild.id,
                limit=100
            )


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

                    total_ads += 1

                except discord.NotFound:

                    print(
                        f"[RESTORE AD] Message "
                        f"{message_id} no longer exists."
                    )

                except Exception as e:

                    print(
                        f"[RESTORE AD] {e}"
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

                        total_tickets += 1

                        break

                except Exception as e:

                    print(
                        f"[RESTORE TICKET] {e}"
                    )

        except Exception as e:

            print(
                f"[RESTORE TICKETS] {e}"
            )

    print(
        f"[RESTORE] Restored {total_ads} ads "
        f"and {total_tickets} tickets."
    )


# ============================================================
# STICKY NOTES (buying / selling / custom channel)
# ============================================================

# guild_id -> (config, timestamp)
_config_cache = {}

# channel_id -> sticky message id
_sticky_messages = {}

# channel_id -> last repost timestamp
_sticky_last = {}

# channels currently reposting their sticky
_sticky_posting = set()


def invalidate_config_cache(guild_id):

    _config_cache.pop(
        int(guild_id),
        None
    )


async def cached_config(guild_id):

    now = time.time()

    cached = _config_cache.get(guild_id)

    if cached and now - cached[1] < 60:
        return cached[0]

    config = await get_server_config(guild_id)

    _config_cache[guild_id] = (config, now)

    return config


async def refresh_sticky(channel, text):

    now = time.time()

    if now - _sticky_last.get(channel.id, 0) < 5:
        return

    if channel.id in _sticky_posting:
        return

    _sticky_last[channel.id] = now
    _sticky_posting.add(channel.id)

    try:

        old_id = _sticky_messages.get(channel.id)

        if old_id:

            try:

                old = await channel.fetch_message(old_id)

                await old.delete()

            except Exception:
                pass

        try:

            sent = await channel.send(text)

            _sticky_messages[channel.id] = sent.id

        except Exception as e:

            print(
                f"[STICKY] {e}"
            )

    finally:

        _sticky_posting.discard(channel.id)


@bot.event
async def on_message(message):

    if message.guild is None:

        await bot.process_commands(message)

        return

    # Never react to our own sticky note, otherwise
    # the bot would repost itself forever.
    if message.id in _sticky_messages.values():

        await bot.process_commands(message)

        return

    if message.channel.id in _sticky_posting:

        await bot.process_commands(message)

        return

    try:

        config = await cached_config(message.guild.id)

        text = sticky_text_for_channel(
            config,
            message.channel.id
        )

        if text:

            await refresh_sticky(
                message.channel,
                text
            )

    except Exception as e:

        print(
            f"[STICKY CHECK] {e}"
        )

    await bot.process_commands(message)


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
