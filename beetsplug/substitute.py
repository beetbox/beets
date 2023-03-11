from beets.plugins import BeetsPlugin
import re

class Substitute(BeetsPlugin):
    def tmpl_substitute(self, text):
        if text:
            for pattern, replacement in self.substitute_rules:
                if pattern.match(text.lower()):
                    return replacement
            return text
        else:
            return u''

    
    def __init__(self):
        super(Substitute, self).__init__()
        self.substitute_rules = []
        self.template_funcs['substitute'] = self.tmpl_substitute

        for key, view in self.config.items():
            value = view.as_str()
            pattern = re.compile(key.lower())
            self.substitute_rules.append((pattern, value))

