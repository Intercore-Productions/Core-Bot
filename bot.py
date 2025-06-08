import discord
from discord import app_commands
from discord.ext import commands
import os

# Replace this with your actual bot token securely (e.g. from environment variables)
TOKEN = os.getenv("MTM4MDY0NjM0NDk3NjQ5ODc3OA.GChJUB.g9vO2G2oCJpnSykkzkVYxK8dyYq_01yUZ6wMuc")

# Make sure TOKEN is set
if TOKEN is None:
    raise ValueError("Please set the DISCORD_BOT_TOKEN environment variable.")

# Set up Discord intents
intents = discord.Intents.default()

# Initialize the bot
bot = commands.Bot(command_prefix="!", intents=intents)

# When the bot is ready
@bot.event
async def on_ready():
    print(f'Bot is online as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f'Successfully synced {len(synced)} slash command(s).')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

# Define a /hello slash command
@bot.tree.command(name="hello", description="Say hi to the bot!")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message("Hi!")

# Run the bot
bot.run(TOKEN)

