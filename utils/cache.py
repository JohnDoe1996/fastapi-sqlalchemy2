import abc
import json
import inspect
import asyncio
from functools import wraps
from typing import Optional, Union, Callable, Tuple, List
try:
    from typing import Self             # python3.11+
except:
    from typing_extensions import Self  # Python3.11-
from datetime import timedelta
import redis
try:
    from redis.asyncio import Redis as aioredis  
except ImportError:
    from aioredis import Redis as aioredis  # Python3.11- and use   pip install aioredis


dict_value_disposer = lambda val: json.dumps(val) if isinstance(val, dict) else val
encode_redis_result = lambda res: None if res is None else res.decode()


def run_async(coroutine):
    try:
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(coroutine)
    except RuntimeError:
        result = asyncio.run(coroutine)
    return result
    
   
def cache_by_arg(ts: Optional[Union[timedelta, int, Callable]] = None,
                redis_arg_name: Optional[str] = None, 
                prefix: str = "",
                group_name: Optional[str] = "", 
                *, 
                joint: str = "-",
                use_arg_names: Optional[Tuple[str]] = None, 
                exclude_arg_names: Optional[Tuple[str]] = None, 
                except_with_arg_not_find: bool = False,
                value_disposer: Optional[Callable] = dict_value_disposer, 
                result_disposer: Optional[Callable] = encode_redis_result):
    """
    cache_by_arg 装饰通过参数形式传递Redis的函数,作为该函数的缓存， 

    :param Optional[Union[timedelta, int, Callable]] ts: 缓存时间, int类型时候单位为秒, None 为缓存不会过期， 0 为不缓存, defaults None
    :param Optional[str] redis_arg_name: Redis参数的参数名, None时候自动获取第一个参数类型为 Redis 或者 asyncRedis的参数, defaults to None
    :param str prefix: Redis key 前缀, defaults to ""
    :param Optional[str] group_name: 分组名， 为""时候为不使用分组。 为None时候使用prefix作为分组名, defaults to ""
    :param bool except_with_arg_not_find: 当找不到参数的时候是否报错，为True的时候找不到Redis参数会报错，为False时候找不到参数会不做缓存, defaults to False
    """
    if use_arg_names and exclude_arg_names:
        raise ValueError("use_arg_names / exclude_arg_names cannot be used simultaneously")
    
    prefix = (prefix + joint) if prefix else ""

    def inner(func):
        arg_names = tuple(inspect.signature(func).parameters)  # 参数名列表
        ##  处理函数/方法名作为RedisKey, 为了方便目前为方法使用 类名.方法名 , 函数使用 函数名 作为key的一部分，可能会出现不同文件的相同方法重名的情况，根据项目自行修改
        key_func = func.__qualname__
 
        def args_disposer(*args, **kwargs) -> Optional[Tuple[Union[redis.Redis, aioredis], str]]:
            kw = dict(zip(arg_names, args))
            kw.update(kwargs)
            nonlocal use_arg_names, exclude_arg_names
            use_arg_names = use_arg_names or tuple(kw.keys())
            exclude_arg_names = exclude_arg_names or ()
            _redis = None
            if redis_arg_name:
                _redis = kw.get(redis_arg_name)
                if _redis is None:
                    return None
            res = []
            for k, v in kw.items():
                if _redis is None and isinstance(v, (aioredis, redis.Redis)):
                    _redis = v
                elif k in (use_arg_names) and not k in (exclude_arg_names):
                    res.append(f"{k}:{v}")
            return None if _redis is None else (_redis, joint.join(res))
    
        def set_cache(r, k, v):
            if group_name:
                r.sadd(group_name, k)
            if ts is None:
                r.set(k, v)
            else:
                r.setex(k, ts, v)

        async def async_set_cache(r, k, v):
            if group_name:
                await r.sadd(group_name, k)
            if ts is None:
                await r.set(k, v)
            else:
                await r.setex(k, ts, v)

        @wraps(func)
        def wrapper(*args, **kwargs):
            ad_res = args_disposer(*args, **kwargs)
            if ad_res:
                r, key_args = ad_res
            elif except_with_arg_not_find:
                raise ValueError("no Redis or async Redis in args")
            else: 
                return func(*args, **kwargs)
            key = f"{prefix}{key_func}{joint}{key_args}"
            if isinstance(r, aioredis):
                res = run_async(r.get(key))
                if res is not None:
                    return result_disposer(res)
                res = func(*args, **kwargs)
                run_async(async_set_cache(r, key, value_disposer(res) if value_disposer else res)) 
                return res
            else:
                res = r.get(key)
                if res is not None:
                    return result_disposer(res)
                res = func(*args, **kwargs)
                set_cache(r, key, value_disposer(res) if value_disposer else res)
                return res 
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            ad_res = args_disposer(*args, **kwargs)
            if ad_res:
                r, key_args = ad_res
            elif except_with_arg_not_find:
                raise ValueError("no Redis or async Redis in args")
            else: 
                return await func(*args, **kwargs)
            key = f"{prefix}{key_func}{joint}{key_args}"
            if isinstance(r, aioredis):
                res = await r.get(key)
                if res is not None:
                    return result_disposer(res)
                res = await func(*args, **kwargs)
                await async_set_cache(r, key, value_disposer(res) if value_disposer else res)
                return res
            else:
                res = r.get(key)
                if res is not None:
                    return result_disposer(res)
                res = await func(*args, **kwargs)
                set_cache(r, key, value_disposer(res) if value_disposer else res)
                return res
            
        return async_wrapper if inspect.iscoroutinefunction(func) else wrapper
        
    return inner if not callable(ts) else inner(ts) 
    
    
