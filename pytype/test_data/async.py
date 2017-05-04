# Tests python 3.5 opcodes
#   BEFORE_ASYNC_WITH
#   GET_AWAITABLE
#   SETUP_ASYNC_WITH
#   WITH_CLEANUP_FINISH
#   WITH_CLEANUP_START
#   YIELD_FROM

import asyncio

class AsyncContextManager:
  async def __aenter__(self):
    await log('entering context')

  async def __aexit__(self, exc_type, exc, tb):
    await log('exiting context')

async def my_coroutine(seconds_to_sleep=0.4):
    await asyncio.sleep(seconds_to_sleep)


async def test_with(x):
  try:
    async with x as y:
      pass
  finally:
    pass


event_loop = asyncio.get_event_loop()
try:
  event_loop.run_until_complete(my_coroutine())
finally:
  event_loop.close()
