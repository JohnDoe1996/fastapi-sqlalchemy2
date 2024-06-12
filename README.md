本项目为 https://github.com/JohnDoe1996/fastAPI-vue 的新后端 使用 新的sqlalchemy2.0+ 的接口并全部使用异步的方式实现增删改查 提高并发。 使用新的fastAPI 和 新的 pydantic。 可以配合配合上述项目的前端代码一起服用。

因为整一次更新代码比较多 目前版本代码没有长时间测试运行，不能保证100%稳定（例如漏了 await 或者 查询sqlalchemy模型时候漏了 selectquery 等），欢迎提出问题，我这边会持续测试和修复问题。https://github.com/JohnDoe1996/fastAPI-vue 的README里面有我的联系方式, 后续稳定后会整合起起来。 

代码尽可能兼容较低版本的python 所有很多地方没有使用最新 python3.10+ 的语法  如多种类型标准 使用 | 等。 

-- 2024.06.05