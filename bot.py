import discord
from discord import app_commands
from discord.ext import commands
import requests
import json
import os

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- SUPABASE CONFIG ---
SUPABASE_URL = "https://fgpcgctimopexdkwgiov.supabase.co"  # URL del progetto Supabase
SUPABASE_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZncGNnY3RpbW9wZXhka3dnaW92Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDgxMDk4NjAsImV4cCI6MjA2MzY4NTg2MH0.ohP_KrJnY5RShx6ONHdNM9bUddqaSKASN4w9bTEoAGY"  # API Key pubblica (anon)
SUPABASE_TABLE = "server_config"
SUPABASE_HEADERS = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json"
}

# --- DATABASE FUNCTIONS (SUPABASE) ---
def init_db():
    # Su Supabase, la tabella va creata dal pannello web. Qui lasciamo solo un commento.
    pass  # Crea la tabella 'server_config' su Supabase con i campi: guild_id (bigint, pk), api_key (text), announce_roles (text), updates_channel (bigint), logs_channel (bigint)

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
        "logs_channel": row["logs_channel"]
    }

# Comando /config
@bot.tree.command(name="config", description="Set API Key, Announcement Roles, Updates and Logs channels")
@app_commands.describe(
    api_key="Your Maple Server API Key",
    announce_roles="Role to mention for remote announcements",
    updates_channel="Channel for updates",
    logs_channel="Channel for logs"
)
async def config(
    interaction: discord.Interaction,
    api_key: str,
    announce_roles: discord.Role,  # accetta un solo ruolo
    updates_channel: discord.TextChannel,
    logs_channel: discord.TextChannel
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only server admins can configure the bot.", ephemeral=True)
        return

    guild_id = interaction.guild.id
    roles_ids = [announce_roles.id]  # lista con un solo ruolo
    roles_json = json.dumps(roles_ids)

    # Upsert su Supabase
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
    payload = {
        "guild_id": guild_id,
        "api_key": api_key,
        "announce_roles": roles_json,
        "updates_channel": updates_channel.id,
        "logs_channel": logs_channel.id
    }
    resp = requests.post(url, headers={**SUPABASE_HEADERS, "Prefer": "resolution=merge-duplicates"}, data=json.dumps(payload))
    if resp.status_code not in (200, 201):
        await interaction.response.send_message(f"❌ Errore nel salvataggio: {resp.text}", ephemeral=True)
        return

    await interaction.response.send_message("✅ Configuration saved!", ephemeral=True)

# Comando /config-view
@bot.tree.command(name="config-view", description="View current configuration")
async def config_view(interaction: discord.Interaction):
    try:
        config = load_config(interaction.guild.id)
        if not config:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ No configuration found for this server.", ephemeral=True)
            return

        embed = discord.Embed(title=f"Configuration for {interaction.guild.name}", color=discord.Color.yellow())
        embed.add_field(name="API Key", value="||Hidden||", inline=False)
        if config["announce_roles"]:
            mention_roles = ", ".join(f"<@&{r}>" for r in config["announce_roles"])
        else:
            mention_roles = "None"
        embed.add_field(name="Announcement Roles", value=mention_roles, inline=False)
        updates_channel = bot.get_channel(config["updates_channel"])
        logs_channel = bot.get_channel(config["logs_channel"])
        embed.add_field(name="Updates Channel", value=updates_channel.mention if updates_channel else "Not found", inline=True)
        embed.add_field(name="Logs Channel", value=logs_channel.mention if logs_channel else "Not found", inline=True)

        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        if not interaction.response.is_done():
            try:
                await interaction.response.send_message(f"❌ Internal error: {str(e)}", ephemeral=True)
            except Exception:
                pass

# Comando /config-reset
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

# Comando /announce con controllo ruolo
@bot.tree.command(name="announce", description="Send an in-game announcement")
@app_commands.describe(message="The message to send in-game")
async def announce(interaction: discord.Interaction, message: str):
    try:
        config = load_config(interaction.guild.id)
        # Rispondi solo se l'interazione è ancora valida
        if not config:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ This server is not configured. Use `/config` first.", ephemeral=True)
            return

        # Controlla se l'utente ha uno dei ruoli permessi
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
        # Catch any unknown interaction error and avoid crash
        if not interaction.response.is_done():
            try:
                await interaction.response.send_message(f"❌ Internal error: {str(e)}", ephemeral=True)
            except Exception:
                pass

# Comando /game-info con controllo permessi e config
@bot.tree.command(name="game-info", description="Show public server information")
async def game_info(interaction: discord.Interaction):
    config = load_config(interaction.guild.id)
    if not config:
        await interaction.response.send_message("❌ This server is not configured. Use `/config` first.", ephemeral=True)
        return

    # Controllo sviluppatori (esempio, aggiungi user IDs come vuoi)
    allowed_ids = [853705827738976277, 1099013081683738676]
    if interaction.user.id not in allowed_ids:
        await interaction.response.send_message("❌ You are not authorized to use this command.", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)
    headers = {"X-Api-Key": config["api_key"]}
    try:
        response = requests.get("https://maple-api.marizma.games/v1/server", headers=headers)
        if response.status_code == 200:
            info = response.json()
            embed = discord.Embed(title="📝 Server Information", color=discord.Color.blue())
            if "name" in info:
                embed.add_field(name="Server Name", value=str(info["name"]), inline=True)
            if "status" in info:
                embed.add_field(name="Status", value=str(info["status"]).capitalize(), inline=True)
            if "players" in info:
                embed.add_field(name="Players Online", value=str(info["players"]), inline=True)
            if "maxPlayers" in info:
                embed.add_field(name="Max Players", value=str(info["maxPlayers"]), inline=True)
            if "version" in info:
                embed.add_field(name="Version", value=str(info["version"]), inline=True)
            if "uptime" in info:
                embed.add_field(name="Uptime", value=str(info["uptime"]), inline=True)
            for k, v in info.items():
                if k not in ["name", "status", "players", "maxPlayers", "version", "uptime"]:
                    embed.add_field(name=k.replace('_', ' ').title(), value=str(v), inline=False)
            embed.set_footer(text="Maple Server • Public Info")
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"❌ Failed to fetch server info. Status: {response.status_code}\n{response.text}")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

