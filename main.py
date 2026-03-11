import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import datetime
import asyncio
import re
import random

# ================== KONFIG ==================

TOKEN = os.getenv("DISCORD_TOKEN")

WARN_FILE = "warns.json"
WELCOME_FILE = "welcome.json"
LEAVE_FILE = "leave.json"
AUTO_ROLE_FILE = "autorole.json"

FORBIDDEN_WORDS = [
    "fasz","geci","buzi","bazdmeg","anyad","anyád","kurva","szar"
]

LINK_REGEX = r"http[s]?://"

FOOTER_TEXT = "✨ DT_bluuuue szervere ✨"

# ================== SEGÉD ==================

def load_json(file, default):
    if not os.path.exists(file):
        return default
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def embed(title, text):
    e = discord.Embed(title=title, description=text, color=discord.Color.blue())
    e.set_footer(text=FOOTER_TEXT)
    return e

# ================== BOT ==================

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot elindult: {bot.user}")

# ================== AUTOMOD ==================

spam_cache = {}

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user = message.author
    content = message.content.lower()
    now = datetime.datetime.utcnow()

    # LINK SZŰRŐ
    if re.search(LINK_REGEX, content):
        try:
            await message.delete()
        except:
            pass

        await user.timeout(
            datetime.timedelta(minutes=10),
            reason="A linkek tiltottak"
        )

        await message.channel.send(
            embed(
                "🔗 Link törölve",
                f"{user.mention}\nIndok: **A linkek tiltottak**\nBüntetés: **10 perc némítás**"
            )
        )
        return

    # SPAM SZŰRŐ
    uid = user.id
    spam_cache.setdefault(uid, [])
    spam_cache[uid] = [t for t in spam_cache[uid] if (now - t).seconds < 5]
    spam_cache[uid].append(now)

    if len(spam_cache[uid]) >= 5:
        try:
            await message.delete()
        except:
            pass

        await user.timeout(
            datetime.timedelta(minutes=5),
            reason="A spammelés tilos"
        )

        await message.channel.send(
            embed(
                "🔁 Spam észlelve",
                f"{user.mention}\nIndok: **A spammelés tilos**\nBüntetés: **5 perc némítás**"
            )
        )

        spam_cache[uid].clear()
        return

    # KÁROMKODÁS
    if any(w in content for w in FORBIDDEN_WORDS):
        try:
            await message.delete()
        except:
            pass

        data = load_json(WARN_FILE, {})
        uid_str = str(user.id)
        data.setdefault(uid_str, []).append("Káromkodás")
        save_json(WARN_FILE, data)

        warn_count = len(data[uid_str])
        mute_minutes = warn_count * 2

        await user.timeout(
            datetime.timedelta(minutes=mute_minutes),
            reason="Káromkodás"
        )

        await message.channel.send(
            embed(
                "🤬 Káromkodás",
                f"{user.mention}\nFigyelmeztetések száma: **{warn_count}**\n"
                f"Büntetés: **{mute_minutes} perc némítás**"
            )
        )
        return

    await bot.process_commands(message)

# ================== ÜDVÖZLÉS + AUTOROLE ==================

@bot.event
async def on_member_join(member):
    # AUTOROLE
    role_data = load_json(AUTO_ROLE_FILE, {})
    role_id = role_data.get("role_id")
    if role_id:
        role = member.guild.get_role(role_id)
        if role:
            try:
                await member.add_roles(role, reason="Automatikus rang belépéskor")
            except:
                pass

    # ÜDVÖZLŐ
    data = load_json(WELCOME_FILE, {})
    channel_id = data.get("channel_id")
    if not channel_id:
        return

    channel = member.guild.get_channel(channel_id)
    if not channel:
        return

    await channel.send(
        f"{member.mention} köszönjük, hogy csatlakoztál a szerverünkhöz! "
        f"Érezd jól magad! "
        f"Te vagy a(z) **{member.guild.member_count}. tag**!"
    )

# ================== KILÉPÉS ==================