class Cache:
    
    def __init__(self, r: Union[redis.Redis, aioredis], prefix: str = "", 
                 group_name: Optional[str] = None, *, joint = "-"):
        if isinstance(r, aioredis): 
            self.is_async = True
        elif isinstance(r, redis.Redis):
            self.is_async = isinstance(r, aioredis)
        else:
            ValueError("arg: r   must type of Redis or async Redis")
        self.r = r
        self.prefix = (prefix + joint) if prefix else ""
        if group_name is None:
            self.group_name = group_name
        elif prefix:
            self.group_name = prefix
        else:
            self.group_name = "default_cache_group"
        self.joint = joint 
        
    def __getitem__(self, name: str) -> Self:
        return self.__class__(self.r, f"{self.prefix}{name}", joint=self.joint)

    def __call__(self, ts: Optional[Union[int, timedelta, Callable]] = None, *,
                 use_arg_names: Optional[Tuple[str]] = None, 
                 exclude_arg_names: Optional[Tuple[str]] = None,
                 value_disposer: Optional[Callable] = dict_value_disposer, 
                 result_disposer: Optional[Callable] =  encode_redis_result, 
                 ) -> Callable:
        
        def inner_call(func: Callable):
            arg_names = tuple(inspect.signature(func).parameters)
            key_func = self.func_disposer(func)
            
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                key_args = self.args_disposer(
                    arg_names, use_arg_names, exclude_arg_names, *args, **kwargs)
                key = f"{key_func}{self.joint}{key_args}"
                if self.is_async:
                    res = await self.async_get_cache(key, result_disposer)
                    if res is None:
                        res = await func(*args, **kwargs)
                        await self.async_set_cache(key, res, ts, value_disposer)
                else:
                    res = self.get_cache(key, result_disposer)
                    if res is None:
                        res = await func(*args, **kwargs)
                        self.set_cache(key, res, ts, value_disposer)
                return res 
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                key_args = self.args_disposer(
                    arg_names, use_arg_names, exclude_arg_names, *args, **kwargs)
                key = f"{key_func}{self.joint}{key_args}"
                if self.is_async:
                    res = run_async(self.async_get_cache(key, result_disposer))
                    if res is None:
                        res = func(*args, **kwargs)
                        run_async(self.async_set_cache(key, ts, value_disposer))
                else:
                    res = self.get_cache(key, result_disposer)
                    if res is None:
                        res = func(*args, **kwargs)
                        self.set_cache(key, res, ts, value_disposer)
                return res
            
            return async_wrapper if inspect.iscoroutinefunction(func) else wrapper
        
        return inner_call if not callable(ts) else inner_call(ts)
    
    def func_disposer(self, func: Callable) -> str:
        """
        func_disposer 通过方法/函数获取 缓存唯一key
        这里为了简单和容易在redis中查询, ismethod时候使用 类名.方法名 作为key ; isfunction时候使用 函数名 作为key。
        这样处理可能会出现不同文件有相同名称的函数、类名时候出现相同key的情况。出现这样的情况可以考虑解决办法:
        1 使用prefix或['...']方式添加前缀区分  2 重写本方法添加模块名文件名等作为key的一部分以满足不同需求
        """
        return func.__qualname__
        
    def args_disposer(self, arg_names: tuple, use_arg_names: Optional[Tuple[str]] = None, 
                      exclude_arg_names: Optional[Tuple] = None , *args, **kwargs) -> str:
        if use_arg_names and exclude_arg_names:
            raise ValueError("use_arg_names / exclude_arg_names cannot be used simultaneously")
        kw = dict(zip(arg_names, args))
        kw.update(kwargs)
        use_arg_names = use_arg_names or tuple(kw.keys())
        exclude_arg_names = exclude_arg_names or ()
        res = []
        for k, v in kw.items():
            if k in use_arg_names and k not in exclude_arg_names:
                res.append(f"{k}:{v}")
        return self.joint.join(res)
    
    def prefix_key(self, key:str):
        """
        prefix_key 用作统一处理prefix和key的拼接， 需要修改拼接规则只需要修改本函数
        """
        return f"{self.prefix}{key}"
    
    def get_cache(self, key:str, result_disposer: Optional[Callable] = encode_redis_result) -> str:
        if self.is_async:
           TypeError("redis is async Redis, please usd .async_get_cache()")
        _key = self.prefix_key(key)
        result = self.r.get(_key)
        if result_disposer:
            return result_disposer(result)
        return result 
        
    async def async_get_cache(self, key:str, result_disposer: Optional[Callable] = encode_redis_result) -> str:
        if not self.is_async:
            TypeError("redis is sync Redis, please usd .get_cache()")
        _key = self.prefix_key(key)
        result = await self.r.get(_key)
        if result_disposer:
            return result_disposer(result)
        return result 
    
    def delete_cache(self, key:str):
        if self.is_async:
            TypeError("redis is async Redis, please usd .async_delete_cache()")
        _key = self.prefix_key(key)
        self.r.delete(_key)
        if self.group_name is not None:
            self.r.srem(self.group_name, _key)

    async def async_delete_cache(self, key:str) -> Optional[Exception]:
        if not self.is_async:
            TypeError("redis is sync Redis, please usd .delete_cache()")
        _key = self.prefix_key(key)
        await self.r.delete(_key)
        if self.group_name is not None:
            await self.r.srem(self.group_name, _key)

    def set_cache(self, key:str, value:str, ts: Optional[Union[int, timedelta]] = None, 
                  value_disposer: Optional[Callable] = dict_value_disposer) -> Optional[Exception]:
        if self.is_async:
            TypeError("redis is async Redis, please usd .async_set_cache()")
        _key = self.prefix_key(key)
        if self.group_name is not None:
            self.r.sadd(self.group_name, _key)
        if value_disposer:
            value = value_disposer(value)
        if ts is None:
            self.r.set(_key, value)
        else:
            self.r.setex(_key, ts, value)

    async def async_set_cache(self, key:str, value:str, ts: Union[int, timedelta] = None, 
                              value_disposer: Optional[Callable] = dict_value_disposer) -> Optional[Exception]:
        if not self.is_async:
            TypeError("redis is sync Redis, please use .set_cache()")
        _key = self.prefix_key(key)
        if self.group_name is not None:
            await self.r.sadd(self.group_name, _key)
        if value_disposer:
            value = value_disposer(value)
        if ts is None:
            await self.r.set(_key, value)
        else:
            await self.r.setex(_key, ts, value)
    
    def clean_group(self):
        if self.group_name is None:  # if not use group， nothing to do
            return
        if self.is_async:
            TypeError("redis is async Redis, please use .async_clean_cache()")
        keys = self.r.smembers(self.group_name)
        if keys:
            self.r.delete(*keys)
            self.r.srem(self.group_name, *keys)
            
    async def async_clean_group(self):
        if self.group_name is None: # if not use group, nothing to do
            return
        if not self.is_async:
            TypeError("redis is async Redis, please usd .clean_group()")
        keys = await self.r.smembers(self.group_name)
        if keys:
            await self.r.delete(*keys)
            await self.r.srem(self.group_name, *keys)

    def list_group(self) -> List[str]:
        if self.group_name is None:  #  if not use group, return void list
            return []
        if self.is_async:
            TypeError("redis is async Redis, please usd .async_list_group()")
        keys = self.r.smembers(self.group_name) 
        return [str(key) for key in keys]

    async def async_list_group(self) -> List[str]:
        if self.group_name is None:  # if not use group, return void list
            return []
        if not self.is_async:
            TypeError("redis is async Redis, please usd .list_group()")
        keys = await self.r.smembers(self.group_name) 
        return [str(key) for key in keys]
    
    
