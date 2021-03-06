import socket
from multiprocessing import Manager

from Crypto.Random import get_random_bytes

import Crypt_Client.Crypt as Crypt


class InvalidToken(Exception):

    def __init__(self, *args):
        super().__init__(*args)


class DisconnectedServer(Exception):

    def __init__(self, *args):
        super().__init__(*args)


class KeyExchangeFailed(Exception):

    def __init__(self, *args):
        super().__init__(*args)


class UnableToDecrypt(Exception):
    def __init__(self, *args):
        super().__init__(*args)


class Client:

    def __init__(self, ip, port, timeout, claves=None, bits=1024, buffersize=1024*1024, token_size=32):
        """
        Crypt_Client object to handle connections
        :param ip: Ip address to connect to
        :param port: Port to connect to
        :param claves: Cryptographic keys to use(same syntax as Crypt.generate())
        :param bits: If claves is None, size of the key to generate
        :param buffersize: Tunnel anchor for exchanging keys
        :param token_size: Authenthication token size to generate
        :raise KeyExchangeFailed
        """
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.settimeout(timeout)
        if claves is None:
            self.claves = Crypt.generate_rsa(bits)
        else:
            self.claves = claves
        self.s.connect((ip, port))
        try:
            self.publica = self.s.recv(buffersize).decode()
            self.s.send(Crypt.encrypt_rsa(self.claves["PUBLIC"], self.publica))
            self.server_token = Crypt.decrypt_rsa(self.s.recv(buffersize), self.claves["PRIVATE"])
            self.client_token = get_random_bytes(token_size)
            self.s.send(Crypt.encrypt_rsa(self.client_token, self.publica))
            self.aes_key = Crypt.decrypt_rsa(self.s.recv(buffersize), self.claves["PRIVATE"])
        except:
            self.s.close()
            raise KeyExchangeFailed("Key exchange failed. Connection closed")
        manager = Manager()
        self.blocked = manager.Value(bool, False)

    def recv(self, timeout=None, number_size=5):
        """
        Receives a message from the server
        :param timeout: Time to wait until timing out 
        :param number_size: Size in bytes of integer representing the size of the message
        :raise DisconnectedServer
        :raise UnableToDecrypt
        :raise InvalidToken
        :return: Message received
        """
        self.s.settimeout(timeout)
        long = int.from_bytes(self.s.recv(number_size), "big")
        msg = self.s.recv(long)
        if msg == b"":
            raise DisconnectedServer("The server seems to be down")

        try:
            msg = Crypt.decrypt_aes(msg, self.aes_key)
        except:
            raise UnableToDecrypt("Unable to decrypt the message sent by the server")
        if self.server_token in msg:
            msg = msg.replace(self.server_token, b"", 1)
        else:
            raise InvalidToken("The token provided by the server doesn't match the original one. Maybe an attempt"
                               "of man-in-the-middle?")
        return msg.decode()

    def send(self, msg, number_size=5):
        """
        Sends a message to the server
        :param msg: Message to send
        :param number_size: Size in bytes of integer representing the size of the message
        :raise DisconnectedServer
        :return: VOID
        """
        msg = self.client_token + msg.encode()
        msg = Crypt.encrypt_aes(msg, self.aes_key)
        leng = len(msg).to_bytes(number_size, "big")

        try:
            self.s.send(leng+msg)
        except BrokenPipeError:
            raise DisconnectedServer("The server has been disconnected")

    def close(self):
        try:
            self.s.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.s.close()

    def get_conn(self):
        """
        Returns the Socket's connection object(It should only be used for gathering information rather than
        sending or receiving information as it would break the protocol). USE AT YOUR OWN RISK
        :return: Socket object
        """
        return self.s


if __name__ == "__main__":
    client = Client("localhost", 8001, timeout=10)
    while True:
        print(client.recv())
        client.send("CUCU")
