import discord
from discord.ext import commands
from discord import app_commands
import os, json, datetime, asyncio, random, re
from collections import defaultdict

# ================== KONFIGURÁCIÓ (ID-K BEÁLLÍTÁSA) ==================

TOKEN = os.getenv("DISCORD_TOKEN")

# IDE MÁSOLD BE A RANGOK ID-JÁT!
TESTER_MOD_ID = 111222333444555666  # [⏰] TESTER MODERÁTOR ID
MOD_ID = 999888777666555444         # [🧨] MODERÁTOR ID

WARN_FILE = "warns.json"
WELCOME_FILE = "welcome.json"
LEAVE_FILE = "leave.json"
AUTO_ROLE_FILE = "autorole.json"
VIDEO_FILE = "videos.json"
STICKY_FILE = "sticky.json"
REACT_FILE = "autoreact.json"

FORBIDDEN_WORDS = ["fasz","geci","buzi","bazdmeg","kurva","anyád","szar","szarka","any@d","apád","cigány","cigany","barom"]
LINK_REGEX = r"http[s]?://"

user_messages = defaultdict(list)
last_sticky_msg = {} 

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= SEGÉDFÜGGVÉNYEK =================

def load_json(file):
    if not os.path.exists(file): return {}
    try:
        with open(file, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)

def make_embed(title, desc, color):
    e = discord.Embed(title=title, description=desc, color=color, timestamp=datetime.datetime.utcnow())
    e.set_footer(text="✨ SERVICE HUN ✨")
    return e

def mod_check(i: discord.Interaction):
    p = i.user.guild_permissions
    return p.administrator or p.manage_messages

def high_mod_check(i: discord.Interaction):
    user_role_ids = [role.id for role in i.user.roles]
    return i.user.guild_permissions.administrator or TESTER_MOD_ID in user_role_ids or MOD_ID in user_role_ids

# ================= DINAMIKUS TICKET RENDSZER UI =================

