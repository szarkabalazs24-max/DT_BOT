import discord
from discord.ext import commands
from discord import app_commands
import os, json, datetime, asyncio, re, random

TOKEN = os.getenv("DISCORD_TOKEN")

WARN_FILE = "warns.json"
WELCOME_FILE = "welcome.json"
GIVEAWAY_LOG_FILE = "giveaway_log.json"

FORBIDDEN_WORDS = ["fasz","geci","meleg","fsz","gci","szarka","Szarka","buzi","bazdmeg","anyad","anyád"]
LINK_REGEX = r"http[s]?://"

FOOTER = "✨ DT_bluuuue szervere ✨"

def load_json(f, d):
    if not os.path.exists(f):
        return d
    with open(f, "r") as file:
        return json.load(file)

def save_json(f, d):
    with open(f, "w") as file:
        json.dump(d, file, indent=4)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot online: {bot.user}")

def embed(t, d):
    e = discord.Embed(title=t, description=d, color=discord.Color.blue())
    e.set_footer(text=FOOTER)
    return e

# ================= AUTOMOD =================

@bot.event
async def on_message(msg):
    if msg.author.bot:
        return
    if re.search(LINK_REGEX, msg.content):
        await msg.delete()
        await msg.author.timeout(datetime.timedelta(minutes=10))
    if any(w in msg.content.lower() for w in FORBIDDEN_WORDS):
        await msg.delete()
    await bot.process_commands(msg)

# ================= ÜDVÖZLŐ =================

@bot.event
async def on_member_join(m):
    d = load_json(WELCOME_FILE, {})
    ch = m.guild.get_channel(d.get("channel_id", 0))
    if ch:
        await ch.send(embed("👋 Üdvözlünk!",
            f"{m.mention}\nÜdv a szerveren!\nTe vagy a(z) **{m.guild.member_count}. tag**"))

@bot.tree.command(name="udvozlo_beallitas")
async def udv(interaction, csatorna: discord.TextChannel):
    save_json(WELCOME_FILE, {"channel_id": csatorna.id})
    await interaction.response.send_message("✅ Üdvözlő beállítva", ephemeral=True)

# ================= MOND =================

@bot.tree.command(name="mond")
async def mond(interaction, szoveg: str):
    if not interaction.user.guild_permissions.manage_messages:
        return await interaction.response.send_message("❌ Nincs jogod", ephemeral=True)
    await interaction.response.send_message("✅ Elkuldve", ephemeral=True)
    await interaction.channel.send(szoveg)

# ================= VIDEÓ =================

@bot.tree.command(name="videokuldes")
async def videokuldes(interaction, video: discord.Attachment, szoveg: str):
    if not interaction.user.guild_permissions.manage_messages:
        return await interaction.response.send_message("❌ Nincs jogod", ephemeral=True)
    await interaction.response.send_message("✅ Bizonyíték elküldve", ephemeral=True)
    await interaction.channel.send(szoveg)
    await interaction.channel.send("📸 **Bizonyíték:**")
    await interaction.channel.send(file=await video.to_file())

# ================= FIGYELMEZTETÉS =================

@bot.tree.command(name="figyelmeztetes")
async def warn(interaction, felhasznalo: discord.Member, indok: str):
    d = load_json(WARN_FILE, {})
    d.setdefault(str(felhasznalo.id), []).append(indok)
    save_json(WARN_FILE, d)
    await interaction.response.send_message(embed("⚠️ Figyelmeztetés", indok))

@bot.tree.command(name="figyelmeztetes_lista")
async def warn_list(interaction, felhasznalo: discord.Member):
    d = load_json(WARN_FILE, {})
    w = d.get(str(felhasznalo.id), [])
    if not w:
        return await interaction.response.send_message("Nincs figyelmeztetés", ephemeral=True)
    txt = "\n".join([f"{i+1}. {x}" for i, x in enumerate(w)])
    await interaction.response.send_message(embed("⚠️ Figyelmeztetések", txt), ephemeral=True)

@bot.tree.command(name="figyelmeztetes_torles")
async def warn_del(interaction, felhasznalo: discord.Member, sorszam: int):
    d = load_json(WARN_FILE, {})
    d[str(felhasznalo.id)].pop(sorszam-1)
    save_json(WARN_FILE, d)
    await interaction.response.send_message("🧹 Törölve")

# ================= MOD =================

@bot.tree.command(name="kirugas")
async def kick(interaction, felhasznalo: discord.Member, indok: str):
    await felhasznalo.kick(reason=indok)
    await interaction.response.send_message(embed("👢 Kirúgás", indok))

@bot.tree.command(name="kitiltas")
async def ban(interaction, felhasznalo: discord.Member, indok: str):
    await felhasznalo.ban(reason=indok)
    await interaction.response.send_message(embed("🚫 Kitiltás", indok))

@bot.tree.command(name="id_kitiltas")
async def idban(interaction, felhasznalo_id: str, indok: str):
    user = await bot.fetch_user(int(felhasznalo_id))
    await interaction.guild.ban(user, reason=indok)
    await interaction.response.send_message("🚫 ID kitiltva")

@bot.tree.command(name="nemitas")
async def mute(interaction, felhasznalo: discord.Member, percek: int, indok: str):
    await felhasznalo.timeout(datetime.timedelta(minutes=percek), reason=indok)
    await interaction.response.send_message("🔇 Némítva")

@bot.tree.command(name="nemitas_feloldas")
async def unmute(interaction, felhasznalo: discord.Member):
    await felhasznalo.timeout(None)
    await interaction.response.send_message("🔊 Feloldva")

@bot.tree.command(name="vkick")
async def vkick(interaction, felhasznalo: discord.Member, indok: str):
    if felhasznalo.voice:
        await felhasznalo.move_to(None, reason=indok)
        await interaction.response.send_message("🔊 Voice kick")

@bot.tree.command(name="uzenetek_torlese")
async def purge(interaction, mennyiseg: int):
    await interaction.channel.purge(limit=mennyiseg)
    await interaction.response.send_message("🧹 Törölve", ephemeral=True)

# ================= FUN =================

@bot.tree.command(name="iq_teszt")
async def iq(interaction, felhasznalo: discord.Member = None):
    f = felhasznalo or interaction.user
    await interaction.response.send_message(embed("🧠 IQ", f"{f.mention}: {random.randint(60,160)}"))

@bot.tree.command(name="szerelemteszt")
async def love(interaction, elso: discord.Member, masodik: discord.Member):
    await interaction.response.send_message(embed("❤️ Szerelem", f"{elso.mention} ❤️ {masodik.mention}\n{random.randint(0,100)}%"))

@bot.tree.command(name="hazasodas")
async def marry(interaction, elso: discord.Member, masodik: discord.Member):
    await interaction.response.send_message(embed("💍 Házasság", f"{elso.mention} 💍 {masodik.mention}"))

@bot.tree.command(name="pofon")
async def slap(interaction, felhasznalo: discord.Member):
    await interaction.response.send_message(embed("👋 Pofon", f"{interaction.user.mention} 👋 {felhasznalo.mention}"))

@bot.tree.command(name="szakitas")
async def breakup(interaction, elso: discord.Member, masodik: discord.Member):
    await interaction.response.send_message(embed("💔 Szakítás", f"{elso.mention} 💔 {masodik.mention}"))

@bot.tree.command(name="csok")
async def kiss(interaction, felhasznalo: discord.Member):
    await interaction.response.send_message(embed("💋 Csók", f"{interaction.user.mention} 💋 {felhasznalo.mention}"))

bot.run(TOKEN)
