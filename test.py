import multiprocessing
import socket
import threading

from construct import *
import netcast as nc

HOST = socket.gethostbyname(socket.gethostname())
PORT = 1199


class Message(nc.Struct):
    start = Const(0x60, Byte)
    message = NullTerminated(PaddedString(200, 'utf8'), term=0x70.to_bytes(1, 'little'))


def server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen(2)
    client_socket, address = server_socket.accept()
    print("New connection from " + str(address))
    message = nc.reinterpret(Message, client_socket.recv(0xffff))
    print(f"Message read: {message.message}, packet: {message}")


def client():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((HOST, PORT))
    message = 'Hi Mr. Brown!'
    packet = Message(message=message)
    print(f'Preparing message: {message}, packet: {packet}')
    client_socket.send(nc.serialize(packet))
    client_socket.close()


threading.Thread(target=server).start()
threading.Thread(target=client).start()
