## 1. Setup

- [x] 1.1 创建项目骨架（pyproject.toml、包结构、__init__.py）
- [x] 1.2 配置 pytest 测试环境
- [x] 1.3 定义项目constants（页大小 4096、magic bytes、版本号）

## 2. Type System

- [x] 2.1 实现 DataType 枚举（INTEGER、FLOAT、TEXT、BOOLEAN）
- [x] 2.2 实现 ColumnDef 数据类（name、type、nullable、constraints）
- [x] 2.3 实现类型检查与隐式转换逻辑（validate/convert）
- [x] 2.4 实现 Value 包装类（含 None/NULL 表示）
- [x] 2.5 编写 type-system 单元测试

## 3. File Format

- [x] 3.1 实现 FileHeader 结构（magic、version、page_size 等）
- [x] 3.2 实现 serialize/deserialize 方法
- [x] 3.3 实现 Database.open(path) — 创建新库/打开已有库
- [x] 3.4 实现 Database.close() — 刷盘并关闭文件
- [x] 3.5 实现完整性校验（checksum 验证）
- [x] 3.6 编写 file-format 单元测试

## 4. Page Storage

- [x] 4.1 实现 Page 类（page_id、data、dirty 标志）
- [x] 4.2 实现 PageAllocator（空闲链表管理）
- [x] 4.3 实现 read_page / write_page 基本操作
- [x] 4.4 编写 page-storage 单元测试

## 5. Buffer Pool

- [x] 5.1 实现 LRU 缓存数据结构（OrderedDict 或双向链表+哈希表）
- [x] 5.2 实现 BufferPool.get_page(page_id) — 缓存命中/缺页处理
- [x] 5.3 实现 BufferPool.flush() — 脏页刷盘
- [x] 5.4 实现 pin/unpin 接口
- [x] 5.5 编写 buffer-pool 单元测试

## 6. Row Format

- [x] 6.1 实现 NULL 位图编码/解码
- [x] 6.2 实现行序列化（serialize_row）
- [x] 6.3 实现行反序列化（deserialize_row）
- [x] 6.4 编写 row-format 单元测试

## 7. Integration

- [x] 7.1 集成所有模块，实现端到端读写
- [x] 7.2 编写集成测试（创建表、插入行、读取行）
- [x] 7.3 编写 README 文档说明模块 API