# simple test
if __name__ == "__main__" and __debug__:
    import time
    from redis import from_url
    from redis.asyncio import from_url as async_from_url
    
    r_url = "redis://127.0.0.1:7379"
    test_redis = from_url(r_url)
    test_async_redis = async_from_url(r_url)
    
    cache = Cache(test_redis, "cache_test", "cache_test_group")
    async_cache = Cache(test_async_redis, "async_cache_test", "async_cache_test_group")
    
    @cache(5, exclude_arg_names=("c",))
    def test_cache(a, b, c):
        print("no cache:", end=" ")
        return a + b + c
    
    @async_cache(5, exclude_arg_names=("c",))
    async def async_test_cache(a, b, c):
        print("no cache:", end=" ")
        return a + b + c
    
    @cache_by_arg(5, exclude_arg_names=("c",), prefix="cache_test_arg")
    def test_cache_arg(rr, a, b, c):
        print("no cache:", end=" ")
        return a + b + c
    
    @cache_by_arg(5, exclude_arg_names=("c",), prefix="cache_test_arg")
    async def async_test_cache_arg(rr, a, b, c):
        print("no cache:", end=" ")
        return a + b + c
    
    
    print("===== test func =====")
    print(test_cache(1, b=2, c=3))  # no cache: 6
    print(test_cache(1, b=2, c=0))  # 6
    time.sleep(6)
    print(test_cache(1, b=2, c=0))  # no cache: 3
    _key = cache.func_disposer(test_cache) + cache.joint + "a:1" + cache.joint + "b:2" 
    cache.delete_cache(_key)
    print(test_cache(1, b=2, c=3))  # no cache: 6
    cache.clean_group()
    
    print("===== test async func =====")
    print(run_async(async_test_cache(1, b=2, c=3))) # no cache: 6
    print(run_async(async_test_cache(1, b=2, c=0))) # 6
    time.sleep(6)
    print(run_async(async_test_cache(1, b=2, c=0))) # no cache: 3
    _key = async_cache.func_disposer(async_test_cache) + cache.joint + "a:1" + cache.joint + "b:2" 
    run_async(async_cache.async_delete_cache(_key))
    print(run_async(async_test_cache(1, b=2, c=3))) # no cache: 6
    run_async(async_cache.async_clean_group())
    
    print("===== test arg =====")
    print(test_cache_arg(test_redis, 1, b=2, c=3))  # no cache: 6
    print(test_cache_arg(test_redis, 1, b=2, c=0))  # 6
    time.sleep(6)
    print(test_cache_arg(test_redis, 1, b=2, c=0))  # no cache: 3
    
    print("===== test async arg =====")
    print(run_async(async_test_cache_arg(test_redis, 1, b=2, c=3)))  # no cache: 6
    print(run_async(async_test_cache_arg(test_redis, 1, b=2, c=0)))  # 6
    time.sleep(6)
    print(run_async(async_test_cache_arg(test_redis, 1, b=2, c=0)))  # no cache: 3
    
    