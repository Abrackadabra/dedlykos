import asyncio
from sqlalchemy import Table, Column, String, UniqueConstraint

from cloudbot import hook
from cloudbot.util import database
from cloudbot.util.persistent_set import PersistentSet

WEREWOLF_CHAN = '##werewolf'
# WEREWOLF_CHAN = '#abrtst'
MIRROR_CHAN = '##werewolf-ded'
# MIRROR_CHAN = '#abrtst'

table = Table(
  'dedlykos_table',
  database.metadata,
  Column('nick', String(50)),
  Column('set', String(50)),
  UniqueConstraint('nick', 'set'))

privileged = PersistentSet('privileged', table)
were_in_chan = PersistentSet('were_in_chan', table)
playing = PersistentSet('playing', table)
kicked = PersistentSet('kicked', table)
test = PersistentSet('test', table)

muted = False

werewolf_nicks = {}
mirror_nicks = {}


@hook.on_start
def load_cache(db):
  """
  :type db: sqlalchemy.orm.Session
  """
  privileged.load(db)
  were_in_chan.load(db)
  were_in_chan.clear(db)
  playing.load(db)
  playing.clear(db)
  kicked.load(db)
  kicked.clear(db)
  test.load(db)


@asyncio.coroutine
def init(db, conn):
  who_w = yield from get_who(WEREWOLF_CHAN, conn)
  who_m = yield from get_who(MIRROR_CHAN, conn)
  for i, j in who_w.items():
    if j == '+':
      playing.add(db, i)
      if i in who_m and who_m[i] != '+':
        conn.send('MODE {} +v {}'.format(MIRROR_CHAN, i))

  werewolf_nicks.clear()
  werewolf_nicks.update(who_w)

  mirror_nicks.clear()
  mirror_nicks.update(who_m)

  muted_w = 'm' in (yield from get_mode(WEREWOLF_CHAN, conn))
  locked_m = 'i' in (yield from get_mode(MIRROR_CHAN, conn))

  global muted
  muted = muted_w

  if muted_w and not locked_m:
    conn.send('MODE {} +i'.format(MIRROR_CHAN))

  if not muted_w and locked_m:
    conn.send('MODE {} -i'.format(MIRROR_CHAN))


@asyncio.coroutine
@hook.irc_raw("MODE")
def mode_catch(event, conn, db):
  if event.chan != WEREWOLF_CHAN:
    return

  yield from process_modechange(event.irc_paramlist, conn, db)


@asyncio.coroutine
def process_modechange(a, conn, db):
  print('  MODE CHANGE: {}'.format(a))
  if len(a) < 2:
    return

  global muted

  i = 2
  plus = True
  new_muted = muted
  for c in a[1]:
    if c == '-':
      plus = False
    elif c == '+':
      plus = True
    elif c == 'v':
      if muted:
        if plus:
          conn.message(MIRROR_CHAN, 'That\'s unexpected.')
        else:
          if a[i] in were_in_chan.set():
            conn.send('INVITE {1} {0}'.format(MIRROR_CHAN, a[i]))
            kicked.remove(db, a[i])
          conn.send('MODE {} -v {}'.format(MIRROR_CHAN, a[i]))
      else:
        if plus:
          playing.add(db, a[i])
          conn.send('MODE {} +v {}'.format(MIRROR_CHAN, a[i]))
        else:
          playing.remove(db, a[i])
          conn.send('MODE {} -v {}'.format(MIRROR_CHAN, a[i]))
      i += 1
    elif c == 'm':
      new_muted = plus

    if muted != new_muted:
      if new_muted:
        muted = True

        were_in_chan.clear(db)
        who = yield from get_who(MIRROR_CHAN, conn)
        were_in_chan.update(db, who.keys())

        conn.send('MODE {} +i'.format(MIRROR_CHAN))

        to_kick = (were_in_chan.set() & playing.set()) | (were_in_chan.set() - privileged.set())

        for j in to_kick:
          conn.send('KICK {} {} {}'.format(
            MIRROR_CHAN, j,
            'The game is starting! You\'ll be invited back when it ends.'))

        kicked.clear(db)
        kicked.update(db, to_kick)
      else:
        muted = False

        for j in kicked.set():
          conn.send('INVITE {1} {0}'.format(MIRROR_CHAN, j))

        conn.send('MODE {} -i'.format(MIRROR_CHAN))
        were_in_chan.clear(db)
        playing.clear(db)