@bot.event
async def on_member_remove(member):
    data = load_json(LEAVE_FILE, {})
    channel_id = data.get("channel_id")
    if not channel_id:
        return

    channel = member.guild.get_channel(channel_id)
    if not channel:
        return

    await channel.send(
        f"🚪 **Kilépett a szerverről:** {member.mention} ({member.name})\n"
        f"Köszönjük, hogy itt voltál, reméljük jól érezted magad! 💙"
    )

# ================== BEÁLLÍTÓ PARANCSOK ==================

@bot.tree.command(name="udvozlo_beallitas")
async def udvozlo_beallitas(interaction, csatorna: discord.TextChannel):
    save_json(WELCOME_FILE, {"channel_id": csatorna.id})
    await interaction.response.send_message("✅ Üdvözlő beállítva", ephemeral=True)

@bot.tree.command(name="kilepo_beallitas")
async def kilepo_beallitas(interaction, csatorna: discord.TextChannel):
    save_json(LEAVE_FILE, {"channel_id": csatorna.id})
    await interaction.response.send_message("✅ Kilépés csatorna beállítva", ephemeral=True)

@bot.tree.command(name="autorole_beallitas")
async def autorole_beallitas(interaction, rang: discord.Role):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Nincs jogod", ephemeral=True)

    save_json(AUTO_ROLE_FILE, {"role_id": rang.id})
    await interaction.response.send_message(
        f"✅ Automatikus rang beállítva: {rang.mention}",
        ephemeral=True
    )

# ================== MOND ==================

@bot.tree.command(name="mond")
async def mond(interaction, szoveg: str):
    if not interaction.user.guild_permissions.manage_messages:
        return await interaction.response.send_message("❌ Nincs jogod", ephemeral=True)

    await interaction.response.send_message("✅ Üzenet elküldve", ephemeral=True)
    await interaction.channel.send(szoveg)

# ================== VIDEÓKÜLDÉS ==================

@bot.tree.command(name="videokuldes")
async def videokuldes(interaction, video: discord.Attachment, szoveg: str):
    if not interaction.user.guild_permissions.manage_messages:
        return await interaction.response.send_message("❌ Nincs jogod", ephemeral=True)

    await interaction.response.send_message("✅ Bizonyíték elküldve", ephemeral=True)
    await interaction.channel.send(szoveg)
    await interaction.channel.send("📸 **Bizonyíték:**")
    await interaction.channel.send(file=await video.to_file())

# ================== FUN PARANCSOK ==================

@bot.tree.command(name="iq_teszt")
async def iq_teszt(interaction, felhasznalo: discord.Member = None):
    f = felhasznalo or interaction.user
    await interaction.response.send_message(
        embed("🧠 IQ teszt", f"{f.mention} IQ-ja: **{random.randint(60,160)}**")
    )

@bot.tree.command(name="szerelemteszt")
async def szerelemteszt(interaction, elso: discord.Member, masodik: discord.Member):
    await interaction.response.send_message(
        embed("❤️ Szerelemteszt",
              f"{elso.mention} ❤️ {masodik.mention}\n"
              f"Összeillés: **{random.randint(0,100)}%**")
    )

@bot.tree.command(name="hazasodas")
async def hazasodas(interaction, elso: discord.Member, masodik: discord.Member):
    await interaction.response.send_message(
        embed("💍 Házasság", f"{elso.mention} 💍 {masodik.mention}")
    )

@bot.tree.command(name="pofon")
async def pofon(interaction, felhasznalo: discord.Member):
    await interaction.response.send_message(
        embed("👋 Pofon", f"{interaction.user.mention} 👋 {felhasznalo.mention}")
    )

@bot.tree.command(name="szakitas")
async def szakitas(interaction, elso: discord.Member, masodik: discord.Member):
    await interaction.response.send_message(
        embed("💔 Szakítás", f"{elso.mention} 💔 {masodik.mention}")
    )

@bot.tree.command(name="csok")
async def csok(interaction, felhasznalo: discord.Member):
    await interaction.response.send_message(
        embed("💋 Csók", f"{interaction.user.mention} 💋 {felhasznalo.mention}")
    )

# ================== INDÍTÁS ==================

bot.run(TOKEN)
