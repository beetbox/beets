from pathlib import Path
import subprocess
import shlex

from beets.autotag.match import Recommendation
from confuse import NotFoundError as ConfigParmNotFound
from beets.plugins import BeetsPlugin
from beets.ui.commands import PromptChoice
from beets.importer import action


class MarkUnmatched(BeetsPlugin):
    def __init__(self):
        super(MarkUnmatched, self).__init__()
        self.register_listener('before_choose_candidate',
                               self.before_choose_candidate_event)

    def before_choose_candidate_event(self, session, task):
        if task.rec == Recommendation.strong:
            self._log.info("recommendation is strong, not notifying")
            return
        notify_command = ""
        try:
            notify_command = shlex.split(str(self.config['notify-command']))
        except ConfigParmNotFound:
            self._log.info("no notify-command was configured")
        if notify_command:
            self._log.info("notifying no-match via command configured: %s",
                           self.config['notify-command'])
            print_cmd = [
                "printf", "%s",
                "failed to find match for paths:\n",
                "\n".join([path.decode('utf-8') for path in task.paths])
            ]
            p_msg = subprocess.Popen(print_cmd, stdout=subprocess.PIPE)
            p_out = subprocess.Popen(notify_command, stdin=p_msg.stdout, stdout=subprocess.PIPE)
            (stdout, stderr) = p_out.communicate()
            if stderr:
                print("'notify-command' printed errors:")
                print(stderr.decode('utf-8'), end='')
            if stdout:
                print("'notify-command' printed:")
                print(stdout.decode('utf-8'), end='')
        return [PromptChoice(
            'f',
            'create a \'beets-unmatched\' File and skip',
            self.touch_unmatched
        )]

    def touch_unmatched(self, session, task):
        for path in task.paths:
            Path(path.decode('utf-8') + "/beets-unmatched").touch()
        return action.SKIP
