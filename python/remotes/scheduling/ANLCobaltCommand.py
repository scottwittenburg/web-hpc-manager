
from SchedulerCommand import SchedulerCommand

import shlex


class ANLCobaltCommand(SchedulerCommand):

    #-------------------------------------------------------------------------
    # Takes the json job descriptor and generates a command line string which
    # invokes the Cobalt 'qsub' program with the appropriate arguments.
    #
    # qsub -n 1 -t 5 -A SkySurvey -q pubnet /home/scott/script.sh
    #
    #-------------------------------------------------------------------------
    def generateSubmitCommand(self, jobDescriptor):
        cmdString = 'qsub'
        cmdString += ' -n ' + jobDescriptor['numberOfNodes']
        cmdString += ' -t ' + jobDescriptor['wallTime']
        cmdString += ' -A ' + jobDescriptor['project']
        cmdString += ' -q ' + jobDescriptor['queue']
        cmdString += ' ' + jobDescriptor['jobScriptFile']

        return shlex.split(str(cmdString))


    #-------------------------------------------------------------------------
    # Keeping this very simple for now, perhaps other arguments can be added
    # later to allow determination of how much time might be left before job
    # is ready, etc...
    #-------------------------------------------------------------------------
    def generateStatusCommand(self):
        return 'qstat'


    #-------------------------------------------------------------------------
    # Thus far, this isn't called, but is the hook which allows parsing the
    # specific output of the qstat program specific to the Cobalt job
    # job scheduler at ANL.
    #-------------------------------------------------------------------------
    def parseStatusOutput(self, statusOutput):
        result = {}
        result['jobid'] = '123456'
        result['status'] = 'queued'
        result['queuepos'] = '17'
        result['waittime'] = '128m'
        result['nodenames'] = 'vs98.tukey'
