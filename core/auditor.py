import yaml
import os
import sys
from .logger import setup_logger
from rules.version_rules import CheckVersionCompatibilityRule
from rules.security_rules import CheckHighRiskCommandsRule, CheckKeyNamingRule, CheckTtlRequirementRule, CheckOverwriteRule, CheckFlushallRule

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class RedisAuditor:
    """
    Main auditing engine that coordinates rules and data.
    """
    def __init__(self, config_loader):
        self.config_loader = config_loader
        self.rules_config = self.config_loader.get_rules_config()
        self.target_version = self.config_loader.get_target_redis_version()
        
        # Setup Logger
        log_level = self.config_loader.get_log_level()
        log_file = self.config_loader.get_log_file()
        self.logger = setup_logger("RedisAuditor", log_level, log_file)
        
        # Load metadata
        self.meta = self._load_meta()
        
        # Initialize Rules
        self.rules = self._init_rules()

    def _load_meta(self):
        meta_path = get_resource_path('data/redis_commands_meta.yaml')
        with open(meta_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _init_rules(self):
        rules = []
        rule_map = {
            'check_version_compatibility': CheckVersionCompatibilityRule,
            'check_high_risk_commands': CheckHighRiskCommandsRule,
            'check_flushall': CheckFlushallRule,
            'check_key_naming': CheckKeyNamingRule,
            'check_ttl_requirement': CheckTtlRequirementRule,
            'check_overwrite': CheckOverwriteRule
        }
        
        for r_id, r_class in rule_map.items():
            if r_id in self.rules_config:
                rules.append(r_class(r_id, self.rules_config[r_id]))
                self.logger.debug(f"Rule '{r_id}' initialized")
        return rules

    def audit_commands(self, parsed_commands, redis_client=None):
        """
        Audit a list of parsed commands.
        """
        audit_results = []
        
        # Determine the target version
        target_version = self.target_version
        if redis_client:
            server_version = redis_client.get_server_version()
            if server_version:
                target_version = server_version
                self.logger.info(f"Using server version {target_version} for audit")
        
        context = {
            'target_redis_version': target_version,
            'meta': self.meta,
            'redis_client': redis_client # Pass the live client to rules
        }
        
        for i, cmd in enumerate(parsed_commands):
            cmd_results = []
            for rule in self.rules:
                res = rule.audit(cmd, context)
                if res:
                    cmd_results.append(res)
            
            # Aggregate result for this command
            if not cmd_results:
                audit_results.append({
                    'order': cmd.get('order', i + 1),
                    'command': cmd['original'],
                    'status': 'passed',
                    'message': 'Audit passed',
                    'level': 'info'
                })
            else:
                # Use the highest level if multiple rules failed
                # Sort: error > warning
                cmd_results.sort(key=lambda x: 0 if x['level'] == 'error' else 1)
                worst_res = cmd_results[0]
                
                audit_results.append({
                    'order': cmd.get('order', i + 1),
                    'command': cmd['original'],
                    'status': 'failed',
                    'message': worst_res['message'],
                    'level': worst_res['level']
                })
                
                self.logger.warning(
                    f"Command '{cmd['original']}' failed audit: {worst_res['message']} (Level: {worst_res['level']})"
                )
        
        return audit_results
