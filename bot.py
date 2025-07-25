import discord
from discord import app_commands
from discord import Interaction
from discord.ext import commands
from discord.ui import View, Select, select
import requests
import json
import os
import asyncio
from dotenv import load_dotenv

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
    return {
        "api_key": row["api_key"],
        "announce_roles": announce_roles,
        "updates_channel": row["updates_channel"],
        "logs_channel": row["logs_channel"],
        "ingame_perms": row.get("ingame_perms"),
        "server_code": row.get("server_code"),
        "session_ping": row.get("session_ping"),
        "session_perms": row.get("session_perms"),
        "session_channel": row.get("session_channel"),
        "welcoming_channel": row.get("welcoming_channel"),
        "welcome_text": row.get("welcome_text")
    }

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

# /config-view
@bot.tree.command(name="config-view", description="View current configuration")
async def config_view(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only server admins can reset the config.", ephemeral=True)
        return
    try:
        config = load_config(interaction.guild.id)
        if not config:
            await interaction.response.send_message("❌ No configuration found for this server.", ephemeral=True)
            return
        embed1 = discord.Embed(title=f"Configuration • API & Announcements", color=discord.Color.yellow())
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
        embed2 = discord.Embed(title=f"Configuration • Session", color=discord.Color.blue())
        embed2.add_field(name="Server Code", value=config["server_code"] if config["server_code"] else "Not set", inline=True)
        embed2.add_field(name="Session Ping", value=config["session_ping"] if config["session_ping"] else "Not set", inline=True)
        embed2.add_field(name="Session Permission Role", value=f"<@&{config['session_perms']}>" if config["session_perms"] else "Not set", inline=True)
        session_channel = bot.get_channel(int(config["session_channel"])) if config["session_channel"] else None
        embed2.add_field(name="Session Channel", value=session_channel.mention if session_channel else "Not set", inline=True)
        embed3 = discord.Embed(title=f"Configuration • Welcoming", color=discord.Color.green())
        welcoming_channel = bot.get_channel(int(config["welcoming_channel"])) if config["welcoming_channel"] else None
        embed3.add_field(name="Welcoming Channel", value=welcoming_channel.mention if welcoming_channel else "Not set", inline=True)
        embed3.add_field(name="Welcome Text", value=config["welcome_text"] if config["welcome_text"] else "Not set", inline=False)
        
        await interaction.response.send_message(embeds=[embed1, embed2, embed3], ephemeral=True)
    except Exception as e:
        if not interaction.response.is_done():
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
from discord import app_commands, Interaction, Embed, TextChannel, Webhook
import discord

@bot.tree.command(name="maple-log", description="Set up a webhook to receive your Maple server logs.")
@app_commands.describe(channel="The channel where the Webhook will be created")
@app_commands.checks.has_permissions(manage_guild=True)
async def maple_log(interaction: Interaction, channel: TextChannel):
    webhook: Webhook = await channel.create_webhook(name="Core")

    embed = Embed(
        title="✅ Webhook Created",
        description=f"A new Webhook has been successfully created in {channel.mention}.\n\n"
                    f"**🔗 Webhook URL:**\n`{webhook.url}`\n\n"
                    f"Your Webhook has been successfully created. Please follow the steps below to set it up on your Server.",
        color=discord.Color.green()
    )

    embed.add_field(
        name="📋 Configuration Steps",
        value=(
            "- Enter your **Custom In-Game Maple Server**\n"
            "- Open the **Settings** menu\n"
            "- Scroll to the bottom and find the **Command Log Webhook** section\n"
            "- Paste the Webhook URL shown above."
        ),
        inline=False
    )

    embed.add_field(
        name="⚙️ Want to customize the Webhook name or avatar?",
        value=(
            "Go to the channel settings > **Integrations** > **Core Webhook**, and edit as you wish."
        ),
        inline=False
    )

    embed.set_footer(text="Maple Log Setup • Core Bot")

    await interaction.response.send_message(embed=embed)

from discord import app_commands, Interaction

# /server-logs-off
@bot.tree.command(name="server-logs-off", description="Disables log Webhook by removing it from Supabase.")
@app_commands.checks.has_permissions(manage_guild=True)
async def server_logs_off(interaction: Interaction):
    guild = interaction.guild

    await interaction.response.defer(thinking=True)

    url_check = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?guild_id=eq.{guild.id}"
    check_resp = requests.get(url_check, headers=SUPABASE_HEADERS)

    if check_resp.status_code != 200 or not check_resp.json():
        await interaction.followup.send("❌ This server is not configured yet.")
        return

    payload = {
        "webhook_url": None
    }
    patch_resp = requests.patch(url_check, headers=SUPABASE_HEADERS, data=json.dumps(payload))

    if patch_resp.status_code == 204:
        await interaction.followup.send("✅ Webhook logging has been **disabled** successfully.")
    else:
        await interaction.followup.send("❌ Failed to disable logging.")

# /server-logs
from discord import app_commands, ui, Interaction, Webhook
import discord
import requests, json
import aiohttp
from io import BytesIO

@bot.tree.command(name="server-logs", description="Creates and saves a webhook for server logs.")
@app_commands.checks.has_permissions(manage_guild=True)
async def server_logs(interaction: Interaction):
    guild = interaction.guild
    channel = interaction.channel

    await interaction.response.defer()

    url_check = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?guild_id=eq.{guild.id}"
    check_resp = requests.get(url_check, headers=SUPABASE_HEADERS)

    if check_resp.status_code != 200 or not check_resp.json():
        await interaction.followup.send(
            "❌ This server is not configured yet. Please use `/config` first."
        )
        return

    current_data = check_resp.json()[0]
    existing_webhook = current_data.get("webhook_url")

    if existing_webhook:
        class ConfirmOverwrite(ui.View):
            def __init__(self):
                super().__init__(timeout=30)
                self.value = None

            @ui.button(label="Continue", style=discord.ButtonStyle.green)
            async def confirm(self, interaction_button: Interaction, button: ui.Button):
                self.value = True
                self.stop()

            @ui.button(label="Cancel", style=discord.ButtonStyle.red)
            async def cancel(self, interaction_button: Interaction, button: ui.Button):
                self.value = False
                self.stop()

        view = ConfirmOverwrite()
        await interaction.followup.send(
            "⚠️ A webhook is already configured for this server.\n"
            "Do you want to **overwrite** the existing one?",
            view=view
        )
        await view.wait()

        if view.value is None or view.value is False:
            await interaction.followup.send("❌ Operation cancelled.")
            return

    webhook_avatar_url = "https://cdn.discordapp.com/avatars/1380646344976498778/45f9b70e6ef22b841179b0aafd4e4934.png?size=1024"

    avatar_bytes = None
    if webhook_avatar_url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(webhook_avatar_url) as resp:
                    if resp.status == 200:
                        avatar_bytes = await resp.read()
        except Exception as e:
            await interaction.followup.send(f"⚠️ Failed to fetch avatar image. Creating webhook without avatar.\nError: `{e}`")

    try:
        webhook: Webhook = await channel.create_webhook(name="Core", avatar=avatar_bytes)
    except discord.Forbidden:
        await interaction.followup.send("❌ I don't have permission to create a webhook in this channel.")
        return

    webhook_url = webhook.url

    payload = {
        "webhook_url": webhook_url
    }
    patch_resp = requests.patch(url_check, headers=SUPABASE_HEADERS, data=json.dumps(payload))

    if patch_resp.status_code == 204:
        await interaction.followup.send(
            f"✅ Log Webhook has been **created and saved** successfully!\n\n**Webhook URL:**\n{webhook_url}"
        )
    else:
        await interaction.followup.send(
            "❌ Failed to update the webhook URL in Supabase."
        )

from datetime import datetime
import discord
from discord.ext import commands
from discord.utils import escape_markdown
import aiohttp

AVATAR_URL = "https://cdn.discordapp.com/avatars/1380646344976498778/45f9b70e6ef22b841179b0aafd4e4934.png?size=1024"

def load_config(guild_id):
    ...

async def send_log(guild_id, embed: discord.Embed):
    config = load_config(guild_id)
    
    webhook_url = config.get("webhook_url") if config else None
    if not webhook_url:
        return

    try:
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(webhook_url, session=session)

            await webhook.send(
                embed=embed,
                username="Core | Server Log",
                avatar_url=AVATAR_URL
            )
    except Exception as e:
        print(f"[Webhook Error] Failed to send log: {e}")


webhook_cache = {}

def load_config(guild_id):
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?guild_id=eq.{guild_id}"
    resp = requests.get(url, headers=SUPABASE_HEADERS)
    if resp.status_code != 200:
        return None
    data = resp.json()
    if not data:
        return None
    return data[0]

def get_webhook_url(guild_id):
    if guild_id in webhook_cache:
        return webhook_cache[guild_id]
    config = load_config(guild_id)
    if config and config.get("webhook_url"):
        webhook_cache[guild_id] = config["webhook_url"]
        return webhook_cache[guild_id]
    return None

def build_embed(title, description, color=0x2ECC71, author=None, avatar_url=None):
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.utcnow()
    )
    if author and avatar_url:
        embed.set_author(name=author, icon_url=avatar_url)
    return embed

