
import sys
import json
import uuid
import re

from girder.api.rest import Resource


### Convenience function to check if all keys are in a dictionary
def allIn(keyTuple, dictionary) :
    return all(k in dictionary for k in keyTuple)


class RemoteConnection(Resource):
    """
    API endpoint for remote connections.  This is a throwaway class, just
    designed to achieve my goals for demo purposes.  This class will need
    to be re-written to fit within the Girder plugin framework whenever
    we come up with that thing.

    Interaction with this REST component is as follows:

    1) Create a new connection to remote host 'mayall':

        http://localhost:8080/api/v1/remoteconnection/create?fqhn=mayall

    2) Actually connect to the host corresponding to this connection.  Make a POST request with the data parameters 'connId', 'username', and 'password' set to the appropriate values.

        http://localhost:8080/api/v1/remoteconnection/connect

    3) Send a command on the connection:

        http://localhost:8080/api/v1/remoteconnection/command?connId=08b8b44e-9800-11e3-b3d4-3ca9f4373d8c&cmdStr=ls%20-al

    4) Close an existing connection:

        http://localhost:8080/api/v1/remoteconnection/disconnect?connId=08b8b44e-9800-11e3-b3d4-3ca9f4373d8c
    """

    #-------------------------------------------------------------------------
    # Constructor for RemoteConnection resource
    #-------------------------------------------------------------------------
    # def __init__(self, pathToConnModule) :
    def __init__(self):
        self.resourceName = 'remoteconnection'

        # Hardcode some paths until we know how to pass our
        # own custom config options to our plugin
        pathToConnModule = '/home/scott/projects/project-backups-scott-wittenburg/scripts/python/cosmoscripts'
        self.mappingFilePath = '/opt/apache-2.4.7/pv-mapping-file/mapping.txt'

        try :
            sys.path.insert(0, pathToConnModule)
            rcm = __import__('RemoteConnection')
            self.remoteConnMgr = rcm.RemoteConnectionManager()
            self.launcherModule = __import__('SecureRemoteLauncher')
        except Exception as inst :
            print "ERROR: remote connections will not work, exception encountered import module"
            print inst

        Resource.__init__(self)

        self.currentJobsMap = {}

        self.route('POST', ('connect',), self.secureConnect)
        self.route('POST', ('tunnellaunch',), self.sshTunnelLaunch)
        self.route('POST', ('jobschedule',), self.scheduleJob)
        self.route('POST', ('jobstatus',), self.checkJobStatus)
        self.route('POST', ('jobcleanup',), self.cleanupJob)
        self.route('GET', ('create',), self.createConnection)
        self.route('GET', ('command',), self.sendShellCommand)
        self.route('GET', ('disconnect',), self.disconnect)


    #-------------------------------------------------------------------------
    # Get the remote connection object and use it to "connect" the ssh
    # connection.  If this succeeds, commands can be issued on the remote,
    # other channels can be opened, etc.
    #-------------------------------------------------------------------------
    def secureConnect(self, params):
        if allIn(('connId', 'username', 'password'), params) :
            conn = self.remoteConnMgr.retrieve(params['connId'])
            if conn is not None and conn.connected is not True :
                try :
                    conn.connect(params['username'], params['password'])
                    return [ 'Connection ' + params['connId'] + ' connected' ]
                except Exception as inst :
                    return [ "Error connecting id %s: %s" % (params['connId'], str(inst)) ]
            else :
                return [ 'Unable to connect for connId ' + params['connId'] ]
        else :
            return [ 'Should have received a connection id, username, and password: ' + str(params) ]


    #-------------------------------------------------------------------------
    # Creates a remote connection item in memory, mapped by a unique id which
    # we return to the client so they can access this connection again in the
    # future.
    #-------------------------------------------------------------------------
    def createConnection(self, params):
        if allIn(('fqhn',), params) :
            connId = self.remoteConnMgr.create({'fqhn': params['fqhn']})
            return { 'connId': connId }
        else :
            return [ 'Should have received a hostname as fqhn: ' + str(params) ]


    #-------------------------------------------------------------------------
    # Uses an ssh connection to execute a shell command on the remote machine.
    #-------------------------------------------------------------------------
    def sendShellCommand(self, params):
        if allIn(('connId', 'cmdStr'), params) :
            conn = self.remoteConnMgr.retrieve(params['connId'])
            if conn is not None :
                return conn.sendCommand(params['cmdStr'])
            else :
                return [ 'Found no connection with id ' + params['connId'] ]
        else :
            return [ 'You must supply a connection id and a command string to run' ]


    #-------------------------------------------------------------------------
    # Disconnects the ssh connection, but the unique id still maps to a
    # remote connection object which can be connected again in the future.
    # There are problems with this when Girder restarts, because the in-memory
    # mapping is killed, after which point the unique identifier is useless.
    #-------------------------------------------------------------------------
    def disconnect(self, params):
        if allIn(('connId',), params) :
            conn = self.remoteConnMgr.retrieve(params['connId'])
            if conn is not None :
                conn.close()
                return [ 'Connection ' + params['connId'] + ' is now closed' ]
            else :
                return [ 'Found no connection with id ' + params['connId'] ]
        else :
            return [ 'You must supply an id to close a connection: ' + str(params) ]


    #-------------------------------------------------------------------------
    # This is the REST api endpoint to get into the SecureRemoteLauncher
    # python module which starts up pvweb on an open port on the remote
    # machine, then creates an ssh tunnel through which you can can connect
    # pvpython to the process.
    #-------------------------------------------------------------------------
    def sshTunnelLaunch(self, params) :
        keyvals = {}

        # This is wrong.  My params are coming over as a JSON encoded string,
        # which may be because of how paraview web is contacting the launcher.
        # But the result is that all my key value pairs are in a single string
        # which is a key in a dictionary which points to no value.  By doing
        # the nested loop below, I can actually extract the keys and the info
        # I need from the request.
        for key in params :
            obj = json.loads(key)
            for k in obj :
                keyvals[k] = obj[k]

        # Grab the connection identified by the passed-in connectionId.  Use it
        # to access the transport object within the associated RemoteConnection
        # object for use in running remote pvpython process and then creating
        # the software port-fowarding ssh tunnel to talk to the process.
        try :
            conn = self.remoteConnMgr.retrieve(keyvals['connectionId'])
            srl = self.launcherModule.SecureRemoteLauncher(self.mappingFilePath)
            (sessionId, actualPort) = srl.startPvwebOnOpenPortInRange(conn.ssh.get_transport(),
                                                                      keyvals['remoteHost'],
                                                                      keyvals['relFileName'],
                                                                      [])
            keyvals.update({ 'id': sessionId,
                             'sessionURL': 'ws://solaris/proxy?sessionId=' + sessionId,
                             'port': actualPort
                             })

        except Exception as inst :
            keyvals.update({'exception': inst})

        return keyvals


    #-------------------------------------------------------------------------
    # Use the remotely installed HPCJobScheduler python module to schedule an
    # HPC job.  Return the result, which either contains the job id
    # or an error message.
    #-------------------------------------------------------------------------
    def scheduleJob(self, params):
        # Get POST data parameters
        girderDir = params['girderDir']
        scriptDir = params['userHomeDir']
        jobDescriptor = params['jobDescriptor']
        jobString = params['jobString']
        connId = params['connId']

        # Generate a unique id so Girder can keep track of this job
        jobUuid = str(uuid.uuid1())

        # escape quotes around keys/values within the json string
        regex = re.compile('"')
        jobDescriptor = re.sub(regex, '\\\"', jobDescriptor)

        # This command gets run on the other end of the ssh connection
        commandStr = 'python ' + girderDir + '/HPCJobScheduler.py --command submit --scriptdir "' + scriptDir + '" --jobuniqueid "' + jobUuid + '" --jobdescriptor "' + jobDescriptor + '" --jobstring "' + jobString + '"'

        conn = self.remoteConnMgr.retrieve(connId)

        if conn is not None :
            returnTuple = conn.sendCommand(commandStr)
            returnVal = returnTuple[0][0]
            if not returnVal.startswith('ERROR') :
                # Did not get an error, so I strip ws/newline, add this
                # unique girder job id to the map, and return to the web
                # client both the girder job id as well as the hpc assigned
                # job id.
                regex = re.compile('^\s+|\s+$')
                returnVal = re.sub(regex, '', returnVal)
                self.currentJobsMap[jobUuid] = returnVal
                return { 'girderJobId': jobUuid, 'hpcJobId': returnVal }
            else :
                # Got an error, so be sure to remove the residual script file
                self.cleanupJob({'jobUuid': jobUuid,
                                 'girderDir': girderDir,
                                 'userHomeDir': scriptDir,
                                 'connId': connId})
                return returnVal

        else :
            return { 'ERROR': 'No such connection (' + connId + ')' }


    #-------------------------------------------------------------------------
    # Use the remotely installed HPCJobScheduler python module to check the
    # status of a job using it's assigned job id to look it up.
    #-------------------------------------------------------------------------
    def checkJobStatus(self, params):
        # Get parameters
        girderDir = params['girderDir']
        connId = params['connId']
        jobUuid = params['jobUuid']
        jobDescriptor = params['jobDescriptor']

        # Look up the assigned hpc job id
        hpcJobId = self.currentJobsMap[jobUuid]

        # escape quotes around keys/values within the json string
        regex = re.compile('"')
        jobDescriptor = re.sub(regex, '\\\"', jobDescriptor)

        # This command gets run on the other end of the ssh connection
        commandStr = 'python ' + girderDir + '/HPCJobScheduler.py --command status --scheduledjobid "' + hpcJobId + '" --jobdescriptor "' + jobDescriptor + '"'

        conn = self.remoteConnMgr.retrieve(params['connId'])

        if conn is not None :
            return conn.sendCommand(commandStr)
        else :
            return { 'ERROR': 'Connection was not retrievable' }


    #-------------------------------------------------------------------------
    # Use the remotely installed HPCJobScheduler python module to clean up
    # after a job.  Mainly, this means removing the generated job script file
    # from the remote file system.
    #-------------------------------------------------------------------------
    def cleanupJob(self, params):
        girderDir = params['girderDir']
        scriptDir = params['userHomeDir']
        jobUuid = params['jobUuid']
        connId = params['connId']

        # This command gets run on the other end of the ssh connection
        commandStr = 'python ' + girderDir + '/HPCJobScheduler.py --command cleanup --scriptdir "' + scriptDir + '" --jobuniqueid "' + jobUuid + '"'

        print 'Here is the command I will run to cleanup:'
        print commandStr

        conn = self.remoteConnMgr.retrieve(connId)

        if conn is not None :
            returnTuple = conn.sendCommand(commandStr)
            print 'Here is what I got back from the cleanup command:'
            print returnTuple
            self.currentJobsMap.pop('jobUuid', None)
            return { 'resultOutput': returnTuple }
        else :
            return { 'ERROR': 'No such connection (' + connId + ')' }


#-------------------------------------------------------------------------
# Extension logic for plugin goes in here
#-------------------------------------------------------------------------
def load(info):
    info['apiRoot'].remoteconnection = RemoteConnection()
