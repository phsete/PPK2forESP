import time
import socket

def myclient(ip, port, message):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ip, port))
    sock.sendall(str.encode(message))
    result = sock.recv(1024)
    print(str(result) + ' final clnt time {}'.format(time.time()))
    sock.close()