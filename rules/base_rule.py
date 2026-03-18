from abc import ABC, abstractmethod

class BaseRule(ABC):
    """
    Abstract Base Class for all audit rules.
    """
    def __init__(self, rule_id, config):
        self.rule_id = rule_id
        self.config = config
        self.enable = config.get('enable', True)
        self.level = config.get('level', 'warning')
        self.params = config.get('params', {})
        if 'description' in config and 'description' not in self.params:
            self.params['description'] = config.get('description')

    @abstractmethod
    def audit(self, command_data, context):
        """
        Perform the audit logic.
        Returns: { 'status': 'passed/failed', 'message': '...', 'level': '...' }
        """
        pass
