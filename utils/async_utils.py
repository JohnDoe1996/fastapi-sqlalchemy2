import asyncio
import functools


def run_async(coroutine):
    """
    run_async 异步运行
    """
    try:
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(coroutine)
    except RuntimeError as e:
        try:
            result = asyncio.run(coroutine)
        except RuntimeError:
            raise e
    return result


def async2sync(func):
    
    @functools.wraps(func)    
    def inner(*args, **kwargs):
        return run_async(func(*args, **kwargs))
    
    return inner