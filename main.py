import discord
from discord.ext import commands
from discord import app_commands
import os, json, datetime, asyncio, re, random

# ================== ALAP ==================

TOKEN = os.getenv("DISCORD_TOKEN")

WARN_FILE = "warns.json"
WELCOME_FILE = "welcome.json"
LEAVE_FILE = "leave.json"
AUTO_ROLE_FILE = "autorole.json"
LOG_FILE = "log.json"
GIVEAWAY_FILE = "giveaways.json"

FORBIDDEN_WORDS = ["fasz","geci","buzi","bazdmeg","anyad","anyád","kurva","szar"]
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

def szep_embed(cim, leiras, szin=discord.Color.red()):
    embed = discord.Embed(
        title=cim,
        description=leiras,
        color=szin,
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text="✨ DT_bluuuue szervere ✨")
    return embed

def get_log_channel(guild):
    data = load_json(LOG_FILE, {})
    cid = data.get(str(guild.id))
    return guild.get_channel(cid) if cid else None

# ================== JOGOSULTSÁG ==================

def mod_vagy_admin(interaction: discord.Interaction):
    p = interaction.user.guild_permissions
    return p.manage_messages or p.administrator

def middleman_check(interaction: discord.Interaction):
    allowed = ["Middleman", "Middleman+", "Fő Middleman"]
    return any(r.name in allowed for r in interaction.user.roles)

# ================== BOT ==================

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print("✅ Bot online")

