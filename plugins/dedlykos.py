import asyncio
from sqlalchemy import Table, Column, String, UniqueConstraint

from cloudbot import hook
from cloudbot.util import database
from cloudbot.util.persistent_set import PersistentSet
from plugins.global_tracking import Registry

WEREWOLF_CHAN = '##werewolf'
# WEREWOLF_CHAN = '##abra2'
MIRROR_CHAN = '##werewolf-ded'
# MIRROR_CHAN = '##abra'

table = Table(
  'dedlykos_table_a',
  database.metadata,
  Column('nick', String(50)),
  Column('set', String(50)),
  UniqueConstraint('nick', 'set'))

privileged = PersistentSet('privileged', table)
were_in_chan = PersistentSet('were_in_chan', table)
playing = PersistentSet('playing', table)
kicked = PersistentSet('kicked', table)
invited = PersistentSet('invited', table)


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
  invited.load(db)
  invited.clear(db)


#
#
# def to_reprs(s):
#   return set(list(map(repr, s)))
#
#
# @asyncio.coroutine
# def init(db, conn):
#   werewolf_dudes = conn.registry.chan(WEREWOLF_CHAN)
#   mirror_dudes = conn.registry.chan(MIRROR_CHAN)
#
#   for dude in werewolf_dudes:
#     if dude.prefix == '+':
#       playing.add(db, repr(dude))
#       if dude in mirror_nicks and dude.prefix_in_chan(mirror_dudes):
#         conn.send('MODE {} +v {}'.format(MIRROR_CHAN, dude.nick))
#
#   muted_w = 'm' in (yield from get_mode(WEREWOLF_CHAN, conn))
#   locked_m = 'i' in (yield from get_mode(MIRROR_CHAN, conn))
#
#   global muted
#   muted = muted_w
#
#   if muted_w and not locked_m:
#     conn.send('MODE {} +i'.format(MIRROR_CHAN))
#
#   if not muted_w and locked_m:
#     conn.send('MODE {} -i'.format(MIRROR_CHAN))
#
#
# @asyncio.coroutine
# @hook.irc_raw("MODE")
# def mode_catch(event, conn, db):
#   if event.chan != WEREWOLF_CHAN:
#     return
#
#   yield from process_modechange(event.irc_paramlist, conn, db)
#
#
# @asyncio.coroutine
# def process_modechange(a, conn, db):
#   print('  MODE CHANGE: {}'.format(a))
#   if len(a) < 2:
#     return
#
#   global muted
#
#   i = 2
#   plus = True
#   new_muted = muted
#   for c in a[1]:
#     if c == '-':
#       plus = False
#     elif c == '+':
#       plus = True
#     elif c == 'v':
#       if muted:
#         if plus:
#           conn.message(MIRROR_CHAN, 'That\'s unexpected.')
#         else:
#           if a[i] in were_in_chan.set():
#             conn.send('INVITE {1} {0}'.format(MIRROR_CHAN, a[i]))
#             kicked.remove(db, a[i])
#           conn.send('MODE {} -v {}'.format(MIRROR_CHAN, a[i]))
#       else:
#         if plus:
#           playing.add(db, a[i])
#           conn.send('MODE {} +v {}'.format(MIRROR_CHAN, a[i]))
#         else:
#           playing.remove(db, a[i])
#           conn.send('MODE {} -v {}'.format(MIRROR_CHAN, a[i]))
#       i += 1
#     elif c == 'm':
#       new_muted = plus
#
#     if muted != new_muted:
#       if new_muted:
#         muted = True
#
#         were_in_chan.clear(db)
#         who = yield from get_who(MIRROR_CHAN, conn)
#         were_in_chan.update(db, who.keys())
#
#         conn.send('MODE {} +i'.format(MIRROR_CHAN))
#
#         to_kick = (were_in_chan.set() & playing.set()) | (were_in_chan.set() - privileged.set())
#
#         for j in to_kick:
#           conn.send('KICK {} {} {}'.format(
#             MIRROR_CHAN, j,
#             'The game is starting! You\'ll be invited back when it ends.'))
#
#         kicked.clear(db)
#         kicked.update(db, to_kick)
#       else:
#         muted = False
#
#         for j in kicked.set():
#           conn.send('INVITE {1} {0}'.format(MIRROR_CHAN, j))
#
#         conn.send('MODE {} -i'.format(MIRROR_CHAN))
#         were_in_chan.clear(db)
#         playing.clear(db)
#
#
# @asyncio.coroutine
# @hook.command(permissions=['botcontrol'])
# def add_privileged(conn, event, bot, nick, reply, db, text):
#   nicks = text.split()
#
#   added = []
#
#   for i in nicks:
#     if i not in privileged.set():
#       privileged.add(db, i)
#       added.append(i)
#
#   return '[{}] have been added to spectators.'.format(', '.join(added))
#
#
# @asyncio.coroutine
# @hook.command(permissions=['botcontrol'])
# def remove_privileged(conn, event, bot, nick, reply, db, text):
#   nicks = text.split()
#
#   removed = []
#
#   for i in nicks:
#     if i in privileged.set():
#       privileged.remove(db, i)
#       removed.append(i)
#
#   return '[{}] have been removed from spectators.'.format(', '.join(removed))
#
#
# @asyncio.coroutine
# @hook.command(permissions=['botcontrol'])
# def list_privileged(conn, event, bot, nick, reply, db, text):
#   return privileged.set()
#
#
# @asyncio.coroutine
# @hook.command(permissions=['botcontrol'])
# def t(conn, chan, event, bot, nick, reply, db, loop):
#   a = yield from get_who(chan, conn)
#   return str(a)
#
#
# @asyncio.coroutine
# @hook.command(permissions=['botcontrol'])
# def c(conn, chan, event, bot, nick, reply, db, loop):
#   conn.send('KICK {} abra2 "test test"'.format(chan))
#
#
# @asyncio.coroutine
# @hook.command(permissions=['botcontrol'])
# def z(conn, chan, event, bot, nick, reply, db, loop, text):
#   if not text:
#     reply('muted: {}'.format(muted))
#     reply('playing: {}'.format(playing.set()))
#     reply('were_in_chan: {}'.format(were_in_chan.set()))
#     reply('kicked: {}'.format(kicked.set()))
#     reply('privileged: {}'.format(privileged.set()))
#     return
#
#   yield from process_modechange(text.split(), conn, db)
#   reply(text.split())
#
#
# @asyncio.coroutine
# @hook.irc_raw("JOIN")
# def on_join(conn, chan, event, nick, db):
#   if chan == MIRROR_CHAN and nick in playing.set():
#     conn.send('MODE {} +v {}'.format(MIRROR_CHAN, nick))
#
#   if nick == conn.nick and (chan == WEREWOLF_CHAN or
#                                 event.irc_paramlist[0] == ':{}'.format(WEREWOLF_CHAN)):
#     yield from init(db, conn)



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

  print('?', end='', flush=True)
  r = conn.registry

  if not r.mode(WEREWOLF_CHAN) or not r.mode(MIRROR_CHAN):
    return

  w = r.chan(WEREWOLF_CHAN)
  m = r.chan(MIRROR_CHAN)

  wm = r.mode(WEREWOLF_CHAN)
  mm = r.mode(MIRROR_CHAN)

  # print(w, m, wm, mm)

  for j in set(m):
    if not j.account:
      conn.send('KICK {} {} :{}'.format(MIRROR_CHAN, j.nick, 'Unidentified.'))
      return

    if j not in w:
      conn.send('KICK {} {} :{}'.format(MIRROR_CHAN, j.nick, 'Not in ##werewolf.'))
      return

  for i in w:
    for j in m:
      if i.account == j.account:
        if i.prefix == '+' and not j.prefix:
          conn.send('MODE {} +v {}'.format(MIRROR_CHAN, j.nick))
        if not i.prefix and j.prefix == '+':
          conn.send('MODE {} -v {}'.format(MIRROR_CHAN, j.nick))

  if 'm' in wm:
    if 'i' not in mm:
      conn.send('MODE {} +i'.format(MIRROR_CHAN))

    for i in w:
      for j in m:
        if i.prefix == '+' and i.account == j.account:
          conn.send('KICK {} {} :{}'.format(MIRROR_CHAN, j.nick, 'Playing ##werewolf.'))
          kicked.add(db, i.account)
          return
        elif not i.prefix and i.account == j.account and i.account not in privileged.set():
          conn.send('KICK {} {} :{}'.format(MIRROR_CHAN, j.nick, 'Not allowed to spectate.'))
          kicked.add(db, i.account)
          return

    for i in w:
      if i not in m and not i.prefix and i.account in kicked.set():
        conn.send('INVITE {} {}'.format(i.nick, MIRROR_CHAN))
        kicked.remove(db, i)
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

  print('+', end='', flush=True)

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


