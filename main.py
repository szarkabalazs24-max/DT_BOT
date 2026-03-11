import discord
from discord.ext import commands, tasks
from discord import app_commands
import os, json, datetime, re, random, asyncio

# ================== TOKEN ==================
TOKEN = os.getenv("DISCORD_TOKEN")

# ================== FILEOK ==================
WARN_FILE = "warns.json"
AUTOMOD_LOG_FILE = "automod_log.json"
WELCOME_FILE = "welcome.json"
LEAVE_FILE = "leave.json"
AUTOROLE_FILE = "autorole.json"
AUTOREACT_FILE = "autoreact.json"
GIVEAWAY_FILE = "giveaway.json"

# ================== KONFIG ==================
FOOTER = "✨ DT_bluuuue szervere ✨"
LINK_REGEX = r"http[s]?://"
FORBIDDEN_WORDS = ["fasz","geci","buzi","bazdmeg","kurva","anyad","anyád"]

MOD_ROLES = ["Moderátor", "Moderátor+", "Adminisztrátor", "Tulajdonos"]
HOZZAAD_ROLES = ["Moderátor","Moderátor+","Tulajdonos","Middleman","Middleman+","Fő Middleman"]

# ================== SEGÉD ==================
def load_json(f, d):
    if not os.path.exists(f):
        return d
    with open(f, "r", encoding="utf-8") as file:
        return json.load(file)

def save_json(f, d):
    with open(f, "w", encoding="utf-8") as file:
        json.dump(d, file, indent=4, ensure_ascii=False)

def embed(t, d, c=discord.Color.blue()):
    e = discord.Embed(title=t, description=d, color=c)
    e.set_footer(text=FOOTER)
    return e

def has_role(member, roles):
    return any(r.name in roles for r in member.roles)

# ================== BOT ==================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
spam = {}

@bot.event
async def on_ready():
    await bot.tree.sync()
    giveaway_check.start()
    print("✅ BOT ONLINE")

# ================== BELÉPÉS ==================
@bot.event
async def on_member_join(m):
    ar = load_json(AUTOROLE_FILE,{})
    rid = ar.get(str(m.guild.id))
    if rid:
        role = m.guild.get_role(rid)
        if role:
            await m.add_roles(role)

    wc = load_json(WELCOME_FILE,{})
    cid = wc.get(str(m.guild.id))
    if cid:
        ch = m.guild.get_channel(cid)
        if ch:
            await ch.send(
                f"{m.mention} Üdv a szerveren!\n"
                f"Köszönjük hogy csatlakoztál 💙\n"
                f"Te vagy a(z) **{m.guild.member_count}. tag**"
            )

# ================== KILÉPÉS ==================
@bot.event
async def on_member_remove(m):
    lc = load_json(LEAVE_FILE,{})
    cid = lc.get(str(m.guild.id))
    if cid:
        ch = m.guild.get_channel(cid)
        if ch:
            await ch.send(
                f"🚪 Kilépett a szerverről: {m.mention}\n"
                f"Köszönjük hogy itt voltál, reméljük jól érezted magad 💙"
            )

# ================== AUTOMOD + AUTOREACT ==================
@bot.event
async def on_message(msg):
    if msg.author.bot:
        return

    # AUTOREACT
    ar = load_json(AUTOREACT_FILE,{})
    emo = ar.get(str(msg.channel.id))
    if emo:
        try:
            if emo.isdigit():
                e = bot.get_emoji(int(emo))
                if e:
                    await msg.add_reaction(e)
            else:
                await msg.add_reaction(emo)
        except:
            pass

    logch = None
    lg = load_json(AUTOMOD_LOG_FILE,{})
    if str(msg.guild.id) in lg:
        logch = msg.guild.get_channel(lg[str(msg.guild.id)])

    # LINK
    if re.search(LINK_REGEX, msg.content.lower()):
        await msg.delete()
        await msg.author.timeout(datetime.timedelta(minutes=10), reason="Linkek tiltottak")
        if logch:
            await logch.send(embed(
                "🔗 Tiltott link",
                f"{msg.author.mention}\n🔇 10 perc",
                discord.Color.red()
            ))
        return

    # SPAM
    spam.setdefault(msg.author.id, [])
    spam[msg.author.id].append(datetime.datetime.utcnow())
    spam[msg.author.id] = [t for t in spam[msg.author.id] if (datetime.datetime.utcnow()-t).seconds < 5]
    if len(spam[msg.author.id]) >= 5:
        await msg.delete()
        await msg.author.timeout(datetime.timedelta(minutes=5), reason="Spam tilos")
        if logch:
            await logch.send(embed(
                "🔁 Spam",
                f"{msg.author.mention}\n🔇 5 perc",
                discord.Color.orange()
            ))
        spam[msg.author.id].clear()
        return

    # KÁROMKODÁS
    if any(w in msg.content.lower() for w in FORBIDDEN_WORDS):
        await msg.delete()
        warns = load_json(WARN_FILE,{})
        uid = str(msg.author.id)
        warns.setdefault(uid, []).append("Káromkodás")
        save_json(WARN_FILE, warns)
        mute = len(warns[uid]) * 2
        await msg.author.timeout(datetime.timedelta(minutes=mute), reason="Káromkodás")
        if logch:
            await logch.send(embed(
                "🤬 Káromkodás",
                f"{msg.author.mention}\n🔇 {mute} perc",
                discord.Color.dark_red()
            ))
        return

    await bot.process_commands(msg)

