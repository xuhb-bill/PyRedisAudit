from .base_rule import BaseRule
from core.version_checker import VersionChecker

class CheckVersionCompatibilityRule(BaseRule):
    """
    Checks if command/parameters are supported in target Redis version.
    """
    def audit(self, command_data, context):
        if not self.enable:
            return None
        
        target_version = context.get('target_redis_version')
        meta = context.get('meta', {}).get('commands', {})
        
        cmd_name = command_data['command']
        params = command_data['params']
        
        # Check command existence
        if cmd_name not in meta:
            # We don't have meta for every command, so just pass
            return None
        
        cmd_meta = meta[cmd_name]
        since = cmd_meta.get('since')
        
        if not VersionChecker.is_supported(target_version, since):
            return {
                'status': 'failed',
                'message': f"Command '{cmd_name}' is not supported in Redis {target_version} (Introduced in {since})",
                'level': self.level
            }
            
        # Check parameters
        params_meta = cmd_meta.get('params', {})
        for p in params:
            if p.upper() in params_meta:
                p_since = params_meta[p.upper()].get('since')
                if not VersionChecker.is_supported(target_version, p_since):
                    return {
                        'status': 'failed',
                        'message': f"Parameter '{p}' for command '{cmd_name}' is not supported in Redis {target_version} (Introduced in {p_since})",
                        'level': self.level
                    }
        
        return None
