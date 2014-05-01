
import paramiko
import select
import argparse
import sys
import threading
import uuid
import tempfile
import os
import getpass

from ForwardSshTunnel import ForwardSshTunnel


class SecureRemoteLauncher(object) :

    #-------------------------------------------------------------------------
    # SecureRemoteLauncher constructor
    #-------------------------------------------------------------------------
    def __init__(self, mapFilePath) :
        self.mappingFilePath = mapFilePath
        self.sessionMap = {}

    #-------------------------------------------------------------------------
    # Create a port forwarding ssh tunnel
    #-------------------------------------------------------------------------
    def createTunnelOnRemotePort(self, transport, host, port) :
        print 'Create a tunnel on remote port ' + str(port)

        try:
            tunnel = ForwardSshTunnel(port,       # local port
                                      host,       # remote host
                                      port,       # remote port
                                      transport)  # SSHClient Transport object
            tunnel.establishForwardTunnel()
        except KeyboardInterrupt:
            print 'C-c: Port forwarding stopped.'
        except Exception as inst :
            print 'Encountered exception in forwarding'
            print inst

        print 'Returning from createTunnelOnRemotePort()'
        return tunnel

    #-------------------------------------------------------------------------
    # Rewrite the mapping file with the current session map
    #-------------------------------------------------------------------------
    def updateMappingFile(self) :
        with open(self.mappingFilePath, 'w') as outfile :
            for session in self.sessionMap :
                outfile.write(session + ' ' + self.sessionMap[session] + '\n')

    #-------------------------------------------------------------------------
    # Wait for process to exit so that when it does we can end the tunnel
    # thread and then end this waiting thread by returning from this
    # function
    #-------------------------------------------------------------------------
    def waitOnChannelExitStatus(self, channel, sessionId, tunnel) :
        # This call will block until channel process has finished
        processReturnVal = channel.recv_exit_status()

        # Now make sure to kill the thread which is running the port
        # forwarding ssh tunnel
        print 'Channel exit status ready, process has terminated'
        if tunnel is not None :
            print 'Attempting to end tunnel request loop...'
            tunnel.terminateRequestLoop()

        # Next remove this session from the map
        del self.sessionMap[sessionId]

        # Finally rewrite the map file with the updated session info
        self.updateMappingFile()

        print 'Returning from wait thread'

    #-------------------------------------------------------------------------
    # Try to start pvweb on remote machine until we successfully start on a
    # port.
    #-------------------------------------------------------------------------
    def startPvwebOnOpenPortInRange(self, transport, remoteHost, fileToLoad, portRange) :
        #port = random.randrange(portRange[0], portRange[1], 1)
        port = 9010

        # Works on mayall
        #cmdFirstPart = 'export LD_LIBRARY_PATH=/opt/python-2.7.3/lib ; export DISPLAY=:0.0 ; /home/kitware/projects/ParaView/build-make-gpu/bin/pvpython /home/kitware/projects/ParaView/build-make-gpu/lib/site-packages/paraview/web/pv_web_visualizer.py --data-dir /home/kitware/Documents/haloregions --port '

        # Works on solaris
        cmdFirstPart = 'export DISPLAY=:0.0 ; /home/scott/projects/ParaView/build-make-gpu/bin/pvpython /home/scott/projects/ParaView/build-make-gpu/lib/site-packages/paraview/web/pv_web_visualizer.py --data-dir /home/scott/Documents/cosmodata/haloregions --port '

        started = False

        while started == False :

            cmd = cmdFirstPart + str(port) + ' --load-file ' + fileToLoad + ' -f'

            channel = transport.open_session()
            channel.exec_command(cmd)

            characters = ''

            while True:
                if channel.exit_status_ready():
                    break

                rl, wl, xl = select.select([channel],[],[],0.0)

                if len(rl) > 0 :
                    characters = channel.recv(1024)

                    if 'CannotListenError' in characters or 'Address already in use' in characters :
                        print 'port ' + str(port) + ' is already being used'
                    elif ('tarting on ' + str(port)) in characters:
                        print 'Ahh, we have finally started on port ' + str(port)

                        # write the mapping file here
                        sessionId = str(uuid.uuid1())
                        connectStr = 'localhost:' + str(port)
                        self.sessionMap[sessionId] = connectStr
                        self.updateMappingFile()
                        tunnel = self.createTunnelOnRemotePort(transport, remoteHost, port)
                        print 'Have now returned from readyCallback() !!!!'
                        t = threading.Thread(target=self.waitOnChannelExitStatus,
                                             args=[channel, sessionId, tunnel],
                                             kwargs={})
                        t.start()
                        print 'wait thread started, returning from startPvwebOnOpenPortInRange()'
                        return (sessionId, port)
                        started = True

            if started == False :
                #port = random.randrange(portRange[0], portRange[1], 1)
                port += 1

        print 'Returning from startPvwebOnOpenPortInRange()'