# ================== BEÁLLÍTÁS PARANCSOK ==================
@bot.tree.command(name="welcome")
async def welcome(i, csatorna: discord.TextChannel):
    if not has_role(i.user, MOD_ROLES): return
    save_json(WELCOME_FILE,{str(i.guild.id): csatorna.id})
    await i.response.send_message("✅ Üdvözlő beállítva", ephemeral=True)

@bot.tree.command(name="leave")
async def leave(i, csatorna: discord.TextChannel):
    if not has_role(i.user, MOD_ROLES): return
    save_json(LEAVE_FILE,{str(i.guild.id): csatorna.id})
    await i.response.send_message("✅ Kilépő beállítva", ephemeral=True)

@bot.tree.command(name="autorole")
async def autorole(i, rang: discord.Role):
    if not has_role(i.user, MOD_ROLES): return
    save_json(AUTOROLE_FILE,{str(i.guild.id): rang.id})
    await i.response.send_message("✅ Autorole beállítva", ephemeral=True)

@bot.tree.command(name="automod_log")
async def automod_log(i, csatorna: discord.TextChannel):
    if not has_role(i.user, MOD_ROLES): return
    save_json(AUTOMOD_LOG_FILE,{str(i.guild.id): csatorna.id})
    await i.response.send_message("✅ Automod log beállítva", ephemeral=True)

# ================== FIGYELMEZTETÉS ==================
@bot.tree.command(name="figyelmeztetes")
async def figy(i, tag: discord.Member, indok: str):
    if not has_role(i.user, MOD_ROLES): return
    w = load_json(WARN_FILE,{})
    w.setdefault(str(tag.id), []).append(indok)
    save_json(WARN_FILE, w)
    await i.response.send_message(embed(
        "⚠️ Figyelmeztetés",
        f"{tag.mention}\nIndok: {indok}\nÖsszes: {len(w[str(tag.id)])}",
        discord.Color.orange()
    ))

@bot.tree.command(name="figyelmeztetesek")
async def figylist(i, tag: discord.Member):
    if not has_role(i.user, MOD_ROLES): return
    w = load_json(WARN_FILE,{})
    l = w.get(str(tag.id), [])
    if not l:
        await i.response.send_message("❌ Nincs figyelmeztetése", ephemeral=True)
        return
    txt = "\n".join(f"{n+1}. {v}" for n,v in enumerate(l))
    await i.response.send_message(embed("📋 Figyelmeztetések", txt))

@bot.tree.command(name="figyelmeztetes_torles")
async def figydel(i, tag: discord.Member, sorszam: int):
    if not has_role(i.user, MOD_ROLES): return
    w = load_json(WARN_FILE,{})
    uid = str(tag.id)
    if uid not in w or sorszam < 1 or sorszam > len(w[uid]):
        await i.response.send_message("❌ Hibás sorszám", ephemeral=True)
        return
    torolt = w[uid].pop(sorszam-1)
    save_json(WARN_FILE, w)
    await i.response.send_message(embed(
        "🗑 Figyelmeztetés törölve",
        f"Törölt: {torolt}\nMaradt: {len(w[uid])}",
        discord.Color.red()
    ))

