
import json, re, os, sys, subprocess

from SchedulerCommand import SchedulerCommand

try:
    import argparse
except ImportError:
    # since  Python 2.6 and earlier don't have argparse, we simply provide
    # the source for the same as _argparse and we use it instead.
    import _argparse as argparse

###
### TODO: This class needs configurable logging to a log file so we
### can get important error condition messages recording as well as
### turn on debugging
###

class HPCJobScheduler(object) :

    #-------------------------------------------------------------------------
    # Constructor for the HPCJobScheduler
    #-------------------------------------------------------------------------
    def __init__(self) :
        ### TODO: this should be moved into the system specific subclasses
        ### of SchedulerCommand
        self.qsubOutputRegex = re.compile('^([\d]+)$')


    #-------------------------------------------------------------------------
    # Write the script file which the scheduler should run
    #-------------------------------------------------------------------------
    def writeScriptFile(self, scriptDir, jobUniqueId, jobString):
        filename = jobUniqueId + '.sh'
        scriptFilePath = os.path.join(scriptDir, filename)

        # Want newlines in the script, but not in the command line args
        nlRegex = re.compile('%0A')
        jobString = re.sub(nlRegex, '\n', jobString)

        with open(scriptFilePath, 'w') as scriptWriter:
            scriptWriter.write(jobString)

        # make sure the script file is executable
        os.chmod(scriptFilePath, 0755);

        return scriptFilePath


    #-------------------------------------------------------------------------
    # Remove the script file which the scheduler ran, now that it's done
    #-------------------------------------------------------------------------
    def removeScriptFile(self, scriptDir, jobUniqueId):
        filename = jobUniqueId + '.sh'
        scriptFilePath = os.path.join(scriptDir, filename)
        os.remove(scriptFilePath)


    #-------------------------------------------------------------------------
    # The only cleanup I can think of currently is removing the script file
    # we generated as a part of the scheduling process.  But other things may
    # come up down the road.
    #-------------------------------------------------------------------------
    def cleanupAfterJob(self, scriptDir, jobUniqueId):
        self.removeScriptFile(scriptDir, jobUniqueId)


    #-------------------------------------------------------------------------
    # Called the schedule command, look through the output, find the job id
    # and return it.
    #-------------------------------------------------------------------------
    def scheduleJob(self, scriptDir, jobUniqueId, jobDescriptor, jobString):
        # Generate the script file
        scriptFilePath = self.writeScriptFile(scriptDir, jobUniqueId, jobString)

        # Update the job descriptor with the path to the generated script
        jobDescriptor['jobScriptFile'] = scriptFilePath

        # Generate the job scheduler command
        schedulerType = jobDescriptor['schedulerType']
        generator = SchedulerCommand.factory(schedulerType)
        command = generator.generateSubmitCommand(jobDescriptor)

        # Now run the generated command
        try :
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            outputTuple = process.communicate(None)
            output = outputTuple[0]
            error = outputTuple[1]
        except subprocess.CalledProcessError as inst :
            return 'ERROR: ' + str(inst)

        # Now look for the job id in the output
        outArray = output.split('\n')
        for line in outArray :
            m = self.qsubOutputRegex.match(line)
            if m :
                return m.group(1)

        return 'ERROR: ' + error + ', OUTPUT: ' + output


    #-------------------------------------------------------------------------
    # Called the job status command, look through the output for the line that
    # starts with the jobid, then grab out the status and any information
    # about the hostname that was provided.
    #-------------------------------------------------------------------------
    def getJobStatus(self, jobId, jobDescriptor) :

        # Generate the job status command
        schedulerType = jobDescriptor['schedulerType']
        generator = SchedulerCommand.factory(schedulerType)
        command = generator.generateStatusCommand()

        try :
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            outputTuple = process.communicate(None)
            output = outputTuple[0]
        except subprocess.CalledProcessError as inst :
            return 'ERROR: ' + str(inst)

        # Now find the line of output corresponding to our job
        #       235364  scottwit  00:05:00  1      starting  vs64.tukey
        matcher = re.compile('^' + str(jobId) + '\s+([^\s]+)\s+([^\s]+)\s+([^\s]+)\s+([^\s]+)\s+([^\s]+)\s*$')

        outArray = output.split('\n')
        for line in outArray :
            m = matcher.match(line)
            if m :
                return json.dumps([ m.group(4), {'hostnames': m.group(5)} ])

        return json.dumps([ 'NO_SUCH_JOB', { 'problem': 'Unable to find job id in status list' } ])


def mainEntryPoint():
    p = argparse.ArgumentParser("Interact with job scheduler on HPC systems")

    p.add_argument("--command",
                   type=str,
                   default="submit",
                   help="One of 'submit', 'status', or 'cleanup'")
    p.add_argument("--scriptdir",
                   type=str,
                   default="",
                   help="The path to where the job script should be written to (or deleted from)")
    p.add_argument("--jobuniqueid",
                   type=str,
                   default="",
                   help="The unique id of the job, generated outside the scheduling system, is used to name the generated job script that should be run")
    p.add_argument("--scheduledjobid",
                   type=str,
                   default="",
                   help="The job id given by the scheduler.  This should be used with the job status command.")
    p.add_argument("--jobdescriptor",
                   type=str,
                   default="",
                   help="Json string describing the parameters for the target HPC job scheduler")
    p.add_argument("--jobstring",
                   type=str,
                   default="",
                   help="Contents of the job script file to be written and then scheduled to run")

    args = p.parse_args()

    # If we got a job descriptor, parse the string into a json object
    if args.jobdescriptor :
        jobDescriptor = json.loads(args.jobdescriptor)

    # Create the HPCJobScheduler
    scheduler = HPCJobScheduler()

    # Perform the appropriate command
    if args.command == 'submit' :
        jobId = scheduler.scheduleJob(args.scriptdir,
                                      args.jobuniqueid,
                                      jobDescriptor,
                                      args.jobstring)
        print jobId
    elif args.command == 'status' :
        statTuple = scheduler.getJobStatus(args.scheduledjobid,
                                           jobDescriptor)
        print statTuple
    elif args.command == 'cleanup' :
        result = scheduler.cleanupAfterJob(args.scriptdir,
                                           args.jobuniqueid)
        print result
    else :
        print 'ERROR: Unrecognized command: ' + args.command

###
### Main script, to run from command line
###
if __name__ == "__main__" :

    try :
        mainEntryPoint()
    except Exception as inst:
        print 'Caught exception: '
        print inst
