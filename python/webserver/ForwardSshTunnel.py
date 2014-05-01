
#
# This code is based on the paramiko forward.py demo, which, at the
# time of this writing, could be found here:
#
# https://github.com/paramiko/paramiko/blob/master/demos/forward.py
#

import threading
import socket
import select
import SocketServer
import sys
import paramiko

class ForwardSshTunnel(object) :

    #-------------------------------------------------------------------------
    # ForwardSshTunnel constructor
    #-------------------------------------------------------------------------
    def __init__(self, local_port, remote_host, remote_port, sshClientTransport) :
        self.localPort = local_port
        self.remoteHost = remote_host
        self.remotePort = remote_port
        self.transport = sshClientTransport

    #-------------------------------------------------------------------------
    # Connects to remote host port 22 and creates a threaded socket server
    # which handles secure port forwarding between remote port and local
    # port.  If this function is run as a thread, then the connection
    # can be shutdown at any time.
    #-------------------------------------------------------------------------
    def requestLoop(self) :
        print 'Now going to forward local port %d to remote port %d ...' % (self.localPort,
                                                                            self.remotePort)

        remote_host = self.remoteHost
        remote_port = self.remotePort

        class SubHander (Handler):
            chain_host = remote_host
            chain_port = remote_port
            ssh_transport = self.transport

        # Create the forward server and start serving
        self.fserv = ForwardServer(('', self.localPort), SubHander)
        self.fserv.serve_forever()

        print 'Returning from ForwardSshTunnel requestLoop() method'

    #-------------------------------------------------------------------------
    # Requests that the ForwardServer stop serving
    #-------------------------------------------------------------------------
    def terminateRequestLoop(self) :
        self.fserv.shutdown()

    #-------------------------------------------------------------------------
    # Runs the request loop function in a separate thread so that the tcp
    # server can be shutdown later on if desired.
    #-------------------------------------------------------------------------
    def establishForwardTunnel(self) :
        t = threading.Thread(target=self.requestLoop,
                             args=[],
                             kwargs={})
        t.start()


class ForwardServer(SocketServer.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler(SocketServer.BaseRequestHandler):
    def handle(self):
        try:
            chan = self.ssh_transport.open_channel('direct-tcpip',
                                                   (self.chain_host, self.chain_port),
                                                   self.request.getpeername())
        except Exception, e:
            print 'Incoming request to %s:%d failed: %s' % (self.chain_host,
                                                            self.chain_port,
                                                            repr(e))
            return
        if chan is None:
            print 'Incoming request to %s:%d was rejected by the SSH server.' % (self.chain_host,
                                                                                 self.chain_port)
            return

        print 'Connected! Tunnel open %r -> %r -> %r' % (self.request.getpeername(),
                                                         chan.getpeername(),
                                                         (self.chain_host, self.chain_port))
        while True:
            r, w, x = select.select([self.request, chan], [], [])
            if self.request in r:
                data = self.request.recv(1024)
                if len(data) == 0:
                    break
                chan.send(data)
            if chan in r:
                data = chan.recv(1024)
                if len(data) == 0:
                    break
                self.request.send(data)

        peername = self.request.getpeername()
        chan.close()
        self.request.close()
        print 'Tunnel closed from %r' % (peername,)