async def send_webhook_log(guild, embed):
    webhook_url = get_webhook_url(guild.id)
    if not webhook_url:
        return
    json_data = {
        "embeds": [embed.to_dict()]
    }
    try:
        requests.post(webhook_url, json=json_data)
    except:
        pass

# --- EVENT HANDLERS ---

@bot.event
async def on_member_join(member):
    embed = discord.Embed(title="📥 Member Joined", description=f"{member.mention} joined the server.", color=0x00ff00)
    embed.set_thumbnail(url=member.avatar.url if member.avatar else "")
    await send_log(member.guild.id, embed)

@bot.event
async def on_member_remove(member):
    embed = discord.Embed(title="📤 Member Left", description=f"{member.mention} left or was removed.", color=0xff0000)
    embed.set_thumbnail(url=member.avatar.url if member.avatar else "")
    await send_log(member.guild.id, embed)

@bot.event
async def on_message_delete(message):
    if message.author.bot or not message.guild:
        return
    embed = discord.Embed(title="🗑️ Message Deleted", description=f"In {message.channel.mention}", color=0xFFA500)
    embed.add_field(name="Author", value=message.author.mention, inline=True)
    embed.add_field(name="Content", value=escape_markdown(message.content)[:1024] or "None", inline=False)
    await send_log(message.guild.id, embed)

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or not before.guild or before.content == after.content:
        return
    embed = discord.Embed(title="✏️ Message Edited", description=f"In {before.channel.mention}", color=0x00BFFF)
    embed.add_field(name="Author", value=before.author.mention, inline=True)
    embed.add_field(name="Before", value=escape_markdown(before.content)[:1024] or "None", inline=False)
    embed.add_field(name="After", value=escape_markdown(after.content)[:1024] or "None", inline=False)
    await send_log(before.guild.id, embed)

