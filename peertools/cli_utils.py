'''
Classes used by peercli
'''

import getpass

_cache = dict()

def ask_pass(user=None):
    '''Request, cache and return a password for a user'''
    user = user or getpass.getuser()

    if user in _cache:
        return _cache['user']
    
    try:
        with open('.password') as f:
            return f.read()
    except Exception, e:
        _cache['user'] = getpass.getpass('\nPASSWORD for %s: ' % user)
        return _cache['user']

def box(words):
    '''print words in a box'''
    if words.startswith('\n'):
        words = words[1:]

    print '\n', '-' * 60, '\n', words, '\n', '-' * 60

def confirm_config(conf):
    '''Ask if a config is ok. Return True if OK'''
    box('config to apply')
    print conf
    if raw_input('> CONFIRM (y/n): ').strip()[:1] != 'y':
        print '> ABORTING'
        return False
    else:
        return True
