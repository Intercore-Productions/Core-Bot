import discord
from discord import app_commands
from discord import Interaction
from discord.ext import commands
from discord.ui import View, Select, select, Button
import requests
import json
import os
import asyncio
import aiohttp
import wavelink
from dotenv import load_dotenv
from discord import ui, TextChannel, Embed
from typing import Optional, List, Dict
load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- SUPABASE CONFIG ---
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_TABLE = "server_config"
SUPABASE_HEADERS = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json"
}

# --- Database Function ---
def init_db():
    pass 
def load_config(guild_id):
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?guild_id=eq.{guild_id}"
    resp = requests.get(url, headers=SUPABASE_HEADERS)
    if resp.status_code != 200:
        return None
    data = resp.json()
    if not data:
        return None
    row = data[0]
    announce_roles = json.loads(row["announce_roles"]) if row.get("announce_roles") else []
    config = {
        "api_key": row.get("api_key"),
        "announce_roles": announce_roles,
        "updates_channel": row.get("updates_channel"),
        "logs_channel": row.get("logs_channel"),
        "ingame_perms": row.get("ingame_perms"),
        "server_code": row.get("server_code"),
        "session_ping": row.get("session_ping"),
        "session_perms": row.get("session_perms"),
        "session_channel": row.get("session_channel"),
        "welcoming_channel": row.get("welcoming_channel"),
        "welcome_text": row.get("welcome_text"),
        "webhook_url": row.get("webhook_url"),
        "premium_server": row.get("premium_server"),
        "session_ssu_message": row.get("session_ssu_message"),
        "session_ssu_color": row.get("session_ssu_color"),
        "session_ssd_message": row.get("session_ssd_message"),
        "session_ssd_color": row.get("session_ssd_color"),
        "session_low_message": row.get("session_low_message"),
        "session_low_color": row.get("session_low_color"),
        "session_cancel_message": row.get("session_cancel_message"),
        "session_cancel_color": row.get("session_cancel_color"),
        "session_ssu_banner": row.get("session_ssu_banner"),
        "session_ssd_banner": row.get("session_ssd_banner"),
        "modmail_enabled": row.get("modmail_enabled"),
        "modmail_category_id": row.get("modmail_category_id"),
        "modmail_staff_role_ids": row.get("modmail_staff_role_ids"),
        "modmail_log_channel_id": row.get("modmail_log_channel_id")
    }
    return config

async def save_config_to_db(interaction, session_id):
    session = config_sessions.get(session_id)
    if not session:
        return
    payload = {
        "guild_id": session.guild_id,
        "api_key": session.api_key,
        "announce_roles": json.dumps([session.announce_role.id]) if session.announce_role else json.dumps([]),
        "updates_channel": session.updates_channel.id if session.updates_channel else None,
        "logs_channel": session.logs_channel.id if session.logs_channel else None,
        "ingame_perms": session.ingame_perms,
        "server_code": session.server_code,
        "session_ping": session.session_ping,
        "session_perms": session.session_perms,
        "session_channel": session.session_channel,
        "welcoming_channel": session.welcoming_channel,
        "welcome_text": session.welcome_text
    }
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
    requests.post(url, headers=SUPABASE_HEADERS, data=json.dumps(payload))
    config_sessions.pop(session_id, None)
    await interaction.response.send_message("✅ Configuration saved.", ephemeral=True)

import psutil

# Giveaway participants cache
import threading
giveaway_participants_cache = {}  # {message_id: set(user_ids)}

def remove_giveaway_cache_later(message_id, delay=86400):
    def remove():
        giveaway_participants_cache.pop(message_id, None)
    t = threading.Timer(delay, remove)
    t.daemon = True
    t.start()

# Permission check: Create Events
def has_create_events():
    async def predicate(interaction: discord.Interaction):
        perms = interaction.user.guild_permissions
        if not getattr(perms, 'create_events', False):
            await interaction.response.send_message("You need the 'Create Events' permission to use this command.", ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

def get_cpu_usage():
    """Returns the current CPU usage percentage."""
    return psutil.cpu_percent(interval=1)

async def send_modlog_and_dm(user, embed, logs_channel_id, guild):
    channel = guild.get_channel(int(logs_channel_id))
    if channel:
        await channel.send(embed=embed)
    try:
        await user.send(embed=embed)
    except Exception:
        pass

from functools import wraps
import requests

def has_premium_server():
    def decorator(func):
        @wraps(func)
        async def wrapper(interaction: discord.Interaction, *args, **kwargs):
            guild_id = str(interaction.guild_id)
            url = f"{SUPABASE_URL}/rest/v1/server_config?guild_id=eq.{guild_id}&select=premium_server"
            resp = requests.get(url, headers=SUPABASE_HEADERS)

            if resp.status_code != 200:
                await interaction.response.send_message(
                    "⚠️ Unable to check premium status. Please try again later.",
                    ephemeral=True
                )
                return

            data = resp.json()
            if not data or data[0].get("premium_server", "No") != "Yes":
                await interaction.response.send_message(
                    "❌ This is a **Premium Feature**.\nBuy Premium to gain access.",
                    ephemeral=True
                )
                return

            return await func(interaction, *args, **kwargs)
        return wrapper
    return decorator

# /purge command
def has_delete_messages():
    async def predicate(interaction: discord.Interaction):
        member = interaction.user
        if not isinstance(member, discord.Member):
            member = await interaction.guild.fetch_member(interaction.user.id)
        if not member.guild_permissions.manage_messages and not member.guild_permissions.administrator:
            await interaction.response.send_message("You need the 'Manage Messages' permission to use this command.", ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

# /giveaway
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
import re

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def parse_duration(duration_str: str) -> int:
    match = re.match(r"(\d+)([mhdw])", duration_str.lower())
    if not match:
        return None

    value, unit = int(match.group(1)), match.group(2)

    if unit == "m":  
        return value * 60
    elif unit == "h":  
        return value * 60 * 60
    elif unit == "d":  
        return value * 60 * 60 * 24
    elif unit == "w":  
        return value * 60 * 60 * 24 * 7

    return None

import time
from discord.ui import View, Button

class GiveawayView(View):
    def __init__(self, duration_seconds, winners, prize, host):
        super().__init__(timeout=duration_seconds)
        self.participants = set()
        self.winners = winners
        self.prize = prize
        self.host = host
        self.button = Button(label="Join (0)", style=discord.ButtonStyle.primary, custom_id="giveaway_join")
        self.button.callback = self.join_leave
        self.add_item(self.button)
        self.message = None
        self.end_time = int(time.time()) + duration_seconds
        self.message_id = None  # Initialize message_id to None

    async def join_leave(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        if user_id in self.participants:
            self.participants.remove(user_id)
            await interaction.response.send_message("You left the giveaway!", ephemeral=True)
        else:
            self.participants.add(user_id)
            await interaction.response.send_message("You joined the giveaway!", ephemeral=True)
        # Aggiorna la cache ogni volta che cambia
        if self.message_id is not None:
            giveaway_participants_cache[self.message_id] = set(self.participants)
        await self.update_button()

    async def update_button(self):
        self.button.label = f"Join ({len(self.participants)})"
        if self.message:
            await self.message.edit(view=self)

    async def on_timeout(self):
        if self.message:
            await self.message.edit(view=None)

from discord.ui import Modal, TextInput

class EmbedBuilderView(View):
    def __init__(self, author_id, premium=False, presets=None):
        super().__init__(timeout=600)
        self.embed = discord.Embed(title="Custom Embed", description="Use Buttons to change text.", color=discord.Color.blurple())
        self.author_id = author_id
        self.premium = premium
        self.presets = presets or []
        self.selected_preset = None
        self.channel_to_send = None
        # Only add the select if there are presets
        if self.presets:
            options = [discord.SelectOption(label=p['name'], value=str(p['id'])) for p in self.presets if 'name' in p and 'id' in p]
            select = Select(placeholder="Load Preset", custom_id="load_preset", options=options)
            async def callback(interaction, select=select):
                await self.load_preset(interaction, select)
            select.callback = callback
            self.add_item(select)
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author_id

    @discord.ui.button(label="Title", style=discord.ButtonStyle.primary, custom_id="edit_title")
    async def edit_title(self, interaction: discord.Interaction, button: Button):
        class TitleModal(Modal):
            def __init__(self, current_title):
                super().__init__(title="Edit Title")
                self.title_input = TextInput(label="Title", max_length=256, default=current_title or "")
                self.add_item(self.title_input)
        modal = TitleModal(self.embed.title)
        await interaction.response.send_modal(modal)
        await modal.wait()
        await interaction.response.defer()
        self.embed.title = modal.title_input.value
        await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label="Description", style=discord.ButtonStyle.primary, custom_id="edit_desc")
    async def edit_desc(self, interaction: discord.Interaction, button: Button):
        class DescModal(Modal, title="Edit Description"):
            desc = TextInput(label="Description", style=discord.TextStyle.paragraph, max_length=2048)
        modal = DescModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        await interaction.response.defer()
        self.embed.description = modal.desc.value
        await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label="Color", style=discord.ButtonStyle.secondary, custom_id="edit_color")
    async def edit_color(self, interaction: discord.Interaction, button: Button):
        class ColorModal(Modal):
            def __init__(self, current_color):
                super().__init__(title="Edit Color (HEX)")
                hex_val = f"#{current_color:06X}" if isinstance(current_color, int) else (str(current_color) if current_color else "#5865F2")
                self.color_input = TextInput(label="HEX Color", placeholder="#5865F2", max_length=7, default=hex_val)
                self.add_item(self.color_input)
        current_color = self.embed.color.value if self.embed.color else None
        modal = ColorModal(current_color)
        await interaction.response.send_modal(modal)
        await modal.wait()
        await interaction.response.defer()
        try:
            self.embed.color = discord.Color(int(modal.color_input.value.replace('#',''), 16))
        except Exception:
            await interaction.followup.send("Invalid color! Usa formato HEX.", ephemeral=True)
        await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label="Author", style=discord.ButtonStyle.secondary, custom_id="edit_author")
    async def edit_author(self, interaction: discord.Interaction, button: Button):
        current_author = self.embed.author.name if self.embed.author else ""
        current_icon = self.embed.author.icon_url if self.embed.author and self.embed.author.icon_url else ""
        class AuthorModal(Modal):
            def __init__(self, author, icon):
                super().__init__(title="Edit Author")
                self.author_input = TextInput(label="Author", max_length=256, default=author or "")
                self.icon_url_input = TextInput(label="Author Icon URL", required=False, default=icon or "")
                self.add_item(self.author_input)
                self.add_item(self.icon_url_input)
        modal = AuthorModal(current_author, current_icon)
        await interaction.response.send_modal(modal)
        await modal.wait()
        await interaction.response.defer()
        icon_url = modal.icon_url_input.value.strip()
        if icon_url:
            self.embed.set_author(name=modal.author_input.value, icon_url=icon_url)
        else:
            self.embed.set_author(name=modal.author_input.value)
        await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label="Footer", style=discord.ButtonStyle.secondary, custom_id="edit_footer")
    async def edit_footer(self, interaction: discord.Interaction, button: Button):
        current_footer = self.embed.footer.text if self.embed.footer else ""
        current_icon = self.embed.footer.icon_url if self.embed.footer and self.embed.footer.icon_url else ""
        class FooterModal(Modal):
            def __init__(self, footer, icon):
                super().__init__(title="Edit Footer")
                self.footer_input = TextInput(label="Footer", max_length=2048, default=footer or "")
                self.icon_url_input = TextInput(label="Footer Icon URL", required=False, default=icon or "")
                self.add_item(self.footer_input)
                self.add_item(self.icon_url_input)
        modal = FooterModal(current_footer, current_icon)
        await interaction.response.send_modal(modal)
        await modal.wait()
        await interaction.response.defer()
        icon_url = modal.icon_url_input.value.strip()
        if icon_url:
            self.embed.set_footer(text=modal.footer_input.value, icon_url=icon_url)
        else:
            self.embed.set_footer(text=modal.footer_input.value)
        await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label="Image", style=discord.ButtonStyle.secondary, custom_id="edit_image")
    async def edit_image(self, interaction: discord.Interaction, button: Button):
        class ImageModal(Modal, title="Edit Image"):
            url = TextInput(label="Image URL", max_length=1024)
        modal = ImageModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        await interaction.response.defer()
        self.embed.set_image(url=modal.url.value)
        await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label="Thumbnail", style=discord.ButtonStyle.secondary, custom_id="edit_thumbnail")
    async def edit_thumbnail(self, interaction: discord.Interaction, button: Button):
        class ThumbModal(Modal, title="Edit Thumbnail"):
            url = TextInput(label="Thumbnail URL", max_length=1024)
        modal = ThumbModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        await interaction.response.defer()
        self.embed.set_thumbnail(url=modal.url.value)
        await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label="Add Field", style=discord.ButtonStyle.secondary, custom_id="add_field")
    async def add_field(self, interaction: discord.Interaction, button: Button):
        class FieldModal(Modal, title="Add Field"):
            name = TextInput(label="Field Name", max_length=256)
            value = TextInput(label="Field Value", style=discord.TextStyle.paragraph, max_length=1024)
            inline = TextInput(label="Inline? (yes/no)", max_length=3, required=False)
        modal = FieldModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        await interaction.response.defer()
        self.embed.add_field(name=modal.name.value, value=modal.value.value, inline=(modal.inline.value.lower() == "yes" if modal.inline.value else False))
        await interaction.edit_original_response(embed=self.embed, view=self)

    @discord.ui.button(label="Save Preset", style=discord.ButtonStyle.success, custom_id="save_preset")
    async def save_preset(self, interaction: discord.Interaction, button: Button):
        if not self.premium:
            await interaction.response.send_message("Only Premium users can save presets.", ephemeral=True)
            return
        # Salva preset su Supabase
        preset_name = self.embed.title or "Preset"
        data = {
            "user_id": str(interaction.user.id),
            "guild_id": str(interaction.guild_id),
            "name": preset_name,
            "embed_json": json.dumps(self.embed.to_dict())
        }
        url = f"{SUPABASE_URL}/rest/v1/embed_presets"
        resp = requests.post(url, headers=SUPABASE_HEADERS, data=json.dumps(data))
        if resp.status_code == 201:
            await interaction.response.send_message(f"Preset '{preset_name}' saved!", ephemeral=True)
        else:
            await interaction.response.send_message("Error saving preset.", ephemeral=True)

    # The select for loading presets will be added dynamically in __init__ only if there are presets
    async def load_preset(self, interaction: discord.Interaction, select: Select):
        preset_id = select.values[0]
        url = f"{SUPABASE_URL}/rest/v1/embed_presets?id=eq.{preset_id}"
        resp = requests.get(url, headers=SUPABASE_HEADERS)
        if resp.status_code == 200 and resp.json():
            preset = resp.json()[0]
            self.embed = discord.Embed.from_dict(json.loads(preset["embed_json"]))
            await interaction.response.defer()
            await interaction.edit_original_response(embed=self.embed, view=self)
        else:
            await interaction.response.send_message("Error loading preset.", ephemeral=True)

    @discord.ui.button(label="Send", style=discord.ButtonStyle.success, custom_id="send_embed")
    async def send_embed(self, interaction: discord.Interaction, button: Button):
        # Mostra una select con tutti i canali testuali dove l'utente può scrivere
        text_channels = [c for c in interaction.guild.text_channels if c.permissions_for(interaction.user).send_messages]
        if not text_channels:
            await interaction.response.send_message("No available text channels to send the embed.", ephemeral=True)
            return
        options = [discord.SelectOption(label=ch.name, value=str(ch.id)) for ch in text_channels]
        select = Select(placeholder="Select a channel", options=options, min_values=1, max_values=1)
        async def select_callback(select_interaction: discord.Interaction):
            channel_id = int(select.values[0])
            channel = interaction.guild.get_channel(channel_id)
            if not channel or not isinstance(channel, TextChannel):
                await select_interaction.response.send_message("Invalid channel!", ephemeral=True)
                return
            await channel.send(embed=self.embed)
            await select_interaction.response.send_message(f"Embed sent in <#{channel_id}>!")
            await select_interaction.message.delete()
        select.callback = select_callback
        view = View()
        view.add_item(select)
        await interaction.response.send_message("Select a channel to send the embed:", view=view, ephemeral=True)

