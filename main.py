import discord
from discord.ext import commands, tasks
from discord import app_commands
import os, json, datetime, re, random

TOKEN = os.getenv("DISCORD_TOKEN")

WARN_FILE = "warns.json"
AUTOMOD_LOG_FILE = "automod_log.json"
WELCOME_FILE = "welcome.json"
LEAVE_FILE = "leave.json"
AUTOROLE_FILE = "autorole.json"
GIVEAWAY_FILE = "giveaway.json"

FORBIDDEN_WORDS = ["fasz","geci","buzi","kurva","bazdmeg","anyad","anyád"]
LINK_REGEX = r"http[s]?://"
FOOTER = "✨ DT_bluuuue szervere ✨"

def load_json(f, d):
    if not os.path.exists(f):
        return d
    with open(f,"r",encoding="utf-8") as file:
        return json.load(file)

def save_json(f, d):
    with open(f,"w",encoding="utf-8") as file:
        json.dump(d,file,indent=4,ensure_ascii=False)

def emb(t,d,c=discord.Color.blue()):
    e=discord.Embed(title=t,description=d,color=c)
    e.set_footer(text=FOOTER)
    return e

def mod(inter):
    p=inter.user.guild_permissions
    return p.manage_messages or p.administrator

intents=discord.Intents.all()
bot=commands.Bot(command_prefix="!",intents=intents)
spam={}

@bot.event
async def on_ready():
    await bot.tree.sync()
    print("BOT ONLINE")

# ================= BELÉPÉS =================
@bot.event
async def on_member_join(m):
    ar=load_json(AUTOROLE_FILE,{})
    r=ar.get(str(m.guild.id))
    if r:
        role=m.guild.get_role(r)
        if role:
            await m.add_roles(role)

    wc=load_json(WELCOME_FILE,{})
    ch=wc.get(str(m.guild.id))
    if ch:
        c=m.guild.get_channel(ch)
        if c:
            await c.send(f"{m.mention} Üdv a szerveren!\nTe vagy a(z) **{m.guild.member_count}. tag**")

@bot.event
async def on_member_remove(m):
    lc=load_json(LEAVE_FILE,{})
    ch=lc.get(str(m.guild.id))
    if ch:
        c=m.guild.get_channel(ch)
        if c:
            await c.send(f"🚪 Kilépett a szerverről: {m.mention}")

# ================= AUTOMOD =================
@bot.event
async def on_message(msg):
    if msg.author.bot:
        return

    logch=None
    lg=load_json(AUTOMOD_LOG_FILE,{})
    if str(msg.guild.id) in lg:
        logch=msg.guild.get_channel(lg[str(msg.guild.id)])

    if re.search(LINK_REGEX,msg.content.lower()):
        await msg.delete()
        await msg.author.timeout(datetime.timedelta(minutes=10),reason="Link tiltott")
        if logch:
            await logch.send(emb("🔗 Link tiltás",f"{msg.author.mention}\n🔇 10 perc",discord.Color.red()))
        return

    spam.setdefault(msg.author.id,[])
    spam[msg.author.id].append(datetime.datetime.utcnow())
    spam[msg.author.id]=[t for t in spam[msg.author.id] if (datetime.datetime.utcnow()-t).seconds<5]
    if len(spam[msg.author.id])>=5:
        await msg.delete()
        await msg.author.timeout(datetime.timedelta(minutes=5),reason="Spam")
        if logch:
            await logch.send(emb("🔁 Spam",f"{msg.author.mention}\n🔇 5 perc",discord.Color.orange()))
        spam[msg.author.id].clear()
        return

    if any(w in msg.content.lower() for w in FORBIDDEN_WORDS):
        await msg.delete()
        warns=load_json(WARN_FILE,{})
        uid=str(msg.author.id)
        warns.setdefault(uid,[]).append("Káromkodás")
        save_json(WARN_FILE,warns)
        mute=len(warns[uid])*2
        await msg.author.timeout(datetime.timedelta(minutes=mute),reason="Káromkodás")
        if logch:
            await logch.send(emb("🤬 Káromkodás",f"{msg.author.mention}\n🔇 {mute} perc",discord.Color.dark_red()))
        return

    await bot.process_commands(msg)

# ================= PARANCSOK =================

@bot.tree.command(name="figyelmeztetes")
@app_commands.check(mod)
async def figy(i,tag:discord.Member,indok:str):
    w=load_json(WARN_FILE,{})
    w.setdefault(str(tag.id),[]).append(indok)
    save_json(WARN_FILE,w)
    await i.response.send_message(emb("⚠️ Figyelmeztetés",f"{tag.mention}\n{indok}"))

@bot.tree.command(name="figyelmeztetesek")
@app_commands.check(mod)
async def figylist(i,tag:discord.Member):
    w=load_json(WARN_FILE,{})
    l=w.get(str(tag.id),[])
    if not l:
        await i.response.send_message("Nincs figyelmeztetés",ephemeral=True)
        return
    txt="\n".join(f"{x+1}. {v}" for x,v in enumerate(l))
    await i.response.send_message(emb("📋 Figyelmeztetések",txt))

@bot.tree.command(name="figyelmeztetes_torles")
@app_commands.check(mod)
async def figydel(i,tag:discord.Member,s:int):
    w=load_json(WARN_FILE,{})
    uid=str(tag.id)
    if uid not in w or s<1 or s>len(w[uid]):
        await i.response.send_message("Hibás sorszám",ephemeral=True)
        return
    w[uid].pop(s-1)
    save_json(WARN_FILE,w)
    await i.response.send_message("✅ Törölve")

@bot.tree.command(name="nemitas")
@app_commands.check(mod)
async def mute(i,tag:discord.Member,perc:int,indok:str):
    await tag.timeout(datetime.timedelta(minutes=perc),reason=indok)
    await i.response.send_message(emb("🔇 Némítás",f"{tag.mention}\n{perc} perc\n{indok}"))

@bot.tree.command(name="kitiltas")
@app_commands.check(mod)
async def ban(i,tag:discord.Member,indok:str):
    await tag.ban(reason=indok)
    await i.response.send_message(emb("🚫 Kitiltás",f"{tag.mention}\n{indok}",discord.Color.red()))

@bot.tree.command(name="id_kitiltas")
@app_commands.check(mod)
async def idban(i,uid:str,indok:str):
    u=await bot.fetch_user(int(uid))
    await i.guild.ban(u,reason=indok)
    await i.response.send_message(emb("🚫 ID Kitiltás",f"{uid}\n{indok}",discord.Color.red()))

@bot.tree.command(name="nyeremenyjatek")
@app_commands.check(mod)
async def gw(i,nyeremeny:str):
    await i.response.send_message(emb("🎉 Nyereményjáték",nyeremeny))

@bot.tree.command(name="csok")
async def csok(i,tag:discord.Member):
    await i.response.send_message(f"{i.user.mention} 💋 {tag.mention}")

bot.run(TOKEN)
