import time
import unittest
import threading
import socket
from beetsplug import web_tagger
from beetsplug.web_tagger import PORT


class MBWebTest(unittest.TestCase):
    def test_server(self):
        url = 'http://127.0.0.1:{0}/openalbum?' \
              'id=8b0b4356-5063-4be3-8aa8-3331a93faef2&t=1483442935'.format(PORT)
        self.start_server()
        time.sleep(0.0001)
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('127.0.0.1', PORT))
        client.send(url)
        data = client.recv(1024)
        self.assertEqual(data, url)
        client.close()
        self.serv_thread.join()

    def start_server(self):
        serv = web_tagger.Server()
        self.serv_thread = threading.Thread(serv.listen())
        self.serv_thread.start()
