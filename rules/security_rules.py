import re
from .base_rule import BaseRule

class CheckHighRiskCommandsRule(BaseRule):
    """
    Checks if a command is in the forbidden list.
    """
    def audit(self, command_data, context):
        if not self.enable:
            return None
        
        forbidden = self.params.get('forbidden', [])
        cmd_name = command_data['command']
        
        if cmd_name in forbidden:
            return {
                'status': 'failed',
                'message': f"High-risk command '{cmd_name}' is forbidden",
                'level': self.level
            }
        return None

class CheckFlushallRule(BaseRule):
    def audit(self, command_data, context):
        if not self.enable:
            return None

        cmd_name = command_data['command']
        if cmd_name in ('FLUSHALL', 'FLUSHDB'):
            message = self.params.get('description') or '禁止使用 FLUSHALL/FLUSHDB 命令'
            return {
                'status': 'failed',
                'message': message,
                'level': self.level
            }
        return None

class CheckKeyNamingRule(BaseRule):
    """
    Checks if Key follows naming conventions.
    """
    def audit(self, command_data, context):
        if not self.enable:
            return None
        
        key = command_data.get('key')
        if not key:
            return None
            
        pattern = self.params.get('pattern')
        max_length = self.params.get('max_length')
        
        if pattern and not re.match(pattern, key):
            return {
                'status': 'failed',
                'message': f"Key '{key}' does not match naming pattern '{pattern}'",
                'level': self.level
            }
            
        if max_length and len(key) > max_length:
            return {
                'status': 'failed',
                'message': f"Key '{key}' exceeds max length of {max_length}",
                'level': self.level
            }
            
        return None

class CheckTtlRequirementRule(BaseRule):
    """
    Checks if write commands have TTL parameters if required.
    """
    def audit(self, command_data, context):
        if not self.enable:
            return None
            
        write_commands = self.params.get('commands', [])
        cmd_name = command_data['command']
        params = [p.upper() for p in command_data['params']]
        
        if cmd_name in write_commands:
            # Check for EX or PX in params
            if 'EX' not in params and 'PX' not in params:
                return {
                    'status': 'failed',
                    'message': f"Write command '{cmd_name}' is missing TTL (EX/PX)",
                    'level': self.level
                }
        return None

class CheckOverwriteRule(BaseRule):
    """
    Checks if the command will overwrite an existing key (requires live connection).
    """
    def audit(self, command_data, context):
        if not self.enable:
            return None
        
        redis_client = context.get('redis_client')
        if not redis_client:
            return None
            
        cmd_name = command_data['command']
        key = command_data.get('key')
        
        if cmd_name == 'SET' and key:
            if redis_client.key_exists(key):
                return {
                    'status': 'failed',
                    'message': f"Key '{key}' already exists. Executing 'SET' will overwrite it.",
                    'level': self.level
                }
        return None
