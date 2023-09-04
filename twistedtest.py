from twisted.internet import reactor
from twisted.internet.protocol import Protocol, Factory
from twisted.internet.endpoints import TCP4ClientEndpoint, TCP4ServerEndpoint, connectProtocol
from twisted.protocols.basic import LineReceiver
from sys import stdout

class Chat(LineReceiver):
    def connectionMade(self):
        self.sendLine(str.encode("What's your name?"))

    def connectionLost(self, reason):
       pass

    def lineReceived(self, line):
        pass


class ChatFactory(Factory):
    def __init__(self):
        pass

    def buildProtocol(self, addr):
        return Chat()
    
def main():
    while(True):
        print("Test")

reactor.listenTCP(1234, ChatFactory())
reactor.run()

