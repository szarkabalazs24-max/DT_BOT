import discord
from discord.ext import commands
from discord import app_commands
import random
import datetime
import re
import json
import os

# ===== TOKEN =====
TOKEN = "IDE_A_BOT_TOKENED"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

FOOTER = "✨ DT_bluuuue szervere ✨"

# ===== AUTOREACT =====
AUTOREACT_FILE = "autoreact.json"

def load_autoreact():
    try:
        if not os.path.exists(AUTOREACT_FILE):
            with open(AUTOREACT_FILE, "w") as f:
                json.dump({}, f)
        with open(AUTOREACT_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except:
        pass
    return {}

def save_autoreact(data):
    try:
        with open(AUTOREACT_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except:
        pass

autoreacts = load_autoreact()

# ===== BEÁLLÍTÁSOK =====
WELCOME_CHANNEL_NAME = "welcome"
AUTO_ROLE_NAME = "Tag"
BAD_WORDS = ["geci", "fasz", "bazd", "kurva"]

warns = {}

# ===== SEGÉD =====
def get_channel(guild, name):
    return discord.utils.get(guild.text_channels, name=name)

# ===== READY =====
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bejelentkezve: {bot.user}")

# ===== MESSAGE (AUTOREACT + AUTOMOD) =====
@bot.event
async def on_message(message):
    if message.author.bot or message.guild is None:
        return

    content = message.content.lower()
    channel_id = str(message.channel.id)

    # AUTOREACT
    if channel_id in autoreacts:
        for emoji in autoreacts[channel_id]:
            try:
                await message.add_reaction(emoji)
            except:
                pass

    # AUTOMOD
    try:
        if any(w in content for w in BAD_WORDS):
            await message.delete()
            await add_warn(message.author, "Káromkodás")
            await safe_mute(message.author, 120, "Káromkodás")
            return

        if re.search(r"https?://", content):
            await message.delete()
            await safe_mute(message.author, 600, "Link tiltott")
            return
    except:
        pass

    await bot.process_commands(message)

# ===== BELÉPÉS =====
@bot.event
async def on_member_join(member):
    try:
        ch = get_channel(member.guild, WELCOME_CHANNEL_NAME)
        if ch:
            embed = discord.Embed(
                title="👋 Üdv a szerveren!",
                description=f"{member.mention}\nTe vagy a **{member.guild.member_count}. tag**",
                color=0x2ecc71
            )
            embed.set_footer(text=FOOTER)
            await ch.send(embed=embed)

        role = discord.utils.get(member.guild.roles, name=AUTO_ROLE_NAME)
        if role:
            await member.add_roles(role)
    except:
        pass

# ===== WARN =====
async def add_warn(user, reason):
    warns.setdefault(user.id, []).append(reason)

@bot.tree.command(name="figyelmeztetés")
async def warn(interaction: discord.Interaction, tag: discord.Member, indok: str):
    await add_warn(tag, indok)
    embed = discord.Embed(
        title="⚠️ Figyelmeztetés",
        description=f"{tag.mention}\nIndok: **{indok}**",
        color=0xf1c40f
    )
    embed.set_footer(text=FOOTER)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="figyelmeztetések")
async def warns_cmd(interaction: discord.Interaction, tag: discord.Member):
    w = warns.get(tag.id, [])
    if not w:
        await interaction.response.send_message("Nincs figyelmeztetés")
        return
    txt = "\n".join([f"{i+1}. {x}" for i, x in enumerate(w)])
    await interaction.response.send_message(txt)

# ===== SAFE MUTE =====
async def safe_mute(member, seconds, reason):
    try:
        if member.guild.me.guild_permissions.moderate_members:
            until = datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds)
            await member.timeout(until, reason=reason)
    except:
        pass

# ===== BAN =====
@bot.tree.command(name="kitiltás")
async def ban(interaction: discord.Interaction, tag: discord.Member, indok: str):
    try:
        await tag.ban(reason=indok)
        await interaction.response.send_message("🔨 Kitiltva")
    except:
        await interaction.response.send_message("❌ Nem sikerült")

# ===== FUN =====
@bot.tree.command(name="csók")
async def kiss(interaction: discord.Interaction, tag: discord.Member):
    gifs = [
        "https://media.tenor.com/0AVbKGY_MxMAAAAC/anime-kiss.gif",
        "https://media.tenor.com/WS6Dm1ZW_vMAAAAC/kiss.gif"
    ]
    embed = discord.Embed(
        description=f"{interaction.user.mention} megcsókolta {tag.mention} 💋",
        color=0xff69b4
    )
    embed.set_image(url=random.choice(gifs))
    embed.set_footer(text=FOOTER)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="iqteszt")
async def iq(interaction: discord.Interaction):
    await interaction.response.send_message(f"🧠 IQ: **{random.randint(70,160)}**")

@bot.tree.command(name="mond")
async def say(interaction: discord.Interaction, szoveg: str):
    await interaction.response.send_message("✅ Elkuldve", ephemeral=True)
    await interaction.channel.send(szoveg)

bot.run(TOKEN)
