'''
Misc Support Functions
'''

import json, signal, sys, traceback, cherrypy, logging, os

log = logging.getLogger(__name__)

class Peer:
    def __init__(self):
        self.ip = None
        self.ver = None
        self.asn = None
        self.last_change = None
        self.state = None
        self.prefixes = None

    def __str__(self):
        return str(self.__dict__)

def default(obj):
    try:
        if hasattr(obj, '_json'):
            return obj._json()
        return obj.__dict__
    except AttributeError:
        return repr(obj)

def encode(obj):
    return json.dumps(obj, default=default, indent=4)

def read_pass():
    '''Read a password from .password'''
    try:
        with open('.password') as f:
            return f.read()
    except Exception, e:
        raise Exception('cannot read password: %s' % e)

class PipeLogger:
    '''Intercepts a file-like object and logs complete lines'''
    def __init__(self, logger):
        self.data = ""
        self.logger = logger

    def write(self, more):
        self.data += more
        while '\n' in self.data:
            line, self.data = self.data.split('\n', 1)
            self.logger.debug('| %s', line.replace(' \r', ''))

    def clear(self):
        if self.data:
            self.logger.error('! ERROR: exiting uncleanly. Remaining data: %r', self.data)

    def flush(self):
        pass

def thread_dump(signum, frame):
    print >> sys.stderr, "\n*** STACKTRACE - START ***\n"
    code = []
    for threadId, stack in sys._current_frames().items():
        code.append("\n# ThreadID: %s" % threadId)
        for filename, lineno, name, line in traceback.extract_stack(stack):
            code.append('File: "%s", line %d, in %s' % (filename,
                                                        lineno, name))
            if line:
                code.append("  %s" % (line.strip()))

    for line in code:
        print >> sys.stderr, line
    print >> sys.stderr, "\n*** STACKTRACE - END ***\n"

def exit():
    '''force exit because it is more user friendly'''
    log.warn('exiting')
    os._exit(0)

def register_signal_handlers():
    signal.signal(signal.SIGUSR2, thread_dump)
   
    cherrypy.engine.signal_handler.handlers['SIGTERM'] = exit
    cherrypy.engine.signal_handler.handlers['SIGINT'] = exit

