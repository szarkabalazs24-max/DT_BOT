import discord
from discord.ext import commands
from discord import app_commands, ui
import os, json, datetime, asyncio, random, re, sqlite3
from collections import defaultdict

# ================== KONFIGURÁCIÓ & RANGOK ==================

TOKEN = os.getenv("DISCORD_TOKEN")

# A TE SAJÁT ID-D (100% FIX)
OWNER_ID = 1436396059738898555 

# RENDSZERGAZDÁK / SUPER MODOK ID-JA (Vesszővel elválasztva, pl: [123, 456])
SUPER_MODS = [] 

# Moderátor rangok ID-jai
TESTER_MOD_ID = 1472187912161464364
MOD_ID = 1461435337791373352

# A SPECIFIKUS RANGOK ID-JA A VIDEÓHOZ
MIDDLEMAN_ID = 1462037200928641044 # {🥉} | Middle Man (100M)
SENIOR_MM_ID = 1462037351399424215  # {🥈} | Senior Middleman (250M)
ELITE_MM_ID = 1462037604139536526   # {🥇} | Elite middleman (315M+-)

# --- FÁJL ELÉRÉSI UTAK & TÁROLÁS ---
PERSISTENT_DATA_PATH = "./data/"
if not os.path.exists(PERSISTENT_DATA_PATH):
    os.makedirs(PERSISTENT_DATA_PATH, exist_ok=True)

WARN_FILE = os.path.join(PERSISTENT_DATA_PATH, "warns.json")
WELCOME_FILE = os.path.join(PERSISTENT_DATA_PATH, "welcome.json")
LEAVE_FILE = os.path.join(PERSISTENT_DATA_PATH, "leave.json")
AUTO_ROLE_FILE = os.path.join(PERSISTENT_DATA_PATH, "autorole.json")
VIDEO_FILE = os.path.join(PERSISTENT_DATA_PATH, "videos.json")
LOG_FILE = os.path.join(PERSISTENT_DATA_PATH, "logs.json")
DB_FILE = os.path.join(PERSISTENT_DATA_PATH, "giveaway.db")

# SZŰRŐ LISTÁK
FORBIDDEN_WORDS = ["fasz","geci","buzi","bazdmeg","kurva","anyád","szar","szarka","any@d","apád","cigány","cigany","barom","bazmeg","pornó","porno","nyomorék","szopj","szopjle","kutya","apad","apád","hülye","fsz","gyász"]
NSFW_WORDS = ["porn", "xvideo", "redtube", "hentai", "rule34", "porno", "pornó", "sex", "szex", "brazzers", "fuck", "cum", "dick", "pussy"]
LINK_REGEX = r"http[s]?://"
GIF_REGEX = r"https?://.*(?:tenor\.com|giphy\.com|.+\.gif)"

user_messages = defaultdict(list)

