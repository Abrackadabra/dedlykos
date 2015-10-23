import asyncio
from cloudbot import hook
from cloudbot.event import EventType

BLACK_CHANS = [
  '##werewolf',
  # '#abrtst',
]


@asyncio.coroutine
@hook.sieve(priority=-1)
def ignore_sieve(bot, event, _hook):
  if (event.type == EventType.message or event.type == EventType.action) and \
          event.chan in BLACK_CHANS:
    return None

  return event