@bot.event
async def on_guild_channel_create(channel):
    embed = discord.Embed(title="📁 Channel Created", description=f"{channel.mention} created.", color=0x32CD32)
    await send_log(channel.guild.id, embed)

@bot.event
async def on_guild_channel_delete(channel):
    embed = discord.Embed(title="❌ Channel Deleted", description=f"{channel.name} deleted.", color=0x8B0000)
    await send_log(channel.guild.id, embed)

@bot.event
async def on_guild_channel_update(before, after):
    if before.name != after.name:
        embed = discord.Embed(title="🔄 Channel Renamed", description=f"{before.mention}", color=0x4682B4)
        embed.add_field(name="Before", value=before.name, inline=True)
        embed.add_field(name="After", value=after.name, inline=True)
        await send_log(after.guild.id, embed)

@bot.event
async def on_member_update(before, after):
    if before.roles != after.roles:
        added_roles = [r.mention for r in after.roles if r not in before.roles]
        removed_roles = [r.mention for r in before.roles if r not in after.roles]
        embed = discord.Embed(title="🔧 Role Update", description=f"{after.mention}", color=0x9370DB)
        if added_roles:
            embed.add_field(name="Roles Added", value=", ".join(added_roles), inline=True)
        if removed_roles:
            embed.add_field(name="Roles Removed", value=", ".join(removed_roles), inline=True)
        await send_log(after.guild.id, embed)

@bot.event
async def on_user_update(before, after):
    if before.avatar != after.avatar or before.name != after.name:
        embed = discord.Embed(title="👤 User Updated", description=f"{after.mention}", color=0x2E8B57)
        embed.add_field(name="Before", value=before.name, inline=True)
        embed.add_field(name="After", value=after.name, inline=True)
        if after.avatar:
            embed.set_thumbnail(url=after.avatar.url)
        await send_log(after.guilds[0].id if after.guilds else None, embed)

@bot.event
async def on_guild_update(before, after):
    if before.name != after.name:
        embed = discord.Embed(title="🏷️ Server Renamed", color=0x1E90FF)
        embed.add_field(name="Old Name", value=before.name, inline=True)
        embed.add_field(name="New Name", value=after.name, inline=True)
        await send_log(after.id, embed)

@bot.event
async def on_guild_emojis_update(guild, before, after):
    embed = discord.Embed(title="😃 Emoji Updated", color=0xFF69B4)
    embed.add_field(name="Before", value=", ".join([e.name for e in before]), inline=True)
    embed.add_field(name="After", value=", ".join([e.name for e in after]), inline=True)
    await send_log(guild.id, embed)

@bot.event
async def on_member_ban(guild, user):
    embed = discord.Embed(title="🚫 Member Banned", description=f"{user.mention} was banned.", color=0xFF0000)
    await send_log(guild.id, embed)

