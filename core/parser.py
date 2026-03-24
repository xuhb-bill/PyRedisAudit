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
        
        # 首先尝试直接将整个脚本作为一条命令进行检查
        # 这可以处理因为 shell 解析导致的换行符问题
        combined_line = script_text.strip()
        if combined_line and not combined_line.startswith('#'):
            # 临时将换行符替换为空格，以便正确分词
            temp_line = combined_line.replace('\n', ' ').replace('\r', ' ')
            ok, message = self.syntax_check_line(temp_line)
            if ok:
                # 如果整个脚本作为一条命令通过了语法检查，直接返回结果
                results.append({
                    'order': 1,
                    'command': combined_line,
                    'status': 'passed',
                    'message': 'Syntax OK',
                    'level': 'info'
                })
                parsed = self.parse_line(temp_line)
                if parsed:
                    parsed['order'] = 1
                    parsed_commands.append(parsed)
                return parsed_commands, results
        
        # 如果直接检查失败，再按换行符分割命令进行检查
        # 处理包含在引号内的换行符，确保命令不会被错误分割
        # 首先将所有引号内的内容替换为占位符，然后分割命令，最后恢复占位符
        import re
        
        # 匹配单引号或双引号内的内容，包括转义的引号
        quoted_pattern = re.compile(r'("(?:\\.|[^"])*"|\'(?:\\.|[^\'])*\')')
        
        # 找出所有引号内的内容
        quoted_matches = quoted_pattern.findall(script_text)
        
        # 创建占位符映射
        placeholders = {}
        for i, match in enumerate(quoted_matches):
            placeholder = f"__QUOTE_PLACEHOLDER_{i}__"
            placeholders[placeholder] = match
            # 替换引号内的内容为占位符
            script_text = script_text.replace(match, placeholder)
        
        # 按换行符分割命令
        lines = script_text.split('\n')
        
        # 恢复占位符
        restored_lines = []
        for line in lines:
            restored_line = line
            for placeholder, original in placeholders.items():
                restored_line = restored_line.replace(placeholder, original)
            restored_lines.append(restored_line)
        
        # 处理每一行命令
        for raw_line in restored_lines:
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
        
        # 特殊处理：如果只有一条命令且语法检查失败，尝试将所有行合并为一条命令重新检查
        if len(results) == 1 and results[0]['status'] == 'failed':
            combined_line = ' '.join([line.strip() for line in restored_lines if line.strip() and not line.strip().startswith('#')])
            if combined_line:
                # 临时将换行符替换为空格，以便正确分词
                temp_line = combined_line.replace('\n', ' ').replace('\r', ' ')
                ok, message = self.syntax_check_line(temp_line)
                if ok:
                    # 替换原来的结果
                    results[0] = {
                        'order': 1,
                        'command': combined_line,
                        'status': 'passed',
                        'message': 'Syntax OK',
                        'level': 'info'
                    }
                    # 重新解析命令
                    parsed = self.parse_line(temp_line)
                    if parsed:
                        parsed['order'] = 1
                        parsed_commands = [parsed]
        
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

        # 支持的 Redis 命令列表
        supported_commands = {
            'GET', 'SET', 'DEL', 'EXISTS', 'INCR', 'DECR', 'TTL', 'EXPIRE',
            'HGET', 'HSET', 'HGETALL', 'HMSET', 'HDEL', 'HLEN',
            'LPUSH', 'RPUSH', 'LPOP', 'RPOP', 'LLEN', 'LRANGE',
            'SADD', 'SREM', 'SMEMBERS', 'SISMEMBER', 'SCARD',
            'ZADD', 'ZREM', 'ZRANGE', 'ZRANK', 'ZCARD'
        }

        if cmd == 'GET':
            if len(tokens) != 2:
                return False, 'GET expects exactly 1 argument: GET <key>'
            return True, None

        if cmd == 'SET':
            ok, msg = self._syntax_check_set(tokens)
            return ok, msg

        if cmd == 'DEL':
            if len(tokens) < 2:
                return False, 'DEL expects at least 1 argument: DEL <key> [key ...]'
            return True, None

        if cmd == 'EXISTS':
            if len(tokens) < 2:
                return False, 'EXISTS expects at least 1 argument: EXISTS <key> [key ...]'
            return True, None

        if cmd == 'INCR':
            if len(tokens) != 2:
                return False, 'INCR expects exactly 1 argument: INCR <key>'
            return True, None

        if cmd == 'DECR':
            if len(tokens) != 2:
                return False, 'DECR expects exactly 1 argument: DECR <key>'
            return True, None

        if cmd == 'TTL':
            if len(tokens) != 2:
                return False, 'TTL expects exactly 1 argument: TTL <key>'
            return True, None

        if cmd == 'EXPIRE':
            if len(tokens) != 3:
                return False, 'EXPIRE expects exactly 2 arguments: EXPIRE <key> <seconds>'
            if not re.fullmatch(r'\d+', str(tokens[2])):
                return False, 'EXPIRE expects an integer argument for seconds'
            return True, None

        if cmd == 'HGET':
            if len(tokens) != 3:
                return False, 'HGET expects exactly 2 arguments: HGET <key> <field>'
            return True, None

        if cmd == 'HSET':
            if len(tokens) < 4 or len(tokens) % 2 != 0:
                return False, 'HSET expects at least 2 arguments: HSET <key> <field> <value> [field value ...]'
            return True, None

        if cmd == 'HGETALL':
            if len(tokens) != 2:
                return False, 'HGETALL expects exactly 1 argument: HGETALL <key>'
            return True, None

        if cmd == 'HMSET':
            if len(tokens) < 4 or len(tokens) % 2 != 0:
                return False, 'HMSET expects at least 2 arguments: HMSET <key> <field> <value> [field value ...]'
            return True, None

        if cmd == 'HDEL':
            if len(tokens) < 3:
                return False, 'HDEL expects at least 2 arguments: HDEL <key> <field> [field ...]'
            return True, None

        if cmd == 'HLEN':
            if len(tokens) != 2:
                return False, 'HLEN expects exactly 1 argument: HLEN <key>'
            return True, None

        if cmd == 'LPUSH':
            if len(tokens) < 3:
                return False, 'LPUSH expects at least 2 arguments: LPUSH <key> <value> [value ...]'
            return True, None

        if cmd == 'RPUSH':
            if len(tokens) < 3:
                return False, 'RPUSH expects at least 2 arguments: RPUSH <key> <value> [value ...]'
            return True, None

        if cmd == 'LPOP':
            if len(tokens) not in (2, 3):
                return False, 'LPOP expects 1 or 2 arguments: LPOP <key> [count]'
            if len(tokens) == 3 and not re.fullmatch(r'\d+', str(tokens[2])):
                return False, 'LPOP expects an integer argument for count'
            return True, None

        if cmd == 'RPOP':
            if len(tokens) not in (2, 3):
                return False, 'RPOP expects 1 or 2 arguments: RPOP <key> [count]'
            if len(tokens) == 3 and not re.fullmatch(r'\d+', str(tokens[2])):
                return False, 'RPOP expects an integer argument for count'
            return True, None

        if cmd == 'LLEN':
            if len(tokens) != 2:
                return False, 'LLEN expects exactly 1 argument: LLEN <key>'
            return True, None

        if cmd == 'LRANGE':
            if len(tokens) != 4:
                return False, 'LRANGE expects exactly 3 arguments: LRANGE <key> <start> <stop>'
            if not re.fullmatch(r'-?\d+', str(tokens[2])):
                return False, 'LRANGE expects an integer argument for start'
            if not re.fullmatch(r'-?\d+', str(tokens[3])):
                return False, 'LRANGE expects an integer argument for stop'
            return True, None

        if cmd == 'SADD':
            if len(tokens) < 3:
                return False, 'SADD expects at least 2 arguments: SADD <key> <member> [member ...]'
            return True, None

        if cmd == 'SREM':
            if len(tokens) < 3:
                return False, 'SREM expects at least 2 arguments: SREM <key> <member> [member ...]'
            return True, None

        if cmd == 'SMEMBERS':
            if len(tokens) != 2:
                return False, 'SMEMBERS expects exactly 1 argument: SMEMBERS <key>'
            return True, None

        if cmd == 'SISMEMBER':
            if len(tokens) != 3:
                return False, 'SISMEMBER expects exactly 2 arguments: SISMEMBER <key> <member>'
            return True, None

        if cmd == 'SCARD':
            if len(tokens) != 2:
                return False, 'SCARD expects exactly 1 argument: SCARD <key>'
            return True, None

        if cmd == 'ZADD':
            if len(tokens) < 4:
                return False, 'ZADD expects at least 3 arguments: ZADD <key> [NX|XX] [CH] [INCR] <score> <member> [score member ...]'
            i = 2
            while i < len(tokens):
                opt = tokens[i].upper()
                if opt in ('NX', 'XX', 'CH', 'INCR'):
                    i += 1
                    continue
                break
            if len(tokens) - i < 2 or (len(tokens) - i) % 2 != 0:
                return False, 'ZADD expects score-member pairs after options'
            for j in range(i, len(tokens), 2):
                if not re.fullmatch(r'-?\d+(\.\d+)?', str(tokens[j])):
                    return False, f'ZADD expects a numeric score, got {tokens[j]}'
            return True, None

        if cmd == 'ZREM':
            if len(tokens) < 3:
                return False, 'ZREM expects at least 2 arguments: ZREM <key> <member> [member ...]'
            return True, None

        if cmd == 'ZRANGE':
            if len(tokens) not in (4, 5):
                return False, 'ZRANGE expects 3 or 4 arguments: ZRANGE <key> <start> <stop> [WITHSCORES]'
            if not re.fullmatch(r'-?\d+', str(tokens[2])):
                return False, 'ZRANGE expects an integer argument for start'
            if not re.fullmatch(r'-?\d+', str(tokens[3])):
                return False, 'ZRANGE expects an integer argument for stop'
            if len(tokens) == 5 and tokens[4].upper() != 'WITHSCORES':
                return False, 'ZRANGE only supports WITHSCORES as optional argument'
            return True, None

        if cmd == 'ZRANK':
            if len(tokens) != 3:
                return False, 'ZRANK expects exactly 2 arguments: ZRANK <key> <member>'
            return True, None

        if cmd == 'ZCARD':
            if len(tokens) != 2:
                return False, 'ZCARD expects exactly 1 argument: ZCARD <key>'
            return True, None

        # 检查命令是否在支持的命令列表中
        if cmd not in supported_commands:
            return False, f"Unsupported command '{cmd}'"

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
        # 首先将整个命令中的换行符替换为空格，以便正确分词
        # 这样可以处理引号内包含换行符的情况
        line = line.replace('\n', ' ').replace('\r', ' ')
        
        # 分词
        tokens = self.tokenizer.findall(line)
        
        if not tokens:
            return None
        
        # 去除引号
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
