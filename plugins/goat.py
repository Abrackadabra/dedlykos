import asyncio
from collections import defaultdict
import random
import re
from datetime import datetime, timedelta

from cloudbot import hook
from cloudbot.event import EventType


@asyncio.coroutine
@hook.sieve(priority=200)
def goat_sieve(bot, event, _hook):
  if event.type == EventType.message and _hook.description == 'log:log_raw':
    asyncio.ensure_future(goat_process(bot, event.conn, event), loop=bot.loop)

  return event


@asyncio.coroutine
def goat_process(bot, conn, event):
  chan = event.chan
  if not chan.startswith('#'):
    return

  nick = event.nick
  text = event.irc_paramlist[1][1:]
  priv = event.mask in conn.permissions.perm_users['botcontrol']
  parts = text.split()
  reg = conn.registry

  if parts[0] in ('!goat', '!fgoat') and len(parts) > 1:
    if not conn.memory.get('last_goated'):
      conn.memory['last_goated'] = defaultdict(lambda: 0)

    last_goated = conn.memory.get('last_goated')
    force = '!f' in parts[0]

    time = last_goated[nick]

    target = parts[1]

    if force and not priv or \
        (not priv and datetime.now() - datetime.fromtimestamp(time) < timedelta(minutes=5)) or \
            nick == target or target == conn.nick:
      conn.message(chan, '{}: nu'.format(nick))
      return

    dude = reg.get_dude(target)
    if dude and dude in reg.chan(chan):
      action = random.choice(('headbutts', 'kicks', 'rams into', 'noms', 'murders', 'disapproves'))
      if force:
        message = '\u0002{}\u0002\'s goat walks by and \u0002forcefully\u0002 {} ' \
                  '\u0002{}\u0002.'.format(nick, action, target)
      else:
        message = '\u0002{}\u0002\'s goat walks by and {} \u0002{}\u0002.' \
          .format(nick, action, target)

      conn.message(chan, message)

      last_goated[nick] = datetime.now().timestamp()
    else:
      event.message(chan, '{}: Who?'.format(nick))