from discord.ui import View, Select

class ModmailServerSelect(View):
    def __init__(self, user, mutual_guilds):
        super().__init__(timeout=60)
        options = [
            discord.SelectOption(
                label=guild.name,
                value=str(guild.id),
                description=f"Send a modmail to {guild.name}"
            )
            for guild in mutual_guilds
        ]
        self.select = Select(placeholder="Select a server...", options=options, min_values=1, max_values=1)
        self.select.callback = self.select_callback
        self.add_item(self.select)
        self.selected_guild_id = None
        self.user = user

    async def select_callback(self, interaction: discord.Interaction):
        self.selected_guild_id = int(self.select.values[0])
        await interaction.response.defer()
        self.stop()

@bot.event
async def on_message(message):
    # Only handle DMs to the bot, not guild messages or bot messages
    if message.guild is not None or message.author.bot:
        return

    # Find mutual guilds with modmail enabled
    mutual_guilds = []
    for guild in bot.guilds:
        if guild.get_member(message.author.id):
            config = load_config(guild.id)
            if config and config.get("modmail_enabled") == "TRUE":
                mutual_guilds.append(guild)

    if not mutual_guilds:
        await message.channel.send("You do not share any server with modmail enabled with this bot.")
        return

    embed = discord.Embed(
        title="Modmail Support",
        description="Select the server you want to contact the staff of.",
        color=discord.Color.blurple()
    )
    view = ModmailServerSelect(message.author, mutual_guilds)
    await message.channel.send(embed=embed, view=view)
    await view.wait()

    if view.selected_guild_id is None:
        await message.channel.send("No server selected. Modmail cancelled.")
        return

    # Next step: ask for reason (to be implemented in step 2)
    await message.channel.send(f"Server selected: <t:{view.selected_guild_id}>.")

        # After server selection, ask for the reason with a message
    if view.selected_guild_id is None:
        await message.channel.send("No server selected. Modmail cancelled.")
        return

    await message.channel.send("Please type the reason for your request. You have 2 minutes:")

    def check(m):
        return m.author.id == message.author.id and m.channel.id == message.channel.id

    try:
        reason_msg = await bot.wait_for('message', check=check, timeout=120)
        reason = reason_msg.content.strip()
    except asyncio.TimeoutError:
        await message.channel.send("⏰ Timeout. Modmail cancelled.")
        return

    # Next step: create staff channel and send embed (to be implemented in step 3)
    await message.channel.send(f"Reason received: `{reason}`. (Next: create staff channel...)")