@bot.tree.error
async def on_app_error(interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("❌ Nincs jogosultságod!", ephemeral=True)

# ================== AUTOMOD ==================

spam_cache = {}

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user = message.author
    content = message.content.lower()
    now = datetime.datetime.utcnow()

    # LINK
    if re.search(LINK_REGEX, content):
        await message.delete()
        await user.timeout(datetime.timedelta(minutes=10), reason="A linkek tiltottak")
        await message.channel.send(embed=szep_embed(
            "🔗 Tiltott link",
            f"{user.mention}\n📄 Indok: **A linkek tiltottak**\n🔇 10 perc némítás"
        ))
        return

    # SPAM
    spam_cache.setdefault(user.id, [])
    spam_cache[user.id] = [t for t in spam_cache[user.id] if (now - t).seconds < 5]
    spam_cache[user.id].append(now)

    if len(spam_cache[user.id]) >= 5:
        await message.delete()
        await user.timeout(datetime.timedelta(minutes=5), reason="Spam tilos")
        await message.channel.send(embed=szep_embed(
            "🔁 Spam",
            f"{user.mention}\n📄 Indok: **Spam tilos**\n🔇 5 perc némítás"
        ))
        spam_cache[user.id].clear()
        return

    # KÁROMKODÁS
    if any(w in content for w in FORBIDDEN_WORDS):
        await message.delete()
        data = load_json(WARN_FILE, {})
        uid = str(user.id)
        data.setdefault(uid, []).append("Káromkodás")
        save_json(WARN_FILE, data)
        mute = len(data[uid]) * 2
        await user.timeout(datetime.timedelta(minutes=mute), reason="Káromkodás")
        await message.channel.send(embed=szep_embed(
            "🤬 Káromkodás",
            f"{user.mention}\n📊 Figyelmeztetések: **{len(data[uid])}**\n🔇 {mute} perc némítás"
        ))
        return

    await bot.process_commands(message)

# ================== BELÉPÉS / KILÉPÉS ==================

@bot.event
async def on_member_join(member):
    role_data = load_json(AUTO_ROLE_FILE, {})
    role = member.guild.get_role(role_data.get("role_id", 0))
    if role:
        await member.add_roles(role)

    data = load_json(WELCOME_FILE, {})
    ch = member.guild.get_channel(data.get("channel_id", 0))
    if ch:
        await ch.send(f"{member.mention} üdv a szerveren! Te vagy a(z) **{member.guild.member_count}. tag**")

@bot.event
async def on_member_remove(member):
    data = load_json(LEAVE_FILE, {})
    ch = member.guild.get_channel(data.get("channel_id", 0))
    if ch:
        await ch.send(
            f"🚪 **Kilépett a szerverről:** {member.mention} ({member.name})\n"
            f"Köszönjük, hogy itt voltál, reméljük jól érezted magad! 💙"
        )

# ================== BEÁLLÍTÁS PARANCSOK ==================

@bot.tree.command(name="log")
@app_commands.check(mod_vagy_admin)
async def log(interaction, csatorna: discord.TextChannel):
    data = load_json(LOG_FILE, {})
    data[str(interaction.guild.id)] = csatorna.id
    save_json(LOG_FILE, data)
    await interaction.response.send_message(embed=szep_embed(
        "📁 Log beállítva", f"{csatorna.mention}"
    ), ephemeral=True)

@bot.tree.command(name="udvozlo_beallitas")
@app_commands.check(mod_vagy_admin)
async def udv(interaction, csatorna: discord.TextChannel):
    save_json(WELCOME_FILE, {"channel_id": csatorna.id})
    await interaction.response.send_message("✅ Üdvözlő beállítva", ephemeral=True)

@bot.tree.command(name="kilepo_beallitas")
@app_commands.check(mod_vagy_admin)
async def kilep(interaction, csatorna: discord.TextChannel):
    save_json(LEAVE_FILE, {"channel_id": csatorna.id})
    await interaction.response.send_message("✅ Kilépés beállítva", ephemeral=True)

@bot.tree.command(name="autorole_beallitas")
@app_commands.check(mod_vagy_admin)
async def autorole(interaction, rang: discord.Role):
    save_json(AUTO_ROLE_FILE, {"role_id": rang.id})
    await interaction.response.send_message("✅ Autorole beállítva", ephemeral=True)

# ================== MOD PARANCSOK ==================

@bot.tree.command(name="kitiltas")
@app_commands.check(mod_vagy_admin)
async def kitiltas(interaction, felhasznalo: discord.Member, indok: str):
    await felhasznalo.ban(reason=indok)
    await interaction.response.send_message(embed=szep_embed(
        "🚫 Kitiltás", f"{felhasznalo.mention}\n📄 {indok}"
    ))

@bot.tree.command(name="kirugas")
@app_commands.check(mod_vagy_admin)
async def kirugas(interaction, felhasznalo: discord.Member, indok: str):
    await felhasznalo.kick(reason=indok)
    await interaction.response.send_message(embed=szep_embed(
        "👢 Kirúgás", f"{felhasznalo.mention}\n📄 {indok}"
    ))

@bot.tree.command(name="id_kitiltas")
@app_commands.check(mod_vagy_admin)
async def idkitiltas(interaction, felhasznalo_id: str, indok: str):
    user = await bot.fetch_user(int(felhasznalo_id))
    await interaction.guild.ban(user, reason=indok)
    await interaction.response.send_message(embed=szep_embed(
        "🚫 ID alapú kitiltás", f"🆔 {felhasznalo_id}\n📄 {indok}"
    ))

@bot.tree.command(name="nemitas")
@app_commands.check(mod_vagy_admin)
async def nemitas(interaction, felhasznalo: discord.Member, percek: int, indok: str):
    await felhasznalo.timeout(datetime.timedelta(minutes=percek), reason=indok)
    await interaction.response.send_message(embed=szep_embed(
        "🔇 Némítás", f"{felhasznalo.mention}\n⏱ {percek} perc\n📄 {indok}"
    ))

@bot.tree.command(name="figyelmeztetes")
@app_commands.check(mod_vagy_admin)
async def figy(interaction, felhasznalo: discord.Member, indok: str):
    data = load_json(WARN_FILE, {})
    uid = str(felhasznalo.id)
    data.setdefault(uid, []).append(indok)
    save_json(WARN_FILE, data)
    mute = len(data[uid]) * 2
    await felhasznalo.timeout(datetime.timedelta(minutes=mute), reason=indok)
    await interaction.response.send_message(embed=szep_embed(
        "⚠️ Figyelmeztetés",
        f"{felhasznalo.mention}\n📄 {indok}\n🔇 {mute} perc"
    ))

# ================== TICKET PANEL ==================

class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="┏〔👤〕 TGF", description="Tagfelvételi jelentkezés"),
            discord.SelectOption(label="┠〔❓〕 Kérdés", description="Általános kérdés"),
            discord.SelectOption(label="┠〔❗〕 Panasz", description="Panasz bejelentés"),
            discord.SelectOption(label="┠〔⏰〕 Middleman váró", description="Trade lebonyolítás"),
            discord.SelectOption(label="┗〔📝〕 Egyéb", description="Egyéb ügy")
        ]
        super().__init__(placeholder="Válassz ticket kategóriát…", options=options)

    async def callback(self, interaction):
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True)
        }
        ch = await interaction.guild.create_text_channel(
            f"ticket-{interaction.user.name}", overwrites=overwrites
        )
        await interaction.response.send_message(f"🎫 Ticket létrehozva: {ch.mention}", ephemeral=True)
        await ch.send(embed=szep_embed(
            "🎫 Ticket megnyitva",
            f"📂 Kategória: **{self.values[0]}**"
        ))

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

