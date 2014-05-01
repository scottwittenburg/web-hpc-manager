
import paramiko
import uuid

##############################################################################
#                            RemoteConnection
##############################################################################
class RemoteConnection(object) :

    #-------------------------------------------------------------------------
    # Constructor
    #-------------------------------------------------------------------------
    def __init__(self, connectionParams) :
        """
        Constructor for a RemoteConnection.  The connectionParams object
        should at least have key 'fqhn', for 'fully qualified host name'.
        """
        self.ssh = None
        self.connected = False
        self.connObj = connectionParams

    #-------------------------------------------------------------------------
    # method to connect to remote machine
    #-------------------------------------------------------------------------
    def connect(self, name, passwd) :
        """
        Supply an ssh username and password to this function so it can
        attempt to connect to the remote machine.
        """
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(self.connObj['fqhn'],
                         username=name,
                         password=passwd,
                         allow_agent=False,
                         look_for_keys=False)
        self.connected = True

    #-------------------------------------------------------------------------
    # close the remote ssh connection
    #-------------------------------------------------------------------------
    def close(self) :
        """
        Close this remote connection.
        """
        if self.ssh is not None :
            self.ssh.close()
            self.ssh = None
            self.connected = False

    #-------------------------------------------------------------------------
    # issue a command on the remote host and return the output and error msgs
    # that may have resulted.
    #-------------------------------------------------------------------------
    def sendCommand(self, commandString) :
        """
        Send a command to be executed at the other end of the remote
        connection.  Some commands can cause this class to hang, these are
        typically ones that paginate results or have continuous output, like
        tail, top, more, etc...
        """
        if self.ssh is not None :
            ins, outs, errs = self.ssh.exec_command(commandString)
            stdout = outs.readlines()
            stderr = outs.readlines()
            return (stdout, stderr)
        return ('','')


##############################################################################
#                         RemoteConnectionManager
##############################################################################
class RemoteConnectionManager(object) :

    #-------------------------------------------------------------------------
    # Constructor
    #-------------------------------------------------------------------------
    def __init__(self) :
        """
        Constructs a new RemoteConnectionManager, setting it's dictionary of
        connections to the empty dict.
        """
        self.remoteConnections = {}

    #-------------------------------------------------------------------------
    # Create a connection, generate a unique id for it, store it by unique id
    # and return the id so users of this class can refer to the connection
    # later.
    #-------------------------------------------------------------------------
    def create(self, connectionParams) :
        """
        Creates a new RemoteConnection and returns an unique id for that
        connection which should be used to refer to it in the future.
        """
        conn = RemoteConnection(connectionParams)

        # Generate a unique id by which to refer to this connection in the future
        id = str(uuid.uuid1())

        self.remoteConnections[id] = conn
        return id

    #-------------------------------------------------------------------------
    # Retrieve a managed connection.
    #-------------------------------------------------------------------------
    def retrieve(self, connectionId) :
        """
        Returns the connection identified by the id.  Returns None if there is
        no such connection managed by this object.
        """
        conn = None

        try :
            conn = self.remoteConnections[connectionId]
        except :
            print 'Error retrieving connection with id ' + connectionId

        return conn
