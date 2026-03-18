import yaml
import os
import sys

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class ConfigLoader:
    """
    Loads configuration from YAML files.
    """
    def __init__(self, config_path=None):
        if config_path is None:
            # Look for default_config.yaml
            config_path = get_resource_path('config/default_config.yaml')
        
        self.config_path = config_path
        self.config = self._load_yaml(config_path)

    def _load_yaml(self, path):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Configuration file not found: {path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def get_global_config(self):
        return self.config.get('global', {})

    def get_rules_config(self):
        return self.config.get('rules', {})

    def get_log_level(self):
        return self.get_global_config().get('log_level', 'INFO')

    def get_log_file(self):
        return self.get_global_config().get('log_file', None)

    def get_target_redis_version(self):
        return self.get_global_config().get('target_redis_version', '6.0')
