import asyncio
from sqlalchemy import Table, Column, String, UniqueConstraint

from cloudbot import hook
from cloudbot.util import database
from cloudbot.util.persistent_set import PersistentSet
from plugins.global_tracking import Registry

# WEREWOLF_CHAN = '##werewolf'
WEREWOLF_CHAN = '##abra2'
# MIRROR_CHAN = '##werewolf-ded'
MIRROR_CHAN = '##abra'

table = Table(
  'dedlykos_table_a',
  database.metadata,
  Column('nick', String(50)),
  Column('set', String(50)),
  UniqueConstraint('nick', 'set'))

privileged = PersistentSet('privileged', table)
kicked = PersistentSet('kicked', table)


@hook.on_start
def load_cache(db):
  """
  :type db: sqlalchemy.orm.Session
  """
  privileged.load(db)
  kicked.load(db)


@asyncio.coroutine
@hook.irc_raw("JOIN")
def on_join(conn, chan, event, nick, db):
  if not chan:
    chan = event.irc_paramlist[0][1:]

  if nick == conn.nick and chan == WEREWOLF_CHAN:
    if not hasattr(conn, 'registry'):
      conn.registry = Registry()


@asyncio.coroutine
@hook.periodic(1)
def periodic_checker(bot, db):
  for conn in bot.connections.values():
    yield from check(conn, db)


@asyncio.coroutine
def check(conn, db):
  if not hasattr(conn, 'registry'):
    conn.registry = Registry()

  r = conn.registry

  if not r.mode(WEREWOLF_CHAN) or not r.mode(MIRROR_CHAN):
    return

  w = r.chan(WEREWOLF_CHAN)
  m = r.chan(MIRROR_CHAN)

  wm = r.mode(WEREWOLF_CHAN)
  mm = r.mode(MIRROR_CHAN)

  for j in set(m):
    if not j.account:
      conn.send('KICK {} {} :{}'.format(MIRROR_CHAN, j.nick, 'Unidentified'))
      return

    if j not in w:
      conn.send('KICK {} {} :{}'.format(MIRROR_CHAN, j.nick, 'Not in ##werewolf'))
      return

  for i in w:
    for j in m:
      if i.account == j.account:
        if i.prefix == '+' and not j.prefix:
          conn.send('MODE {} +v {}'.format(MIRROR_CHAN, j.nick))
          return
        if not i.prefix and j.prefix == '+':
          conn.send('MODE {} -v {}'.format(MIRROR_CHAN, j.nick))
          return

  if 'm' in wm:
    if 'i' not in mm:
      conn.send('MODE {} +i'.format(MIRROR_CHAN))

    for i in w:
      for j in m:
        if i.prefix == '+' and i.account == j.account:
          conn.send('KICK {} {} :{}'.format(MIRROR_CHAN, j.nick, 'Playing ##werewolf'))
          kicked.add(db, i.account)
          return
        elif not i.prefix and i.account == j.account and i.account not in privileged.set():
          conn.send('KICK {} {} :{}'.format(MIRROR_CHAN, j.nick, 'Not allowed to spectate'))
          kicked.add(db, i.account)
          return

    for i in w:
      if i not in m and not i.prefix and i.account in kicked.set():
        conn.send('INVITE {} {}'.format(i.nick, MIRROR_CHAN))
        kicked.remove(db, i.account)
        return
  else:
    if 'i' in mm:
      conn.send('MODE {} -i'.format(MIRROR_CHAN))

    for i in set(kicked.set()):
      for j in w:
        if j.account == i and j not in m:
          conn.send('INVITE {} {}'.format(j.nick, MIRROR_CHAN))
          kicked.remove(db, i)
          return


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
def a(conn, chan, event, bot, nick, reply, db, loop, text):
  conn.message(chan, '{}'.format(kicked.set()))
  conn.message(chan, '{}'.format(privileged.set()))
