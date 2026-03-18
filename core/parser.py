import re

class RedisCommandParser:
    """
    Parses Redis command text or scripts.
    """
    def __init__(self):
        # Regex to match words, but respect quotes
        self.tokenizer = re.compile(r'(?:[^\s"\']|"(?:\\.|[^"])*"|\'(?:\\.|[^\'])*\')+')

    def parse_script_with_syntax(self, script_text):
        results = []
        parsed_commands = []
        order = 0
        for raw_line in script_text.split('\n'):
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            order += 1
            ok, message = self.syntax_check_line(line)
            results.append({
                'order': order,
                'command': line,
                'status': 'passed' if ok else 'failed',
                'message': message if message else ('Syntax OK' if ok else 'Syntax error'),
                'level': 'info' if ok else 'error'
            })
            if ok:
                parsed = self.parse_line(line)
                if parsed:
                    parsed['order'] = order
                    parsed_commands.append(parsed)
        return parsed_commands, results

    def parse_line(self, line):
        """
        Parses a single line of Redis command.
        Example: SET "my key" value EX 3600
        Returns: { 'command': 'SET', 'key': 'my key', 'params': ['EX', '3600'], 'original': ... }
        """
        line = line.strip()
        if not line or line.startswith('#'):
            return None

        tokens = self._tokenize(line)
        if not tokens:
            return None

        command = tokens[0].upper()
        tokens[0] = command
        key = tokens[1] if len(tokens) > 1 else None
        params = tokens[2:] if len(tokens) > 2 else []

        return {
            'command': command,
            'key': key,
            'params': params,
            'tokens': tokens,
            'original': line
        }

    def parse_script(self, script_text):
        """
        Parses a multiline script.
        """
        commands = []
        for line in script_text.split('\n'):
            parsed = self.parse_line(line)
            if parsed:
                commands.append(parsed)
        return commands

    def syntax_check_line(self, line):
        if self._has_unbalanced_quotes(line):
            return False, 'Unbalanced quotes'

        tokens = self._tokenize(line)
        if not tokens:
            return False, 'Empty command'

        cmd = tokens[0].upper()
        if not re.fullmatch(r'[A-Z][A-Z0-9_]*', cmd):
            return False, f"Invalid command name '{tokens[0]}'"

        if cmd == 'GET':
            if len(tokens) != 2:
                return False, 'GET expects exactly 1 argument: GET <key>'
            return True, None

        if cmd == 'SET':
            ok, msg = self._syntax_check_set(tokens)
            return ok, msg

        return True, None

    def _syntax_check_set(self, tokens):
        if len(tokens) < 3:
            return False, 'SET expects at least 2 arguments: SET <key> <value>'

        i = 3
        while i < len(tokens):
            opt = tokens[i].upper()
            if opt in ('EX', 'PX'):
                if i + 1 >= len(tokens):
                    return False, f"SET option '{opt}' expects an integer argument"
                if not re.fullmatch(r'\d+', str(tokens[i + 1])):
                    return False, f"SET option '{opt}' expects an integer argument"
                i += 2
                continue
            if opt in ('NX', 'XX', 'GET', 'KEEPTTL'):
                i += 1
                continue
            return False, f"Unknown SET option '{tokens[i]}'"

        return True, None

    def _tokenize(self, line):
        tokens = self.tokenizer.findall(line)
        if not tokens:
            return None
        return [self._unquote(t) for t in tokens]

    def _has_unbalanced_quotes(self, line):
        dq = 0
        sq = 0
        escaped = False
        for ch in line:
            if escaped:
                escaped = False
                continue
            if ch == '\\':
                escaped = True
                continue
            if ch == '"':
                dq ^= 1
                continue
            if ch == "'":
                sq ^= 1
                continue
        return dq == 1 or sq == 1

    def _unquote(self, token):
        if (token.startswith('"') and token.endswith('"')) or \
           (token.startswith("'") and token.endswith("'")):
            return token[1:-1]
        return token