@bot.event
async def on_member_unban(guild, user):
    embed = discord.Embed(title="✅ Member Unbanned", description=f"{user.mention} was unbanned.", color=0x00FF00)
    await send_log(guild.id, embed)

@bot.event
async def on_guild_role_create(role):
    embed = discord.Embed(
        title="🆕 Role Created",
        description=f"Role `{role.name}` was created.",
        color=0x00FF00
    )
    await send_log(role.guild.id, embed)

@bot.event
async def on_guild_role_delete(role):
    embed = discord.Embed(
        title="🗑️ Role Deleted",
        description=f"Role `{role.name}` was deleted.",
        color=0xFF0000
    )
    await send_log(role.guild.id, embed)

@bot.event
async def on_guild_role_update(before, after):
    embed = discord.Embed(
        title="♻️ Role Updated",
        description=f"Role `{before.name}` was updated.",
        color=0x1E90FF
    )
    if before.name != after.name:
        embed.add_field(name="Name Before", value=before.name, inline=True)
        embed.add_field(name="Name After", value=after.name, inline=True)
    if before.permissions != after.permissions:
        embed.add_field(name="Permissions Changed", value="Yes", inline=False)
    await send_log(after.guild.id, embed)        

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
    await interaction.response.send_message("👋 Hello!")

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="🔧 Bot in development"))
    print(f"✅ Bot is online as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")

async def send_modlog_and_dm(user: discord.Member, embed: discord.Embed, log_channel_id: int, guild: discord.Guild):
    try:
        await user.send(embed=embed)
    except Exception:
        pass
    log_channel = guild.get_channel(log_channel_id)
    if log_channel:
        await log_channel.send(embed=embed)

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

def log_mod_action(guild_id, user_id, action, moderator_id):
    case_number = get_next_case_number()
    payload = {
        "case_number": case_number,
        "guild_id": guild_id,
        "user_id": user_id,
        "action": action,
        "moderator_id": moderator_id,
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
    case_number = log_mod_action(interaction.guild.id, user.id, "warn", interaction.user.id)
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
    case_number = log_mod_action(interaction.guild.id, user.id, "unwarn", interaction.user.id)
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
    case_number = log_mod_action(interaction.guild.id, user.id, "mute", interaction.user.id)
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
    case_number = log_mod_action(interaction.guild.id, user.id, "unmute", interaction.user.id)
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
    case_number = log_mod_action(interaction.guild.id, user.id, "kick", interaction.user.id)
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
    case_number = log_mod_action(interaction.guild.id, user.id, "soft-ban", interaction.user.id)
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
    case_number = log_mod_action(interaction.guild.id, user.id, "t-ban", interaction.user.id)
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
    case_number = log_mod_action(interaction.guild.id, user.id, "p-ban", interaction.user.id)
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
    case_number = log_mod_action(interaction.guild.id, user.id, "unban", interaction.user.id)
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
        embed.add_field(
            name=f"Case #{log['case_number']} - {log['action']}",
            value=f"By: {mod.mention if mod else log['moderator_id']}\nDate: {log['date']}",
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

    if action.value == "SSU":
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
        embed = discord.Embed(
            title=f"SSU | Server Start Up",
            description="A new session is starting in our Maple Server! Join now with the Code Below!",
            color=discord.Color.green()
        )
        embed.add_field(name="Session Host", value=interaction.user.mention, inline=True)
        embed.add_field(name="Session Code", value=server_code, inline=True)
        await session_channel.send(f"{session_ping}", embed=embed)
        await interaction.followup.send("✅ Session start announced.", ephemeral=True)

    elif action.value == "SSD":
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
        embed = discord.Embed(
            title="SSD | Server Shut Down",  # Fixed Grammar Error
            description=f"The session hosted by {interaction.user.mention} has ended. Thank you for participating! See you soon!",
            color=discord.Color.orange()
        )
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

        embed = discord.Embed(
            title="Low Player Count",
            description=f"There are currently not enough players in-game.\n**Players Online:** {player_count}\nPlease join the game if you want to participate!",
            color=discord.Color.red()
        )
        await session_channel.send(f"{session_ping}", embed=embed)
        await interaction.followup.send("✅ Low player alert sent.", ephemeral=True)

    elif action.value == "Session Cancellation":
        embed = discord.Embed(
            title="Session Cancelled",
            description="The session has been cancelled by the host due to unforeseen reasons. Stay tuned for future sessions!",
            color=discord.Color.dark_red()
        )
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
from discord import ui

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

# Start
@bot.event
async def on_ready():
    print(f"Bot is logged in as {bot.user.name} ({bot.user.id})")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="🏥 Maple Communities"))
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

token = os.getenv("DISCORD_TOKEN")
bot.run(token)