# Comando /active-players con controllo permessi e config
@bot.tree.command(name="active-players", description="Show active players on the server")
async def active_players(interaction: discord.Interaction):
    config = load_config(interaction.guild.id)
    if not config:
        await interaction.response.send_message("❌ This server is not configured. Use `/config` first.", ephemeral=True)
        return

    allowed_ids = [853705827738976277, 1099013081683738676]
    if interaction.user.id not in allowed_ids:
        await interaction.response.send_message("❌ You are not authorized to use this command.", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)
    headers = {"X-Api-Key": config["api_key"]}
    try:
        response = requests.get("https://maple-api.marizma.games/v1/server/players", headers=headers)
        if response.status_code == 200:
            data = response.json()
            players = data.get("players", data)
            embed = discord.Embed(title="👥 Active Players", color=discord.Color.green())
            if players and isinstance(players, list) and len(players) > 0:
                for p in players:
                    name = p.get("name", "Unknown") if isinstance(p, dict) else str(p)
                    embed.add_field(name=name, value="Online", inline=True)
            else:
                embed.description = "No active players online."
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"❌ Failed to fetch active players. Status: {response.status_code}\n{response.text}")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

# Comando /hello semplice
@bot.tree.command(name="hello", description="Say hi to the bot!")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message("👋 Hello!")

# Stato del bot: Watching 🔧 Bot in development
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
    # DM
    try:
        await user.send(embed=embed)
    except Exception:
        pass
    # Log channel
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
    # Prende il massimo case_number e incrementa
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

# Esempio di logging in un comando di moderazione:
# case_number = log_mod_action(interaction.guild.id, user.id, "Warn", interaction.user.id)
# Puoi poi includere il case_number nell'embed:
# embed.add_field(name="Case #", value=str(case_number), inline=False)

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