class DynamicTicketView(discord.ui.View):
    def __init__(self, category_id: int, welcome_msg: str):
        super().__init__(timeout=None)
        self.category_id = category_id
        self.welcome_msg = welcome_msg

    @discord.ui.button(label="Ticket Nyitása 🎫", style=discord.ButtonStyle.primary, custom_id="persistent_open_ticket")
    async def open_ticket(self, i: discord.Interaction, button: discord.ui.Button):
        guild = i.guild
        category = guild.get_channel(self.category_id)
        if not category: return await i.response.send_message("❌ Kategória nem található!", ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            i.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await guild.create_text_channel(f"ticket-{i.user.name}", category=category, overwrites=overwrites)
        await i.response.send_message(f"✅ Ticket: {channel.mention}", ephemeral=True)
        await channel.send(embed=make_embed("🎫 Üdvözlünk!", self.welcome_msg, discord.Color.blue()))

# ================= AUTOMOD + AUTO-REACT + STICKY =================

@bot.event
async def on_message(msg):
    if msg.author.bot or not msg.guild: return
    uid, cid, txt = str(msg.author.id), str(msg.channel.id), msg.content.lower()
    is_mod_immune = msg.author.guild_permissions.manage_messages or msg.author.guild_permissions.administrator

    react_data = load_json(REACT_FILE)
    if cid in react_data:
        for emoji in react_data[cid]:
            try: await msg.add_reaction(emoji)
            except: pass

    indok = None
    if not is_mod_immune:
        if re.search(LINK_REGEX, txt): indok = "Tiltott link küldése"
        elif any(w in txt for w in FORBIDDEN_WORDS): indok = "Káromkodás"
        else:
            now = datetime.datetime.now()
            user_messages[uid] = [t for t in user_messages[uid] if (now - t).seconds < 5]
            user_messages[uid].append(now)
            if len(user_messages[uid]) >= 5: indok = "Spamming (Túl sok üzenet)"

    if indok:
        await msg.delete()
        data = load_json(WARN_FILE)
        now_iso = datetime.datetime.utcnow().isoformat()
        data.setdefault(uid, []).append({"indok": indok, "mod": "Rendszer (Automod)", "ido": now_iso})
        save_json(WARN_FILE, data)
        mute_time = len(data[uid]) * 2
        await msg.author.timeout(datetime.timedelta(minutes=mute_time))
        
        await msg.channel.send(embed=make_embed(
            "🛑 Automatikus figyelmeztetés",
            f"👤 **Tag:** {msg.author.mention}\n📄 **Indok:** {indok}\n⚠️ **Figyelmeztetések:** {len(data[uid])}\n🔇 **Némítás:** {mute_time} perc\n👮‍♂️ **Intézkedett:** Rendszer (Automod)",
            discord.Color.red()
        ))
        return

    sticky_data = load_json(STICKY_FILE)
    if cid in sticky_data:
        if cid in last_sticky_msg:
            try:
                old_msg = await msg.channel.fetch_message(last_sticky_msg[cid])
                await old_msg.delete()
            except: pass
        new_sticky = await msg.channel.send(sticky_data[cid])
        last_sticky_msg[cid] = new_sticky.id

    await bot.process_commands(msg)

# ================= BELÉPÉS / KILÉPÉS / NYEREMÉNYJÁTÉK =================

@bot.event
async def on_member_join(member):
    ar = load_json(AUTO_ROLE_FILE)
    role = member.guild.get_role(ar.get("role_id", 0))
    if role: await member.add_roles(role)
    data = load_json(WELCOME_FILE)
    ch = member.guild.get_channel(data.get("channel_id", 0))
    if ch: await ch.send(f"👋 Üdv a szerveren {member.mention}! Te vagy a(z) {member.guild.member_count}. tag 💙")

@bot.event
async def on_member_remove(member):
    data = load_json(LEAVE_FILE)
    ch = member.guild.get_channel(data.get("channel_id", 0))
    if ch: await ch.send(f"🚪 {member.name} kilépett a szerverről.")

@bot.tree.command(name="nyereményjáték")
@app_commands.check(mod_check)
async def giveaway(i: discord.Interaction, idő_perc: int, nyeremény: str, nyertesek_száma: int = 1):
    embed = make_embed("🎉 NYEREMÉNYJÁTÉK 🎉", f"🎁 Nyeremény: **{nyeremény}**\n👤 Nyertesek: **{nyertesek_száma}**\n⌛ Idő: **{idő_perc} perc**", discord.Color.blue())
    await i.response.send_message("✅ Elindítva!", ephemeral=True)
    msg = await i.channel.send(embed=embed)
    await msg.add_reaction("🎉")
    await asyncio.sleep(idő_perc * 60)
    msg = await i.channel.fetch_message(msg.id)
    users = [u async for u in msg.reactions[0].users() if not u.bot]
    if len(users) < nyertesek_száma: return await i.channel.send(f"❌ Nincs elég jelentkező: **{nyeremény}**")
    winners = random.sample(users, nyertesek_száma)
    await i.channel.send(f"🎊 Gratulálunk {', '.join([w.mention for w in winners])}! Megnyerted: **{nyeremény}**!")

# ================= TICKET / REACT / BEÁLLÍTÁSOK =================

@bot.tree.command(name="ticket_panel")
@app_commands.check(mod_check)
async def ticket_panel(i: discord.Interaction, cím: str, panel_leírás: str, kategória_id: str, ticket_üdvözlő_szöveg: str):
    view = DynamicTicketView(int(kategória_id), ticket_üdvözlő_szöveg)
    await i.channel.send(embed=make_embed(cím, panel_leírás, discord.Color.green()), view=view)
    await i.response.send_message("✅ Panel kész!", ephemeral=True)

@bot.tree.command(name="ticket_hozzáadás")
@app_commands.check(mod_check)
async def ticket_add(i: discord.Interaction, tag: discord.Member):
    if "ticket-" in i.channel.name:
        await i.channel.set_permissions(tag, read_messages=True, send_messages=True)
        await i.response.send_message(f"✅ {tag.mention} hozzáadva a tickethez!")
    else: await i.response.send_message("❌ Ez nem ticket csatorna!", ephemeral=True)

@bot.tree.command(name="autoreact_beállít")
@app_commands.check(mod_check)
async def react_set(i: discord.Interaction, emoji: str):
    data = load_json(REACT_FILE); cid = str(i.channel.id)
    if cid not in data: data[cid] = []
    data[cid].append(emoji); save_json(REACT_FILE, data)
    await i.response.send_message(f"✅ Auto-React hozzáadva: {emoji}")

@bot.tree.command(name="auto_szöveg_beállít")
@app_commands.check(mod_check)
async def sticky_set(i: discord.Interaction, szöveg: str):
    data = load_json(STICKY_FILE); data[str(i.channel.id)] = szöveg; save_json(STICKY_FILE, data)
    await i.response.send_message("✅ Beállítva!", ephemeral=True)

@bot.tree.command(name="üdvözlő_beállítás")
@app_commands.check(mod_check)
async def welcome_set(i: discord.Interaction, csatorna: discord.TextChannel):
    save_json(WELCOME_FILE, {"channel_id": csatorna.id})
    await i.response.send_message("✅ Beállítva!", ephemeral=True)

# ================= MODERÁCIÓ =================

@bot.tree.command(name="figyelmeztetés_info")
@app_commands.check(mod_check)
async def warn_info(i: discord.Interaction, tag: discord.Member):
    data = load_json(WARN_FILE)
    warns = data.get(str(tag.id), [])
    if not warns: return await i.response.send_message(f"✅ {tag.mention}-nak nincs figyelmeztetése.", ephemeral=True)
    desc = ""
    for idx, w in enumerate(warns, 1):
        try:
            diff = datetime.datetime.utcnow() - datetime.datetime.fromisoformat(w['ido'])
            napja = f"{diff.days} napja" if diff.days > 0 else "ma"
        except: napja = "régen"
        desc += f"**{idx}.** `{w['indok']}`\n└ 👮‍♂️: {w['mod']} | 📅: {napja}\n\n"
    await i.response.send_message(embed=make_embed(f"⚠️ {tag.name} figyelmeztetései", desc, discord.Color.blue()))

@bot.tree.command(name="figyelmeztetés")
@app_commands.check(mod_check)
async def warn(i: discord.Interaction, tag: discord.Member, indok: str):
    data = load_json(WARN_FILE)
    uid = str(tag.id)
    now = datetime.datetime.utcnow().isoformat()
    data.setdefault(uid, []).append({"indok": indok, "mod": str(i.user), "ido": now})
    save_json(WARN_FILE, data)
    mute_time = len(data[uid]) * 2
    await tag.timeout(datetime.timedelta(minutes=mute_time))
    await i.response.send_message(embed=make_embed("⚠️ Figyelmeztetés", f"👤 **Tag:** {tag.mention}\n📄 **Indok:** {indok}\n⚠️ **Összesen:** {len(data[uid])}\n🔇 **Némítás:** {mute_time} perc\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.orange()))

@bot.tree.command(name="figyelmeztetés_törlés")
@app_commands.check(mod_check)
async def warn_del(i: discord.Interaction, tag: discord.Member, szám: int):
    data = load_json(WARN_FILE)
    warns = data.get(str(tag.id), [])
    if 0 < szám <= len(warns):
        warns.pop(szám - 1); save_json(WARN_FILE, data)
        await i.response.send_message(embed=make_embed("🧹 Törlés", f"👤 **Tag:** {tag.mention}\n📉 **Maradt:** {len(warns)}\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.green()))
    else: await i.response.send_message("❌ Hibás sorszám!", ephemeral=True)

@bot.tree.command(name="némítás")
@app_commands.check(mod_check)
async def mute(i: discord.Interaction, tag: discord.Member, perc: int, indok: str):
    await tag.timeout(datetime.timedelta(minutes=perc))
    await i.response.send_message(embed=make_embed("🔇 Némítás", f"👤 **Tag:** {tag.mention}\n⏱ **Időtartam:** {perc} perc\n📄 **Indok:** {indok}\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.red()))

@bot.tree.command(name="némítás_feloldás")
@app_commands.check(mod_check)
async def unmute(i: discord.Interaction, tag: discord.Member):
    await tag.timeout(None)
    await i.response.send_message(embed=make_embed("🔊 Némítás feloldva", f"👤 **Tag:** {tag.mention}\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.green()))

# ================= SZIGORÚ JOGOK (BAN/KICK) =================

@bot.tree.command(name="kirúgás")
@app_commands.check(high_mod_check)
@app_commands.default_permissions(kick_members=True)
async def kick(i: discord.Interaction, tag: discord.Member, indok: str):
    await tag.kick(reason=indok)
    await i.response.send_message(embed=make_embed("👢 Kirúgás", f"👤 **Tag:** {tag.mention}\n📄 **Indok:** {indok}\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.orange()))

@bot.tree.command(name="kitiltás")
@app_commands.check(high_mod_check)
@app_commands.default_permissions(ban_members=True)
async def ban(i: discord.Interaction, tag: discord.Member, indok: str):
    await tag.ban(reason=indok)
    await i.response.send_message(embed=make_embed("🚫 Kitiltás", f"👤 **Tag:** {tag.mention}\n📄 **Indok:** {indok}\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.dark_red()))

# ================= VIDEÓ TRADE =================

@bot.tree.command(name="videó")
@app_commands.check(mod_check)
async def video(i: discord.Interaction, szoveg: str, video: discord.Attachment):
    await i.response.defer()
    if not video.content_type or not video.content_type.startswith("video"):
        return await i.followup.send("❌ Csak videó tölthető fel!", ephemeral=True)
    data = load_json(VIDEO_FILE)
    data["count"] = data.get("count", 149) + 1
    save_json(VIDEO_FILE, data)
    await i.followup.send(content=f"**{data['count']}. Sikeres trade bizonyíték**\n{szoveg}\n📸 **Bizonyíték:**", file=await video.to_file())

@bot.tree.error
async def on_app_command_error(i: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        if not i.response.is_done(): await i.response.send_message("❌ **Ezt a parancsot nem áll jogodban használni!**", ephemeral=True)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot online: {bot.user}")

if TOKEN: bot.run(TOKEN)
  import discord
from discord.ext import commands
from discord import app_commands
import os, json, datetime, asyncio, random, re
from collections import defaultdict

# ================== KONFIGURÁCIÓ (ID-K BEÁLLÍTÁSA) ==================

TOKEN = os.getenv("DISCORD_TOKEN")

# IDE MÁSOLD BE A RANGOK ID-JÁT!
TESTER_MOD_ID = 111222333444555666  # [⏰] TESTER MODERÁTOR ID
MOD_ID = 999888777666555444         # [🧨] MODERÁTOR ID

WARN_FILE = "warns.json"
WELCOME_FILE = "welcome.json"
LEAVE_FILE = "leave.json"
AUTO_ROLE_FILE = "autorole.json"
VIDEO_FILE = "videos.json"
STICKY_FILE = "sticky.json"
REACT_FILE = "autoreact.json"

FORBIDDEN_WORDS = ["fasz","geci","buzi","bazdmeg","kurva","anyád","szar","szarka","any@d","apád","cigány","cigany","barom"]
LINK_REGEX = r"http[s]?://"

user_messages = defaultdict(list)
last_sticky_msg = {} 

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= SEGÉDFÜGGVÉNYEK =================

def load_json(file):
    if not os.path.exists(file): return {}
    try:
        with open(file, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)

def make_embed(title, desc, color):
    e = discord.Embed(title=title, description=desc, color=color, timestamp=datetime.datetime.utcnow())
    e.set_footer(text="✨ SERVICE HUN ✨")
    return e

def mod_check(i: discord.Interaction):
    p = i.user.guild_permissions
    return p.administrator or p.manage_messages

def high_mod_check(i: discord.Interaction):
    user_role_ids = [role.id for role in i.user.roles]
    return i.user.guild_permissions.administrator or TESTER_MOD_ID in user_role_ids or MOD_ID in user_role_ids

# ================= DINAMIKUS TICKET RENDSZER UI =================

class DynamicTicketView(discord.ui.View):
    def __init__(self, category_id: int, welcome_msg: str):
        super().__init__(timeout=None)
        self.category_id = category_id
        self.welcome_msg = welcome_msg

    @discord.ui.button(label="Ticket Nyitása 🎫", style=discord.ButtonStyle.primary, custom_id="persistent_open_ticket")
    async def open_ticket(self, i: discord.Interaction, button: discord.ui.Button):
        guild = i.guild
        category = guild.get_channel(self.category_id)
        if not category: return await i.response.send_message("❌ Kategória nem található!", ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            i.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await guild.create_text_channel(f"ticket-{i.user.name}", category=category, overwrites=overwrites)
        await i.response.send_message(f"✅ Ticket: {channel.mention}", ephemeral=True)
        await channel.send(embed=make_embed("🎫 Üdvözlünk!", self.welcome_msg, discord.Color.blue()))

# ================= AUTOMOD + AUTO-REACT + STICKY =================

@bot.event
async def on_message(msg):
    if msg.author.bot or not msg.guild: return
    uid, cid, txt = str(msg.author.id), str(msg.channel.id), msg.content.lower()
    is_mod_immune = msg.author.guild_permissions.manage_messages or msg.author.guild_permissions.administrator

    react_data = load_json(REACT_FILE)
    if cid in react_data:
        for emoji in react_data[cid]:
            try: await msg.add_reaction(emoji)
            except: pass

    indok = None
    if not is_mod_immune:
        if re.search(LINK_REGEX, txt): indok = "Tiltott link küldése"
        elif any(w in txt for w in FORBIDDEN_WORDS): indok = "Káromkodás"
        else:
            now = datetime.datetime.now()
            user_messages[uid] = [t for t in user_messages[uid] if (now - t).seconds < 5]
            user_messages[uid].append(now)
            if len(user_messages[uid]) >= 5: indok = "Spamming (Túl sok üzenet)"

    if indok:
        await msg.delete()
        data = load_json(WARN_FILE)
        now_iso = datetime.datetime.utcnow().isoformat()
        data.setdefault(uid, []).append({"indok": indok, "mod": "Rendszer (Automod)", "ido": now_iso})
        save_json(WARN_FILE, data)
        mute_time = len(data[uid]) * 2
        await msg.author.timeout(datetime.timedelta(minutes=mute_time))
        
        await msg.channel.send(embed=make_embed(
            "🛑 Automatikus figyelmeztetés",
            f"👤 **Tag:** {msg.author.mention}\n📄 **Indok:** {indok}\n⚠️ **Figyelmeztetések:** {len(data[uid])}\n🔇 **Némítás:** {mute_time} perc\n👮‍♂️ **Intézkedett:** Rendszer (Automod)",
            discord.Color.red()
        ))
        return

    sticky_data = load_json(STICKY_FILE)
    if cid in sticky_data:
        if cid in last_sticky_msg:
            try:
                old_msg = await msg.channel.fetch_message(last_sticky_msg[cid])
                await old_msg.delete()
            except: pass
        new_sticky = await msg.channel.send(sticky_data[cid])
        last_sticky_msg[cid] = new_sticky.id

    await bot.process_commands(msg)

# ================= BELÉPÉS / KILÉPÉS =================

@bot.event
async def on_member_join(member):
    ar = load_json(AUTO_ROLE_FILE)
    role = member.guild.get_role(ar.get("role_id", 0))
    if role: await member.add_roles(role)
    data = load_json(WELCOME_FILE)
    ch = member.guild.get_channel(data.get("channel_id", 0))
    if ch: await ch.send(f"👋 Üdv a szerveren {member.mention}! Te vagy a(z) {member.guild.member_count}. tag 💙")

@bot.event
async def on_member_remove(member):
    data = load_json(LEAVE_FILE)
    ch = member.guild.get_channel(data.get("channel_id", 0))
    if ch: await ch.send(f"🚪 {member.name} kilépett a szerverről.")

# ================= NYEREMÉNYJÁTÉK (GIVEAWAY) =================

@bot.tree.command(name="nyereményjáték", description="Nyereményjáték indítása")
@app_commands.check(mod_check)
async def giveaway(i: discord.Interaction, idő_perc: int, nyeremény: str, nyertesek_száma: int = 1):
    embed = make_embed(
        "🎉 NYEREMÉNYJÁTÉK 🎉",
        f"🎁 Nyeremény: **{nyeremény}**\n"
        f"👤 Nyertesek száma: **{nyertesek_száma}**\n"
        f"⌛ Időtartam: **{idő_perc} perc**\n\n"
        f"Reagálj a 🎉 gombbal a jelentkezéshez!",
        discord.Color.blue()
    )
    
    await i.response.send_message("✅ Játék elindítva!", ephemeral=True)
    msg = await i.channel.send(embed=embed)
    await msg.add_reaction("🎉")
    
    await asyncio.sleep(idő_perc * 60)
    
    msg = await i.channel.fetch_message(msg.id)
    reaction = discord.utils.get(msg.reactions, emoji="🎉")
    users = [u async for u in reaction.users() if not u.bot]
    
    if len(users) < nyertesek_száma:
        return await i.channel.send(f"❌ Nincs elég jelentkező a nyereményjátékhoz (**{nyeremény}**).")
    
    winners = random.sample(users, nyertesek_száma)
    winner_mentions = ", ".join([w.mention for w in winners])
    
    await i.channel.send(f"🎊 Gratulálunk {winner_mentions}! Megnyerted: **{nyeremény}**! 🏆")

# ================= TICKET / REACT / BEÁLLÍTÁSOK =================

@bot.tree.command(name="ticket_panel")
@app_commands.check(mod_check)
async def ticket_panel(i: discord.Interaction, cím: str, panel_leírás: str, kategória_id: str, ticket_üdvözlő_szöveg: str):
    view = DynamicTicketView(int(kategória_id), ticket_üdvözlő_szöveg)
    await i.channel.send(embed=make_embed(cím, panel_leírás, discord.Color.green()), view=view)
    await i.response.send_message("✅ Panel kész!", ephemeral=True)

@bot.tree.command(name="ticket_hozzáadás")
@app_commands.check(mod_check)
async def ticket_add(i: discord.Interaction, tag: discord.Member):
    if "ticket-" in i.channel.name:
        await i.channel.set_permissions(tag, read_messages=True, send_messages=True)
        await i.response.send_message(f"✅ {tag.mention} hozzáadva a tickethez!")
    else: await i.response.send_message("❌ Ez nem ticket csatorna!", ephemeral=True)

@bot.tree.command(name="autoreact_beállít")
@app_commands.check(mod_check)
async def react_set(i: discord.Interaction, emoji: str):
    data = load_json(REACT_FILE); cid = str(i.channel.id)
    if cid not in data: data[cid] = []
    data[cid].append(emoji); save_json(REACT_FILE, data)
    await i.response.send_message(f"✅ Auto-React hozzáadva: {emoji}")

@bot.tree.command(name="auto_szöveg_beállít")
@app_commands.check(mod_check)
async def sticky_set(i: discord.Interaction, szöveg: str):
    data = load_json(STICKY_FILE); data[str(i.channel.id)] = szöveg; save_json(STICKY_FILE, data)
    await i.response.send_message("✅ Beállítva!", ephemeral=True)

@bot.tree.command(name="üdvözlő_beállítás")
@app_commands.check(mod_check)
async def welcome_set(i: discord.Interaction, csatorna: discord.TextChannel):
    save_json(WELCOME_FILE, {"channel_id": csatorna.id})
    await i.response.send_message("✅ Beállítva!", ephemeral=True)

@bot.tree.command(name="autorole_beállítás")
@app_commands.check(mod_check)
async def autorole_set(i: discord.Interaction, rang: discord.Role):
    save_json(AUTO_ROLE_FILE, {"role_id": rang.id})
    await i.response.send_message("✅ Beállítva!", ephemeral=True)

# ================= MODERÁCIÓ =================

@bot.tree.command(name="figyelmeztetés_info")
@app_commands.check(mod_check)
async def warn_info(i: discord.Interaction, tag: discord.Member):
    data = load_json(WARN_FILE)
    warns = data.get(str(tag.id), [])
    if not warns: return await i.response.send_message(f"✅ {tag.mention}-nak nincs figyelmeztetése.", ephemeral=True)
    desc = ""
    for idx, w in enumerate(warns, 1):
        try:
            diff = datetime.datetime.utcnow() - datetime.datetime.fromisoformat(w['ido'])
            napja = f"{diff.days} napja" if diff.days > 0 else "ma"
        except: napja = "régen"
        desc += f"**{idx}.** `{w['indok']}`\n└ 👮‍♂️: {w['mod']} | 📅: {napja}\n\n"
    await i.response.send_message(embed=make_embed(f"⚠️ {tag.name} figyelmeztetései", desc, discord.Color.blue()))

@bot.tree.command(name="figyelmeztetés")
@app_commands.check(mod_check)
async def warn(i: discord.Interaction, tag: discord.Member, indok: str):
    data = load_json(WARN_FILE)
    uid = str(tag.id)
    now = datetime.datetime.utcnow().isoformat()
    data.setdefault(uid, []).append({"indok": indok, "mod": str(i.user), "ido": now})
    save_json(WARN_FILE, data)
    mute_time = len(data[uid]) * 2
    await tag.timeout(datetime.timedelta(minutes=mute_time))
    await i.response.send_message(embed=make_embed("⚠️ Figyelmeztetés", f"👤 **Tag:** {tag.mention}\n📄 **Indok:** {indok}\n⚠️ **Összesen:** {len(data[uid])}\n🔇 **Némítás:** {mute_time} perc\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.orange()))

@bot.tree.command(name="figyelmeztetés_törlés")
@app_commands.check(mod_check)
async def warn_del(i: discord.Interaction, tag: discord.Member, szám: int):
    data = load_json(WARN_FILE)
    warns = data.get(str(tag.id), [])
    if 0 < szám <= len(warns):
        warns.pop(szám - 1); save_json(WARN_FILE, data)
        await i.response.send_message(embed=make_embed("🧹 Törlés", f"👤 **Tag:** {tag.mention}\n📉 **Maradt:** {len(warns)}\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.green()))
    else: await i.response.send_message("❌ Hibás sorszám!", ephemeral=True)

@bot.tree.command(name="némítás")
@app_commands.check(mod_check)
async def mute(i: discord.Interaction, tag: discord.Member, perc: int, indok: str):
    await tag.timeout(datetime.timedelta(minutes=perc))
    await i.response.send_message(embed=make_embed("🔇 Némítás", f"👤 **Tag:** {tag.mention}\n⏱ **Időtartam:** {perc} perc\n📄 **Indok:** {indok}\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.red()))

@bot.tree.command(name="némítás_feloldás")
@app_commands.check(mod_check)
async def unmute(i: discord.Interaction, tag: discord.Member):
    await tag.timeout(None)
    await i.response.send_message(embed=make_embed("🔊 Némítás feloldva", f"👤 **Tag:** {tag.mention}\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.green()))

# ================= SZIGORÚ JOGOK (BAN/KICK) =================

@bot.tree.command(name="kirúgás")
@app_commands.check(high_mod_check)
@app_commands.default_permissions(kick_members=True)
async def kick(i: discord.Interaction, tag: discord.Member, indok: str):
    await tag.kick(reason=indok)
    await i.response.send_message(embed=make_embed("👢 Kirúgás", f"👤 **Tag:** {tag.mention}\n📄 **Indok:** {indok}\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.orange()))

@bot.tree.command(name="kitiltás")
@app_commands.check(high_mod_check)
@app_commands.default_permissions(ban_members=True)
async def ban(i: discord.Interaction, tag: discord.Member, indok: str):
    await tag.ban(reason=indok)
    await i.response.send_message(embed=make_embed("🚫 Kitiltás", f"👤 **Tag:** {tag.mention}\n📄 **Indok:** {indok}\n👮‍♂️ **Intézkedett:** {i.user.mention}", discord.Color.dark_red()))

# ================= VIDEÓ TRADE =================

@bot.tree.command(name="videó")
@app_commands.check(mod_check)
async def video(i: discord.Interaction, szoveg: str, video: discord.Attachment):
    await i.response.defer()
    if not video.content_type or not video.content_type.startswith("video"):
        return await i.followup.send("❌ Csak videó tölthető fel!", ephemeral=True)
    data = load_json(VIDEO_FILE)
    data["count"] = data.get("count", 149) + 1
    save_json(VIDEO_FILE, data)
    await i.followup.send(content=f"**{data['count']}. Sikeres trade bizonyíték**\n{szoveg}\n📸 **Bizonyíték:**", file=await video.to_file())

@bot.tree.error
async def on_app_command_error(i: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        if not i.response.is_done(): await i.response.send_message("❌ **Ezt a parancsot nem áll jogodban használni!**", ephemeral=True)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot online: {bot.user}")

if TOKEN: bot.run(TOKEN)
