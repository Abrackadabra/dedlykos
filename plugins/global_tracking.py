import asyncio
import re

from cloudbot import hook


class Dude(object):
  """
  :type nick: str
  :type username: str
  :type host: str
  :type account: str
  :type prefix: str
  """

  def __init__(self, nick, username, host, account, prefix):
    self.nick = nick
    self.username = username
    self.host = host
    self.account = account
    self.prefix = prefix

  def __repr__(self):
    return '{}{}!{}@{} as {}'.format(self.prefix, self.nick, self.username, self.host, self.account)

  def __eq__(self, other):
    return self.nick == other.nick and self.username == other.username and \
           self.host == other.host and self.account == other.account

  def __hash__(self):
    return hash(self.nick) + hash(self.account)

  @staticmethod
  def from_repr(s):
    match = re.findall(r'([@+]+)([^!]*)!([^@]*)@([^ ]*) as (.*)', s)
    if match:
      prefix, nick, username, host, account = match[0]
      dude = Dude(nick, username, host, account, prefix)
      return dude

  def prefix_in_chan(self, s):
    for i in s:
      if self == i:
        return i.prefix


class Registry(object):
  """
  :type chans: dict[str, set[Dude]]
  :type modes: dict[str, set[str]]
  :type change_callbacks: list[function]
  """

  def __init__(self):
    self.chans = {}
    self.modes = {}
    self.change_callbacks = []

  def process_who(self, conn, chan, who):
    self.chans[chan] = set(who)

  def process_join(self, conn, chan, dude):
    if chan not in self.chans:
      return

    self.chans[chan].add(dude)

  def process_part(self, conn, chan, dude):
    if chan not in self.chans:
      return

    self.chans[chan].remove(dude)

  def process_self_part(self, conn, chan):
    if chan in self.chans:
      del self.chans[chan]

  def get_dude(self, nick):
    """
    :type nick: str
    :returns Dude
    """
    for i in self.chans.values():
      for j in i:
        if j.nick == nick:
          return j

  def process_quit(self, conn, nick):
    dude = self.get_dude(nick)
    if dude:
      for i, j in self.chans.items():
        if dude in j:
          j.remove(dude)

  def chan(self, chan):
    """
    :rtype: set[Dude]
    """
    if chan in self.chans:
      return set(self.chans[chan])

  def mode(self, chan):
    """
    :rtype: set[str]
    """
    if chan in self.modes:
      return set(self.modes[chan])

  def process_nick(self, conn, old, new):
    dude = self.get_dude(old)
    if dude:
      new_dude = Dude(new, dude.username, dude.host, dude.account, dude.prefix)
      for i in self.chans.values():
        if dude in i:
          i.remove(dude)
          i.add(new_dude)

  def process_mode(self, conn, chan, mode):
    self.modes[chan] = set()

    self.process_mode_change(conn, chan, [mode])

  def process_mode_change(self, conn, chan, mode):
    a = []
    plus = True
    j = 0
    for i in mode[0]:
      if i == '+':
        plus = True
      elif i == '-':
        plus = False
      elif i in 'oqbv':
        j += 1
        a.append([chan, '{}{}'.format('+' if plus else '-', i), mode[j]])
      elif i in 'ciCgtnjm':
        a.append([chan, '{}{}'.format('+' if plus else '-', i), None])

    for i in a:
      if not i[2]:
        chan = i[0]
        ch = i[1]
        if ch[0] == '+':
          self.modes[chan].add(ch[1])
        else:
          self.modes[chan].remove(ch[1])


@asyncio.coroutine
def delayed_coro(delay, coro):
  yield from asyncio.sleep(delay)
  yield from coro


def init_locks(conn):
  if not hasattr(conn, 'who_lock'):
    conn.who_lock = asyncio.Lock()
  if not hasattr(conn, 'whois_lock'):
    conn.whois_lock = asyncio.Lock()
  if not hasattr(conn, 'mode_lock'):
    conn.mode_lock = asyncio.Lock()


@asyncio.coroutine
def get_who(conn, chan):
  init_locks(conn)

  spec = '%chnufa'

  with (yield from conn.who_lock):
    conn.who_queue = asyncio.Queue()
    conn.who_chan = chan

    a = []

    conn.send("WHO {} {}".format(chan, spec))
    while True:
      item = yield from conn.who_queue.get()
      if not item:
        break

      if item.nick == conn.nick:
        continue

      a.append(item)

  return a


@asyncio.coroutine
@hook.irc_raw("354")
def who_item(conn, event, bot):
  init_locks(conn)
  chan, username, host, nick, prefix, account = event.irc_paramlist[1:]

  if not conn.who_lock.locked() or conn.who_chan != chan:
    bot.logger.warning('unexpected who item {}'.format(event.irc_paramlist))
    return

  if '+' in prefix:
    prefix = '+'
  elif '@' in prefix:
    prefix = '@'
  else:
    prefix = ''

  if account == '0':
    account = ''

  yield from conn.who_queue.put(Dude(nick, username, host, account, prefix))


@asyncio.coroutine
@hook.irc_raw("315")
def who_end(bot, conn, event):
  init_locks(conn)
  chan = event.irc_paramlist[1]
  if not conn.who_lock.locked() or conn.who_chan != chan:
    bot.logger.warning('unexpected who end {}'.format(event.irc_paramlist))
    return

  yield from conn.who_queue.put(None)


