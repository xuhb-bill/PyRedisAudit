import argparse
import sys
from flask import Flask, request, jsonify
from config.config_loader import ConfigLoader
from core.parser import RedisCommandParser
from core.auditor import RedisAuditor
from core.redis_client import RedisClient
import os

app = Flask(__name__)

# Global instances (will be initialized in main)
auditor = None
parser = None

def _resp(code, status, msg, http_status=200):
    return jsonify({"code": code, "status": status, "msg": msg}), http_status

@app.route('/audit', methods=['POST'])
def audit():
    """
    Endpoint to audit Redis commands.
    Expected JSON: 
    { 
        "commands": "SET key val\nGET key",
        "redis_info": { "host": "127.0.0.1", "port": 6379, "password": "..." } # Optional
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return _resp(40001, "failed", "No JSON data provided", 400)

    commands_text = data.get('commands') or data.get('command')
    if not commands_text:
        return _resp(40002, "failed", "No commands provided in 'commands' or 'command' field", 400)

    try:
        check = int(data.get('check', 1))
        execute = int(data.get('execute', 0))
    except Exception:
        return _resp(40003, "failed", "Invalid 'check' or 'execute' value, must be 0 or 1", 400)

    if check not in (0, 1) or execute not in (0, 1):
        return _resp(40003, "failed", "Invalid 'check' or 'execute' value, must be 0 or 1", 400)

    if check == 1:
        execute = 0

    # Optional: Setup Redis connection
    redis_info = data.get('redis_info')
    redis_client = None
    server_version = None
    if execute == 1 and not redis_info:
        return _resp(40004, "failed", "execute=1 requires 'redis_info'", 400)

    if redis_info:
        try:
            redis_client = RedisClient(
                host=redis_info.get('host', '127.0.0.1'),
                port=redis_info.get('port', 6379),
                password=redis_info.get('password'),
                db=redis_info.get('db', 0)
            )
            success, error_msg = redis_client.connect()
            if not success:
                return _resp(
                    40005,
                    "failed",
                    f"Failed to connect to Redis at {redis_client.host}:{redis_client.port}. Reason: {error_msg}",
                    400
                )
            server_version = redis_client.get_server_version()
        except Exception as e:
            return _resp(50001, "failed", f"Error setting up Redis client: {str(e)}", 500)

    try:
        parsed_commands, syntax_results = parser.parse_script_with_syntax(commands_text)

        syntax_failed = next((s for s in syntax_results if s.get('status') != 'passed'), None)
        if syntax_failed is not None:
            order = syntax_failed.get('order')
            msg = syntax_failed.get('message') or 'Syntax error'
            if redis_client:
                redis_client.close()
            return _resp(1001, "failed", f"Syntax error at #{order}: {msg}", 200)

        audit_results = []
        if check == 1 or execute == 1:
            audit_results = auditor.audit_commands(parsed_commands, redis_client=redis_client)

        warn_item = None
        if audit_results:
            error_item = next((r for r in audit_results if r.get('status') == 'failed' and r.get('level') == 'error'), None)
            warn_item = next((r for r in audit_results if r.get('status') == 'failed' and r.get('level') == 'warning'), None)

            if error_item is not None:
                if redis_client:
                    redis_client.close()
                return _resp(2001, "failed", f"Audit error at #{error_item.get('order')}: {error_item.get('message')}", 200)

        if execute == 1:
            for cmd in parsed_commands:
                ok, exec_result = redis_client.execute(cmd.get('tokens'))
                if not ok:
                    if redis_client:
                        redis_client.close()
                    return _resp(3001, "failed", f"Execute failed at #{cmd.get('order')}: {exec_result}", 200)

            if redis_client:
                redis_client.close()
            if warn_item is not None:
                return _resp(2002, "warning", f"Audit warning at #{warn_item.get('order')}: {warn_item.get('message')}", 200)
            return _resp(0, "passed", "OK", 200)

        if redis_client:
            redis_client.close()

        if warn_item is not None:
            return _resp(2002, "warning", f"Audit warning at #{warn_item.get('order')}: {warn_item.get('message')}", 200)
        return _resp(0, "passed", "OK", 200)
    except Exception as e:
        if redis_client:
            redis_client.close()
        return _resp(50002, "failed", str(e), 500)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "target_redis_version": auditor.target_version})

def start_server():
    global auditor, parser
    
    arg_parser = argparse.ArgumentParser(description="PyRedisAudit API Server")
    arg_parser.add_argument(
        '--config', 
        type=str, 
        default=None, 
        help='Path to the configuration YAML file'
    )
    arg_parser.add_argument(
        '--port', 
        type=int, 
        default=5000, 
        help='Port to run the server on'
    )
    arg_parser.add_argument(
        '--host', 
        type=str, 
        default='0.0.0.0', 
        help='Host to bind the server to'
    )
    arg_parser.add_argument(
        '--log-file',
        type=str,
        default=None,
        help='Override log file path'
    )
    arg_parser.add_argument(
        '--log-level',
        type=str,
        default=None,
        help='Override log level (INFO, DEBUG, WARNING, ERROR)'
    )
    
    args = arg_parser.parse_args()

    # Initialize components
    try:
        config_loader = ConfigLoader(args.config)
        if args.log_file is not None:
            config_loader.config.setdefault('global', {})
            config_loader.config['global']['log_file'] = args.log_file
        if args.log_level is not None:
            config_loader.config.setdefault('global', {})
            config_loader.config['global']['log_level'] = args.log_level

        parser = RedisCommandParser()
        auditor = RedisAuditor(config_loader)
        
        print(f"--- PyRedisAudit Server Starting ---")
        print(f"Config: {config_loader.config_path}")
        print(f"Log File: {config_loader.get_log_file()}")
        print(f"Log Level: {config_loader.get_log_level()}")
        print(f"Target Redis Version: {auditor.target_version}")
        print(f"Listening on {args.host}:{args.port}")
        print(f"------------------------------------")
        
        app.run(host=args.host, port=args.port)
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    start_server()
