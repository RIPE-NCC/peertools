'''
Classes used by peerweb
'''
import logging, time

from functools import wraps
from cherrypy import serving, expose
from utils import read_pass, encode
from routers import RouterHandle

log = logging.getLogger(__name__)

def expose_json(func):
    '''Decorate a method to automatically return json'''
    @wraps(func)
    def wrapper(*a, **kw):
        serving.response.headers['Content-Type'] = 'application/json'
        raw = func(*a, **kw)
        return encode(raw)

    return expose(wrapper)

class RouterData:
    '''Hold the cached results'''
    def __init__(self, handle):
        self.name = handle.host.replace('.ripe.net', '').replace('router.', '')
        self.state = 'uninitiated'
        self.updated = 0
        self.peers = []
        self.hardware = dict(vendor=None, model=None, serial=None)
        self.handle = handle

    def refresh(self):
        self.state = 'refreshing'

        try:
            start = time.time()

            with self.handle as con:
                self.peers = con.peers()
                for peer in self.peers:
                    peer.router = self.name
                self.hardware = con.hardware()
            
            self.updated = time.time() * 1000;
            self.state = 'ok in %.1fs' % (
                time.time() - start
                )
            log.info('%s: %s', self.name, self.state)
        except Exception, e:
            self.state = 'error: %s' % e.__class__.__name__
            log.error('error updating %s', self.name, exc_info=True)

    def _json(self):
        return {
            'name': self.name,
            'host': self.handle.host,
            'updated': self.updated,
            'state': self.state,
            'peers': len(self.peers),
            'hardware': self.hardware,
            'error': self.handle.error,
        }
