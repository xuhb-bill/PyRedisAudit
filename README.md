# PyRedisAudit (Redis 命令审计系统)

这是一个受 `goInception` 启发的 Python 项目，旨在对 Redis 命令进行静态审计。它可以识别不兼容的版本命令、高风险操作、命名规范冲突以及性能隐患。

## 核心特性

- **版本兼容性检查**：根据配置的目标 Redis 版本，自动识别不支持的命令或参数。
- **高风险命令拦截**：拦截如 `FLUSHALL`, `KEYS *` 等可能导致生产事故的命令。
- **命名规范校验**：通过正则表达式强制执行 Key 的命名约定。
- **性能风险评估**：例如强制要求写操作（如 `SET`）必须带有 TTL。
- **高度可配置**：支持通过 YAML 文件调整所有规则的开关、错误等级及参数。
- **Web API 接口**：提供 HTTP 接口，支持通过接口提交命令并返回审计结果。
- **日志记录**：支持日志分级记录及滚动保存。

## 项目结构

- `app.py`: Web API 服务入口。
- `config/`: 配置文件及加载逻辑。
- `core/`: 审计引擎、解析器、日志系统等核心组件。
- `rules/`: 具体审计规则实现。
- `data/`: Redis 命令版本元数据。
- `logs/`: 运行日志存放目录。

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 启动服务
你可以通过命令行参数指定配置文件、主机和端口：
```bash
python3 app.py --config config/default_config.yaml --port 5000 --host 0.0.0.0
```

你也可以在启动时覆盖日志路径与日志等级（优先级高于配置文件）：
```bash
python3 app.py --config config/default_config.yaml --port 5000 \
  --log-file /var/log/pyredisaudit/audit.log --log-level INFO
```

或者使用项目自带脚本启动/停止（适合后台运行）：

启动：
```bash
./startup.sh
```

停止：
```bash
./stop.sh
```

脚本支持通过环境变量覆盖启动参数：
```bash
CONFIG_FILE=/path/to/config.yaml \
HOST=0.0.0.0 \
PORT=5000 \
LOG_FILE=/var/log/pyredisaudit/audit.log \
LOG_LEVEL=INFO \
./startup.sh
```

脚本默认行为：
- PID 文件：`run/pyredisaudit.pid`
- stdout 日志：`logs/stdout.log`

### 3. 使用接口进行审计
发送 POST 请求到 `/audit` 接口，提交需要审计的命令：

请求字段说明：
- `command` 或 `commands`：单条命令或多条命令（用 `\n` 分隔）
- `check`：是否开启审计与语法检查，默认 `1`；当 `check=1` 时，`execute` 不生效
- `execute`：是否执行命令，默认 `0`（仅当 `check=0` 且 `execute=1` 时执行；开启执行必须提供 `redis_info`）
- `redis_info`：Redis 连接信息（执行或需要实时检查时传入）

**请求示例 (Single Command):**
```bash
curl -X POST http://127.0.0.1:5000/audit \
     -H "Content-Type: application/json" \
     -d '{"command": "set dba-test 12345", "check": 1, "execute": 0}'
```

**请求示例 (Multiple Commands):**
```bash
curl -X POST http://127.0.0.1:5000/audit \
     -H "Content-Type: application/json" \
     -d '{"commands": "SET key val\nFLUSHALL", "check": 1, "execute": 0}'
```

**请求示例 (Dynamic Audit with Redis Connection):**
```bash
curl -X POST http://127.0.0.1:5000/audit \
     -H "Content-Type: application/json" \
     -d '{
          "command": "SET app:test:key \"value\" EX 3600",
          "check": 1,
          "execute": 0,
           "redis_info": {
             "host": "127.0.0.1",
             "port": 6379,
             "password": "your_password",
             "db": 0
           }
         }'
```
*如果提供了 `redis_info`，程序将：*
1. *自动获取该 Redis 实例的真实版本号进行兼容性检查。*
2. *启用需要实时连接的规则（如 `check_overwrite`：检查 Key 是否已存在）。*

**请求示例 (Execute):**
```bash
curl -X POST http://127.0.0.1:5000/audit \
     -H "Content-Type: application/json" \
     -d '{
           "command": "SET app:test:key \"value\" EX 3600",
           "check": 1,
           "execute": 1,
           "redis_info": {
             "host": "127.0.0.1",
             "port": 6379,
             "password": "your_password",
             "db": 0
           }
         }'
```

**响应示例:**
```json
{
  "check": 1,
  "execute": 0,
  "target_redis_version": "6.0",
  "results": [
    {
      "order": 1,
      "command": "SET dba-test 12345",
      "syntax": { "status": "passed", "message": "Syntax OK", "level": "info" },
      "audit": {
        "status": "failed",
        "message": "Write command 'SET' is missing TTL (EX/PX)",
        "level": "warning"
      }
    }
  ]
}
```

## 打包为可执行文件 (Executable)

如果你希望将程序打包成独立的可执行文件，可以使用 `PyInstaller`：

1. 安装 PyInstaller:
   ```bash
   pip install pyinstaller
   ```

2. 执行打包命令：
   ```bash
   pyinstaller --onefile --add-data "config:config" --add-data "data:data" app.py
   ```
   *注意：打包后，你需要确保 `config` 和 `data` 目录在可执行文件的相对路径下，或者在启动时通过 `--config` 指定外部配置。*