# ================== NÉMÍTÁS / KITILTÁS ==================
@bot.tree.command(name="nemitas")
async def mute(i, tag: discord.Member, percek: int, indok: str):
    if not has_role(i.user, MOD_ROLES): return
    await tag.timeout(datetime.timedelta(minutes=percek), reason=indok)
    await i.response.send_message(embed(
        "🔇 Némítás",
        f"{tag.mention}\nIdő: {percek} perc\nIndok: {indok}"
    ))

@bot.tree.command(name="kirugas")
async def kick(i, tag: discord.Member, indok: str):
    if not has_role(i.user, MOD_ROLES): return
    await tag.kick(reason=indok)
    await i.response.send_message(embed(
        "👢 Kirúgás",
        f"{tag.mention}\nIndok: {indok}",
        discord.Color.red()
    ))

@bot.tree.command(name="kitiltas")
async def ban(i, tag: discord.Member, indok: str):
    if not has_role(i.user, MOD_ROLES): return
    await tag.ban(reason=indok)
    await i.response.send_message(embed(
        "🚫 Kitiltás",
        f"{tag.mention}\nIndok: {indok}",
        discord.Color.dark_red()
    ))

@bot.tree.command(name="id_kitiltas")
async def idban(i, felhasznalo_id: str, indok: str):
    if not has_role(i.user, MOD_ROLES): return
    u = await bot.fetch_user(int(felhasznalo_id))
    await i.guild.ban(u, reason=indok)
    await i.response.send_message(embed(
        "🚫 ID alapú kitiltás",
        f"ID: {felhasznalo_id}\nIndok: {indok}",
        discord.Color.dark_red()
    ))

# ================== AUTOREACT ==================
@bot.tree.command(name="autoreact_add")
async def autoreact_add(i, csatorna: discord.TextChannel, emoji: str):
    if not has_role(i.user, MOD_ROLES): return
    d = load_json(AUTOREACT_FILE,{})
    d[str(csatorna.id)] = emoji
    save_json(AUTOREACT_FILE, d)
    await i.response.send_message("✅ Autoreact beállítva", ephemeral=True)

# ================== GIVEAWAY ==================
@bot.tree.command(name="nyeremenyjatek")
async def nyeremenyjatek(i, nyeremeny: str, percek: int):
    if not has_role(i.user, MOD_ROLES): return
    end = (datetime.datetime.utcnow() + datetime.timedelta(minutes=percek)).isoformat()
    g = load_json(GIVEAWAY_FILE,{})
    g[str(i.id)] = {"channel": i.channel.id, "prize": nyeremeny, "end": end, "ended": False}
    save_json(GIVEAWAY_FILE, g)
    await i.response.send_message(embed(
        "🎉 Nyereményjáték",
        f"Nyeremény: {nyeremeny}\nIdő: {percek} perc"
    ))

@tasks.loop(seconds=30)
async def giveaway_check():
    g = load_json(GIVEAWAY_FILE,{})
    now = datetime.datetime.utcnow()
    for k,v in g.items():
        if not v["ended"] and now >= datetime.datetime.fromisoformat(v["end"]):
            ch = bot.get_channel(v["channel"])
            if ch:
                await ch.send(embed("🎉 Nyereményjáték vége", v["prize"]))
            v["ended"] = True
    save_json(GIVEAWAY_FILE, g)

# ================== FUN / SZERELEM ==================
@bot.tree.command(name="csok")
async def csok(i, tag: discord.Member):
    await i.response.send_message(f"{i.user.mention} 💋 {tag.mention}")

@bot.tree.command(name="szerelemteszt")
async def szerelemteszt(i, tag: discord.Member):
    await i.response.send_message(embed("❤️ Szerelem teszt", f"{random.randint(1,100)}%"))

@bot.tree.command(name="hazasodas")
async def hazasodas(i, tag: discord.Member):
    await i.response.send_message(embed("💍 Házasság", f"{i.user.mention} 💍 {tag.mention}"))

@bot.tree.command(name="iqteszt")
async def iqteszt(i):
    await i.response.send_message(embed("🧠 IQ teszt", str(random.randint(60,160))))

@bot.tree.command(name="rizz")
async def rizz(i):
    await i.response.send_message(embed(
        "💘 Rizz",
        random.choice([
            "Hiszel a szerelemben első látásra?",
            "Elvesztem a szemedben.",
            "Van térképed? Elvesztem benned."
        ])
    ))

# ================== INDÍTÁS ==================
bot.run(TOKEN)
