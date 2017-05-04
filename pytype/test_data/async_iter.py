# Tests python 3.5 opcodes
#   GET_AITER
#   GET_ANEXT
#   GET_AWAITABLE
#   YIELD_FROM
import asyncio

class AsyncIterable:
  def __aiter__(self):
    return self

  async def __anext__(self):
    data = await self.fetch_data()
    if data:
      return data
    else:
      raise StopAsyncIteration

  async def fetch_data(self):
    pass


async def iterate(x):
  async for i in x:
    pass
  else:
    pass

iterate(AsyncIterable())