# --- DEV COMMAND GROUP ---
dev_group = app_commands.Group(name="dev", description="Developer commands")

@dev_group.command(name="remove-guild", description="Remove a guild configuration (developers only)")
@app_commands.describe(guild_id="Guild ID to remove", reason="Reason for removal")
async def remove_guild(interaction: discord.Interaction, guild_id: int, reason: str):
    allowed_ids = [853705827738976277, 1099013081683738676]
    if interaction.user.id not in allowed_ids:
        return await interaction.response.send_message("❌ Only bot developers can use this command.", ephemeral=True)
    # Prendi la config
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?guild_id=eq.{guild_id}"
    resp = requests.get(url, headers=SUPABASE_HEADERS)
    config = resp.json()[0] if resp.status_code == 200 and resp.json() else None
    # Rimuovi la config
    del_url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?guild_id=eq.{guild_id}"
    requests.delete(del_url, headers=SUPABASE_HEADERS)
    # Manda embed nel canale updates
    if config and config.get("updates_channel"):
        embed = discord.Embed(title="❌ Guild Configuration Removed", color=discord.Color.red())
        embed.add_field(name="Guild ID", value=str(guild_id), inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="By", value=interaction.user.mention, inline=False)
        embed.timestamp = discord.utils.utcnow()
        channel = bot.get_channel(config["updates_channel"])
        if channel:
            await channel.send(embed=embed)
    await interaction.response.send_message(f"✅ Config for guild {guild_id} removed.", ephemeral=True)

@dev_group.command(name="ban-guild", description="Ban a guild from using the bot (developers only)")
@app_commands.describe(guild_id="Guild ID to ban", reason="Reason for ban")
async def ban_guild(interaction: discord.Interaction, guild_id: int, reason: str):
    allowed_ids = [853705827738976277, 1099013081683738676]
    if interaction.user.id not in allowed_ids:
        return await interaction.response.send_message("❌ Only bot developers can use this command.", ephemeral=True)
    payload = {
        "guild_id": guild_id,
        "banned_by": interaction.user.id,
        "reason": reason,
        "date": discord.utils.utcnow().isoformat()
    }
    url = f"{SUPABASE_URL}/rest/v1/{BANNED_GUILDS_TABLE}"
    requests.post(url, headers=SUPABASE_HEADERS, data=json.dumps(payload))
    await interaction.response.send_message(f"✅ Guild {guild_id} banned.", ephemeral=True)

@dev_group.command(name="unban-guild", description="Unban a guild (developers only)")
@app_commands.describe(guild_id="Guild ID to unban")
async def unban_guild(interaction: discord.Interaction, guild_id: int):
    allowed_ids = [853705827738976277, 1099013081683738676]
    if interaction.user.id not in allowed_ids:
        return await interaction.response.send_message("❌ Only bot developers can use this command.", ephemeral=True)
    url = f"{SUPABASE_URL}/rest/v1/{BANNED_GUILDS_TABLE}?guild_id=eq.{guild_id}"
    resp = requests.delete(url, headers=SUPABASE_HEADERS)
    if resp.status_code in (200, 204):
        await interaction.response.send_message(f"✅ Guild {guild_id} unbanned.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Failed to unban guild: {resp.text}", ephemeral=True)

