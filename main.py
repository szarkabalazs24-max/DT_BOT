import discord
from discord.ext import commands
from discord import app_commands, ui, Embed, Color
import os, json, datetime, asyncio, random, re, sqlite3
from collections import defaultdict

# ================== ⚙️ KONFIGURÁCIÓ & RANGOK ⚙️ ==================

# Railway-en add meg a DISCORD_TOKEN-t a Variables fül alatt!
TOKEN = os.getenv("DISCORD_TOKEN")

# Moderátor és Speciális rangok ID-jai (Cseréld le a sajátjaidra!)
TESTER_MOD_ID = 1485380635442020352
MOD_ID = 1462561594473975969
MIDDLEMAN_ID = 1454586433292468235
SENIOR_MM_ID = 1454586731528454308
ELITE_MM_ID = 1454587037205135474

# Fájlnevek
WARN_FILE = "warns.json"
WELCOME_FILE = "welcome.json"
LEAVE_FILE = "leave.json"
AUTO_ROLE_FILE = "autorole.json"
VIDEO_FILE = "videos.json"
LOG_FILE = "logs.json"
TICKET_CONFIG_FILE = "ticket_config.json"

# Szűrők
FORBIDDEN_WORDS = ["fasz","geci","buzi","bazdmeg","kurva","anyád","szar","any@d","apád","cigány","cigany","barom","bazmeg","pornó","porno","nyomorék","szopj","szopjle","kutya","apad","apád"]
LINK_REGEX = r"http[s]?://"

user_messages = defaultdict(list)

# ================== 🗄️ ADATBÁZIS & JSON KEZELÉS 🗄️ ==================

def init_db():
    try:
        conn = sqlite3.connect('giveaway.db')
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS participants 
                          (msg_id TEXT, user_id TEXT, UNIQUE(msg_id, user_id))''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Adatbázis hiba: {e}")

init_db()

def load_json(file):
    if not os.path.exists(file): return {}
    try:
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()
            return json.loads(content) if content else {}
    except Exception as e:
        print(f"Hiba a(z) {file} betöltésekor: {e}")
        return {}

def save_json(file, data):
    try:
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Hiba a(z) {file} mentésekor: {e}")

def make_embed(title, desc, color):
    e = Embed(title=title, description=desc, color=color, timestamp=datetime.datetime.utcnow())
    e.set_footer(text="✨ teszt✨")
    return e

# ================== 🛡️ JOGOSULTSÁG ELLENŐRZŐK 🛡️ ==================

def is_target_mod(member: discord.Member):
    user_role_ids = [role.id for role in member.roles]
    return member.guild_permissions.administrator or member.guild_permissions.manage_messages or TESTER_MOD_ID in user_role_ids or MOD_ID in user_role_ids

def tester_and_up(i: discord.Interaction):
    user_role_ids = [role.id for role in i.user.roles]
    return i.user.guild_permissions.administrator or i.user.guild_permissions.manage_messages or TESTER_MOD_ID in user_role_ids or MOD_ID in user_role_ids

def mod_and_up(i: discord.Interaction):
    user_role_ids = [role.id for role in i.user.roles]
    return i.user.guild_permissions.administrator or i.user.guild_permissions.manage_messages or MOD_ID in user_role_ids

def video_check(i: discord.Interaction):
    user_role_ids = [role.id for role in i.user.roles]
    allowed_ids = [MIDDLEMAN_ID, SENIOR_MM_ID, ELITE_MM_ID]
    return any(rid in user_role_ids for rid in allowed_ids)

# ================== 🎫 PROFI TICKET RENDSZER 🎫 ==================

class TicketDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Panaszkezelés", description="🚫 Szabályszegés jelentése", emoji="🚫"),
            discord.SelectOption(label="Tagfelvétel", description="📝 Jelentkezés a csapatba", emoji="📝"),
            discord.SelectOption(label="Support", description="❓ Általános segítségnyújtás", emoji="❓")
        ]
        super().__init__(placeholder="Válassz kategóriát a ticketnyitáshoz...", min_values=1, max_values=1, custom_id="ticket_select_main")

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        valasztott = self.values[0]
        config = load_json(TICKET_CONFIG_FILE)
        
        tema_data = config.get(valasztott, {})
        kat_id = tema_data.get("category_id")
        role_id = tema_data.get("role_id")

        category = guild.get_channel(kat_id) if kat_id else None
        role = guild.get_role(role_id) if role_id else None

        if not category or not role:
            return await interaction.response.send_message(f"❌ Hiba: A(z) **{valasztott}** kategória vagy felelős rang nincs beállítva a `/ticket_beállítás` parancssal!", ephemeral=True)

        ticket_ch = await guild.create_text_channel(
            name=f"{valasztott.lower()}-{interaction.user.name}",
            category=category,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True),
                role: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
        )

        e = Embed(title=f"🎫 {valasztott.upper()} - TICKET", color=Color.blue(), timestamp=datetime.datetime.utcnow())
        e.add_field(name="👤 Beküldő", value=interaction.user.mention, inline=True)
        e.add_field(name="👥 Illetékes rang", value=role.mention, inline=True)
        e.description = f"Szia {interaction.user.mention}! A(z) **{role.name}** csapat hamarosan válaszol. Addig is fejtsd ki a problémád!"
        e.set_footer(text="✨ SERVICE HUN ✨")

        await ticket_ch.send(content=f"{role.mention} | Új ticket érkezett!", embed=e)
        await interaction.response.send_message(f"✅ Ticket sikeresen létrehozva: {ticket_ch.mention}", ephemeral=True)

class TicketView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())

# ================== 🎁 NYEREMÉNYJÁTÉK RENDSZER 🎁 ==================

