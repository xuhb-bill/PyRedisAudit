import json
import sys
import os

# 将项目目录加入 sys.path 以便导入
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from config.config_loader import ConfigLoader
from core.parser import RedisCommandParser
from core.auditor import RedisAuditor

def audit_single_command(cmd_text):
    # 1. 加载配置
    config_loader = ConfigLoader()
    
    # 2. 初始化解析器和审计引擎
    parser = RedisCommandParser()
    auditor = RedisAuditor(config_loader)
    
    # 3. 解析命令
    parsed_cmd = parser.parse_line(cmd_text)
    if not parsed_cmd:
        print("Invalid command format.")
        return

    # 4. 执行审计
    result = auditor.audit_commands([parsed_cmd])
    
    # 5. 输出结果
    print(f"Audit Result for: {cmd_text}")
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    test_command = "set dba-test 12345"
    audit_single_command(test_command)
