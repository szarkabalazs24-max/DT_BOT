import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
import datetime
import re
import json
import os

# ====== TOKEN ======
TOKEN = "IDE_A_BOT_TOKENED"

# ====== BOT ======
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

FOOTER = "✨ DT_bluuuue szervere ✨"

# ====== AUTOREACT ======
AUTOREACT_FILE = "autoreact.json"

def load_autoreact():
    if not os.path.exists(AUTOREACT_FILE):
        with open(AUTOREACT_FILE, "w") as f:
            json.dump({}, f)
    with open(AUTOREACT_FILE, "r") as f:
        return json.load(f)

def save_autoreact(data):
    with open(AUTOREACT_FILE, "w") as f:
        json.dump(data, f, indent=4)

autoreacts = load_autoreact()

# ====== BEÁLLÍTÁSOK ======
WELCOME_CHANNEL_NAME = "welcome"
LOG_CHANNEL_NAME = "log"
AUTO_ROLE_NAME = "Tag"

BAD_WORDS = ["geci", "fasz", "bazd", "kurva"]

warns = {}

# ====== SEGÉD ======
def get_channel(guild, name):
    return discord.utils.get(guild.text_channels, name=name)

# ====== READY ======
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bejelentkezve: {bot.user}")

# ====== MESSAGE (AUTOREACT + AUTOMOD) ======
@bot.event
async def on_message(message):
    if message.author.bot:
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

    # AUTOMOD - káromkodás
    if any(w in content for w in BAD_WORDS):
        await message.delete()
        await add_warn(message.author, "Káromkodás")
        await mute_user(message.author, 120, "Káromkodás")

    # AUTOMOD - link
    if re.search(r"https?://", content):
        await message.delete()
        await mute_user(message.author, 600, "Link tiltott")

    await bot.process_commands(message)

# ====== BELÉPÉS ======
@bot.event
async def on_member_join(member):
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

# ====== KILÉPÉS ======
@bot.event
async def on_member_remove(member):
    ch = get_channel(member.guild, WELCOME_CHANNEL_NAME)
    if ch:
        embed = discord.Embed(
            title="👋 Kilépett egy tag",
            description=f"**{member.name}** kilépett a szerverről",
            color=0xe74c3c
        )
        embed.set_footer(text=FOOTER)
        await ch.send(embed=embed)

# ====== WARN ======
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
    embed = discord.Embed(title="⚠️ Figyelmeztetések", description=txt, color=0xe67e22)
    embed.set_footer(text=FOOTER)
    await interaction.response.send_message(embed=embed)

# ====== MUTE ======
async def mute_user(member, seconds, reason):
    until = datetime.datetime.utcnow() + datetime.timedelta(seconds=seconds)
    await member.timeout(until, reason=reason)

# ====== BAN ======
@bot.tree.command(name="kitiltás")
async def ban(interaction: discord.Interaction, tag: discord.Member, indok: str):
    await tag.ban(reason=indok)
    await interaction.response.send_message(f"🔨 {tag} kitiltva | {indok}")

@bot.tree.command(name="id_kitiltás")
async def idban(interaction: discord.Interaction, userid: str, indok: str):
    user = await bot.fetch_user(int(userid))
    await interaction.guild.ban(user, reason=indok)
    await interaction.response.send_message(f"🔨 ID kitiltva | {indok}")

# ====== FUN ======
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

# ====== SAY ======
@bot.tree.command(name="mond")
async def say(interaction: discord.Interaction, szoveg: str):
    await interaction.response.send_message("✅ Elkuldve", ephemeral=True)
    await interaction.channel.send(szoveg)

# ====== TICKET ======
class TicketView(discord.ui.View):
    @discord.ui.button(label="🎫 Ticket nyitás", style=discord.ButtonStyle.green)
    async def open(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        ch = await guild.create_text_channel(
            f"ticket-{interaction.user.name}",
            overwrites={
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
        )
        await interaction.response.send_message(f"Ticket létrehozva: {ch.mention}", ephemeral=True)

@bot.tree.command(name="ticket_panel")
async def ticket_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎫 Ticket rendszer",
        description="Kattints a gombra ticket nyitásához",
        color=0x3498db
    )
    embed.set_footer(text=FOOTER)
    await interaction.response.send_message(embed=embed, view=TicketView())

# ====== GIVEAWAY ======
@bot.tree.command(name="nyereményjáték")
async def giveaway(interaction: discord.Interaction, nyeremény: str):
    embed = discord.Embed(
        title="🎉 Nyereményjáték",
        description=f"Nyeremény: **{nyeremény}**\nReagálj 🎉-val!",
        color=0x9b59b6
    )
    embed.set_footer(text=FOOTER)
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("🎉")
    await interaction.response.send_message("✅ Elindítva", ephemeral=True)

bot.run(TOKEN)