@asyncio.coroutine
def get_whois(conn, nick):
  init_locks(conn)
  with (yield from conn.whois_lock):
    conn.whois_queue = asyncio.Queue()
    conn.whois_nick = nick

    conn.send("WHOIS {}".format(nick))

    a = []
    for i in range(4):
      x = yield from conn.whois_queue.get()
      if not x:
        break
      a.append(x)

  if len(a) != 3 and len(a) != 4:
    return

  nick, username, host = a[:3]

  account = a[3] if len(a) == 4 else None

  dude = Dude(nick, username, host, account, '')

  return dude


@asyncio.coroutine
@hook.irc_raw("311")
def whois_item(conn, event, bot):
  init_locks(conn)
  nick, username, host = event.irc_paramlist[1:4]

  if not conn.whois_lock.locked() or conn.whois_nick != nick:
    bot.logger.warning('unexpected whois item {}'.format(event.irc_paramlist))
    return

  yield from conn.whois_queue.put(nick)
  yield from conn.whois_queue.put(username)
  yield from conn.whois_queue.put(host)


@asyncio.coroutine
@hook.irc_raw("330")
def whois_acc(conn, event, bot):
  init_locks(conn)
  nick, account = event.irc_paramlist[1:3]

  if not conn.whois_lock.locked() or conn.whois_nick != nick:
    bot.logger.warning('unexpected whois item {}'.format(event.irc_paramlist))
    return

  yield from conn.whois_queue.put(account)


@asyncio.coroutine
@hook.irc_raw("318")
def whois_end(conn, event, bot):
  init_locks(conn)
  nick = event.irc_paramlist[1]

  if not conn.whois_lock.locked() or conn.whois_nick != nick:
    bot.logger.warning('unexpected whois end {}'.format(event.irc_paramlist))
    return

  yield from conn.whois_queue.put(None)


@asyncio.coroutine
def get_mode(conn, chan):
  init_locks(conn)
  with (yield from conn.mode_lock):
    conn.mode_queue = asyncio.Queue()
    conn.mode_chan = chan

    conn.send("MODE {}".format(chan))

    mode = yield from conn.mode_queue.get()
    return mode


@asyncio.coroutine
@hook.irc_raw("324")
def mode_item(bot, conn, chan, event):
  init_locks(conn)

  chan = event.irc_paramlist[1]

  if not conn.mode_lock.locked() or conn.mode_chan != chan:
    bot.logger.warning('unexpected mode item {}'.format(event.irc_paramlist))
    return

  yield from conn.mode_queue.put(event.irc_paramlist[2])


@asyncio.coroutine
@hook.irc_raw("PART")
def tracking_on_part(event, chan, nick, conn, db):
  if nick and chan:
    if nick == conn.nick:
      conn.registry.process_self_part(conn, chan)
    else:
      dude = conn.registry.get_dude(nick)

      conn.registry.process_part(conn, chan, dude)


@asyncio.coroutine
@hook.irc_raw("KICK")
def tracking_on_kick(event, chan, nick, conn, db):
  nick = event.irc_paramlist[1]
  if nick and chan:
    if nick == conn.nick:
      conn.registry.process_self_part(conn, chan)
    else:
      dude = conn.registry.get_dude(nick)

      conn.registry.process_part(conn, chan, dude)


@asyncio.coroutine
@hook.irc_raw("JOIN")
def tracking_on_join(event, chan, nick, conn, db):
  if not hasattr(conn, 'registry'):
    conn.registry = Registry()

  if not chan:
    chan = event.irc_paramlist[0][1:]

  if nick == conn.nick:
    who = yield from get_who(conn, chan)
    conn.registry.process_who(conn, chan, who)

    mode = yield from get_mode(conn, chan)
    conn.registry.process_mode(conn, chan, mode)
  else:
    dude = yield from get_whois(conn, nick)
    conn.registry.process_join(conn, chan, dude)


@asyncio.coroutine
@hook.irc_raw("QUIT")
def tracking_on_quit(event, nick, conn, db):
  if nick:
    if nick != conn.nick:
      conn.registry.process_quit(conn, nick)


@asyncio.coroutine
@hook.irc_raw("NICK")
def tracking_on_nick(event, chan, nick, conn, db):
  old_nick = nick
  new_nick = event.irc_paramlist[0][1:]
  conn.registry.process_nick(conn, old_nick, new_nick)


@asyncio.coroutine
@hook.irc_raw("MODE")
def tracking_on_mode(event, chan, nick, conn, db):
  if not chan.startswith('#'):
    return
  conn.registry.process_mode_change(conn, chan, event.irc_paramlist[1:])

  who = yield from get_who(conn, chan)
  conn.registry.process_who(conn, chan, who)


@asyncio.coroutine
@hook.command(permissions=['botcontrol'])
def show_tracking(conn, chan, event, bot, nick, reply, db, loop, text):
  return '{}'.format(conn.registry.chan(text))


@asyncio.coroutine
@hook.command(permissions=['botcontrol'])
def show_mode(conn, chan, event, bot, nick, reply, db, loop, text):
  return '{}'.format(conn.registry.mode(text))


@asyncio.coroutine
@hook.command(permissions=['botcontrol'])
def z(conn, chan, event, bot, nick, reply, db, loop, text):
  x = yield from get_mode(conn, chan)
  return '{}'.format(x)

@asyncio.coroutine
@hook.command(permissions=['botcontrol'])
def s(conn, chan, event, bot, nick, reply, db, loop, text):
  conn.message('##abra', '{}  : {}'.format('##werewolf', conn.registry.chan('##werewolf')))
  conn.message('##abra', '{}M : {}'.format('##werewolf', conn.registry.mode('##werewolf')))
  conn.message('##abra', '{} : {}'.format('##werewolf-ded', conn.registry.chan('##werewolf-ded')))
  conn.message('##abra', '{}M: {}'.format('##werewolf-ded', conn.registry.mode('##werewolf-ded')))
