import socket


class Server:
    def __init__(self, port=8000):
        self.host = '127.0.0.1'
        self.port = port
        self.start = None

    def start_server(self):
        self.start = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.start.bind((self.host, self.port))
        self.start.listen(1)

    def listen(self):
        self.start_server()
        while True:
            connection, addr = self.start.accept()
            data = connection.recv(1024)
            if not data:
                break
            yield data