@bot.tree.command(name="ticket_panel")
@app_commands.check(mod_vagy_admin)
async def ticket_panel(interaction):
    await interaction.response.send_message(
        embed=szep_embed("🎫 Ticket rendszer", "Válassz kategóriát!"),
        view=TicketView()
    )

@bot.tree.command(name="hozzaad")
@app_commands.check(middleman_check)
async def hozzaad(interaction, felhasznalo: discord.Member):
    if not interaction.channel.name.startswith("ticket-"):
        return await interaction.response.send_message("❌ Csak ticketben!", ephemeral=True)
    await interaction.channel.set_permissions(felhasznalo, view_channel=True, send_messages=True)
    await interaction.response.send_message(embed=szep_embed(
        "➕ Hozzáadva", f"{felhasznalo.mention}"
    ))

# ================== NYEREMÉNYJÁTÉK ==================

@bot.tree.command(name="nyeremenyjatek")
@app_commands.check(mod_vagy_admin)
async def nyer(interaction, ido_perc: int, nyeremeny: str):
    embed = discord.Embed(
        title="🎉 NYEREMÉNYJÁTÉK 🎉",
        description=f"🎁 {nyeremeny}\n⏰ {ido_perc} perc\n🎉 Reagálj 🎉",
        color=discord.Color.purple()
    )
    embed.set_footer(text="✨ DT_bluuuue szervere ✨")
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("🎉")
    await interaction.response.send_message("✅ Elindítva", ephemeral=True)
    await asyncio.sleep(ido_perc * 60)
    m = await interaction.channel.fetch_message(msg.id)
    r = discord.utils.get(m.reactions, emoji="🎉")
    users = [u async for u in r.users() if not u.bot]
    if users:
        winner = random.choice(users)
        await interaction.channel.send(embed=szep_embed(
            "🏆 NYERTES", f"{winner.mention}\n🎁 {nyeremeny}", discord.Color.green()
        ))

@bot.tree.command(name="reroll")
@app_commands.check(mod_vagy_admin)
async def reroll(interaction, uzenet_id: str):
    msg = await interaction.channel.fetch_message(int(uzenet_id))
    r = discord.utils.get(msg.reactions, emoji="🎉")
    users = [u async for u in r.users() if not u.bot]
    if users:
        await interaction.response.send_message(embed=szep_embed(
            "🔄 Új nyertes", f"{random.choice(users).mention}", discord.Color.green()
        ))

# ================== INDÍTÁS ==================

bot.run(TOKEN)
