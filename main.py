import discord
from discord.ext import commands
from discord import app_commands
import os, json, datetime, asyncio, re, random

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
    return discord.Embed(title=title, description=text, color=discord.Color.blue())

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

    # LINK SZŰRŐ – 10 PERC
    if re.search(LINK_REGEX, content):
        await message.delete()
        await user.timeout(datetime.timedelta(minutes=10), reason="A linkek tiltottak")
        await message.channel.send(
            embed("🔗 Link törölve",
                  f"{user.mention}\nIndok: **A linkek tiltottak**\nBüntetés: **10 perc némítás**")
        )
        return

    # SPAM SZŰRŐ – 5 PERC
    spam_cache.setdefault(user.id, [])
    spam_cache[user.id] = [t for t in spam_cache[user.id] if (now - t).seconds < 5]
    spam_cache[user.id].append(now)

    if len(spam_cache[user.id]) >= 5:
        await message.delete()
        await user.timeout(datetime.timedelta(minutes=5), reason="A spammelés tilos")
        await message.channel.send(
            embed("🔁 Spam",
                  f"{user.mention}\nIndok: **A spammelés tilos**\nBüntetés: **5 perc némítás**")
        )
        spam_cache[user.id].clear()
        return

    # KÁROMKODÁS – +2 PERC / WARN
    if any(w in content for w in FORBIDDEN_WORDS):
        await message.delete()

        data = load_json(WARN_FILE, {})
        uid = str(user.id)
        data.setdefault(uid, []).append("Káromkodás")
        save_json(WARN_FILE, data)

        warn_count = len(data[uid])
        mute_minutes = warn_count * 2

        await user.timeout(
            datetime.timedelta(minutes=mute_minutes),
            reason="Káromkodás"
        )

        await message.channel.send(
            embed("🤬 Káromkodás",
                  f"{user.mention}\nFigyelmeztetések: **{warn_count}**\n"
                  f"Büntetés: **{mute_minutes} perc némítás**")
        )
        return

    await bot.process_commands(message)

# ================== BELÉPÉS ==================

@bot.event
async def on_member_join(member):
    # AUTOROLE
    role_data = load_json(AUTO_ROLE_FILE, {})
    role_id = role_data.get("role_id")
    if role_id:
        role = member.guild.get_role(role_id)
        if role:
            await member.add_roles(role, reason="Automatikus rang")

    # ÜDVÖZLÉS (NEM EMBED)
    data = load_json(WELCOME_FILE, {})
    channel = member.guild.get_channel(data.get("channel_id", 0))
    if channel:
        await channel.send(
            f"{member.mention} köszönjük, hogy csatlakoztál! "
            f"Te vagy a(z) **{member.guild.member_count}. tag**!"
        )

# ================== KILÉPÉS ==================

@bot.event
async def on_member_remove(member):
    data = load_json(LEAVE_FILE, {})
    channel = member.guild.get_channel(data.get("channel_id", 0))
    if channel:
        await channel.send(
            f"🚪 **Kilépett a szerverről:** {member.mention} ({member.name})\n"
            f"Köszönjük, hogy itt voltál, reméljük jól érezted magad! 💙"
        )

# ================== BEÁLLÍTÁSOK ==================

@bot.tree.command(name="udvozlo_beallitas")
async def udvozlo_beallitas(interaction, csatorna: discord.TextChannel):
    save_json(WELCOME_FILE, {"channel_id": csatorna.id})
    await interaction.response.send_message("✅ Üdvözlő beállítva", ephemeral=True)

@bot.tree.command(name="kilepo_beallitas")
async def kilepo_beallitas(interaction, csatorna: discord.TextChannel):
    save_json(LEAVE_FILE, {"channel_id": csatorna.id})
    await interaction.response.send_message("✅ Kilépés beállítva", ephemeral=True)

@bot.tree.command(name="autorole_beallitas")
async def autorole_beallitas(interaction, rang: discord.Role):
    save_json(AUTO_ROLE_FILE, {"role_id": rang.id})
    await interaction.response.send_message("✅ Automatikus rang beállítva", ephemeral=True)

# ================== MOD PARANCSOK ==================

@bot.tree.command(name="kitiltas")
async def kitiltas(interaction, felhasznalo: discord.Member, indok: str):
    await felhasznalo.ban(reason=indok)
    await interaction.response.send_message(
        embed("🚫 Kitiltás", f"{felhasznalo.mention}\nIndok: **{indok}**")
    )

@bot.tree.command(name="kirugas")
async def kirugas(interaction, felhasznalo: discord.Member, indok: str):
    await felhasznalo.kick(reason=indok)
    await interaction.response.send_message(
        embed("👢 Kirúgás", f"{felhasznalo.mention}\nIndok: **{indok}**")
    )

@bot.tree.command(name="id_kitiltas")
async def id_kitiltas(interaction, felhasznalo_id: str, indok: str):
    user = await bot.fetch_user(int(felhasznalo_id))
    await interaction.guild.ban(user, reason=indok)
    await interaction.response.send_message(
        embed("🚫 ID kitiltás", f"ID: `{felhasznalo_id}`\nIndok: **{indok}**")
    )

@bot.tree.command(name="nemitas")
async def nemitas(interaction, felhasznalo: discord.Member, percek: int, indok: str):
    await felhasznalo.timeout(datetime.timedelta(minutes=percek), reason=indok)
    await interaction.response.send_message(
        embed("🔇 Némítás",
              f"{felhasznalo.mention}\nIdő: **{percek} perc**\nIndok: **{indok}**")
    )

@bot.tree.command(name="figyelmeztetes")
async def figyelmeztetes(interaction, felhasznalo: discord.Member, indok: str):
    data = load_json(WARN_FILE, {})
    uid = str(felhasznalo.id)
    data.setdefault(uid, []).append(indok)
    save_json(WARN_FILE, data)

    warn_count = len(data[uid])
    mute_minutes = warn_count * 2

    await felhasznalo.timeout(
        datetime.timedelta(minutes=mute_minutes),
        reason=indok
    )

    await interaction.response.send_message(
        embed("⚠️ Figyelmeztetés",
              f"{felhasznalo.mention}\nIndok: **{indok}**\n"
              f"Figyelmeztetések: **{warn_count}**\n"
              f"Automatikus némítás: **{mute_minutes} perc**")
    )

# ================== MOND ==================

@bot.tree.command(name="mond")
async def mond(interaction, szoveg: str):
    await interaction.channel.send(szoveg)
    await interaction.response.send_message("✅ Elkuldve", ephemeral=True)

# ================== VIDEÓ ==================

@bot.tree.command(name="videokuldes")
async def videokuldes(interaction, video: discord.Attachment, szoveg: str):
    await interaction.channel.send(szoveg)
    await interaction.channel.send("📸 **Bizonyíték:**")
    await interaction.channel.send(file=await video.to_file())
    await interaction.response.send_message("✅ Videó elküldve", ephemeral=True)

# ================== FUN ==================

@bot.tree.command(name="iq_teszt")
async def iq_teszt(interaction):
    await interaction.response.send_message(
        embed("🧠 IQ teszt", f"Az IQ-d: **{random.randint(60,160)}**")
    )

@bot.tree.command(name="szerelemteszt")
async def szerelemteszt(interaction, elso: discord.Member, masodik: discord.Member):
    await interaction.response.send_message(
        embed("❤️ Szerelem", f"{elso.mention} ❤️ {masodik.mention}\n"
                              f"{random.randint(0,100)}%")
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