# --- ADATBÁZIS INICIALIZÁLÁSA ---
def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS participants 
                          (msg_id TEXT, user_id TEXT, UNIQUE(msg_id, user_id))''')
        conn.commit()
        conn.close()
    except:
        pass

init_db()

intents = discord.Intents.all()

# ================= SEGÉDFÜGGVÉNYEK =================

def parse_duration(duration_str):
    time_dict = {"d": 86400, "h": 3600, "m": 60}
    seconds = 0
    matches = re.findall(r"(\d+)([dhm])", duration_str.lower())
    
    display_parts = []
    for amount, unit in matches:
        amount = int(amount)
        seconds += amount * time_dict[unit]
        if unit == "d": display_parts.append(f"{amount} nap")
        elif unit == "h": display_parts.append(f"{amount} óra")
        elif unit == "m": display_parts.append(f"{amount} perc")
        
    if seconds == 0:
        try:
            val = int(duration_str)
            return val * 60, f"{val} perc"
        except: return 0, ""
        
    return seconds, ", ".join(display_parts)

def load_json(file):
    if not os.path.exists(file): return {}
    try:
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()
            if not content: return {}
            return json.loads(content)
    except: return {}

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f: 
        json.dump(data, f, indent=4, ensure_ascii=False)

def make_embed(title, desc, color):
    e = discord.Embed(title=title, description=desc, color=color, timestamp=datetime.datetime.utcnow())
    e.set_footer(text="✨ Steal a Brainrot Trade Central ✨")
    return e

async def send_log(guild, embed):
    data = load_json(LOG_FILE)
    ch_id = data.get("log_channel")
    if ch_id:
        try:
            channel = guild.get_channel(int(ch_id))
            if channel: await channel.send(embed=embed)
        except: pass

# --- JOGOSULTSÁG ELLENŐRZŐK ---

def is_target_mod(member: discord.Member):
    user_role_ids = [role.id for role in member.roles]
    return member.guild_permissions.administrator or TESTER_MOD_ID in user_role_ids or MOD_ID in user_role_ids

def tester_check(i: discord.Interaction):
    user_role_ids = [role.id for role in i.user.roles]
    return i.user.guild_permissions.administrator or i.user.id in SUPER_MODS or i.user.id == OWNER_ID or TESTER_MOD_ID in user_role_ids or MOD_ID in user_role_ids

def mod_check(i: discord.Interaction):
    user_role_ids = [role.id for role in i.user.roles]
    return i.user.guild_permissions.administrator or i.user.id in SUPER_MODS or i.user.id == OWNER_ID or MOD_ID in user_role_ids

def admin_check(i: discord.Interaction):
    return i.user.guild_permissions.administrator or i.user.id in SUPER_MODS or i.user.id == OWNER_ID

def video_check(i: discord.Interaction):
    user_role_ids = [role.id for role in i.user.roles]
    allowed_ids = [MIDDLEMAN_ID, SENIOR_MM_ID, ELITE_MM_ID]
    return i.user.guild_permissions.administrator or i.user.id in SUPER_MODS or i.user.id == OWNER_ID or any(rid in user_role_ids for rid in allowed_ids)

# ================= BOT SETUP =================

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        self.add_view(GiveawayButtons())
        await self.tree.sync()

bot = MyBot()

# ================= ESEMÉNYEK & AUTOMOD =================

@bot.event
async def on_ready():
    print(f"✅ Bot online: {bot.user}")

@bot.event
async def on_message(msg):
    if msg.author.bot or not msg.guild: return

    user_role_ids = [role.id for role in msg.author.roles]
    is_mod_or_tester = msg.author.guild_permissions.administrator or msg.author.id in SUPER_MODS or msg.author.id == OWNER_ID or TESTER_MOD_ID in user_role_ids or MOD_ID in user_role_ids

    # MODERÁTOROKRA NEM HAT SEMMI (Automod mentesség)
    if is_mod_or_tester:
        return await bot.process_commands(msg)

    uid = str(msg.author.id)
    txt = msg.content.lower()

    # 1. OWNER PING SZŰRŐ (Csak direkt @mention esetén, válasznál NEM)
    owner_mentions = [f"<@{OWNER_ID}>", f"<@!{OWNER_ID}>"]
    if any(m in msg.content for m in owner_mentions) and msg.reference is None:
        indok = "Tulajdonos pingelése tilos!"
        try: await msg.delete()
        except: pass
        data = load_json(WARN_FILE); now = datetime.datetime.utcnow().isoformat()
        data.setdefault(uid, []).append({"indok": indok, "mod": "Rendszer (Automod)", "ido": now})
        save_json(WARN_FILE, data); mute_time = len(data[uid]) * 2
        try: await msg.author.timeout(datetime.timedelta(minutes=mute_time), reason=indok)
        except: pass
        await msg.channel.send(embed=make_embed("🛑 Automatikus figyelmeztetés", f"👤 **Tag:** {msg.author.mention}\n📄 **Indok:** {indok}\n⚠️ **Figyelmeztetések:** {len(data[uid])}\n🔇 **Némítás:** {mute_time} perc\n👮‍♂️ **Intézkedett:** Rendszer (Automod)", discord.Color.red()))
        return

    # 2. EGYÉB AUTOMOD (Link, GIF, Káromkodás, NSFW, Spam)
    indok = None
    if re.search(LINK_REGEX, txt) or re.search(GIF_REGEX, txt): 
        indok = "Tiltott link küldése"
    elif any(w in txt for w in FORBIDDEN_WORDS): 
        indok = "Káromkodás"
    elif any(w in txt for w in NSFW_WORDS):
        indok = "NSFW tartalom küldése"
    else:
        now = datetime.datetime.now()
        user_messages[uid] = [t for t in user_messages[uid] if (now - t).seconds < 5]
        user_messages[uid].append(now)
        if len(user_messages[uid]) >= 5: 
            indok = "Spamming (Túl sok üzenet)"

    if indok:
        try: await msg.delete()
        except: pass
        data = load_json(WARN_FILE); now = datetime.datetime.utcnow().isoformat()
        data.setdefault(uid, []).append({"indok": indok, "mod": "Rendszer (Automod)", "ido": now})
        save_json(WARN_FILE, data); mute_time = len(data[uid]) * 2
        try: await msg.author.timeout(datetime.timedelta(minutes=mute_time), reason=indok)
        except: pass
        await msg.channel.send(embed=make_embed("🛑 Automatikus figyelmeztetés", f"👤 **Tag:** {msg.author.mention}\n📄 **Indok:** {indok}\n⚠️ **Figyelmeztetések:** {len(data[uid])}\n🔇 **Némítás:** {mute_time} perc\n👮‍♂️ **Intézkedett:** Rendszer (Automod)", discord.Color.red()))
        return

    await bot.process_commands(msg)

@bot.event
async def on_member_join(member):
    ar = load_json(AUTO_ROLE_FILE); rid = ar.get("role_id")
    if rid:
        try:
            role = member.guild.get_role(int(rid))
            if role: await member.add_roles(role)
        except: pass
    data = load_json(WELCOME_FILE); cid = data.get("channel_id")
    if cid:
        try:
            ch = member.guild.get_channel(int(cid))
            if ch: await ch.send(f"👋 Üdvözlünk a szerveren {member.mention}! Érezd jól magad! Te vagy a(z) {member.guild.member_count}. tag 💙")
        except: pass

@bot.event
async def on_member_remove(member):
    data = load_json(LEAVE_FILE); cid = data.get("channel_id")
    if cid:
        try:
            ch = member.guild.get_channel(int(cid))
            if ch: await ch.send(f"🚪 {member.name} ({member.mention}) kilépett a szerverről.\nKöszönjük, hogy itt voltál!")
        except: pass

@bot.event
async def on_message_delete(message):
    if message.author.bot: return
    await send_log(message.guild, make_embed("🗑️ Log: Üzenet Törölve", f"**Szerző:** {message.author.mention}\n**Csatorna:** {message.channel.mention}\n**Tartalom:**\n{message.content or '*Csak média*'}", discord.Color.orange()))

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content: return
    desc = f"**Szerző:** {before.author.mention}\n**Csatorna:** {before.channel.mention}\n**Régi:**\n{before.content}\n**Új:**\n{after.content}"
    await send_log(before.guild, make_embed("📝 Log: Üzenet Szerkesztve", desc, discord.Color.blue()))

# ================= MODERÁCIÓS PARANCSOK =================

@bot.tree.command(name="figyelmeztetés")
async def warn(i: discord.Interaction, tag: discord.Member, indok: str):
    if not tester_check(i):
        return await i.response.send_message(f"❌ **{i.user.name}**, ezt a parancsot nem áll jogodban használni!", ephemeral=False)
    if is_target_mod(tag): return await i.response.send_message("🛑 Moderátort nem figyelmeztethetsz!", ephemeral=False)
    data = load_json(WARN_FILE); uid = str(tag.id)
    data.setdefault(uid, []).append({"indok": indok, "mod": str(i.user), "ido": datetime.datetime.utcnow().isoformat()})
    save_json(WARN_FILE, data); mute_time = len(data[uid]) * 2
    try: await tag.timeout(datetime.timedelta(minutes=mute_time), reason=indok)
    except: pass
    await i.response.send_message(embed=make_embed("⚠️ Figyelmeztetés", f"👤 **Tag:** {tag.mention}\n📄 **Indok:** {indok}\n⚠️ **Figyelmeztetések**: {len(data[uid])}\n🔇 **Némítás:** {mute_time} perc\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.orange()))

@bot.tree.command(name="némítás")
async def mute(i: discord.Interaction, tag: discord.Member, időtartam: str, indok: str):
    if not mod_check(i):
        return await i.response.send_message(f"❌ **{i.user.name}**, ezt a parancsot nem áll jogodban használni!", ephemeral=False)
    if is_target_mod(tag): return await i.response.send_message("🛑 Moderátort nem némíthatsz le!", ephemeral=False)
    sec, human_readable = parse_duration(időtartam)
    if sec == 0: return await i.response.send_message("❌ Érvénytelen időformátum! (Pl: 1d 2h 30m)", ephemeral=False)
    await tag.timeout(datetime.timedelta(seconds=sec), reason=indok)
    await i.response.send_message(embed=make_embed("🔇 Némítás", f"👤 **Tag:** {tag.mention}\n⏳ **Időtartam:** {human_readable}\n📄 **Indok:** {indok}\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.red()))

@bot.tree.command(name="némítás_feloldás")
async def unmute(i: discord.Interaction, tag: discord.Member):
    if not mod_check(i):
        return await i.response.send_message(f"❌ **{i.user.name}**, ezt a parancsot nem áll jogodban használni!", ephemeral=False)
    await tag.timeout(None)
    await i.response.send_message(embed=make_embed("🔊 Némítás feloldva", f"👤 **Tag:** {tag.mention}\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.green()))

@bot.tree.command(name="figyelmeztetés_info")
async def warn_info(i: discord.Interaction, tag: discord.Member):
    if not mod_check(i):
        return await i.response.send_message(f"❌ **{i.user.name}**, ezt a parancsot nem áll jogodban használni!", ephemeral=False)
    data = load_json(WARN_FILE); warns = data.get(str(tag.id), [])
    desc = "".join([f"**{idx+1}.** `{w['indok']}`\n└ 👮‍♂️**intézkedő:** {w['mod']}\n" for idx, w in enumerate(warns)]) if warns else "Nincs figyelmeztetése."
    await i.response.send_message(embed=make_embed(f"⚠️ {tag.name} figyelmeztetései", desc, discord.Color.blue()))

@bot.tree.command(name="figyelmeztetés_törlés")
async def warn_del(i: discord.Interaction, tag: discord.Member, mennyiség: int):
    if not mod_check(i):
        return await i.response.send_message(f"❌ **{i.user.name}**, ezt a parancsot nem áll jogodban használni!", ephemeral=False)
    data = load_json(WARN_FILE); uid = str(tag.id); warns = data.get(uid, [])
    if not warns: return await i.response.send_message(f"❌ {tag.mention}-nak nincs figyelmeztetése.", ephemeral=False)
    torelendo = min(len(warns), mennyiség)
    for _ in range(torelendo): warns.pop()
    save_json(WARN_FILE, data)
    await i.response.send_message(embed=make_embed("🧹 Figyelmeztetések törölve", f"👤 **Tag:** {tag.mention}\n📉 **Törölve:** {torelendo} db\n⚠️ **Maradt:** {len(warns)}\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.green()))

@bot.tree.command(name="kirúgás")
async def kick(i: discord.Interaction, tag: discord.Member, indok: str):
    if not admin_check(i):
        return await i.response.send_message(f"❌ **{i.user.name}**, ezt a parancsot nem áll jogodban használni!", ephemeral=False)
    if is_target_mod(tag): return await i.response.send_message("🛑 Moderátort nem rúghatsz ki!", ephemeral=False)
    await tag.kick(reason=indok)
    await i.response.send_message(embed=make_embed("👢 Kirúgás", f"👤 **Tag:** {tag.mention}\n📄 **Indok:** {indok}\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.orange()))

@bot.tree.command(name="kitiltás")
async def ban(i: discord.Interaction, tag: discord.Member, indok: str):
    if not admin_check(i):
        return await i.response.send_message(f"❌ **{i.user.name}**, ezt a parancsot nem áll jogodban használni!", ephemeral=False)
    if is_target_mod(tag): return await i.response.send_message("🛑 Moderátort nem tilthatsz ki!", ephemeral=False)
    await tag.ban(reason=indok)
    await i.response.send_message(embed=make_embed("🚫 Kitiltás", f"👤 **Tag:** {tag.mention}\n📄 **Indok:** {indok}\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.dark_red()))

# ================= BEÁLLÍTÁSOK (ELREJTETT) =================

@bot.tree.command(name="üdvözlő_beállítás")
@app_commands.default_permissions(administrator=True)
async def welcome_set(i: discord.Interaction, csatorna: discord.TextChannel):
    if not admin_check(i): return await i.response.send_message(f"❌ **{i.user.name}**, nincs jogod ehhez!", ephemeral=False)
    save_json(WELCOME_FILE, {"channel_id": csatorna.id})
    await i.response.send_message(f"✅ Üdvözlő csatorna beállítva: {csatorna.mention}", ephemeral=True)

@bot.tree.command(name="kilépő_beállítás")
@app_commands.default_permissions(administrator=True)
async def leave_set(i: discord.Interaction, csatorna: discord.TextChannel):
    if not admin_check(i): return await i.response.send_message(f"❌ **{i.user.name}**, nincs jogod ehhez!", ephemeral=False)
    save_json(LEAVE_FILE, {"channel_id": csatorna.id})
    await i.response.send_message(f"✅ Kilépő csatorna beállítva: {csatorna.mention}", ephemeral=True)

@bot.tree.command(name="log_beállítás")
@app_commands.default_permissions(administrator=True)
async def log_set(i: discord.Interaction, csatorna: discord.TextChannel):
    if not admin_check(i): return await i.response.send_message(f"❌ **{i.user.name}**, nincs jogod ehhez!", ephemeral=False)
    save_json(LOG_FILE, {"log_channel": csatorna.id})
    await i.response.send_message(f"✅ Log csatorna beállítva: {csatorna.mention}", ephemeral=True)

@bot.tree.command(name="autorole_beállítás")
@app_commands.default_permissions(administrator=True)
async def autorole_set(i: discord.Interaction, rang: discord.Role):
    if not admin_check(i): return await i.response.send_message(f"❌ **{i.user.name}**, nincs jogod ehhez!", ephemeral=False)
    save_json(AUTO_ROLE_FILE, {"role_id": rang.id})
    await i.response.send_message(f"✅ Autorole rang beállítva: {rang.name}", ephemeral=True)

# ================= VIDEÓ & NYEREMÉNYJÁTÉK =================

@bot.tree.command(name="videó")
async def video(i: discord.Interaction, szoveg: str, video: discord.Attachment):
    if not video_check(i):
        return await i.response.send_message(f"❌ **{i.user.name}**, ezt a parancsot nem áll jogodban használni!", ephemeral=False)
    
    await i.response.defer()
    data = load_json(VIDEO_FILE)
    data["count"] = data.get("count", 0) + 1
    save_json(VIDEO_FILE, data)
    await i.followup.send(content=f"**{data['count']}. Sikeres trade bizonyíték**\n{szoveg}", file=await video.to_file())

class GiveawayButtons(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Jelentkezem!", style=discord.ButtonStyle.primary, custom_id="toggle_join_btn")
    async def toggle_join(self, interaction: discord.Interaction, button: ui.Button):
        msg_id = str(interaction.message.id); user_id = str(interaction.user.id)
        conn = sqlite3.connect(DB_FILE); c = conn.cursor()
        c.execute("SELECT * FROM participants WHERE msg_id = ? AND user_id = ?", (msg_id, user_id))
        if c.fetchone():
            c.execute("DELETE FROM participants WHERE msg_id = ? AND user_id = ?", (msg_id, user_id))
            status_text = "❌ Sikeresen kiléptél a nyereményjátékból!"
        else:
            c.execute("INSERT INTO participants VALUES (?, ?)", (msg_id, user_id))
            status_text = "✅ Sikeresen jelentkeztél a nyereményjátékra!"
        conn.commit()
        c.execute("SELECT COUNT(*) FROM participants WHERE msg_id = ?", (msg_id,))
        count_res = c.fetchone()
        count = count_res[0] if count_res else 0
        conn.close()
        
        embed = interaction.message.embeds[0]
        for idx, field in enumerate(embed.fields):
            if "Jelentkezők" in field.name:
                embed.set_field_at(idx, name="👤 Jelentkezők", value=f"**{count}** fő", inline=False)
                break
        await interaction.message.edit(embed=embed)
        await interaction.response.send_message(status_text, ephemeral=True)

class GiveawayModal(ui.Modal, title='Nyereményjáték Beállítása'):
    duration = ui.TextInput(label='Mennyi ideig tartson? (pl. 10m, 2h, 1d)', placeholder='Pl. 1d 2h 30m', required=True)
    winner_count = ui.TextInput(label='Hány nyertes legyen?', default='1', required=True)
    prize = ui.TextInput(label='Mi a nyeremény?', placeholder='Írd ide a nyereményt!', required=True)
    description = ui.TextInput(label='Leírás', style=discord.TextStyle.paragraph, required=False, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        seconds, human_readable = parse_duration(self.duration.value)
        if seconds <= 0:
            return await interaction.response.send_message("❌ Hibás időformátum!", ephemeral=True)

        end_timestamp = int((discord.utils.utcnow() + datetime.timedelta(seconds=seconds)).timestamp())
        
        
        embed = discord.Embed(title="🎁 NYEREMÉNYJÁTÉK ELINDULT", description=f"Nyeremény: **{self.prize.value}**", color=0x5865F2)
        if self.description.value: 
            embed.add_field(name="📝 Leírás", value=self.description.value, inline=False)
        embed.add_field(name="🏆 Nyertesek", value=f"{self.winner_count.value} fő", inline=True)
        embed.add_field(name="⏳ Időtartam", value=f"{human_readable} (<t:{end_timestamp}:R>)", inline=True)
        embed.add_field(name="👤 Jelentkezők", value="**0** fő", inline=False)
        embed.set_footer(text="Kattints a gombra a jelentkezéshez! 🎉")

        view = GiveawayButtons()
        await interaction.response.send_message(embed=embed, view=view)
        msg = await interaction.original_response()
        
        await asyncio.sleep(seconds)
        
        # SORSOLÁS
        conn = sqlite3.connect(DB_FILE); c = conn.cursor()
        c.execute("SELECT user_id FROM participants WHERE msg_id = ?", (str(msg.id),))
        users = [row[0] for row in c.fetchall()]; conn.close()
        
        if users:
            winners = random.sample(users, min(len(users), int(self.winner_count.value)))
            mentions = ", ".join([f"<@{w}>" for w in winners])
            await interaction.channel.send(f"🎊 **GRATULÁLUNK!** {mentions} megnyerte a következőt: **{self.prize.value}**! 🏆")
        else:
            await interaction.channel.send(f"😢 A(z) **{self.prize.value}** sorsolása sikertelen (nincs jelentkező).")

@bot.tree.command(name="nyeremenyjatek")
async def start_giveaway(i: discord.Interaction):
    if not admin_check(i):
        return await i.response.send_message(f"❌ **{i.user.name}**, ezt a parancsot nem áll jogodban használni!", ephemeral=False)
    await i.response.send_modal(GiveawayModal())

# ================= INDÍTÁS =================
if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("HIBA: DISCORD_TOKEN nem található!")
