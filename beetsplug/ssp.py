from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets import config
from openai import OpenAI
import time
import json

class OpenAICaller:
    def __init__(self, api_key, assistant_id):
        """
        Args:
            api_key (str): key for Open ai. ideally grabbed from env as OPENAI_API_KEY
            assistant_id (str): id of the assistant to pass the request to
        """
        self.client = OpenAI(api_key=api_key)
        self.assistant_id = assistant_id

    def _create_thread(self):
        """ Create a thread

        Returns:
            Thread: A new/fresh OpenAI thread object to use for parsing a song string
        """
        return self.client.beta.threads.create()
    
    def _submit_message(self, t, p):
        """ Post a prompt p to a thread t

        Args:
            t (thread object): OpenAI thread object, create with the function self._create_thread
            p (string): prompt to send to the assistant 

        Returns:
            OpenAI run object: Run object
        """
        self.client.beta.threads.messages.create(thread_id=t.id, role="user", content=p)
        return self.client.beta.threads.runs.create(thread_id=t.id, assistant_id=self.assistant_id)

    def _wait_for_response(self, thread, run):
        """ Wait for an OpenAI run to finish so we can extract data from the response

        Args:
            run (Run): The run we want to wait for

        Returns:
            Run: the finished run
        """
        while run.status == "queued" or run.status == "in_progress":
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id,
            )
            time.sleep(0.5)
        return run

    def _get_messages(self, thread):
        """ Get all messages for a given thread

        Args:
            tread (Thread): OpenAI Thread object for which to fetch all messages

        Returns:
            list: list of all messages within the thread
        """
        return json.loads(self.client.beta.threads.messages.list(thread_id=thread.id, order="asc").to_json())['data']
    
    def _parse_response(self, messages):
        """ Get last message from a thread and parse the content of that message so we can return a dictionary containing song_data

        Args:
            thread (Thread): OpenAI thread object to retreive the last message from
        """
        last_message = messages[-1]['content']
        answer = last_message[0]['text']['value']
        data = eval(answer)
        return data

    def parse_song_string(self, song_string):
        """ Use an OpenAI assistant to parse a song string and extract data from it.
                1. Create a thread
                2. Submit a message to the thread and run the thread
                3. Wait for a response
                4. Get messages in thread from response
                4. Get last message and parse it to return a dictionary of song data
        Args:
            song_string (str): String representing a song 

        Returns:
            dict: Dictionary containing song data (keys match beets database columns)
        """
        thread = self._create_thread()
        run = self._submit_message(thread, song_string)
        run = self._wait_for_response(thread, run)
        messages = self._get_messages(thread)
        song_data = self._parse_response(messages)
        return song_data
   
class SongStringParser(BeetsPlugin):
    def __init__(self):
        super(SongStringParser, self).__init__()

        # Load configuration
        self.config.add({
            'api_key': '',
            'assistant_id': ''
        })

        try:
            api_key = self.config['api_key'].get(str)
            assistant_id = self.config['assistant_id'].get(str)
        except config.ConfigValueError as e:
            self._log.error('Configuration error: %s', e)
            return

        self.parser = OpenAICaller(api_key, assistant_id)

        # Define a custom command for Beets
        self.custom_gpt_command = Subcommand('ssp', help='Send request to OpenAI GPT')
        self.custom_gpt_command.func = self.send_gpt_request

    def commands(self):
        return [self.custom_gpt_command]

    def send_gpt_request(self, args):
        results = list()
        for song_string in args:
            try:
                response = self.parser.parse_song_string(song_string)
                # print(response)
                # self._log.info(f'Song String: {song_string}\nParsed response: {response}')
                results.append((song_string, response))
            except Exception as e:
                self._log.error(f"Error processing song string {song_string}: {e}")

        print(results)
        return results
