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
        return jsonify({"error": "No JSON data provided"}), 400

    commands_text = data.get('commands') or data.get('command')
    if not commands_text:
        return jsonify({"error": "No commands provided in 'commands' or 'command' field"}), 400

    try:
        check = int(data.get('check', 1))
        execute = int(data.get('execute', 0))
    except Exception:
        return jsonify({"error": "Invalid 'check' or 'execute' value, must be 0 or 1"}), 400

    if check not in (0, 1) or execute not in (0, 1):
        return jsonify({"error": "Invalid 'check' or 'execute' value, must be 0 or 1"}), 400

    if check == 1:
        execute = 0

    # Optional: Setup Redis connection
    redis_info = data.get('redis_info')
    redis_client = None
    server_version = None
    if execute == 1 and not redis_info:
        return jsonify({"error": "execute=1 requires 'redis_info'"}), 400

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
                return jsonify({"error": f"Failed to connect to Redis at {redis_client.host}:{redis_client.port}. Reason: {error_msg}"}), 400
            server_version = redis_client.get_server_version()
        except Exception as e:
            return jsonify({"error": f"Error setting up Redis client: {str(e)}"}), 500

    try:
        parsed_commands, syntax_results = parser.parse_script_with_syntax(commands_text)

        parsed_by_order = {c.get('order'): c for c in parsed_commands}
        audit_results = None
        audit_by_order = {}
        if check == 1 or execute == 1:
            audit_results = auditor.audit_commands(parsed_commands, redis_client=redis_client)
            audit_by_order = {r.get('order'): r for r in audit_results}

        results = []
        for s in syntax_results:
            order = s.get('order')
            entry = {
                'order': order,
                'command': s.get('command'),
                'syntax': {
                    'status': s.get('status'),
                    'message': s.get('message'),
                    'level': s.get('level')
                }
            }

            if s.get('status') == 'passed' and (check == 1 or execute == 1):
                a = audit_by_order.get(order)
                if a:
                    entry['audit'] = {
                        'status': a.get('status'),
                        'message': a.get('message'),
                        'level': a.get('level')
                    }

            if execute == 1:
                if s.get('status') != 'passed':
                    entry['execute'] = {
                        'status': 'skipped',
                        'message': 'Skipped due to syntax error'
                    }
                else:
                    a = audit_by_order.get(order)
                    if a and a.get('status') == 'failed' and a.get('level') == 'error':
                        entry['execute'] = {
                            'status': 'skipped',
                            'message': 'Skipped due to audit error'
                        }
                    else:
                        cmd_data = parsed_by_order.get(order)
                        if not cmd_data:
                            entry['execute'] = {
                                'status': 'skipped',
                                'message': 'No parsed command for execution'
                            }
                        else:
                            ok, exec_result = redis_client.execute(cmd_data.get('tokens'))
                            entry['execute'] = {
                                'status': 'succeeded' if ok else 'failed',
                                'message': 'OK' if ok else exec_result,
                                'result': exec_result if ok else None
                            }

            results.append(entry)

        payload = {
            'check': check,
            'execute': execute,
            'target_redis_version': server_version or auditor.target_version,
            'results': results
        }

        if redis_client:
            redis_client.close()

        return jsonify(payload)
    except Exception as e:
        if redis_client:
            redis_client.close()
        return jsonify({"error": str(e)}), 500

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