@bot.tree.command(name="giveaway", description="Start a giveaway")
@app_commands.describe(duration="Ex: 10m, 2h, 1d, 1w", winners="Number of winners", prize="Prize of the giveaway")
@has_premium_server()
@has_create_events()
async def giveaway(interaction: discord.Interaction, duration: str, winners: int, prize: str):
    seconds = parse_duration(duration)
    if seconds is None:
        return await interaction.response.send_message("❌ Invalid duration format! Use `10m`, `2h`, `1d`, `1w`.", ephemeral=True)

    end_timestamp = int(time.time()) + seconds
    embed = discord.Embed(
        title="🎉 Giveaway 🎉",
        description=f"**Prize:** {prize}\n\n⏳ Ends: <t:{end_timestamp}:R>\n👑 Winners: {winners}",
        color=discord.Color.blurple()
    )
    embed.set_footer(text=f"Hosted by {interaction.user}")
    embed.set_image(url="https://media.discordapp.net/attachments/1383202755727855707/1419240376828432445/ou61gyY.png?ex=68d10a1a&is=68cfb89a&hm=be59cc2b3faa3e163b01e78882dddee313f73a5233a51f97cf48b3cb7ecdb613&=&width=1589&height=729")

    view = GiveawayView(duration_seconds=seconds, winners=winners, prize=prize, host=interaction.user)
    msg = await interaction.channel.send(embed=embed, view=view)
    view.message = msg
    view.message_id = msg.id
    giveaway_participants_cache[msg.id] = set(view.participants)

    await interaction.response.send_message("✅ Giveaway started!", ephemeral=True)

    # Update button label every minute
    for _ in range(seconds // 60):
        await asyncio.sleep(60)
        await view.update_button()

    await asyncio.sleep(seconds % 60)
    await view.update_button()

    # Select winners

    users = [await interaction.guild.fetch_member(uid) for uid in view.participants if await interaction.guild.fetch_member(uid) is not None]
    if not users:
        no_entry_embed = discord.Embed(
            title="❌ Giveaway Cancelled",
            description="No one entered the giveaway.",
            color=discord.Color.red()
        )
        return await interaction.channel.send(embed=no_entry_embed)

    winners_list = random.sample(users, min(len(users), winners))
    winners_mentions = ", ".join(w.mention for w in winners_list)

    end_embed = discord.Embed(
        title="🎉 Giveaway Ended 🎉",
        description=f"**Prize:** {prize}\n👑 Winners: {winners_mentions}",
        color=discord.Color.green()
    )
    await interaction.channel.send(embed=end_embed)
    view.message_id = msg.id  # Set the message_id for the giveaway

@bot.tree.command(name="giveaway-reroll", description="Reroll the winners for a giveaway")
@app_commands.describe(message_id="ID of the giveaway message", winners="Number of winners to reroll")
@has_create_events()
async def giveaway_reroll(interaction: discord.Interaction, message_id: str, winners: int):
    try:
        participants = giveaway_participants_cache.get(int(message_id), set())
        users = [await interaction.guild.fetch_member(uid) for uid in participants if await interaction.guild.fetch_member(uid) is not None]
        if not users:
            return await interaction.response.send_message("❌ No participants found for this giveaway.", ephemeral=True)
        winners_list = random.sample(users, min(len(users), winners))
        winners_mentions = ", ".join(w.mention for w in winners_list)
        reroll_embed = discord.Embed(
            title="🎉 Giveaway Rerolled 🎉",
            description=f"👑 New Winners: {winners_mentions}",
            color=discord.Color.orange()
        )
        await interaction.channel.send(embed=reroll_embed)
        await interaction.response.send_message("✅ Giveaway rerolled!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)

# --- /embed command ---
@bot.tree.command(name="embed", description="Create a custom embed")
@has_premium_server()
async def embed_command(interaction: discord.Interaction):
    # Carica preset se premium
    premium = True
    presets = []
    if hasattr(interaction, 'guild_id') and hasattr(interaction, 'user'):
        # Check premium status
        guild_id = str(interaction.guild_id)
        url = f"{SUPABASE_URL}/rest/v1/server_config?guild_id=eq.{guild_id}&select=premium_server"
        resp = requests.get(url, headers=SUPABASE_HEADERS)
        premium = resp.status_code == 200 and resp.json() and resp.json()[0].get("premium_server", "No") == "Yes"
        if premium:
            # Carica preset
            url = f"{SUPABASE_URL}/rest/v1/embed_presets?user_id=eq.{interaction.user.id}&guild_id=eq.{guild_id}"
            resp = requests.get(url, headers=SUPABASE_HEADERS)
            if resp.status_code == 200:
                presets = resp.json()
    view = EmbedBuilderView(author_id=interaction.user.id, premium=premium, presets=presets)
    await interaction.response.send_message("Create your embed:", embed=view.embed, view=view)

# /premium
@bot.tree.command(name="premium", description="Toggle premium status for a guild (developers only)")
@app_commands.describe(guild_id="Guild ID to update", premium="Set premium status: True (Yes) or False (No)")
async def premium(interaction: discord.Interaction, guild_id: str, premium: bool):
    allowed_ids = {1099013081683738676, 1044899567822454846}
    if interaction.user.id not in allowed_ids:
        await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
        return
    url = f"{SUPABASE_URL}/rest/v1/server_config?guild_id=eq.{guild_id}"
    resp = requests.get(url, headers=SUPABASE_HEADERS)
    if resp.status_code != 200 or not resp.json():
        await interaction.response.send_message("❌ Guild not found in database.", ephemeral=True)
        return
    premium_value = "Yes" if premium else "No"
    payload = {"premium_server": premium_value}
    patch_url = f"{SUPABASE_URL}/rest/v1/server_config?guild_id=eq.{guild_id}" 
    patch_headers = SUPABASE_HEADERS.copy()
    patch_headers["Prefer"] = "return=representation"
    patch_resp = requests.patch(patch_url, headers=patch_headers, data=json.dumps(payload))
    if patch_resp.status_code in (200, 204):
        await interaction.response.send_message(f"✅ Premium status for guild {guild_id} set to {premium_value}.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Failed to update premium status: {patch_resp.text}", ephemeral=True)

@bot.tree.command(name="purge", description="Delete up to 150 messages from this channel.")
@app_commands.describe(amount="Number of messages to delete (max 150)")
@has_premium_server()
@has_delete_messages()
async def purge(interaction: discord.Interaction, amount: int):
    if amount < 1 or amount > 150:
        return await interaction.response.send_message("You can only delete between 1 and 150 messages.", ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.response.send_message(f"✅ Deleted {len(deleted)} messages.", ephemeral=True)

# /suggest
from discord import Embed
from discord.ext import commands
import time

SUGGEST_CHANNEL_ID = 1407400015621521559
SUGGEST_GUILD_ID = 1383077857554727085
suggest_cooldowns = {}

@bot.tree.command(name="suggest", description="Send a Suggestion to our server")
@app_commands.describe(title="Suggestion Title", suggestion="Your suggestion")
async def suggest(interaction: discord.Interaction, title: str, suggestion: str):
    user_id = interaction.user.id
    now = time.time()
    last = suggest_cooldowns.get(user_id, 0)
    if now - last < 1800:
        mins = int((1800 - (now - last)) // 60)
        secs = int((1800 - (now - last)) % 60)
        return await interaction.response.send_message(f"⏳ TIMEOUT: You must wait {mins}m {secs}s to send another suggestion.", ephemeral=True)
    suggest_cooldowns[user_id] = now
    guild = bot.get_guild(SUGGEST_GUILD_ID)
    if not guild:
        return await interaction.response.send_message("❌ Guild not found.", ephemeral=True)
    channel = guild.get_channel(SUGGEST_CHANNEL_ID)
    if not channel:
        return await interaction.response.send_message("❌ Channel not found.", ephemeral=True)
    embed = Embed(title=title, description=suggestion, color=discord.Color.blurple())
    embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
    embed.set_footer(text=f"User ID: {user_id}")
    msg = await channel.send(embed=embed)
    for emoji in ["👍", "🤷‍♂️", "👎"]:
        await msg.add_reaction(emoji)
    await interaction.response.send_message("✅ Suggestion submitted!", ephemeral=True)

# Music System
import discord
from discord import app_commands
from discord.ext import commands
import wavelink

queues = {}

async def get_player(interaction: discord.Interaction) -> wavelink.Player:
    if not interaction.guild:
        raise ValueError("Interaction has no guild.")

    if not interaction.user.voice or not interaction.user.voice.channel:
        raise ValueError("User is not connected to a voice channel.")

    channel = interaction.user.voice.channel
    player: wavelink.Player = channel.guild.voice_client  

    if not player:
        player = await channel.connect(cls=wavelink.Player)
        queues[interaction.guild.id] = []

    return player


async def play_next(guild_id: int):
    queue = queues.get(guild_id)
    if not queue:
        player: wavelink.Player = discord.utils.get(bot.voice_clients, guild__id=guild_id)
        if player:
            await player.disconnect()
        return

    track, user = queue.pop(0)

    player: wavelink.Player = discord.utils.get(bot.voice_clients, guild__id=guild_id)
    if not player:
        return

    await player.play(track)

    channel = player.guild.system_channel or player.guild.text_channels[0]
    await channel.send(f"🎶 Now playing: `{track.title}` requested by {user.mention}")


@bot.tree.command(name="join", description="Join your voice channel")
async def join(interaction: discord.Interaction):
    try:
        await get_player(interaction)
        await interaction.response.send_message("✅ Joined your voice channel.")
    except ValueError as e:
        await interaction.response.send_message(f"❌ {e}", ephemeral=True)


@bot.tree.command(name="play", description="Play a YouTube song")
@app_commands.describe(query="YouTube URL or search keywords")
async def play(interaction: discord.Interaction, query: str):
    try:
        player = await get_player(interaction)
    except ValueError as e:
        await interaction.response.send_message(f"❌ {e}", ephemeral=True)
        return

    tracks = await wavelink.YouTubeTrack.search(query)
    if not tracks:
        await interaction.response.send_message("❌ No results found.", ephemeral=True)
        return

    track = tracks[0]
    queue = queues.setdefault(interaction.guild.id, [])
    queue.append((track, interaction.user))

    await interaction.response.send_message(f"🎵 Added to queue: `{track.title}`")

    if not player.is_playing():
        await play_next(interaction.guild.id)


@bot.tree.command(name="pause", description="Pause the music")
async def pause(interaction: discord.Interaction):
    player: wavelink.Player = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if not player or not player.is_playing():
        await interaction.response.send_message("❌ No music is playing.", ephemeral=True)
        return
    await player.pause(True)
    await interaction.response.send_message("⏸️ Music paused.")


@bot.tree.command(name="resume", description="Resume the music")
async def resume(interaction: discord.Interaction):
    player: wavelink.Player = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if not player or not player.is_paused():
        await interaction.response.send_message("❌ Music is not paused.", ephemeral=True)
        return
    await player.pause(False)
    await interaction.response.send_message("▶️ Music resumed.")


@bot.tree.command(name="stop", description="Stop and clear the queue")
async def stop(interaction: discord.Interaction):
    player: wavelink.Player = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if not player:
        await interaction.response.send_message("❌ Not connected to a voice channel.", ephemeral=True)
        return
    await player.stop()
    queues[interaction.guild.id] = []
    await interaction.response.send_message("⏹️ Stopped music and cleared queue.")


@bot.tree.command(name="leave", description="Leave the voice channel")
async def leave(interaction: discord.Interaction):
    player: wavelink.Player = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if not player:
        await interaction.response.send_message("❌ Not connected to a voice channel.", ephemeral=True)
        return
    await player.disconnect()
    queues[interaction.guild.id] = []
    await interaction.response.send_message("👋 Disconnected from the voice channel.")


@bot.tree.command(name="queue", description="Show the current music queue")
async def queue(interaction: discord.Interaction):
    queue = queues.get(interaction.guild.id, [])
    if not queue:
        await interaction.response.send_message("🎶 The queue is empty.")
        return

    desc = "\n".join(
        f"{i+1}. {track.title} (requested by {user.mention})" for i, (track, user) in enumerate(queue)
    )
    embed = discord.Embed(title="🎶 Music Queue", description=desc, color=discord.Color.blurple())
    await interaction.response.send_message(embed=embed)
    
@bot.tree.command(name="cpu", description="Show bot CPU usage")
async def music_cpu(interaction: discord.Interaction):
    usage = get_cpu_usage()
    embed = discord.Embed(title="🖥️ CPU Usage", description=f"Current CPU usage: {usage}%", color=discord.Color.blurple())
    await interaction.response.send_message(embed=embed)

# /game-bans
BANS_URL = 'https://maple-api.marizma.games/v1/server/bans'

@bot.tree.command(name="game-bans", description="Retrieve the list of game server bans.")
@has_premium_server()
async def game_bans(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ You don’t have permission to use this command.", ephemeral=True)
        return

    config = load_config(interaction.guild.id)
    if not config:
        await interaction.response.send_message("❌ This server is not configured. Use `/config` first.", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)

    headers = {
        "X-Api-Key": config["api_key"],
        "Accept": "application/json"
    }

    try:
        response = requests.get(BANS_URL, headers=headers)
        if response.status_code == 200:
            data = response.json()
            bans = data.get("data", {}).get("Bans", [])
            if not bans:
                await interaction.followup.send("✅ No bans found on the server.")
                return
                
            usernames = {}
            for uid in bans:
                try:
                    roblox_response = requests.get(f"https://users.roblox.com/v1/users/{uid}")
                    if roblox_response.status_code == 200:
                        usernames[uid] = roblox_response.json().get("name", f"Unknown ({uid})")
                    else:
                        usernames[uid] = f"Unknown ({uid})"
                except Exception:
                    usernames[uid] = f"Unknown ({uid})"

            bans_list = "\n".join(f"{usernames[uid]} ({uid})" for uid in bans)
            await interaction.followup.send(f"🚫 **Bans List:**\n```\n{bans_list}\n```")
        elif response.status_code == 401:
            await interaction.followup.send("❌ Unauthorized. Please check your API key.")
        elif response.status_code == 429:
            await interaction.followup.send("⚠️ Rate limit exceeded. Please try again later.")
        else:
            await interaction.followup.send(f"❌ Failed to fetch bans. Status: {response.status_code}\n{response.text}")
    except Exception as e:
        await interaction.followup.send(f"❌ An unexpected error occurred: {e}")

# /modmail
from discord import TextChannel, CategoryChannel

@bot.tree.command(name="modmail", description="Configure or disable the modmail system for this server")
@has_premium_server()
@app_commands.describe(
    category="Category where modmail channels will be created",
    staff_roles="Staff roles allowed (mention or ID, comma separated)",
    log_channel="Channel where modmail logs will be sent"
)
async def modmail(
    interaction: discord.Interaction,
    category: Optional[CategoryChannel] = None,
    staff_roles: Optional[str] = None,
    log_channel: Optional[TextChannel] = None
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only administrators can use this command.", ephemeral=True)
        return

    config = load_config(interaction.guild.id)
    if config and config.get("modmail_enabled") == "true":
        # Already enabled, ask if disable
        class ConfirmView(View):
            def __init__(self):
                super().__init__(timeout=30)
                self.value = None
            @discord.ui.button(label="Disable Modmail", style=discord.ButtonStyle.danger)
            async def confirm(self, interaction2, button):
                self.value = True
                await interaction2.response.defer()
                self.stop()
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, interaction2, button):
                self.value = False
                await interaction2.response.defer()
                self.stop()
        view = ConfirmView()
        await interaction.response.send_message(
            "Modmail is already enabled. Do you want to disable it and clear the configuration?",
            view=view, ephemeral=True
        )
        await view.wait()
        if view.value:
            # Disable and clear columns
            patch_url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?guild_id=eq.{interaction.guild.id}"
            payload = {
                "modmail_enabled": "false",
                "modmail_category_id": "",
                "modmail_staff_role_ids": "",
                "modmail_log_channel_id": ""
            }
            headers = SUPABASE_HEADERS.copy()
            headers["Content-Type"] = "application/json"
            requests.patch(patch_url, headers=headers, data=json.dumps(payload))
            await interaction.followup.send("✅ Modmail disabled and configuration cleared.", ephemeral=True)
        else:
            await interaction.followup.send("Operation cancelled.", ephemeral=True)
        return

    # If not enabled, ask for params if not provided
    if not (category and staff_roles and log_channel):
        await interaction.response.send_message(
            "To configure modmail, use `/modmail category: <category> staff_roles: <roles> log_channel: <channel>`\nExample: `/modmail category: #modmail staff_roles: @Staff,@Helper log_channel: #modmail-log`",
            ephemeral=True
        )
        return

    # Prepare data
    staff_ids = []
    for s in staff_roles.split(","):
        s = s.strip()
        if s.startswith("<@&") and s.endswith(">"):
            staff_ids.append(s[3:-1])
        elif s.isdigit():
            staff_ids.append(s)
    payload = {
        "modmail_enabled": "true",
        "modmail_category_id": str(category.id),
        "modmail_staff_role_ids": json.dumps(staff_ids),
        "modmail_log_channel_id": str(log_channel.id)
    }
    patch_url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?guild_id=eq.{interaction.guild.id}"
    headers = SUPABASE_HEADERS.copy()
    headers["Content-Type"] = "application/json"
    requests.patch(patch_url, headers=headers, data=json.dumps(payload))
    await interaction.response.send_message("✅ Modmail configured and enabled!", ephemeral=True)

# /game-queue
@bot.tree.command(name="game-queue", description="Show the current server queue.")
@has_premium_server()
async def game_queue(interaction: discord.Interaction):
    config = load_config(interaction.guild.id)
    if not config:
        await interaction.response.send_message("❌ This server is not configured. Use `/config` first.", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)

    headers = {
        "X-Api-Key": config["api_key"],
        "Accept": "application/json"
    }

    try:
        response = requests.get("https://maple-api.marizma.games/v1/server/queue", headers=headers)
        if response.status_code == 200:
            data = response.json()
            queue_ids = data.get("data", {}).get("Queue", [])

            if not queue_ids:
                await interaction.followup.send("✅ The queue is currently empty.")
                return

            usernames = {}
            for uid in queue_ids:
                try:
                    roblox_resp = requests.get(f"https://users.roblox.com/v1/users/{uid}")
                    if roblox_resp.status_code == 200:
                        usernames[uid] = roblox_resp.json().get("name", f"Unknown ({uid})")
                    else:
                        usernames[uid] = f"Unknown ({uid})"
                except Exception:
                    usernames[uid] = f"Unknown ({uid})"

            queue_list = "\n".join(f"{usernames[uid]} ({uid})" for uid in queue_ids)
            await interaction.followup.send(f"🎮 **Current Queue:**\n```\n{queue_list}\n```")
        elif response.status_code == 401:
            await interaction.followup.send("❌ Unauthorized. Please check your API key.")
        elif response.status_code == 429:
            await interaction.followup.send("⚠️ Rate limit exceeded. Please try again later.")
        else:
            await interaction.followup.send(f"❌ Failed to fetch queue. Status: {response.status_code}\n{response.text}")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

# /game-settings
@bot.tree.command(name="game-settings", description="Update the server's settings.")
@app_commands.describe(
    hide_from_list="Hide the server from the public list",
    private="Make the server private",
    min_level="Minimum level required to join"
)
@has_premium_server()
async def game_settings(
    interaction: discord.Interaction,
    hide_from_list: Optional[bool] = None,
    private: Optional[bool] = None,
    min_level: Optional[int] = None
):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("❌ You need the **Manage Server** permission to use this command.", ephemeral=True)
        return

    config = load_config(interaction.guild.id)
    if not config:
        await interaction.response.send_message("❌ This server is not configured. Use `/config` first.", ephemeral=True)
        return

    if hide_from_list is None and private is None and min_level is None:
        await interaction.response.send_message("⚠️ You must provide at least one setting to change.", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)

    headers = {
        "X-Api-Key": config["api_key"],
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {}
    if hide_from_list is not None:
        payload["HideFromList"] = hide_from_list
    if private is not None:
        payload["Private"] = private
    if min_level is not None:
        payload["minLevel"] = min_level

    try:
        response = requests.post("https://maple-api.marizma.games/v1/server/setSetting", headers=headers, json=payload)
        if response.status_code == 200:
            await interaction.followup.send("✅ Server settings updated successfully.")
        elif response.status_code == 400:
            await interaction.followup.send("❌ Invalid request or server is already banned.")
        elif response.status_code == 401:
            await interaction.followup.send("❌ Unauthorized. Please check your API key.")
        elif response.status_code == 403:
            await interaction.followup.send("❌ Invalid setting or permission denied.")
        else:
            await interaction.followup.send(f"❌ Unexpected error: {response.status_code}\n{response.text}")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

# /config-view
@bot.tree.command(name="config-view", description="View current configuration")
async def config_view(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only server administrators can view the configuration.", ephemeral=True)
        return
    try:
        config = load_config(interaction.guild.id)
        if not config:
            await interaction.response.send_message("❌ No configuration found for this server.", ephemeral=True)
            return
        embed1 = discord.Embed(title="Configuration • API & Announcements", color=discord.Color.yellow())
        embed1.add_field(name="API Key", value="||Hidden||", inline=False)
        announce_roles = config["announce_roles"]
        if announce_roles:
            mention_roles = ", ".join(f"<@&{rid}>" for rid in announce_roles)
        else:
            mention_roles = "Not set"
        embed1.add_field(name="Announcement Roles", value=mention_roles, inline=False)
        updates_channel = bot.get_channel(config["updates_channel"]) if config["updates_channel"] else None
        logs_channel = bot.get_channel(config["logs_channel"]) if config["logs_channel"] else None
        embed1.add_field(name="Updates Channel", value=updates_channel.mention if updates_channel else "Not set", inline=True)
        embed1.add_field(name="Logs Channel", value=logs_channel.mention if logs_channel else "Not set", inline=True)
        embed1.add_field(name="In-Game Mod Role", value=f"<@&{config['ingame_perms']}>" if config["ingame_perms"] else "Not set", inline=False)

        embed2 = discord.Embed(title="Configuration • Session", color=discord.Color.blue())
        embed2.add_field(name="Server Code", value=config["server_code"] if config["server_code"] else "Not set", inline=True)
        embed2.add_field(name="Session Ping", value=config["session_ping"] if config["session_ping"] else "Not set", inline=True)
        embed2.add_field(name="Session Permission Role", value=f"<@&{config['session_perms']}>" if config["session_perms"] else "Not set", inline=True)
        session_channel = bot.get_channel(int(config["session_channel"])) if config["session_channel"] else None
        embed2.add_field(name="Session Channel", value=session_channel.mention if session_channel else "Not set", inline=True)

        embed3 = discord.Embed(title="Configuration • Welcoming", color=discord.Color.green())
        welcoming_channel = bot.get_channel(int(config["welcoming_channel"])) if config["welcoming_channel"] else None
        embed3.add_field(name="Welcoming Channel", value=welcoming_channel.mention if welcoming_channel else "Not set", inline=True)
        embed3.add_field(name="Welcome Text", value=config["welcome_text"] if config["welcome_text"] else "Not set", inline=False)

        await interaction.response.send_message(embeds=[embed1, embed2, embed3], ephemeral=True)
    except Exception as e:
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)



from discord import ui
# /server-log
@bot.tree.command(name="server-log", description="Create a Core webhook for server logs in this channel")
async def server_log(interaction: discord.Interaction):
    import requests
    import json
    import asyncio

    channel = interaction.channel
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        config = load_config(interaction.guild.id)
    except Exception as e:
        await interaction.followup.send(f"❌ Errore nel caricamento config: {e}", ephemeral=True)
        return
    if not config:
        await interaction.followup.send("❌ This server is not configured. Use `/config` first.", ephemeral=True)
        return

    existing_url = config.get("webhook_url")
    if existing_url:
        class OverwriteView(ui.View):
            def __init__(self):
                super().__init__(timeout=30)
                self.value = None
            @ui.button(label="Yes", style=discord.ButtonStyle.green)
            async def yes(self, interaction2: discord.Interaction, button: ui.Button):
                self.value = True
                self.stop()
                await interaction2.response.defer()
            @ui.button(label="No", style=discord.ButtonStyle.red)
            async def no(self, interaction2: discord.Interaction, button: ui.Button):
                self.value = False
                self.stop()
                await interaction2.response.defer()

        view = OverwriteView()
        await interaction.followup.send(
            f"A Core webhook already exists for this server. Do you want to overwrite it?", view=view, ephemeral=True
        )
        try:
            await asyncio.wait_for(view.wait(), timeout=35)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ Timeout. Operation cancelled.", ephemeral=True)
            return
        if view.value is None or not view.value:
            await interaction.followup.send("Operation cancelled.", ephemeral=True)
            return
        try:
            webhooks = await channel.webhooks()
            for wh in webhooks:
                if wh.url == existing_url:
                    await wh.delete()
        except Exception:
            pass

    avatar_url = "https://images-ext-1.discordapp.net/external/zJLrKSkDoB9qgHC1L7xXS5jnWMv9CFQO2O-8RnhvBXQ/%3Fsize%3D4096/https/cdn.discordapp.com/avatars/1380646344976498778/45f9b70e6ef22b841179b0aafd4e4934.webp?width=1050&height=1050"
    try:
        avatar_bytes = requests.get(avatar_url).content
        webhook = await channel.create_webhook(name="Core", avatar=avatar_bytes)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to create webhook: {e}", ephemeral=True)
        return

    patch_url = f"{SUPABASE_URL}/rest/v1/server_config?guild_id=eq.{interaction.guild.id}"
    headers = SUPABASE_HEADERS.copy()
    headers["Content-Type"] = "application/json"
    headers["Prefer"] = "return=representation"
    payload = {"webhook_url": webhook.url}
    try:
        resp = requests.patch(patch_url, headers=headers, data=json.dumps(payload))
        if resp.status_code not in (200, 204):
            await interaction.followup.send(f"❌ Error saving webhook URL: {resp.text}", ephemeral=True)
            return
    except Exception as e:
        await interaction.followup.send(f"❌ Error saving webhook URL: {e}", ephemeral=True)
        return

    embed = discord.Embed(title="✅ Core Webhook Created", color=discord.Color.green())
    embed.add_field(name="Webhook URL", value=f"`{webhook.url}`", inline=False)
    embed.add_field(name="Instructions", value="Use this webhook for server logs.", inline=False)
    embed.set_thumbnail(url=avatar_url)
    await interaction.followup.send(embed=embed, ephemeral=True)

# /session-config
@bot.tree.command(name="session-config", description="Configure session messages and colors")
async def session_config(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only administrators can use this command.", ephemeral=True)
        return

    questions = [
        ("session_ssu_message", "Enter the message for Session Start (SSU):"),
        ("session_ssu_color", "Enter the HEX color for SSU (e.g. #00FF00):"),
        ("session_ssu_banner", "Enter the banner text for Session Start (SSU):"),
        ("session_ssd_message", "Enter the message for Session End (SSD):"),
        ("session_ssd_color", "Enter the HEX color for SSD (e.g. #FFA500):"),
        ("session_ssd_banner", "Enter the banner text for Session End (SSD):"),
        ("session_low_message", "Enter the message for Low Players:"),
        ("session_low_color", "Enter the HEX color for Low Players (e.g. #FF0000):"),
        ("session_cancel_message", "Enter the message for Session Cancellation:"),
        ("session_cancel_color", "Enter the HEX color for Cancellation (e.g. #8B0000):"),
    ]
    answers = {}
    await interaction.response.send_message("Session configuration started. Please answer the following questions.", ephemeral=True)
    channel = interaction.channel
    user = interaction.user

    def check(m):
        return m.author.id == user.id and m.channel.id == channel.id

    def is_hex_color(s):
        return s.startswith("#") and len(s) == 7 and all(c in "0123456789abcdefABCDEF" for c in s[1:])

    for key, question in questions:
        while True:
            await channel.send(question)
            try:
                msg = await bot.wait_for('message', check=check, timeout=180)
                value = msg.content.strip()
                await msg.delete()
                # Validate HEX color fields
                if "color" in key:
                    if not is_hex_color(value):
                        await channel.send("❌ Invalid HEX color. Please use format #RRGGBB (e.g. #00FF00).", delete_after=10)
                        continue
                answers[key] = value
                break
            except asyncio.TimeoutError:
                await channel.send("⏰ Timeout. Configuration cancelled.", delete_after=10)
                return

    # Save to Supabase (all fields as text)
    # Only set the 8 session columns and guild_id
    session_fields = [
        "session_ssu_message",
        "session_ssu_color",
        "session_ssu_banner",
        "session_ssd_message",
        "session_ssd_color",
        "session_ssd_banner",
        "session_low_message",
        "session_low_color",
        "session_cancel_message",
        "session_cancel_color"
    ]
    payload = {"guild_id": str(interaction.guild.id)}
    for k in session_fields:
        if k in answers:
            payload[k] = str(answers[k])

    url = f"{SUPABASE_URL}/rest/v1/server_config"
    headers = SUPABASE_HEADERS.copy()
    headers["Content-Type"] = "application/json"
    headers["Prefer"] = "return=representation"
    patch_url = f"{SUPABASE_URL}/rest/v1/server_config?guild_id=eq.{interaction.guild.id}"
    try:
        resp = requests.patch(patch_url, headers=headers, data=json.dumps(payload))
        if resp.status_code in (200, 204):
            await channel.send("✅ Session configuration updated successfully!", delete_after=10)
        else:
            await channel.send(f"❌ Error updating configuration: {resp.text}", delete_after=10)
    except Exception as e:
        await channel.send(f"❌ Error: {str(e)}", delete_after=10)

# /session-reset
@bot.tree.command(name="session-reset", description="Reset session message/color customizarion")
async def session_reset(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only administrators can use this command.", ephemeral=True)
        return

    session_fields = [
        "session_ssu_message",
        "session_ssu_color",
        "session_ssd_message",
        "session_ssd_color",
        "session_low_message",
        "session_low_color",
        "session_cancel_message",
        "session_cancel_color"
    ]
    payload = {k: "" for k in session_fields}

    headers = SUPABASE_HEADERS.copy()
    headers["Content-Type"] = "application/json"
    headers["Prefer"] = "return=representation"
    patch_url = f"{SUPABASE_URL}/rest/v1/server_config?guild_id=eq.{interaction.guild.id}"
    try:
        resp = requests.patch(patch_url, headers=headers, data=json.dumps(payload))
        if resp.status_code in (200, 204):
            await interaction.response.send_message("✅ Session columns reset.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Error resetting columns: {resp.text}", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

# /config-reset
@bot.tree.command(name="config-reset", description="Reset the server configuration")
async def config_reset(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only server admins can reset the config.", ephemeral=True)
        return

    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?guild_id=eq.{interaction.guild.id}"
    resp = requests.delete(url, headers=SUPABASE_HEADERS)
    if resp.status_code not in (200, 204):
        await interaction.response.send_message(f"❌ Errore nel reset: {resp.text}", ephemeral=True)
        return

    await interaction.response.send_message("✅ Configuration reset.", ephemeral=True)

# /maple-log
@bot.tree.command(name="maple-log", description="Create a 'Core' webhook for your private in-game server logs.")
@app_commands.describe(channel="The channel where the webhook will be created.")
async def maple_log(interaction: discord.Interaction, channel: TextChannel):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message(
            "❌ You need the **Manage Server** permission to use this command.",
            ephemeral=True
        )
        return

    webhook = await channel.create_webhook(name="Core")

    embed = Embed(
        title="✅ Webhook Created Successfully",
        color=discord.Color.green()
    )

    embed.add_field(
        name="🔗 Webhook URL",
        value=f"```{webhook.url}```",
        inline=False
    )

    embed.add_field(
        name="🛠 Setup Instructions",
        value=(
            "**1.** Enter your **Custom In-Game Server**\n"
            "**2.** Open the **Settings** menu\n"
            "**3.** Scroll to the section **Command Log Webhook**\n"
            "**4.** Paste the **Webhook URL** above into the required field"
        ),
        inline=False
    )

    embed.add_field(
        name="🎨 Want to customize the webhook?",
        value=(
            "Go to **Channel Settings → Integrations → Core**, and edit the name or avatar of the webhook."
        ),
        inline=False
    )

    embed.set_footer(text="Maple Server • Webhook Setup")
    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/1006/1006555.png")  # Optional custom image

    await interaction.response.send_message(embed=embed)
    

# /stats
@bot.tree.command(name="stats", description="Show bot statistics")
async def stats(interaction: discord.Interaction):
    guild_count = len(bot.guilds)
    member_count = sum(g.member_count for g in bot.guilds)
    ping = round(bot.latency * 1000)
    embed = discord.Embed(title="Bot Statistics", color=discord.Color.blurple())
    embed.add_field(name="Servers", value=str(guild_count), inline=True)
    embed.add_field(name="Total Members", value=str(member_count), inline=True)
    embed.add_field(name="Ping", value=f"{ping} ms", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)
   
# /announce
@bot.tree.command(name="announce", description="Send an in-game announcement")
@app_commands.describe(message="The message to send in-game")
async def announce(interaction: discord.Interaction, message: str):
    try:
        config = load_config(interaction.guild.id)
        if not config:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ This server is not configured. Use `/config` first.", ephemeral=True)
            return

        if not any(role.id in config["announce_roles"] for role in interaction.user.roles):
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ You do not have the required role to use this command.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        headers = {
            "X-Api-Key": config["api_key"],
            "Content-Type": "application/json"
        }
        data = json.dumps({"Message": message})
        try:
            response = requests.post("https://maple-api.marizma.games/v1/server/announce", headers=headers, data=data)
            if response.status_code == 200:
                await interaction.followup.send(f"✅ Announcement sent: `{message}`")
                # Log embed
                log_channel = bot.get_channel(config["logs_channel"])
                if log_channel:
                    embed = discord.Embed(title="📢 Announcement Sent", color=discord.Color.blue())
                    embed.add_field(name="By", value=interaction.user.mention, inline=False)
                    embed.add_field(name="Message", value=message, inline=False)
                    embed.timestamp = discord.utils.utcnow()
                    await log_channel.send(embed=embed)
            else:
                await interaction.followup.send(
                    f"❌ Failed to send announcement.\n"
                    f"🔢 Status Code: {response.status_code}\n"
                    f"📨 Response: {response.text}\n"
                    f"📝 Payload: {data}"
                )
        except Exception as e:
            await interaction.followup.send(f"❌ Error while sending request:\n```{str(e)}```")
    except Exception as e:
        if not interaction.response.is_done():
            try:
                await interaction.response.send_message(f"❌ Internal error: {str(e)}", ephemeral=True)
            except Exception:
                pass

# /game-info
@bot.tree.command(name="game-info", description="Show public server information")
async def game_info(interaction: discord.Interaction):
    config = load_config(interaction.guild.id)
    if not config:
        await interaction.response.send_message("❌ This server is not configured. Use `/config` first.", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)
    headers = {"X-Api-Key": config["api_key"]}
    try:
        response = requests.get("https://maple-api.marizma.games/v1/server", headers=headers)
        if response.status_code == 200:
            info = response.json()
            data = info.get("Data", info.get("data", {}))
            embed = discord.Embed(title="📝 Server Information", color=discord.Color.blue())
            embed.add_field(name="Server Name", value=str(data.get("ServerName", "Unknown")), inline=True)
            embed.add_field(name="Description", value=str(data.get("ServerDescription", "None")), inline=True)
            embed.add_field(name="Code", value=str(data.get("Code", "Unknown")), inline=True)
            embed.add_field(name="Owner", value=str(data.get("Owner", "Unknown")), inline=True)
            embed.add_field(name="Player Count", value=str(data.get("PlayerCount", "0")), inline=True)
            embed.add_field(name="Max Players", value=str(data.get("MaxPlayers", "Unknown")), inline=True)
            admins = data.get("Admins", [])
            embed.add_field(name="Admins", value=", ".join(map(str, admins)) if admins else "None", inline=True)
            head_admins = data.get("HeadAdmins", [])
            embed.add_field(name="Head Admins", value=", ".join(map(str, head_admins)) if head_admins else "None", inline=True)
            embed.add_field(name="Documentation", value="https://api-docs.marizma.games/", inline=False)
            embed.set_footer(text="Maple Server • Public Info")
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"❌ Failed to fetch server info. Status: {response.status_code}\n{response.text}")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

# /active-players
@bot.tree.command(name="active-players", description="Show active players on the server")
async def active_players(interaction: discord.Interaction):
    config = load_config(interaction.guild.id)
    if not config:
        await interaction.response.send_message("❌ This server is not configured. Use `/config` first.", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)
    headers = {"X-Api-Key": config["api_key"]}
    try:
        response = requests.get("https://maple-api.marizma.games/v1/server/players", headers=headers)
        if response.status_code == 200:
            data = response.json()
            players = data.get("data", {}).get("Players", [])
            count = len(players)
            await interaction.followup.send(f"👥 Players online: {count}")
        else:
            await interaction.followup.send(f"❌ Failed to fetch active players. Status: {response.status_code}\n{response.text}")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

# /hello (only for test)
@bot.tree.command(name="hello", description="Say hi to the bot!")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message("👋 Hello! I'm Core, here to help!")

# --- MODERATION COMMANDS ---

def check_config_and_log(interaction):
    config = load_config(interaction.guild.id)
    if not config:
        return None, None
    log_channel = interaction.guild.get_channel(config["logs_channel"])
    return config, log_channel

# --- MODLOGS SUPABASE ---
MODLOGS_TABLE = "modlogs"

def get_next_case_number():
    url = f"{SUPABASE_URL}/rest/v1/{MODLOGS_TABLE}?select=case_number&order=case_number.desc&limit=1"
    resp = requests.get(url, headers=SUPABASE_HEADERS)
    if resp.status_code == 200 and resp.json():
        return resp.json()[0]["case_number"] + 1
    return 1

def log_mod_action(guild_id, user_id, action, moderator_id, reason=None):
    case_number = get_next_case_number()
    payload = {
        "case_number": case_number,
        "guild_id": guild_id,
        "user_id": user_id,
        "action": action,
        "moderator_id": moderator_id,
        "reason": reason or "N/A",
        "date": discord.utils.utcnow().isoformat()
    }
    url = f"{SUPABASE_URL}/rest/v1/{MODLOGS_TABLE}"
    requests.post(url, headers=SUPABASE_HEADERS, data=json.dumps(payload))
    return case_number

@bot.tree.command(name="warn", description="Warn a user")
@app_commands.describe(user="User to warn", reason="Reason for warning")
async def warn(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not interaction.user.guild_permissions.mute_members:
        return await interaction.response.send_message("❌ You need the Mute Members permission.", ephemeral=True)
    config, log_channel = check_config_and_log(interaction)
    if not config:
        return await interaction.response.send_message("❌ Bot not configured. Use /config.", ephemeral=True)
    await interaction.response.defer(thinking=True)
    embed = discord.Embed(title="⚠️ Warning Issued", color=discord.Color.orange())
    embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=False)
    embed.add_field(name="Moderator", value=f"{interaction.user.mention}", inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.timestamp = discord.utils.utcnow()
    case_number = log_mod_action(interaction.guild.id, user.id, "warn", interaction.user.id, reason)
    embed.add_field(name="Case Number", value=str(case_number), inline=False)
    await send_modlog_and_dm(user, embed, config["logs_channel"], interaction.guild)
    await interaction.followup.send(f"✅ Warned {user.mention}.", ephemeral=True)

@bot.tree.command(name="unwarn", description="Remove a warning from a user")
@app_commands.describe(user="User to unwarn", reason="Reason for unwarn")
async def unwarn(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not interaction.user.guild_permissions.mute_members:
        return await interaction.response.send_message("❌ You need the Mute Members permission.", ephemeral=True)
    config, log_channel = check_config_and_log(interaction)
    if not config:
        return await interaction.response.send_message("❌ Bot not configured. Use /config.", ephemeral=True)
    await interaction.response.defer(thinking=True)
    embed = discord.Embed(title="✅ Warning Removed", color=discord.Color.green())
    embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=False)
    embed.add_field(name="Moderator", value=f"{interaction.user.mention}", inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.timestamp = discord.utils.utcnow()
    case_number = log_mod_action(interaction.guild.id, user.id, "unwarn", interaction.user.id, reason)
    embed.add_field(name="Case Number", value=str(case_number), inline=False)
    await send_modlog_and_dm(user, embed, config["logs_channel"], interaction.guild)
    await interaction.followup.send(f"✅ Unwarned {user.mention}.", ephemeral=True)

@bot.tree.command(name="mute", description="Mute a user")
@app_commands.describe(user="User to mute", reason="Reason for mute")
async def mute(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not interaction.user.guild_permissions.mute_members:
        return await interaction.response.send_message("❌ You need the Mute Members permission.", ephemeral=True)
    config, log_channel = check_config_and_log(interaction)
    if not config:
        return await interaction.response.send_message("❌ Bot not configured. Use /config.", ephemeral=True)
    await interaction.response.defer(thinking=True)
    try:
        await user.edit(timeout=discord.utils.utcnow() + discord.timedelta(days=28))
    except Exception:
        return await interaction.followup.send("❌ Failed to mute user.", ephemeral=True)
    embed = discord.Embed(title="🔇 User Muted", color=discord.Color.red())
    embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=False)
    embed.add_field(name="Moderator", value=f"{interaction.user.mention}", inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.timestamp = discord.utils.utcnow()
    case_number = log_mod_action(interaction.guild.id, user.id, "mute", interaction.user.id, reason)
    embed.add_field(name="Case Number", value=str(case_number), inline=False)
    await send_modlog_and_dm(user, embed, config["logs_channel"], interaction.guild)
    await interaction.followup.send(f"✅ Muted {user.mention}.", ephemeral=True)

@bot.tree.command(name="unmute", description="Unmute a user")
@app_commands.describe(user="User to unmute", reason="Reason for unmute")
async def unmute(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not interaction.user.guild_permissions.mute_members:
        return await interaction.response.send_message("❌ You need the Mute Members permission.", ephemeral=True)
    config, log_channel = check_config_and_log(interaction)
    if not config:
        return await interaction.response.send_message("❌ Bot not configured. Use /config.", ephemeral=True)
    await interaction.response.defer(thinking=True)
    try:
        await user.edit(timeout=None)
    except Exception:
        return await interaction.followup.send("❌ Failed to unmute user.", ephemeral=True)
    embed = discord.Embed(title="🔊 User Unmuted", color=discord.Color.green())
    embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=False)
    embed.add_field(name="Moderator", value=f"{interaction.user.mention}", inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.timestamp = discord.utils.utcnow()
    case_number = log_mod_action(interaction.guild.id, user.id, "unmute", interaction.user.id, reason)
    embed.add_field(name="Case Number", value=str(case_number), inline=False)
    await send_modlog_and_dm(user, embed, config["logs_channel"], interaction.guild)
    await interaction.followup.send(f"✅ Unmuted {user.mention}.", ephemeral=True)

@bot.tree.command(name="kick", description="Kick a user")
@app_commands.describe(user="User to kick", reason="Reason for kick")
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not interaction.user.guild_permissions.kick_members:
        return await interaction.response.send_message("❌ You need the Kick Members permission.", ephemeral=True)
    config, log_channel = check_config_and_log(interaction)
    if not config:
        return await interaction.response.send_message("❌ Bot not configured. Use /config.", ephemeral=True)
    await interaction.response.defer(thinking=True)
    embed = discord.Embed(title="👢 User Kicked", color=discord.Color.orange())
    embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=False)
    embed.add_field(name="Moderator", value=f"{interaction.user.mention}", inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.timestamp = discord.utils.utcnow()
    case_number = log_mod_action(interaction.guild.id, user.id, "kick", interaction.user.id, reason)
    embed.add_field(name="Case Number", value=str(case_number), inline=False)
    await send_modlog_and_dm(user, embed, config["logs_channel"], interaction.guild)
    try:
        await user.kick(reason=reason)
    except Exception:
        return await interaction.followup.send("❌ Failed to kick user.", ephemeral=True)
    await interaction.followup.send(f"✅ Kicked {user.mention}.", ephemeral=True)

@bot.tree.command(name="soft-ban", description="Soft-ban a user (ban and unban)")
@app_commands.describe(user="User to soft-ban", reason="Reason for soft-ban")
async def soft_ban(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not interaction.user.guild_permissions.ban_members:
        return await interaction.response.send_message("❌ You need the Ban Members permission.", ephemeral=True)
    config, log_channel = check_config_and_log(interaction)
    if not config:
        return await interaction.response.send_message("❌ Bot not configured. Use /config.", ephemeral=True)
    await interaction.response.defer(thinking=True)
    embed = discord.Embed(title="🚫 User Soft-Banned", color=discord.Color.orange())
    embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=False)
    embed.add_field(name="Moderator", value=f"{interaction.user.mention}", inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.timestamp = discord.utils.utcnow()
    case_number = log_mod_action(interaction.guild.id, user.id, "soft-ban", interaction.user.id, reason)
    embed.add_field(name="Case Number", value=str(case_number), inline=False)
    await send_modlog_and_dm(user, embed, config["logs_channel"], interaction.guild)
    try:
        await user.ban(reason=reason, delete_message_days=1)
        await interaction.guild.unban(user, reason="Soft-ban")
    except Exception:
        return await interaction.followup.send("❌ Failed to soft-ban user.", ephemeral=True)
    await interaction.followup.send(f"✅ Soft-banned {user.mention}.", ephemeral=True)

@bot.tree.command(name="t-ban", description="Temp-ban a user (ban for N days)")
@app_commands.describe(user="User to temp-ban", days="Number of days", reason="Reason for temp-ban")
async def t_ban(interaction: discord.Interaction, user: discord.Member, days: int, reason: str):
    if not interaction.user.guild_permissions.ban_members:
        return await interaction.response.send_message("❌ You need the Ban Members permission.", ephemeral=True)
    config, log_channel = check_config_and_log(interaction)
    if not config:
        return await interaction.response.send_message("❌ Bot not configured. Use /config.", ephemeral=True)
    await interaction.response.defer(thinking=True)
    embed = discord.Embed(title="⏳ User Temp-Banned", color=discord.Color.red())
    embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=False)
    embed.add_field(name="Moderator", value=f"{interaction.user.mention}", inline=False)
    embed.add_field(name="Days", value=str(days), inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.timestamp = discord.utils.utcnow()
    case_number = log_mod_action(interaction.guild.id, user.id, "t-ban", interaction.user.id, reason)
    embed.add_field(name="Case Number", value=str(case_number), inline=False)
    await send_modlog_and_dm(user, embed, config["logs_channel"], interaction.guild)
    try:
        await user.ban(reason=reason, delete_message_days=days)
    except Exception:
        return await interaction.followup.send("❌ Failed to temp-ban user.", ephemeral=True)
    await interaction.followup.send(f"✅ Temp-banned {user.mention} for {days} days.", ephemeral=True)

@bot.tree.command(name="p-ban", description="Permanently ban a user")
@app_commands.describe(user="User to ban", reason="Reason for ban")
async def p_ban(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not interaction.user.guild_permissions.ban_members:
        return await interaction.response.send_message("❌ You need the Ban Members permission.", ephemeral=True)
    config, log_channel = check_config_and_log(interaction)
    if not config:
        return await interaction.response.send_message("❌ Bot not configured. Use /config.", ephemeral=True)
    await interaction.response.defer(thinking=True)
    embed = discord.Embed(title="🔨 User Permanently Banned", color=discord.Color.dark_red())
    embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=False)
    embed.add_field(name="Moderator", value=f"{interaction.user.mention}", inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.timestamp = discord.utils.utcnow()
    case_number = log_mod_action(interaction.guild.id, user.id, "p-ban", interaction.user.id, reason)
    embed.add_field(name="Case Number", value=str(case_number), inline=False)
    await send_modlog_and_dm(user, embed, config["logs_channel"], interaction.guild)
    try:
        await user.ban(reason=reason)
    except Exception:
        return await interaction.followup.send("❌ Failed to ban user.", ephemeral=True)
    await interaction.followup.send(f"✅ Permanently banned {user.mention}.", ephemeral=True)

@bot.tree.command(name="unban", description="Unban a user")
@app_commands.describe(user_id="ID of the user to unban", reason="Reason for unban")
async def unban(interaction: discord.Interaction, user_id: int, reason: str):
    if not interaction.user.guild_permissions.ban_members:
        return await interaction.response.send_message("❌ You need the Ban Members permission.", ephemeral=True)
    config, log_channel = check_config_and_log(interaction)
    if not config:
        return await interaction.response.send_message("❌ Bot not configured. Use /config.", ephemeral=True)
    await interaction.response.defer(thinking=True)
    user = await bot.fetch_user(user_id)
    embed = discord.Embed(title="🔓 User Unbanned", color=discord.Color.green())
    embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=False)
    embed.add_field(name="Moderator", value=f"{interaction.user.mention}", inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.timestamp = discord.utils.utcnow()
    case_number = log_mod_action(interaction.guild.id, user.id, "unban", interaction.user.id, reason)
    embed.add_field(name="Case Number", value=str(case_number), inline=False)
    await send_modlog_and_dm(user, embed, config["logs_channel"], interaction.guild)
    try:
        await interaction.guild.unban(user, reason=reason)
    except Exception:
        return await interaction.followup.send("❌ Failed to unban user.", ephemeral=True)
    await interaction.followup.send(f"✅ Unbanned {user.mention}.", ephemeral=True)

# --- /modlogs ---
@bot.tree.command(name="modlogs", description="View moderation logs for a user")
@app_commands.describe(user="User to view logs for")
async def modlogs(interaction: discord.Interaction, user: discord.User):
    if not (interaction.user.guild_permissions.moderate_members or interaction.user.guild_permissions.kick_members or interaction.user.guild_permissions.ban_members):
        return await interaction.response.send_message("❌ You need moderation permissions.", ephemeral=True)
    config = load_config(interaction.guild.id)
    if not config:
        return await interaction.response.send_message("❌ Bot not configured. Use /config.", ephemeral=True)
    url = f"{SUPABASE_URL}/rest/v1/{MODLOGS_TABLE}?guild_id=eq.{interaction.guild.id}&user_id=eq.{user.id}&order=date.desc"
    resp = requests.get(url, headers=SUPABASE_HEADERS)
    logs = resp.json() if resp.status_code == 200 else []
    if not logs:
        return await interaction.response.send_message(f"Nessun log trovato per {user.mention}.", ephemeral=True)
    embed = discord.Embed(title=f"Modlogs for {user}", color=discord.Color.blurple())
    for log in logs[:10]:
        mod = await bot.fetch_user(log["moderator_id"])
        reason = log.get("reason", "N/A")
        embed.add_field(
            name=f"Case #{log['case_number']} - {log['action']}",
            value=f"By: {mod.mention if mod else log['moderator_id']}\nDate: {log['date']}\nReason: {reason}",
            inline=False
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# --- /clear-modlog-user ---
@bot.tree.command(name="clear-modlog-user", description="Clear all modlogs for a user")
@app_commands.describe(user="User to clear logs for")
async def clear_modlog_user(interaction: discord.Interaction, user: discord.User):
    if not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message("❌ You need Manage Guild permission.", ephemeral=True)
    config = load_config(interaction.guild.id)
    if not config:
        return await interaction.response.send_message("❌ Bot not configured. Use /config.", ephemeral=True)
    url = f"{SUPABASE_URL}/rest/v1/{MODLOGS_TABLE}?guild_id=eq.{interaction.guild.id}&user_id=eq.{user.id}"
    resp = requests.delete(url, headers=SUPABASE_HEADERS)
    if resp.status_code in (200, 204):
        await interaction.response.send_message(f"✅ Modlogs for {user.mention} cleared.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Failed to clear modlogs: {resp.text}", ephemeral=True)

# --- /clear-modlog-all ---
@bot.tree.command(name="clear-modlog-all", description="Clear all modlogs for this guild")
async def clear_modlog_all(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message("❌ You need Manage Guild permission.", ephemeral=True)
    config = load_config(interaction.guild.id)
    if not config:
        return await interaction.response.send_message("❌ Bot not configured. Use /config.", ephemeral=True)
    url = f"{SUPABASE_URL}/rest/v1/{MODLOGS_TABLE}?guild_id=eq.{interaction.guild.id}"
    resp = requests.delete(url, headers=SUPABASE_HEADERS)
    if resp.status_code in (200, 204):
        await interaction.response.send_message(f"✅ All modlogs for this guild cleared.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Failed to clear modlogs: {resp.text}", ephemeral=True)

def username_to_userid(username):
    url = "https://users.roblox.com/v1/usernames/users"
    payload = {
        "usernames": [username],
        "excludeBannedUsers": False
    }
    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()  

        data = response.json()

        if data["data"]:
            user_id = data["data"][0]["id"]
            return user_id
        else:
            return None
    except requests.exceptions.RequestException:
        return None

# /game-kick
@bot.tree.command(name="game-kick", description="Kick a player from the game server")
@app_commands.describe(user="Username of the player to kick", reason="Optional reason for the kick")
async def game_kick(interaction: discord.Interaction, user: str, reason: str = None):
    config = load_config(interaction.guild.id)
    if not config:
        await interaction.response.send_message("❌ This server is not configured. Use `/config` first.", ephemeral=True)
        return

    ingame_role_id = config.get("ingame_perms")
    if not ingame_role_id or not any(str(role.id) == str(ingame_role_id) for role in interaction.user.roles):
        await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
        return

    user_id = username_to_userid(user)
    if not user_id:
        await interaction.response.send_message("❌ User not found. Please check the username.", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)
    headers = {"X-Api-Key": config["api_key"], "Content-Type": "application/json"}
    body = {"UserId": user_id}
    if reason:
        body["ModerationReason"] = reason
    try:
        resp = requests.post("https://maple-api.marizma.games/v1/server/moderation/kick", headers=headers, data=json.dumps(body))
        if resp.status_code == 200:
            embed = discord.Embed(title="📤 Game Kick", color=discord.Color.orange())
            embed.add_field(name="User ID", value=str(user_id), inline=False)
            embed.add_field(name="Username", value=user, inline=False)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)
            embed.timestamp = discord.utils.utcnow()

            log_channel = interaction.guild.get_channel(config["logs_channel"])
            if log_channel:
                await log_channel.send(embed=embed)
            try:
                await interaction.user.send(embed=embed)
            except Exception:
                pass
        else:
            await interaction.followup.send("❌ Failed to kick the user. Try again later.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send("❌ An error occurred during kick. Try again later.", ephemeral=True)

# Game-Ban 
@bot.tree.command(name="game-ban", description="Ban or unban a player from the game server")
@app_commands.describe(user="Username of the player to ban/unban", banned="Ban = True / Unban = False", reason="Reason for the action")
async def game_ban(interaction: discord.Interaction, user: str, banned: bool, reason: str = None):
    config = load_config(interaction.guild.id)
    if not config:
        await interaction.response.send_message("❌ This server is not configured.", ephemeral=True)
        return

    ingame_role_id = config.get("ingame_perms")
    if not ingame_role_id or not any(str(role.id) == str(ingame_role_id) for role in interaction.user.roles):
        await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)

    # Convert username to user ID
    user_id = username_to_userid(user)
    if not user_id:
        await interaction.followup.send("❌ User not found. Please check the username.", ephemeral=True)
        return

    # Prepare request
    body = {
        "UserId": user_id,
        "BanStatus": banned
    }
    if reason:
        body["ModerationReason"] = reason

    headers = {
        "X-Api-Key": config.get("api_key"),
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(
            "https://maple-api.marizma.games/v1/server/banplayer",
            headers=headers,
            data=json.dumps(body)
        )
        if resp.status_code == 200:
            embed = discord.Embed(
                title="🔨 Game Ban" if banned else "✅ Game Unban",
                color=discord.Color.red() if banned else discord.Color.green()
            )
            embed.add_field(name="User ID", value=str(user_id), inline=False)
            embed.add_field(name="Username", value=user, inline=False)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
            embed.add_field(name="Action", value="Ban" if banned else "Unban", inline=False)
            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)
            embed.timestamp = discord.utils.utcnow()

            log_channel = interaction.guild.get_channel(config["logs_channel"])
            if log_channel:
                await log_channel.send(embed=embed)

            try:
                await interaction.user.send(embed=embed)
            except Exception:
                pass

            await interaction.followup.send("✅ Ban status updated.")
        else:
            await interaction.followup.send(f"❌ API Error {resp.status_code}: {resp.text}", ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"❌ Error while updating ban: {e}", ephemeral=True)

from discord import app_commands

@bot.tree.command(name="session", description="Manage a session announcement")
@app_commands.describe(
    action="Session action: Start (SSU), End (SSD), Low Players, or Cancellation"
)
@app_commands.choices(
    action=[
        app_commands.Choice(name="Session Start (SSU)", value="SSU"),
        app_commands.Choice(name="Session End (SSD)", value="SSD"),
        app_commands.Choice(name="Low Players", value="Low Players"),
        app_commands.Choice(name="Session Cancellation", value="Session Cancellation"),
    ]
)
async def session(
    interaction: discord.Interaction,
    action: app_commands.Choice[str],
):
    config = load_config(interaction.guild.id)
    if not config:
        await interaction.response.send_message("❌ This server is not configured. Use `/config` first.", ephemeral=True)
        return

    session_perms = config.get("session_perms")
    if not session_perms or not any(str(role.id) == str(session_perms) for role in interaction.user.roles):
        await interaction.response.send_message("❌ You do not have the required role to use this command.", ephemeral=True)
        return

    session_channel_id = config.get("session_channel")
    session_channel = bot.get_channel(int(session_channel_id)) if session_channel_id else None
    if not session_channel:
        await interaction.response.send_message("❌ Session channel is not set in the configuration.", ephemeral=True)
        return

    session_ping = config.get("session_ping") or ""
    server_code = config.get("server_code") or "Unknown"
    api_key = config.get("api_key")

    await interaction.response.defer(thinking=True)

    # --- Premium/Default logic ---
    # Check premium status (same as /premium logic)
    # Fix: premium_server is stored as 'Yes' or 'No', not boolean
    is_premium = str(config.get("premium_server", "No")).lower() == "yes"
    # Get custom session config fields
    custom_fields = {
        "SSU": {
            "message": config.get("session_ssu_message"),
            "color": config.get("session_ssu_color"),
        },
        "SSD": {
            "message": config.get("session_ssd_message"),
            "color": config.get("session_ssd_color"),
        },
        "Low Players": {
            "message": config.get("session_low_message"),
            "color": config.get("session_low_color"),
        },
        "Session Cancellation": {
            "message": config.get("session_cancel_message"),
            "color": config.get("session_cancel_color"),
        },
    }

    def get_embed(action_name, player_count=None):
        # If premium and custom config set, use it, else fallback to default
        if is_premium:
            msg = custom_fields[action_name]["message"]
            color_hex = custom_fields[action_name]["color"]
            # Accept empty string as not set
            if msg is not None and color_hex is not None and msg.strip() != "" and color_hex.strip() != "":
                use_custom = True
                # Robust HEX: add # if missing
                color_hex = color_hex.strip()
                if not color_hex.startswith("#"):
                    color_hex = "#" + color_hex
            else:
                use_custom = False
        else:
            use_custom = False

        if action_name == "SSU":
            if use_custom:
                embed = discord.Embed(
                    title="SSU | Server Start Up",
                    description=msg,
                    color=int(color_hex.lstrip("#"), 16)
                )
            else:
                embed = discord.Embed(
                    title="SSU | Server Start Up",
                    description="A new session is starting in our Maple Server! Join now with the Code Below!",
                    color=discord.Color.green()
                )
            embed.add_field(name="Session Host", value=interaction.user.mention, inline=True)
            embed.add_field(name="Session Code", value=server_code, inline=True)
            return embed
        elif action_name == "SSD":
            if use_custom:
                embed = discord.Embed(
                    title="SSD | Server Shut Down",
                    description=msg,
                    color=int(color_hex.lstrip("#"), 16)
                )
            else:
                embed = discord.Embed(
                    title="SSD | Server Shut Down",
                    description=f"The session hosted by {interaction.user.mention} has ended. Thank you for participating! See you soon!",
                    color=discord.Color.orange()
                )
            return embed
        elif action_name == "Low Players":
            # Always include Players Online: {player_count}
            if use_custom:
                desc = f"{msg}\n**Players Online:** {player_count}\nPlease join the game if you want to participate!"
                embed = discord.Embed(
                    title="Low Player Count",
                    description=desc,
                    color=int(color_hex.lstrip("#"), 16)
                )
            else:
                embed = discord.Embed(
                    title="Low Player Count",
                    description=f"There are currently not enough players in-game.\n**Players Online:** {player_count}\nPlease join the game if you want to participate!",
                    color=discord.Color.red()
                )
            return embed
        elif action_name == "Session Cancellation":
            if use_custom:
                embed = discord.Embed(
                    title="Session Cancelled",
                    description=msg,
                    color=int(color_hex.lstrip("#"), 16)
                )
            else:
                embed = discord.Embed(
                    title="Session Cancelled",
                    description="The session has been cancelled by the host due to unforeseen reasons. Stay tuned for future sessions!",
                    color=discord.Color.dark_red()
                )
            return embed
        else:
            return None

    # --- Action logic ---
    if action.value == "SSU":
        # Use custom banner if premium and configured
        if is_premium and config.get("session_ssu_banner") and config.get("session_ssu_banner").strip():
            banner_text = config.get("session_ssu_banner")
        else:
            banner_text = f"[SSU] A new Session hosted by {interaction.user.display_name} is started. Use !mod or !help for any problem."
        headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json"
        }
        data = {"banner": banner_text}
        try:
            requests.post(
                "https://maple-api.marizma.games/v1/server/setbanner",
                headers=headers,
                data=json.dumps(data)
            )
        except Exception:
            pass
        embed = get_embed("SSU")
        await session_channel.send(f"{session_ping}", embed=embed)
        await interaction.followup.send("✅ Session start announced.", ephemeral=True)

    elif action.value == "SSD":
        # Use custom banner if premium and configured
        if is_premium and config.get("session_ssd_banner") and config.get("session_ssd_banner").strip():
            banner_text = config.get("session_ssd_banner")
        else:
            banner_text = f"[SSD] The session hosted by {interaction.user.display_name} is now concluded, we invite you to leave our server. See you soon!"
        headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json"
        }
        data = {"banner": banner_text}
        try:
            requests.post(
                "https://maple-api.marizma.games/v1/server/setbanner",
                headers=headers,
                data=json.dumps(data)
            )
        except Exception:
            pass
        embed = get_embed("SSD")
        await session_channel.send(embed=embed)
        await interaction.followup.send("✅ Session end announced.", ephemeral=True)

    elif action.value == "Low Players":
        player_count = "?"
        try:
            headers_api = {"X-Api-Key": api_key}
            resp = requests.get("https://maple-api.marizma.games/v1/server/players", headers=headers_api)
            if resp.status_code == 200:
                data = resp.json()
                players = data.get("data", {}).get("Players", [])
                player_count = len(players)
        except Exception:
            pass
        embed = get_embed("Low Players", player_count=player_count)
        await session_channel.send(f"{session_ping}", embed=embed)
        await interaction.followup.send("✅ Low player alert sent.", ephemeral=True)

    elif action.value == "Session Cancellation":
        embed = get_embed("Session Cancellation")
        await session_channel.send(f"{session_ping}", embed=embed)
        await interaction.followup.send("✅ Session cancellation announced.", ephemeral=True)

    else:
        await interaction.followup.send("❌ Invalid action.", ephemeral=True)

@bot.tree.command(name="setbanner", description="Set a banner for the game server")
@app_commands.describe(banner="The banner text to set")
async def setbanner(interaction: discord.Interaction, banner: str):
    config = load_config(interaction.guild.id)
    if not config:
        await interaction.response.send_message("❌ This server is not configured. Use `/config` first.", ephemeral=True)
        return
    # 20498585101349
    if not any(role.id in config["announce_roles"] for role in interaction.user.roles):
        await interaction.response.send_message("❌ You do not have the required role to use this command.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    headers = {
        "X-Api-Key": config["api_key"],
        "Content-Type": "application/json"
    }
    data = {"banner": banner}
    try:
        resp = requests.post(
            "https://maple-api.marizma.games/v1/server/setbanner",
            headers=headers,
            data=json.dumps(data)
        )
        if resp.status_code == 200:
            embed = discord.Embed(title="🖼️ Banner Set", color=discord.Color.blue())
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
            embed.add_field(name="Banner", value=banner, inline=False)
            embed.timestamp = discord.utils.utcnow()
            log_channel = interaction.guild.get_channel(config["logs_channel"])
            if log_channel:
                await log_channel.send(embed=embed)
            await interaction.followup.send(f"✅ Banner set: `{banner}`", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ Failed to set banner. Status: {resp.status_code}\n{resp.text}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="promote", description="Promote a user and log the action")
@app_commands.describe(user="User to promote", past_rank="Previous rank", new_rank="New rank", reason="Reason for promotion")
async def promote(interaction: discord.Interaction, user: discord.Member, past_rank: str, new_rank: str, reason: str):
    if not interaction.user.guild_permissions.manage_roles:
        return await interaction.response.send_message("❌ You need the Manage Roles permission to use this command.", ephemeral=True)
    config = load_config(interaction.guild.id)
    if not config:
        return await interaction.response.send_message("❌ Bot not configured. Use /config.", ephemeral=True)
    await interaction.response.defer(thinking=True)
    embed = discord.Embed(title="⬆️ User Promoted", color=discord.Color.green())
    embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=False)
    embed.add_field(name="Past Rank", value=past_rank, inline=True)
    embed.add_field(name="New Rank", value=new_rank, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
    embed.timestamp = discord.utils.utcnow()
    embed.set_thumbnail(url=user.display_avatar.url)
    log_channel = interaction.guild.get_channel(config["logs_channel"])
    if log_channel:
        await log_channel.send(embed=embed)
    try:
        await user.send(embed=embed)
    except Exception:
        pass
    await interaction.followup.send(f"✅ Promoted {user.mention}.", ephemeral=True)

@bot.tree.command(name="demote", description="Demote a user and log the action")
@app_commands.describe(user="User to demote", past_rank="Previous rank", new_rank="New rank", reason="Reason for demotion")
async def demote(interaction: discord.Interaction, user: discord.Member, past_rank: str, new_rank: str, reason: str):
    if not interaction.user.guild_permissions.manage_roles:
        return await interaction.response.send_message("❌ You need the Manage Roles permission to use this command.", ephemeral=True)
    config = load_config(interaction.guild.id)
    if not config:
        return await interaction.response.send_message("❌ Bot not configured. Use /config.", ephemeral=True)
    await interaction.response.defer(thinking=True)
    embed = discord.Embed(title="⬇️ User Demoted", color=discord.Color.red())
    embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=False)
    embed.add_field(name="Past Rank", value=past_rank, inline=True)
    embed.add_field(name="New Rank", value=new_rank, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
    embed.timestamp = discord.utils.utcnow()
    embed.set_thumbnail(url=user.display_avatar.url)
    log_channel = interaction.guild.get_channel(config["logs_channel"])
    if log_channel:
        await log_channel.send(embed=embed)
    try:
        await user.send(embed=embed)
    except Exception:
        pass
    await interaction.followup.send(f"✅ Demoted {user.mention}.", ephemeral=True)

# --- /config (guided setup) ---
from discord import ui, TextChannel, Embed

class ConfigSession:
    def __init__(self, user_id, guild_id):
        self.user_id = user_id
        self.guild_id = guild_id
        self.api_key = None
        self.announce_role = None
        self.updates_channel = None
        self.logs_channel = None
        self.ingame_perms = None
        self.server_code = None
        self.session_ping = None
        self.session_perms = None
        self.session_channel = None
        self.welcoming_channel = None
        self.welcome_text = None
        self.session_ssu_banner = None
        self.session_ssd_banner = None
        self.step = 0
        self.message = None
        self.cancelled = False

config_sessions = {}

class StartConfigView(discord.ui.View):
    def __init__(self, author_id, session_id):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.session_id = session_id

    @discord.ui.button(label="Start Configuration", style=discord.ButtonStyle.green)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Only the command author can start the configuration.", ephemeral=True)
            return
        try:
            await interaction.message.delete()
        except discord.NotFound:
            pass
        await start_config_steps(interaction, self.session_id)

    @discord.ui.button(label="Delete Configuration", style=discord.ButtonStyle.red)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Only the command author can delete the configuration.", ephemeral=True)
            return
        await interaction.message.delete()
        config_sessions.pop(self.session_id, None)
        await interaction.response.send_message("Configuration cancelled.", ephemeral=True)

class ConfirmConfigView(discord.ui.View):
    def __init__(self, author_id, session_id):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.session_id = session_id
        self.value = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, buttoSn: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Only the command author can confirm.", ephemeral=True)
            return
        self.value = True
        self.stop()
        await interaction.message.delete()
        await save_config_to_db(interaction, self.session_id)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.red)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Only the command author can reject.", ephemeral=True)
            return
        self.value = False
        self.stop()
        await interaction.message.delete()
        config_sessions.pop(self.session_id, None)
        await interaction.response.send_message("Configuration cancelled.", ephemeral=True)

async def start_config_steps(interaction, session_id):
    # Check for administrator permission
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only server administrators can start the configuration.", ephemeral=True)
        return
    session = config_sessions.get(session_id)
    if not session:
        return
    user = interaction.user
    guild = interaction.guild
    channel = interaction.channel
    def check(m):
        return m.author.id == user.id and m.channel.id == channel.id
    async def cancel_callback(interaction):
        if interaction.user.id != user.id:
            await interaction.response.send_message("Only the command author can cancel.", ephemeral=True)
            return
        config_sessions.pop(session_id, None)
        await interaction.message.delete()
        await interaction.response.send_message("Configuration cancelled.", ephemeral=True)
    embed = discord.Embed(title="Step 1: API Key", description="Please reply with your Maple Server API Key.\n[How to find your API Key](https://api-docs.marizma.games/for-developers/api-keys)\n\nYou can cancel at any time with the button below.", color=discord.Color.blurple())
    view = discord.ui.View()
    btn1 = discord.ui.Button(label="Delete Configuration", style=discord.ButtonStyle.red, custom_id="cancel")
    btn1.callback = cancel_callback
    view.add_item(btn1)
    msg = await channel.send(embed=embed, view=view)
    try:
        reply = await bot.wait_for('message', check=check, timeout=180)
        session.api_key = reply.content.strip()
        await msg.delete()
        await reply.delete()
    except asyncio.TimeoutError:
        await msg.delete()
        config_sessions.pop(session_id, None)
        await channel.send("Configuration timed out.", delete_after=10)
        return
    embed = discord.Embed(title="Step 2: Announcement Role", description="Please mention the role to use for remote announcements (e.g. @Announcements).\n\nYou can cancel at any time with the button below.", color=discord.Color.blurple())
    view = discord.ui.View()
    btn2 = discord.ui.Button(label="Delete Configuration", style=discord.ButtonStyle.red, custom_id="cancel2")
    btn2.callback = cancel_callback
    view.add_item(btn2)
    msg = await channel.send(embed=embed, view=view)
    try:
        reply = await bot.wait_for('message', check=check, timeout=180)
        if not reply.role_mentions:
            await reply.delete()
            await msg.delete()
            await channel.send("You must mention a role. Configuration cancelled.", delete_after=10)
            config_sessions.pop(session_id, None)
            return
        session.announce_role = reply.role_mentions[0]
        await msg.delete()
        await reply.delete()
    except asyncio.TimeoutError:
        await msg.delete()
        config_sessions.pop(session_id, None)
        await channel.send("Configuration timed out.", delete_after=10)
        return
    # Step 3: Updates Channel
    embed = discord.Embed(title="Step 3: Updates Channel", description="Please mention the channel to use for updates (e.g. #updates).\n\nYou can cancel at any time with the button below.", color=discord.Color.blurple())
    view = discord.ui.View()
    btn3 = discord.ui.Button(label="Delete Configuration", style=discord.ButtonStyle.red, custom_id="cancel3")
    btn3.callback = cancel_callback
    view.add_item(btn3)
    msg = await channel.send(embed=embed, view=view)
    try:
        reply = await bot.wait_for('message', check=check, timeout=180)
        if not reply.channel_mentions:
            await reply.delete()
            await msg.delete()
            await channel.send("You must mention a channel. Configuration cancelled.", delete_after=10)
            config_sessions.pop(session_id, None)
            return
        session.updates_channel = reply.channel_mentions[0]
        await msg.delete()
        await reply.delete()
    except asyncio.TimeoutError:
        await msg.delete()
        config_sessions.pop(session_id, None)
        await channel.send("Configuration timed out.", delete_after=10)
        return
    embed = discord.Embed(title="Step 4: Logs Channel", description="Please mention the channel to use for logs (e.g. #logs).\n\nYou can cancel at any time with the button below.", color=discord.Color.blurple())
    view = discord.ui.View()
    btn4 = discord.ui.Button(label="Delete Configuration", style=discord.ButtonStyle.red, custom_id="cancel4")
    btn4.callback = cancel_callback
    view.add_item(btn4)
    msg = await channel.send(embed=embed, view=view)
    try:
        reply = await bot.wait_for('message', check=check, timeout=180)
        if not reply.channel_mentions:
            await reply.delete()
            await msg.delete()
            await channel.send("You must mention a channel. Configuration cancelled.", delete_after=10)
            config_sessions.pop(session_id, None)
            return
        session.logs_channel = reply.channel_mentions[0]
        await msg.delete()
        await reply.delete()
    except asyncio.TimeoutError:
        await msg.delete()
        config_sessions.pop(session_id, None)
        await channel.send("Configuration timed out.", delete_after=10)
        return
    embed = discord.Embed(title="Step 5: In-Game Moderator Permission", description="Please mention the role that will have in-game moderator permissions.\n\nYou can cancel at any time with the button below.", color=discord.Color.blurple())
    view = discord.ui.View()
    btn5 = discord.ui.Button(label="Delete Configuration", style=discord.ButtonStyle.red, custom_id="cancel5")
    btn5.callback = cancel_callback
    view.add_item(btn5)
    msg = await channel.send(embed=embed, view=view)
    try:
        reply = await bot.wait_for('message', check=check, timeout=180)
        if not reply.role_mentions:
            await reply.delete()
            await msg.delete()
            await channel.send("You must mention a role. Configuration cancelled.", delete_after=10)
            config_sessions.pop(session_id, None)
            return
        session.ingame_perms = str(reply.role_mentions[0].id)
        await msg.delete()
        await reply.delete()
    except asyncio.TimeoutError:
        await msg.delete()
        config_sessions.pop(session_id, None)
        await channel.send("Configuration timed out.", delete_after=10)
        return
    embed = discord.Embed(title="Session Configuration: Server Code", description="Please enter the Server Code (e.g. d23-fd8).\n\nYou can cancel at any time with the button below.", color=discord.Color.blurple())
    view = discord.ui.View()
    btn6 = discord.ui.Button(label="Delete Configuration", style=discord.ButtonStyle.red, custom_id="cancel6")
    btn6.callback = cancel_callback
    view.add_item(btn6)
    msg = await channel.send(embed=embed, view=view)
    try:
        reply = await bot.wait_for('message', check=check, timeout=180)
        session.server_code = reply.content.strip()
        await msg.delete()
        await reply.delete()
    except asyncio.TimeoutError:
        await msg.delete()
        config_sessions.pop(session_id, None)
        await channel.send("Configuration timed out.", delete_after=10)
        return
    embed = discord.Embed(title="Session Configuration: Session Ping", description="Please enter the Session Ping (e.g. @everyone or @role).\n\nYou can cancel at any time with the button below.", color=discord.Color.blurple())
    view = discord.ui.View()
    btn7 = discord.ui.Button(label="Delete Configuration", style=discord.ButtonStyle.red, custom_id="cancel7")
    btn7.callback = cancel_callback
    view.add_item(btn7)
    msg = await channel.send(embed=embed, view=view)
    try:
        reply = await bot.wait_for('message', check=check, timeout=180)
        session.session_ping = reply.content.strip()
        await msg.delete()
        await reply.delete()
    except asyncio.TimeoutError:
        await msg.delete()
        config_sessions.pop(session_id, None)
        await channel.send("Configuration timed out.", delete_after=10)
        return
    embed = discord.Embed(title="Session Configuration: Session Permission Role", description="Please mention the role that will have session permissions.\n\nYou can cancel at any time with the button below.", color=discord.Color.blurple())
    view = discord.ui.View()
    btn8 = discord.ui.Button(label="Delete Configuration", style=discord.ButtonStyle.red, custom_id="cancel8")
    btn8.callback = cancel_callback
    view.add_item(btn8)
    msg = await channel.send(embed=embed, view=view)
    try:
        reply = await bot.wait_for('message', check=check, timeout=180)
        if not reply.role_mentions:
            await reply.delete()
            await msg.delete()
            await channel.send("You must mention a role. Configuration cancelled.", delete_after=10)
            config_sessions.pop(session_id, None)
            return
        session.session_perms = str(reply.role_mentions[0].id)
        await msg.delete()
        await reply.delete()
    except asyncio.TimeoutError:
        await msg.delete()
        config_sessions.pop(session_id, None)
        await channel.send("Configuration timed out.", delete_after=10)
        return
    embed = discord.Embed(title="Session Configuration: Session Channel", description="Please mention the channel to use for sessions (e.g. #sessions).\n\nYou can cancel at any time with the button below.", color=discord.Color.blurple())
    view = discord.ui.View()
    btn9 = discord.ui.Button(label="Delete Configuration", style=discord.ButtonStyle.red, custom_id="cancel9")
    btn9.callback = cancel_callback
    view.add_item(btn9)
    msg = await channel.send(embed=embed, view=view)
    try:
        reply = await bot.wait_for('message', check=check, timeout=180)
        if not reply.channel_mentions:
            await reply.delete()
            await msg.delete()
            await channel.send("You must mention a channel. Configuration cancelled.", delete_after=10)
            config_sessions.pop(session_id, None)
            return
        session.session_channel = str(reply.channel_mentions[0].id)
        await msg.delete()
        await reply.delete()
    except asyncio.TimeoutError:
        await msg.delete()
        config_sessions.pop(session_id, None)
        await channel.send("Configuration timed out.", delete_after=10)
        return
    # Welcoming Channel Step
    embed = discord.Embed(
        title="Welcoming Configuration: Welcoming Channel",
        description=(
            "Please mention the channel to use for welcoming new users (e.g. #welcome).\n\n"
            "You can cancel or skip this step with the buttons below."
        ),
        color=discord.Color.blurple()
    )
    view = discord.ui.View()
    btn_skip = discord.ui.Button(label="Skip", style=discord.ButtonStyle.gray)
    async def skip_callback(interaction: discord.Interaction):
        if interaction.user.id != user.id:
            await interaction.response.send_message("Only the command author can skip.", ephemeral=True)
            return
        session.welcoming_channel = None
        await interaction.message.delete()
        # Go to next step: Welcome Text
        embed2 = discord.Embed(
            title="Welcoming Configuration: Welcome Text",
            description="Please enter the welcome text for new users.\n\nYou can use variables like `{user}` for the username.\n\nYou can cancel or skip this step with the buttons below.",
            color=discord.Color.blurple()
        )
        view2 = discord.ui.View()
        btn_skip_text = discord.ui.Button(label="Skip", style=discord.ButtonStyle.gray)
        async def skip_text_callback(interaction2: discord.Interaction):
            if interaction2.user.id != user.id:
                await interaction2.response.send_message("Only the command author can skip.", ephemeral=True)
                return
            session.welcome_text = None
            await interaction2.message.delete()
            # Show config summary
            embed_summary = discord.Embed(
                title="✅ Configuration Complete",
                description="The server configuration is complete! Here's a summary:",
                color=discord.Color.green()
            )
            welcoming_channel_obj = bot.get_channel(int(session.welcoming_channel)) if session.welcoming_channel else None
            config_summary = (
                f"**API Key:** ||Hidden||\n"
                f"**Announcement Role:** {session.announce_role.mention if session.announce_role else 'None'}\n"
                f"**Updates Channel:** {session.updates_channel.mention if session.updates_channel else 'None'}\n"
                f"**Logs Channel:** {session.logs_channel.mention if session.logs_channel else 'None'}\n"
                f"**In-Game Moderator Permission:** {session.ingame_perms}\n"
                f"**Server Code:** {session.server_code}\n"
                f"**Session Ping:** {session.session_ping}\n"
                f"**Session Permission Role:** {session.session_perms}\n"
                f"**Session Channel:** {session.session_channel}\n"
                f"**Welcoming Channel:** {welcoming_channel_obj.mention if welcoming_channel_obj else 'None'}\n"
                f"**Welcome Text:** {session.welcome_text}"
            )
            embed_summary.add_field(name="Configuration Summary", value=config_summary, inline=False)
            embed_summary.set_footer(text="Maple Server • Configuration")
            view_summary = ConfirmConfigView(user.id, session_id)
            await channel.send(embed=embed_summary, view=view_summary)
        btn_skip_text.callback = skip_text_callback
        view2.add_item(btn_skip_text)
        btn_cancel_text = discord.ui.Button(label="Delete Configuration", style=discord.ButtonStyle.red, custom_id="cancel11")
        btn_cancel_text.callback = cancel_callback
        view2.add_item(btn_cancel_text)
        msg2 = await channel.send(embed=embed2, view=view2)
        try:
            reply2 = await bot.wait_for('message', check=check, timeout=180)
            session.welcome_text = reply2.content.strip()
            await msg2.delete()
            await reply2.delete()
            # Show config summary
            embed_summary = discord.Embed(
                title="✅ Configuration Complete",
                description="The server configuration is complete! Here's a summary:",
                color=discord.Color.green()
            )
            welcoming_channel_obj = bot.get_channel(int(session.welcoming_channel)) if session.welcoming_channel else None
            config_summary = (
                f"**API Key:** ||Hidden||\n"
                f"**Announcement Role:** {session.announce_role.mention if session.announce_role else 'None'}\n"
                f"**Updates Channel:** {session.updates_channel.mention if session.updates_channel else 'None'}\n"
                f"**Logs Channel:** {session.logs_channel.mention if session.logs_channel else 'None'}\n"
                f"**In-Game Moderator Permission:** {session.ingame_perms}\n"
                f"**Server Code:** {session.server_code}\n"
                f"**Session Ping:** {session.session_ping}\n"
                f"**Session Permission Role:** {session.session_perms}\n"
                f"**Session Channel:** {session.session_channel}\n"
                f"**Welcoming Channel:** {welcoming_channel_obj.mention if welcoming_channel_obj else 'None'}\n"
                f"**Welcome Text:** {session.welcome_text}"
            )
            embed_summary.add_field(name="Configuration Summary", value=config_summary, inline=False)
            embed_summary.set_footer(text="Maple Server • Configuration")
            view_summary = ConfirmConfigView(user.id, session_id)
            await channel.send(embed=embed_summary, view=view_summary)
        except asyncio.TimeoutError:
            await msg2.delete()
            config_sessions.pop(session_id, None)
            await channel.send("Configuration timed out.", delete_after=10)
        return
    btn_skip.callback = skip_callback
    view.add_item(btn_skip)
    btn_cancel = discord.ui.Button(label="Delete Configuration", style=discord.ButtonStyle.red, custom_id="cancel10")
    btn_cancel.callback = cancel_callback
    view.add_item(btn_cancel)
    msg = await channel.send(embed=embed, view=view)
    try:
        reply = await bot.wait_for('message', check=check, timeout=180)
        if reply.content.lower() == "skip":
            session.welcoming_channel = None
            await msg.delete()
            await reply.delete()
            # Go to next step: Welcome Text (same as skip_callback above)
            embed2 = discord.Embed(
                title="Welcoming Configuration: Welcome Text",
                description="Please enter the welcome text for new users.\n\nYou can use variables like `{user}` for the username.\n\nYou can cancel or skip this step with the buttons below.",
                color=discord.Color.blurple()
            )
            view2 = discord.ui.View()
            btn_skip_text = discord.ui.Button(label="Skip", style=discord.ButtonStyle.gray)
            async def skip_text_callback(interaction2: discord.Interaction):
                if interaction2.user.id != user.id:
                    await interaction2.response.send_message("Only the command author can skip.", ephemeral=True)
                    return
                session.welcome_text = None
                await interaction2.message.delete()
                # Show config summary
                embed_summary = discord.Embed(
                    title="✅ Configuration Complete",
                    description="The server configuration is complete! Here's a summary:",
                    color=discord.Color.green()
                )
                welcoming_channel_obj = bot.get_channel(int(session.welcoming_channel)) if session.welcoming_channel else None
                config_summary = (
                    f"**API Key:** ||Hidden||\n"
                    f"**Announcement Role:** {session.announce_role.mention if session.announce_role else 'None'}\n"
                    f"**Updates Channel:** {session.updates_channel.mention if session.updates_channel else 'None'}\n"
                    f"**Logs Channel:** {session.logs_channel.mention if session.logs_channel else 'None'}\n"
                    f"**In-Game Moderator Permission:** {session.ingame_perms}\n"
                    f"**Server Code:** {session.server_code}\n"
                    f"**Session Ping:** {session.session_ping}\n"
                    f"**Session Permission Role:** {session.session_perms}\n"
                    f"**Session Channel:** {session.session_channel}\n"
                    f"**Welcoming Channel:** {welcoming_channel_obj.mention if welcoming_channel_obj else 'None'}\n"
                    f"**Welcome Text:** {session.welcome_text}"
                )
                embed_summary.add_field(name="Configuration Summary", value=config_summary, inline=False)
                embed_summary.set_footer(text="Maple Server • Configuration")
                view_summary = ConfirmConfigView(user.id, session_id)
                await channel.send(embed=embed_summary, view=view_summary)
            btn_skip_text.callback = skip_text_callback
            view2.add_item(btn_skip_text)
            btn_cancel_text = discord.ui.Button(label="Delete Configuration", style=discord.ButtonStyle.red, custom_id="cancel11")
            btn_cancel_text.callback = cancel_callback
            view2.add_item(btn_cancel_text)
            msg2 = await channel.send(embed=embed2, view=view2)
            try:
                reply2 = await bot.wait_for('message', check=check, timeout=180)
                session.welcome_text = reply2.content.strip()
                await msg2.delete()
                await reply2.delete()
                # Show config summary
                embed_summary = discord.Embed(
                    title="✅ Configuration Complete",
                    description="The server configuration is complete! Here's a summary:",
                    color=discord.Color.green()
                )
                welcoming_channel_obj = bot.get_channel(int(session.welcoming_channel)) if session.welcoming_channel else None
                config_summary = (
                    f"**API Key:** ||Hidden||\n"
                    f"**Announcement Role:** {session.announce_role.mention if session.announce_role else 'None'}\n"
                    f"**Updates Channel:** {session.updates_channel.mention if session.updates_channel else 'None'}\n"
                    f"**Logs Channel:** {session.logs_channel.mention if session.logs_channel else 'None'}\n"
                    f"**In-Game Moderator Permission:** {session.ingame_perms}\n"
                    f"**Server Code:** {session.server_code}\n"
                    f"**Session Ping:** {session.session_ping}\n"
                    f"**Session Permission Role:** {session.session_perms}\n"
                    f"**Session Channel:** {session.session_channel}\n"
                    f"**Welcoming Channel:** {welcoming_channel_obj.mention if welcoming_channel_obj else 'None'}\n"
                    f"**Welcome Text:** {session.welcome_text}"
                )
                embed_summary.add_field(name="Configuration Summary", value=config_summary, inline=False)
                embed_summary.set_footer(text="Maple Server • Configuration")
                view_summary = ConfirmConfigView(user.id, session_id)
                await channel.send(embed=embed_summary, view=view_summary)
            except asyncio.TimeoutError:
                await msg2.delete()
                config_sessions.pop(session_id, None)
                await channel.send("Configuration timed out.", delete_after=10)
            return
        if not reply.channel_mentions:
            await reply.delete()
            await msg.delete()
            await channel.send("You must mention a channel. Configuration cancelled.", delete_after=10)
            config_sessions.pop(session_id, None)
            return
        session.welcoming_channel = str(reply.channel_mentions[0].id)
        await msg.delete()
        await reply.delete()
    except asyncio.TimeoutError:
        await msg.delete()
        config_sessions.pop(session_id, None)
        await channel.send("Configuration timed out.", delete_after=10)
        return

    # Welcome Text Step (if not skipped)
    embed = discord.Embed(
        title="Welcoming Configuration: Welcome Text",
        description="Please enter the welcome text for new users.\n\nYou can use variables like `{user}` for the username.\n\nYou can cancel or skip this step with the buttons below.",
        color=discord.Color.blurple()
    )
    view = discord.ui.View()
    btn_skip_text = discord.ui.Button(label="Skip", style=discord.ButtonStyle.gray)
    async def skip_text_callback(interaction: discord.Interaction):
        if interaction.user.id != user.id:
            await interaction.response.send_message("Only the command author can skip.", ephemeral=True)
            return
        session.welcome_text = None
        await interaction.message.delete()
        # Show config summary
        embed_summary = discord.Embed(
            title="✅ Configuration Complete",
            description="The server configuration is complete! Here's a summary:",
            color=discord.Color.green()
        )
        welcoming_channel_obj = bot.get_channel(int(session.welcoming_channel)) if session.welcoming_channel else None
        config_summary = (
            f"**API Key:** ||Hidden||\n"
            f"**Announcement Role:** {session.announce_role.mention if session.announce_role else 'None'}\n"
            f"**Updates Channel:** {session.updates_channel.mention if session.updates_channel else 'None'}\n"
            f"**Logs Channel:** {session.logs_channel.mention if session.logs_channel else 'None'}\n"
            f"**In-Game Moderator Permission:** {session.ingame_perms}\n"
            f"**Server Code:** {session.server_code}\n"
            f"**Session Ping:** {session.session_ping}\n"
            f"**Session Permission Role:** {session.session_perms}\n"
            f"**Session Channel:** {session.session_channel}\n"
            f"**Welcoming Channel:** {welcoming_channel_obj.mention if welcoming_channel_obj else 'None'}\n"
            f"**Welcome Text:** {session.welcome_text}"
        )
        embed_summary.add_field(name="Configuration Summary", value=config_summary, inline=False)
        embed_summary.set_footer(text="Maple Server • Configuration")
        view_summary = ConfirmConfigView(user.id, session_id)
        await channel.send(embed=embed_summary, view=view_summary)
    btn_skip_text.callback = skip_text_callback
    view.add_item(btn_skip_text)
    btn_cancel_text = discord.ui.Button(label="Delete Configuration", style=discord.ButtonStyle.red, custom_id="cancel11")
    btn_cancel_text.callback = cancel_callback
    view.add_item(btn_cancel_text)
    msg = await channel.send(embed=embed, view=view)
    try:
        reply = await bot.wait_for('message', check=check, timeout=180)
        session.welcome_text = reply.content.strip()
        await msg.delete()
        await reply.delete()
        # Show config summary
        embed_summary = discord.Embed(
            title="✅ Configuration Complete",
            description="The server configuration is complete! Here's a summary:",
            color=discord.Color.green()
        )
        welcoming_channel_obj = bot.get_channel(int(session.welcoming_channel)) if session.welcoming_channel else None
        config_summary = (
            f"**API Key:** ||Hidden||\n"
            f"**Announcement Role:** {session.announce_role.mention if session.announce_role else 'None'}\n"
            f"**Updates Channel:** {session.updates_channel.mention if session.updates_channel else 'None'}\n"
            f"**Logs Channel:** {session.logs_channel.mention if session.logs_channel else 'None'}\n"
            f"**In-Game Moderator Permission:** {session.ingame_perms}\n"
            f"**Server Code:** {session.server_code}\n"
            f"**Session Ping:** {session.session_ping}\n"
            f"**Session Permission Role:** {session.session_perms}\n"
            f"**Session Channel:** {session.session_channel}\n"
            f"**Welcoming Channel:** {welcoming_channel_obj.mention if welcoming_channel_obj else 'None'}\n"
            f"**Welcome Text:** {session.welcome_text}"
        )
        embed_summary.add_field(name="Configuration Summary", value=config_summary, inline=False)
        embed_summary.set_footer(text="Maple Server • Configuration")
        view_summary = ConfirmConfigView(user.id, session_id)
        await channel.send(embed=embed_summary, view=view_summary)
    except asyncio.TimeoutError:
        await msg.delete()
        config_sessions.pop(session_id, None)
        await channel.send("Configuration timed out.", delete_after=10)
        return

# --- /config (guided setup) ---
@bot.tree.command(name="config", description="Start the guided onboarding configuration")
async def onboarding(interaction: discord.Interaction):
    config = load_config(interaction.guild.id)
    if config:
        return await interaction.response.send_message("❌ This server is already configured. Use `/config-view` to see the current configuration.", ephemeral=True)
    session_id = str(interaction.guild.id)
    config_sessions[session_id] = ConfigSession(interaction.user.id, interaction.guild.id)
    embed = discord.Embed(title="Welcome to Maple Server Bot!", description="Let's get your server configured. This will only take a few minutes.", color=discord.Color.green())
    embed.add_field(name="How it works", value="I'll guide you through the configuration steps. You can cancel at any time.", inline=False)
    embed.add_field(name="Start", value="Click the button below to start the configuration.", inline=False)
    view = StartConfigView(interaction.user.id, session_id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

import io
from discord import File

async def send_webhook_embed(guild_id, embed, file=None):
    config = load_config(guild_id)
    webhook_url = config.get("webhook_url") if config else None
    if not webhook_url:
        return
    import requests
    from discord import SyncWebhook
    try:
        webhook = SyncWebhook.from_url(webhook_url)
        if file:
            webhook.send(embed=embed, file=file)
        else:
            webhook.send(embed=embed)
    except Exception as e:
        print(f"Webhook send error: {e}")

# --- MEMBER JOIN ---
@bot.event
async def on_member_join(member):
    config = load_config(member.guild.id)
    if not config:
        return
    if not config.get("webhook_url"):
        return
    embed = discord.Embed(title="👤 Member Joined", color=discord.Color.green())
    embed.add_field(name="User", value=f"{member.mention} ({member.id})", inline=False)
    embed.set_thumbnail(url=member.avatar.url if member.avatar else discord.Embed.Empty)
    embed.timestamp = discord.utils.utcnow()
    await send_webhook_embed(member.guild.id, embed)
    
@bot.event    
async def on_member_join(member):
    config = load_config(member.guild.id)
    if not config or not config.get("welcoming_channel") or not config.get("welcome_text"):
        return
    channel = member.guild.get_channel(int(config["welcoming_channel"]))
    if not channel:
        return
    welcome_text = config["welcome_text"].replace("{user}", member.mention)
    embed = discord.Embed(
    title="👋 Welcome {}".format(member.display_name),
    description=welcome_text,
    color=discord.Color.from_rgb(114, 137, 218)
)
    
    embed.set_thumbnail(url=member.display_avatar.url)
    await channel.send(embed=embed)   
    
# --- MEMBER LEAVE ---
@bot.event
async def on_member_remove(member):
    config = load_config(member.guild.id)
    if not config:
        return
    if not config.get("webhook_url"):
        return
    embed = discord.Embed(title="🚪 Member Left", color=discord.Color.red())
    embed.add_field(name="User", value=f"{member.mention} ({member.id})", inline=False)
    embed.set_thumbnail(url=member.avatar.url if member.avatar else discord.Embed.Empty)
    embed.timestamp = discord.utils.utcnow()
    await send_webhook_embed(member.guild.id, embed)

# --- ROLE CREATE ---
@bot.event
async def on_guild_role_create(role):
    config = load_config(role.guild.id)
    if not config:
        return
    if not config.get("webhook_url"):
        return
    embed = discord.Embed(title="🆕 Role Created", color=discord.Color.blue())
    embed.add_field(name="Role", value=f"{role.name} ({role.id})", inline=False)
    embed.timestamp = discord.utils.utcnow()
    await send_webhook_embed(role.guild.id, embed)

# --- ROLE DELETE ---
@bot.event
async def on_guild_role_delete(role):
    config = load_config(role.guild.id)
    if not config:
        return
    if not config.get("webhook_url"):
        return
    embed = discord.Embed(title="❌ Role Deleted", color=discord.Color.red())
    embed.add_field(name="Role", value=f"{role.name} ({role.id})", inline=False)
    embed.timestamp = discord.utils.utcnow()
    await send_webhook_embed(role.guild.id, embed)

# --- ROLE UPDATE ---
@bot.event
async def on_guild_role_update(before, after):
    config = load_config(after.guild.id)
    if not config:
        return
    if not config.get("webhook_url"):
        return
    embed = discord.Embed(title="✏️ Role Updated", color=discord.Color.orange())
    embed.add_field(name="Before Name", value=f"{before.name}", inline=True)
    embed.add_field(name="After Name", value=f"{after.name}", inline=True)
    # Check for permission changes
    if before.permissions != after.permissions:
        perms_before = [p for p, v in before.permissions if v]
        perms_after = [p for p, v in after.permissions if v]
        added = set(perms_after) - set(perms_before)
        removed = set(perms_before) - set(perms_after)
        if added:
            embed.add_field(name="Permissions Added", value=", ".join(added), inline=False)
        if removed:
            embed.add_field(name="Permissions Removed", value=", ".join(removed), inline=False)
    embed.timestamp = discord.utils.utcnow()
    await send_webhook_embed(after.guild.id, embed)

# --- CHANNEL CREATE ---
@bot.event
async def on_guild_channel_create(channel):
    config = load_config(channel.guild.id)
    if not config:
        return
    if not config.get("webhook_url"):
        return
    embed = discord.Embed(title="📺 Channel Created", color=discord.Color.blue())
    embed.add_field(name="Channel", value=f"{channel.name} ({channel.id})", inline=False)
    embed.timestamp = discord.utils.utcnow()
    await send_webhook_embed(channel.guild.id, embed)

# --- CHANNEL DELETE ---
@bot.event
async def on_guild_channel_delete(channel):
    config = load_config(channel.guild.id)
    if not config:
        return
    if not config.get("webhook_url"):
        return
    embed = discord.Embed(title="❌ Channel Deleted", color=discord.Color.red())
    embed.add_field(name="Channel", value=f"{channel.name} ({channel.id})", inline=False)
    embed.timestamp = discord.utils.utcnow()
    await send_webhook_embed(channel.guild.id, embed)

# --- CHANNEL UPDATE ---
@bot.event
async def on_guild_channel_update(before, after):
    config = load_config(after.guild.id)
    if not config:
        return
    if not config.get("webhook_url"):
        return
    embed = discord.Embed(title="✏️ Channel Updated", color=discord.Color.orange())
    embed.add_field(name="Before Name", value=f"{before.name}", inline=True)
    embed.add_field(name="After Name", value=f"{after.name}", inline=True)
    # Check for permission overwrites changes
    if before.overwrites != after.overwrites:
        perms_before = {str(target): perms._values for target, perms in before.overwrites.items()}
        perms_after = {str(target): perms._values for target, perms in after.overwrites.items()}
        added = set(perms_after.keys()) - set(perms_before.keys())
        removed = set(perms_before.keys()) - set(perms_after.keys())
        changed = [t for t in perms_before if t in perms_after and perms_before[t] != perms_after[t]]
        if added:
            embed.add_field(name="Permissions Added For", value=", ".join(added), inline=False)
        if removed:
            embed.add_field(name="Permissions Removed For", value=", ".join(removed), inline=False)
        for t in changed:
            embed.add_field(name=f"Permissions Changed For {t}", value=f"Before: {perms_before[t]}\nAfter: {perms_after[t]}", inline=False)
    embed.timestamp = discord.utils.utcnow()
    await send_webhook_embed(after.guild.id, embed)

# --- EMOJI CREATE/DELETE ---
@bot.event
async def on_guild_emojis_update(guild, before, after):
    config = load_config(guild.id)
    if not config:
        return
    if not config.get("webhook_url"):
        return
    before_set = set(e.id for e in before)
    after_set = set(e.id for e in after)
    added = [e for e in after if e.id not in before_set]
    removed = [e for e in before if e.id not in after_set]
    if added:
        for emoji in added:
            embed = discord.Embed(title="😀 Emoji Added", color=discord.Color.green())
            embed.add_field(name="Emoji", value=f"{str(emoji)} ({emoji.id})", inline=False)
            embed.timestamp = discord.utils.utcnow()
            await send_webhook_embed(guild.id, embed)
    if removed:
        for emoji in removed:
            embed = discord.Embed(title="❌ Emoji Removed", color=discord.Color.red())
            embed.add_field(name="Emoji", value=f"{str(emoji)} ({emoji.id})", inline=False)
            embed.timestamp = discord.utils.utcnow()
            await send_webhook_embed(guild.id, embed)

# --- VOICE STATE UPDATE ---
@bot.event
async def on_voice_state_update(member, before, after):
    config = load_config(member.guild.id)
    if not config:
        return
    if not config.get("webhook_url"):
        return
    if before.channel != after.channel:
        if after.channel:
            embed = discord.Embed(title="🔊 VC Joined", color=discord.Color.green())
            embed.add_field(name="User", value=f"{member.mention} ({member.id})", inline=False)
            embed.add_field(name="Channel", value=f"{after.channel.name}", inline=False)
            embed.timestamp = discord.utils.utcnow()
            await send_webhook_embed(member.guild.id, embed)
        if before.channel:
            embed = discord.Embed(title="🔈 VC Left", color=discord.Color.red())
            embed.add_field(name="User", value=f"{member.mention} ({member.id})", inline=False)
            embed.add_field(name="Channel", value=f"{before.channel.name}", inline=False)
            embed.timestamp = discord.utils.utcnow()
            await send_webhook_embed(member.guild.id, embed)

# --- MESSAGE UPDATE ---
@bot.event
async def on_message_edit(before, after):
    if before.author.bot:
        return
    config = load_config(before.guild.id) if before.guild else None
    webhook_url = config.get("webhook_url") if config else None
    if webhook_url:
        embed = discord.Embed(title="✏️ Message Edited", color=discord.Color.orange())
        embed.add_field(name="Author", value=f"{before.author.mention} ({before.author.id})", inline=False)
        embed.add_field(name="Channel", value=before.channel.mention, inline=False)
        embed.add_field(name="Before", value=before.content or "(empty)", inline=False)
        embed.add_field(name="After", value=after.content or "(empty)", inline=False)
        embed.timestamp = discord.utils.utcnow()
        await send_webhook_embed(before.guild.id, embed)

@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    config = load_config(message.guild.id) if message.guild else None
    webhook_url = config.get("webhook_url") if config else None
    if webhook_url:
        embed = discord.Embed(title="🗑️ Message Deleted", color=discord.Color.red())
        embed.add_field(name="Author", value=f"{message.author.mention} ({message.author.id})", inline=False)
        embed.add_field(name="Channel", value=message.channel.mention, inline=False)
        embed.add_field(name="Content", value=message.content or "(empty)", inline=False)
        embed.timestamp = discord.utils.utcnow()
        await send_webhook_embed(message.guild.id, embed)
        
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    try:
        if isinstance(error, app_commands.CommandOnCooldown):
            msg = f"⏳ This command is on cooldown. Please wait {error.retry_after:.2f} seconds."
        elif isinstance(error, app_commands.MissingPermissions):
            msg = "❌ You do not have permission to use this command."
        elif isinstance(error, app_commands.CommandNotFound):
            msg = "❌ Command not found."
        else:
            msg = f"❌ An unexpected error occurred: {str(error)}"
        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.followup.send(msg, ephemeral=True)
    except Exception:
        pass  

# /servers
@bot.tree.command(name="servers", description="List all servers using the bot, sorted by member count")
async def servers(interaction: discord.Interaction):
    allowed_ids = {1099013081683738676, 1044899567822454846}
    if interaction.user.id not in allowed_ids:
        await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
        return
    guilds_sorted = sorted(bot.guilds, key=lambda g: g.member_count, reverse=True)
    lines = []
    for g in guilds_sorted:
        lines.append(f"{g.name} | Members: {g.member_count} | Guild ID: {g.id}")
    if not lines:
        await interaction.response.send_message("No servers found.", ephemeral=True)
        return
    header = "**Servers using the bot:**\n"
    chunk = header
    for line in lines:
        if len(chunk) + len(line) + 1 > 2000:
            await interaction.followup.send(chunk, ephemeral=True)
            chunk = ""
        chunk += line + "\n"
    if chunk:
        await interaction.followup.send(chunk, ephemeral=True)

# /invite
@bot.tree.command(name="invite", description="Create a temporary invite for a server (developers only)")
@app_commands.describe(guild_id="Guild ID to create invite for")
async def invite(interaction: discord.Interaction, guild_id: str):
    allowed_ids = {1099013081683738676, 1044899567822454846}
    if interaction.user.id not in allowed_ids:
        await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
        return
    guild = discord.utils.get(bot.guilds, id=int(guild_id))
    if not guild:
        await interaction.response.send_message("❌ Guild not found or bot is not in that guild.", ephemeral=True)
        return
    target_channel = None
    for ch in guild.text_channels:
        perms = ch.permissions_for(guild.me)
        if perms.create_instant_invite:
            target_channel = ch
            break
    if not target_channel:
        await interaction.response.send_message("❌ No channel found where bot can create invites.", ephemeral=True)
        return
    invite_obj = await target_channel.create_invite(max_age=300, max_uses=1, unique=True)
    await interaction.response.send_message(f"Invite for **{guild.name}**: {invite_obj.url}", ephemeral=True)


# Start
import discord
from discord.ext import commands
import wavelink
import asyncio
import os

@bot.event
async def on_ready():
    print(f"Bot is logged in as {bot.user.name} ({bot.user.id})")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="🏥 Maple Communities"))

    # Sync commands and detailed logs
    try:
        synced = await bot.tree.sync()
        print(f"[SYNC] Synced {len(synced)} commands: {[cmd.name for cmd in synced]}")
    except Exception as e:
        print(f"[SYNC][ERROR] Error syncing commands: {e}")

    # Log ticket commands
    ticket_cmds = [cmd for cmd in bot.tree.get_commands() if 'ticket' in cmd.name]
    print(f"[TICKET] Registered ticket commands: {[cmd.name for cmd in ticket_cmds]}")

    # Connect to Lavalink with detailed logs
    try:
        await wavelink.Pool.connect(
            client=bot,
            nodes=[
                wavelink.Node(
                    uri="http://localhost:5001",
                    password="CoreBot25"
                )
            ]
        )
        print("[LAVALINK] Connected to Lavalink.")
    except Exception as e:
        print(f"[LAVALINK][ERROR] Failed to connect to Lavalink: {e}")

async def shutdown():
    print("Shutting down the bot... Closing Lavalink and HTTP sessions.")
    await wavelink.Pool.disconnect()
    await bot.close()

async def main():
    token = os.getenv("TOKEN")

    try:
        async with bot:
            await bot.start(token)
    except KeyboardInterrupt:
        print("🔴 KeyboardInterrupt received. Shutting down...")
        await shutdown()
    except asyncio.CancelledError:
        print("🟡 CancelledError during shutdown (safe to ignore).")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        await shutdown()

if __name__ == "__main__":
    asyncio.run(main())



# END          real
