import json
from config.config_loader import ConfigLoader
from core.parser import RedisCommandParser
from core.auditor import RedisAuditor

def main():
    # 1. Load Configuration
    config_loader = ConfigLoader()
    
    # 2. Initialize Parser and Auditor
    parser = RedisCommandParser()
    auditor = RedisAuditor(config_loader)
    
    # 3. Sample script to audit
    script = """
    # Normal commands
    SET user:1001 "John Doe" EX 3600
    GET user:1001
    
    # High-risk command (forbidden in config)
    FLUSHALL
    
    # Version compatibility issue (GET parameter for SET introduced in 6.2)
    # Target version is 6.0 in default_config.yaml
    SET user:1002 "Jane Doe" GET
    
    # Key naming violation (forbidden characters)
    SET user@1003 "Invalid Key"
    
    # TTL requirement violation (SET needs EX/PX)
    SET user:1004 "No TTL"
    
    # New command check (ZPOPMAX introduced in 5.0, COPY in 6.2)
    ZPOPMAX myzset
    COPY key1 key2
    """
    
    print(f"--- PyRedisAudit Starting ---")
    print(f"Target Redis Version: {config_loader.get_target_redis_version()}")
    print(f"-----------------------------\n")
    
    # 4. Parse and Audit
    parsed_commands = parser.parse_script(script)
    results = auditor.audit_commands(parsed_commands)
    
    # 5. Output results
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
