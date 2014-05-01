

class SchedulerCommand(object):

    #-------------------------------------------------------------------------
    # The idea here is that when we want to add command string generation for
    # for other schedulers beyond the Argonne Cobalt scheduling system, then
    # we just need to write a new subclass which correctly implements the
    # generateCommand function, then add an "if" case in here that returns
    # an instance of the new subclass.
    #-------------------------------------------------------------------------
    def factory(cmdGenType):
        if cmdGenType == "ANLCobalt":
            from ANLCobaltCommand import ANLCobaltCommand
            return ANLCobaltCommand()
        assert 0, "Unknown command generator creation: " + cmdGenType

    factory = staticmethod(factory)

    #-------------------------------------------------------------------------
    # To be overridden by subclasses.  The generateCommand() function takes a
    # json object which can describe everything necessary to generate a 'qsub'
    # command for the target system.
    #-------------------------------------------------------------------------
    def generateSubmitCommand(self, jobDescriptor):
        pass

    def generateStatusCommand(self):
        pass

    def parseStatusOutput(self, statusOutput):
        pass
