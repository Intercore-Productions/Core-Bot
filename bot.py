import discord
from discord import app_commands
from discord.ext import commands

TOKEN = 'MTM4MDY0NjM0NDk3NjQ5ODc3OA.GChJUB.g9vO2G2oCJpnSykkzkVYxK8dyYq_01yUZ6wMuc'

# Intents richiesti
intents = discord.Intents.default()

# Creazione client
bot = commands.Bot(command_prefix="!", intents=intents)

# Comando /hello
@bot.event
async def on_ready():
    print(f'{bot.user} è online!')
    try:
        synced = await bot.tree.sync()
        print(f"Comandi slash sincronizzati: {len(synced)}")
    except Exception as e:
        print(f"Errore nella sincronizzazione dei comandi slash: {e}")

@bot.tree.command(name="hello", description="Saluta il bot!")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message("Hi!")

bot.run(TOKEN)