class GiveawayButtons(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Jelentkezem!", style=discord.ButtonStyle.primary, custom_id="toggle_join_btn")
    async def toggle_join(self, interaction: discord.Interaction, button: ui.Button):
        msg_id, user_id = str(interaction.message.id), str(interaction.user.id)
        conn = sqlite3.connect('giveaway.db'); c = conn.cursor()
        c.execute("SELECT * FROM participants WHERE msg_id = ? AND user_id = ?", (msg_id, user_id))
        
        if c.fetchone():
            c.execute("DELETE FROM participants WHERE msg_id = ? AND user_id = ?", (msg_id, user_id))
            status = "❌ Eltávolítottalak a nyereményjátékból!"
        else:
            c.execute("INSERT INTO participants VALUES (?, ?)", (msg_id, user_id))
            status = "✅ Sikeresen jelentkeztél a játékra!"
        
        conn.commit()
        c.execute("SELECT COUNT(*) FROM participants WHERE msg_id = ?", (msg_id,))
        count = c.fetchone()[0]
        conn.close()

        embed = interaction.message.embeds[0]
        for i, field in enumerate(embed.fields):
            if "Jelentkezők" in field.name:
                embed.set_field_at(i, name="👤 Jelentkezők", value=f"**{count}** fő", inline=False)
                break
        
        await interaction.message.edit(embed=embed)
        await interaction.response.send_message(status, ephemeral=True)

class GiveawayModal(ui.Modal, title='🎁 Nyereményjáték Beállítása'):
    duration = ui.TextInput(label='Időtartam (pl. 10m, 2h, 1d)', placeholder='Pl. 30m', required=True)
    winner_count = ui.TextInput(label='Hány nyertes legyen?', default='1', required=True)
    prize = ui.TextInput(label='Mi a nyeremény?', placeholder='Írd ide a nyereményt!', required=True)
    description = ui.TextInput(label='Leírás', style=discord.TextStyle.paragraph, required=False, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        raw_time = self.duration.value.lower(); seconds = 0
        try:
            if 'm' in raw_time: seconds = int(raw_time.replace('m', '')) * 60
            elif 'h' in raw_time: seconds = int(raw_time.replace('h', '')) * 3600
            elif 'd' in raw_time: seconds = int(raw_time.replace('d', '')) * 86400
            else: seconds = int(raw_time) * 60
        except: return await interaction.response.send_message("❌ Hibás időformátum! (Példa: 10m, 1h, 1d)", ephemeral=True)

        end_timestamp = int((discord.utils.utcnow() + datetime.timedelta(seconds=seconds)).timestamp())
        embed = Embed(title="🎁 NYEREMÉNYJÁTÉK ELINDULT", description=f"Nyeremény: **{self.prize.value}**", color=0x5865F2)
        embed.add_field(name="🏆 Nyertesek", value=f"{self.winner_count.value} fő", inline=True)
        embed.add_field(name="⏳ Hátralévő idő", value=f"<t:{end_timestamp}:R> múlva ér véget", inline=True)
        embed.add_field(name="👤 Jelentkezők", value="**0** fő", inline=False)
        embed.set_footer(text="Kattints a gombra a jelentkezéshez! 🎉")

        view = GiveawayButtons()
        await interaction.response.send_message(embed=embed, view=view)
        msg = await interaction.original_response()
        
        await asyncio.sleep(seconds)
        
        # LEZÁRÁS (A beküldött fotó stílusa alapján)
        conn = sqlite3.connect('giveaway.db'); c = conn.cursor()
        c.execute("SELECT user_id FROM participants WHERE msg_id = ?", (str(msg.id),))
        users = [row[0] for row in c.fetchall()]; conn.close()

        end_embed = Embed(title="🔒 NYEREMÉNYJÁTÉK LEZÁRULT", description=f"Nyeremény: **{self.prize.value}**", color=0x2b2d31)
        end_embed.add_field(name="📝 Leírás", value=self.description.value or "Xdd akinek kell jelentkezzen", inline=False)
        end_embed.add_field(name="🏆 Nyertesek", value=f"{self.winner_count.value} fő", inline=False)
        end_embed.add_field(name="⏳ Állapot", value="Véget ért", inline=False)
        end_embed.add_field(name="👤 Jelentkezők", value=f"{len(users)} fő", inline=False)
        end_embed.set_footer(text="Kattints a gombra a jelentkezéshez vagy leiratkozáshoz! 🎉")

        await msg.edit(embed=end_embed, view=None)

        if users:
            winners = random.sample(users, min(len(users), int(self.winner_count.value)))
            mentions = ", ".join([f"<@{w}>" for w in winners])
            await interaction.channel.send(f"🎊 **GRATULÁLUNK!** {mentions} megnyerte a következőt: **{self.prize.value}**! 🏆")
        else:
            await interaction.channel.send(f"😢 A(z) **{self.prize.value}** sorsolása sikertelen, mert nem maradt jelentkező.")

# ================== 🤖 BOT SETUP & AUTOMOD 🤖 ==================

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())

    async def setup_hook(self):
        self.add_view(GiveawayButtons())
        self.add_view(TicketView())
        await self.tree.sync()

bot = MyBot()

@bot.event
async def on_ready():
    print(f"✅ Bot sikeresen bejelentkezve: {bot.user}")

@bot.event
async def on_message(msg):
    if msg.author.bot or not msg.guild: return
    
    # MODERÁTOR KIVÉTEL: Ha van Manage Messages joga vagy a rangja mod, nem bántja a bot
    if is_target_mod(msg.author):
        await bot.process_commands(msg)
        return

    txt = msg.content.lower()
    uid = str(msg.author.id)
    indok = None

    # Automata szűrők tagoknak
    if re.search(LINK_REGEX, txt): indok = "Tiltott link küldése"
    elif any(word in txt for word in FORBIDDEN_WORDS): indok = "Káromkodás / Csúnya beszéd"
    else:
        # Spam szűrő
        now = datetime.datetime.now()
        user_messages[uid] = [t for t in user_messages[uid] if (now - t).seconds < 5]
        user_messages[uid].append(now)
        if len(user_messages[uid]) >= 5: indok = "Spammelés (Túl sok üzenet)"

    if indok:
        try:
            await msg.delete()
            data = load_json(WARN_FILE)
            data.setdefault(uid, []).append({"indok": indok, "mod": "Rendszer (Automod)", "ido": datetime.datetime.utcnow().isoformat()})
            save_json(WARN_FILE, data)
            
            mute_time = len(data[uid]) * 2
            await msg.author.timeout(datetime.timedelta(minutes=mute_time), reason=indok)
            
            e = make_embed("🛑 Automatikus Moderáció", f"👤 **Tag:** {msg.author.mention}\n📄 **Indok:** {indok}\n⚠️ **Büntetések száma:** {len(data[uid])}\n🔇 **Némítás:** {mute_time} perc", Color.red())
            await msg.channel.send(embed=e, delete_after=10)
            return
        except Exception as e:
            print(f"AutoMod hiba: {e}")

    await bot.process_commands(msg)

# ================== 🛠️ MODERÁCIÓS PARANCSOK 🛠️ ==================

@bot.tree.command(name="figyelmeztetés", description="⚠️ Figyelmeztetés kiosztása")
@app_commands.check(tester_and_up)
async def warn(i: discord.Interaction, tag: discord.Member, indok: str):
    if is_target_mod(tag): return await i.response.send_message("🛑 Moderátort nem figyelmeztethetsz!", ephemeral=True)
    
    data = load_json(WARN_FILE); uid = str(tag.id)
    data.setdefault(uid, []).append({"indok": indok, "mod": str(i.user), "ido": datetime.datetime.utcnow().isoformat()})
    save_json(WARN_FILE, data)
    
    mute_time = len(data[uid]) * 2
    await tag.timeout(datetime.timedelta(minutes=mute_time))
    
    e = make_embed("⚠️ Figyelmeztetés", f"👤 **Tag:** {tag.mention}\n📄 **Indok:** {indok}\n📊 **Összes figyelmeztetés:** {len(data[uid])}\n🔇 **Némítás:** {mute_time} perc\n👮 **Intézkedett:** {i.user.mention}", Color.orange())
    await i.response.send_message(embed=e)

@bot.tree.command(name="figyelmeztetés_törlés", description="🗑️ Megadott mennyiségű figyelmeztetés törlése")
@app_commands.check(mod_and_up)
async def warn_del(i: discord.Interaction, tag: discord.Member, mennyiseg: int):
    data = load_json(WARN_FILE); uid = str(tag.id); warns = data.get(uid, [])
    
    torolt = min(mennyiseg, len(warns))
    for _ in range(torolt): warns.pop()
    
    data[uid] = warns
    save_json(WARN_FILE, data)
    
    e = make_embed("🧹 Figyelmeztetések Levonva", f"👤 **Tag:** {tag.mention}\n📉 **Törölt mennyiség:** {torolt} db\n⚠️ **Maradék:** {len(warns)} db\n👮 **Intézkedett:** {i.user.mention}", Color.green())
    await i.response.send_message(embed=e)

@bot.tree.command(name="figyelmeztetés_lista", description="📋 Felhasználó figyelmeztetéseinek megtekintése")
@app_commands.check(mod_and_up)
async def warn_list(i: discord.Interaction, tag: discord.Member):
    data = load_json(WARN_FILE); warns = data.get(str(tag.id), [])
    
    if not warns:
        return await i.response.send_message(f"✅ {tag.mention} nem rendelkezik figyelmeztetésekkel.")
    
    desc = ""
    for idx, w in enumerate(warns):
        desc += f"**{idx+1}.** `{w['indok']}`\n└ 👮: {w['mod']} | 📅: {w['ido'][:10]}\n"
    
    await i.response.send_message(embed=make_embed(f"📋 {tag.name} büntetései", desc, Color.blue()))

@bot.tree.command(name="kitiltás", description="🚫 Felhasználó kitiltása a szerverről")
@app_commands.check(mod_and_up)
async def ban(i: discord.Interaction, tag: discord.Member, indok: str):
    if is_target_mod(tag): return await i.response.send_message("🛑 Moderátort nem tilthatsz ki!", ephemeral=True)
    await tag.ban(reason=indok)
    await i.response.send_message(embed=make_embed("🚫 Kitiltás", f"👤 **Tag:** {tag.name}\n📄 **Indok:** {indok}\n👮 **Moderátor:** {i.user.mention}", Color.dark_red()))

# ================== 🎫 TICKET BEÁLLÍTÁSOK 🎫 ==================

@bot.tree.command(name="ticket_beállítás", description="⚙️ Téma, kategória és felelős rang összekötése")
@app_commands.check(mod_and_up)
@app_commands.choices(tema=[
    app_commands.Choice(name="Panaszkezelés", value="Panaszkezelés"),
    app_commands.Choice(name="Tagfelvétel", value="Tagfelvétel"),
    app_commands.Choice(name="Support", value="Support")
])
async def t_setup(itn: discord.Interaction, tema: str, kategoria: discord.CategoryChannel, rang: discord.Role):
    config = load_json(TICKET_CONFIG_FILE)
    config[tema] = {"category_id": kategoria.id, "role_id": rang.id}
    save_json(TICKET_CONFIG_FILE, config)
    
    await itn.response.send_message(f"✅ **{tema}** sikeresen beállítva!\n📁 Kategória: {kategoria.name}\n👥 Rang: {rang.mention}", ephemeral=True)

@bot.tree.command(name="ticketpanel", description="📨 Ticket indító panel kiküldése")
@app_commands.check(mod_and_up)
async def tpanel(itn: discord.Interaction):
    e = make_embed("📩 SEGÍTSÉG ÉS ÜGYFÉLSZOLGÁLAT", "Válaszd ki az alábbi menüből a problémád típusát!", Color.blue())
    await itn.response.send_message(embed=e, view=TicketView())

@bot.tree.command(name="hozzáad", description="➕ Felhasználó hozzáadása a jelenlegi tickethez")
async def t_add(itn: discord.Interaction, tag: discord.Member):
    if "ticket-" in itn.channel.name:
        await itn.channel.set_permissions(tag, view_channel=True, send_messages=True, read_message_history=True)
        await itn.response.send_message(embed=make_embed("➕ Tag Hozzáadva", f"{tag.mention} mostantól látja a ticketet.", Color.green()))
    else:
        await itn.response.send_message("❌ Ezt csak ticket csatornában teheted meg!", ephemeral=True)

# ================== 🎉 GIVEAWAY & VIDEÓ 🎉 ==================

@bot.tree.command(name="nyeremenyjatek", description="🎉 Nyereményjáték indítása űrlappal")
@app_commands.check(mod_and_up)
async def g_start(itn: discord.Interaction):
    await itn.response.send_modal(GiveawayModal())

@bot.tree.command(name="videó", description="🎬 Trade bizonyíték feltöltése sorszámozva")
@app_commands.check(video_check)
async def video_cmd(i: discord.Interaction, szoveg: str, video: discord.Attachment):
    data = load_json(VIDEO_FILE)
    data["count"] = data.get("count", 147) + 1
    save_json(VIDEO_FILE, data)
    
    await i.response.send_message(content=f"**{data['count']}. Sikeres trade bizonyíték**\n{szoveg}", file=await video.to_file())

# ================== 🛠️ HIBAKEZELÉS 🛠️ ==================

@bot.tree.error
async def on_app_command_error(i: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        await i.response.send_message(f"🛑 {i.user.mention}, nincs jogosultságod a parancs használatához!", ephemeral=True)
    else:
        print(f"Hiba: {error}")

if TOKEN:
    bot.run(TOKEN)
else:
    print("CRITICAL ERROR: Nincs beállítva a DISCORD_TOKEN a környezeti változók között!")