@asyncio.coroutine
@hook.command(permissions=['botcontrol'])
def add_privileged(conn, event, bot, nick, reply, db, text):
  nicks = text.split()

  added = []

  for i in nicks:
    if i not in privileged.set():
      privileged.add(db, i)
      added.append(i)

  return '[{}] have been added to spectators.'.format(', '.join(added))


@asyncio.coroutine
@hook.command(permissions=['botcontrol'])
def remove_privileged(conn, event, bot, nick, reply, db, text):
  nicks = text.split()

  removed = []

  for i in nicks:
    if i in privileged.set():
      privileged.remove(db, i)
      removed.append(i)

  return '[{}] have been removed from spectators.'.format(', '.join(removed))


@asyncio.coroutine
@hook.command(permissions=['botcontrol'])
def list_privileged(conn, event, bot, nick, reply, db, text):
  return privileged.set()


@asyncio.coroutine
@hook.command(permissions=['botcontrol'])
def t(conn, chan, event, bot, nick, reply, db, loop):
  a = yield from get_who(chan, conn)
  return str(a)


@asyncio.coroutine
@hook.command(permissions=['botcontrol'])
def c(conn, chan, event, bot, nick, reply, db, loop):
  conn.send('KICK {} abra2 "test test"'.format(chan))


@asyncio.coroutine
@hook.command(permissions=['botcontrol'])
def z(conn, chan, event, bot, nick, reply, db, loop, text):
  if not text:
    reply('muted: {}'.format(muted))
    reply('playing: {}'.format(playing.set()))
    reply('were_in_chan: {}'.format(were_in_chan.set()))
    reply('kicked: {}'.format(kicked.set()))
    reply('privileged: {}'.format(privileged.set()))
    return

  yield from process_modechange(text.split(), conn, db)
  reply(text.split())


_who_queue = asyncio.Queue()


@asyncio.coroutine
def get_who(chan, conn):
  global _who_queue
  _who_queue = asyncio.Queue()

  conn.send("WHO {}".format(chan))
  a = {}
  while True:
    val = yield from _who_queue.get()
    if not val:
      break
    nick, pref = val
    a[nick] = pref

  del a[conn.nick]

  return a


@asyncio.coroutine
@hook.irc_raw("352")
def who_item(event):
  nick = event.irc_paramlist[5]
  pref = event.irc_paramlist[6]
  if '+' in pref:
    pref = '+'
  elif '@' in pref:
    pref = '@'
  else:
    pref = ''

  yield from _who_queue.put((nick, pref))


@asyncio.coroutine
@hook.irc_raw("315")
def who_end(event):
  yield from _who_queue.put(None)


@asyncio.coroutine
@hook.irc_raw("JOIN")
def on_join(conn, chan, event, nick, db):
  if chan == MIRROR_CHAN and nick in playing.set():
    conn.send('MODE {} +v {}'.format(MIRROR_CHAN, nick))

  if nick == conn.nick and (chan == WEREWOLF_CHAN or
                                event.irc_paramlist[0] == ':{}'.format(WEREWOLF_CHAN)):
    yield from init(db, conn)


_mode_queue = asyncio.Queue()


@asyncio.coroutine
def get_mode(chan, conn):
  global _mode_queue
  _mode_queue = asyncio.Queue()

  conn.send("MODE {}".format(chan))
  val = yield from _mode_queue.get()
  return val


@asyncio.coroutine
@hook.irc_raw("324")
def mode_item(event):
  print(event.irc_paramlist)
  yield from _mode_queue.put(event.irc_paramlist[2])