@dev_group.command(name="view-banned-guild", description="View all banned guilds (developers only)")
async def view_banned_guild(interaction: discord.Interaction):
    allowed_ids = [853705827738976277, 1099013081683738676]
    if interaction.user.id not in allowed_ids:
        return await interaction.response.send_message("❌ Only bot developers can use this command.", ephemeral=True)
    url = f"{SUPABASE_URL}/rest/v1/{BANNED_GUILDS_TABLE}?order=date.desc"
    resp = requests.get(url, headers=SUPABASE_HEADERS)
    logs = resp.json() if resp.status_code == 200 else []
    if not logs:
        return await interaction.response.send_message("No banned guilds found.", ephemeral=True)
    embed = discord.Embed(title="Banned Guilds", color=discord.Color.red())
    for log in logs[:10]:
        embed.add_field(
            name=f"Guild ID: {log['guild_id']}",
            value=f"By: <@{log['banned_by']}>\nDate: {log['date']}\nReason: {log['reason']}",
            inline=False
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@dev_group.command(name="clear-modlog-global", description="Clear ALL modlogs (developers only)")
async def clear_modlog_global(interaction: discord.Interaction):
    allowed_ids = [853705827738976277, 1099013081683738676]
    if interaction.user.id not in allowed_ids:
        return await interaction.response.send_message("❌ Only bot developers can use this command.", ephemeral=True)
    url = f"{SUPABASE_URL}/rest/v1/{MODLOGS_TABLE}?case_number=gt.0"
    resp = requests.delete(url, headers=SUPABASE_HEADERS)
    if resp.status_code in (200, 204):
        await interaction.response.send_message(f"✅ All modlogs globally cleared.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Failed to clear modlogs: {resp.text}", ephemeral=True)

@dev_group.command(name="view-active-guilds", description="View all active guilds (developers only)")
async def view_active_guilds(interaction: discord.Interaction):
    allowed_ids = [853705827738976277, 1099013081683738676]
    if interaction.user.id not in allowed_ids:
        return await interaction.response.send_message("❌ Only bot developers can use this command.", ephemeral=True)
    # Get all configs
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?select=guild_id"
    resp = requests.get(url, headers=SUPABASE_HEADERS)
    guilds = resp.json() if resp.status_code == 200 else []
    if not guilds:
        return await interaction.response.send_message("No active guilds found.", ephemeral=True)
    embed = discord.Embed(title="Active Guilds", color=discord.Color.green())
    for g in guilds[:20]:
        embed.add_field(name=f"Guild ID", value=str(g['guild_id']), inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Register the dev group
bot.tree.add_command(dev_group)

# --- BAN GUILD TABLE ---
BANNED_GUILDS_TABLE = "banned_guilds"

# /remove-guild
@bot.tree.command(name="remove-guild", description="Remove a guild configuration (developers only)")
@app_commands.describe(guild_id="Guild ID to remove", reason="Reason for removal")
async def remove_guild(interaction: discord.Interaction, guild_id: int, reason: str):
    allowed_ids = [853705827738976277, 1099013081683738676]
    if interaction.user.id not in allowed_ids:
        return await interaction.response.send_message("❌ Only bot developers can use this command.", ephemeral=True)
    # Prendi la config
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?guild_id=eq.{guild_id}"
    resp = requests.get(url, headers=SUPABASE_HEADERS)
    config = resp.json()[0] if resp.status_code == 200 and resp.json() else None
    # Rimuovi la config
    del_url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?guild_id=eq.{guild_id}"
    requests.delete(del_url, headers=SUPABASE_HEADERS)
    # Manda embed nel canale updates
    if config and config.get("updates_channel"):
        embed = discord.Embed(title="❌ Guild Configuration Removed", color=discord.Color.red())
        embed.add_field(name="Guild ID", value=str(guild_id), inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="By", value=interaction.user.mention, inline=False)
        embed.timestamp = discord.utils.utcnow()
        channel = bot.get_channel(config["updates_channel"])
        if channel:
            await channel.send(embed=embed)
    await interaction.response.send_message(f"✅ Config for guild {guild_id} removed.", ephemeral=True)

# /ban-guild
@bot.tree.command(name="ban-guild", description="Ban a guild from using the bot (developers only)")
@app_commands.describe(guild_id="Guild ID to ban", reason="Reason for ban")
async def ban_guild(interaction: discord.Interaction, guild_id: int, reason: str):
    allowed_ids = [853705827738976277, 1099013081683738676]
    if interaction.user.id not in allowed_ids:
        return await interaction.response.send_message("❌ Only bot developers can use this command.", ephemeral=True)
    payload = {
        "guild_id": guild_id,
        "banned_by": interaction.user.id,
        "reason": reason,
        "date": discord.utils.utcnow().isoformat()
    }
    url = f"{SUPABASE_URL}/rest/v1/{BANNED_GUILDS_TABLE}"
    requests.post(url, headers=SUPABASE_HEADERS, data=json.dumps(payload))
    await interaction.response.send_message(f"✅ Guild {guild_id} banned.", ephemeral=True)

# /unban-guild
@bot.tree.command(name="unban-guild", description="Unban a guild (developers only)")
@app_commands.describe(guild_id="Guild ID to unban")
async def unban_guild(interaction: discord.Interaction, guild_id: int):
    allowed_ids = [853705827738976277, 1099013081683738676]
    if interaction.user.id not in allowed_ids:
        return await interaction.response.send_message("❌ Only bot developers can use this command.", ephemeral=True)
    url = f"{SUPABASE_URL}/rest/v1/{BANNED_GUILDS_TABLE}?guild_id=eq.{guild_id}"
    resp = requests.delete(url, headers=SUPABASE_HEADERS)
    if resp.status_code in (200, 204):
        await interaction.response.send_message(f"✅ Guild {guild_id} unbanned.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Failed to unban guild: {resp.text}", ephemeral=True)

# /view-banned-guild
@bot.tree.command(name="view-banned-guild", description="View all banned guilds (developers only)")
async def view_banned_guild(interaction: discord.Interaction):
    allowed_ids = [853705827738976277, 1099013081683738676]
    if interaction.user.id not in allowed_ids:
        return await interaction.response.send_message("❌ Only bot developers can use this command.", ephemeral=True)
    url = f"{SUPABASE_URL}/rest/v1/{BANNED_GUILDS_TABLE}?order=date.desc"
    resp = requests.get(url, headers=SUPABASE_HEADERS)
    logs = resp.json() if resp.status_code == 200 else []
    if not logs:
        return await interaction.response.send_message("No banned guilds found.", ephemeral=True)
    embed = discord.Embed(title="Banned Guilds", color=discord.Color.red())
    for log in logs[:10]:
        embed.add_field(
            name=f"Guild ID: {log['guild_id']}",
            value=f"By: <@{log['banned_by']}>\nDate: {log['date']}\nReason: {log['reason']}",
            inline=False
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# --- BLOCCO COMANDI PER GUILD BANNATE ---
async def interaction_check(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return True  # Allow DMs
    url = f"{SUPABASE_URL}/rest/v1/{BANNED_GUILDS_TABLE}?guild_id=eq.{interaction.guild.id}"
    resp = requests.get(url, headers=SUPABASE_HEADERS)
    if resp.status_code == 200 and resp.json():
        await interaction.response.send_message("❌ This server is banned from using the bot.", ephemeral=True)
        return False
    return True

bot.tree.interaction_check = interaction_check

# --- /view-active-guilds ---
@bot.tree.command(name="view-active-guilds", description="View all active guilds (developers only)")
async def view_active_guilds(interaction: discord.Interaction):
    allowed_ids = [853705827738976277, 1099013081683738676]
    if interaction.user.id not in allowed_ids:
        return await interaction.response.send_message("❌ Only bot developers can use this command.", ephemeral=True)
    # Get all configs
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?select=guild_id"
    resp = requests.get(url, headers=SUPABASE_HEADERS)
    guilds = resp.json() if resp.status_code == 200 else []
    if not guilds:
        return await interaction.response.send_message("No active guilds found.", ephemeral=True)
    embed = discord.Embed(title="Active Guilds", color=discord.Color.green())
    for g in guilds[:20]:
        embed.add_field(name=f"Guild ID", value=str(g['guild_id']), inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

if __name__ == "__main__":
    bot.run("MTM4MDY0NjM0NDk3NjQ5ODc3OA.GxFFdu.SMvuxSUimEvShg5z2E0Zpx3BmS_RtrZ6slBS1o")