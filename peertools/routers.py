#!/usr/bin/env python
'''
API for access to routers

see http://pexpect.sourceforge.net/pexpect.html

Always try to leave the console at the prompt
'''

import re, netaddr, pexpect, logging
import xml.etree.ElementTree as ET
import config, utils

log = logging.getLogger(__name__)

class RouterHandle(object):
    '''A context manager maintaining an open connection to a router'''

    def __init__(self, host, asn, password=None):
        self.host = host
        self.password = password
        self.asn = asn
        self.error = None
        self._socket = None
        self._pipe = utils.PipeLogger(logging.getLogger(self.host))

    def _connect(self):
        '''Try to connect to host (an IP or hostname) and return the correct Router object'''
        log.debug('connecting to %s', self.host)
        args = [ '-oProtocol=2,1', self.host ]
        
        con = pexpect.spawn('ssh', args)
        con.logfile_read = self._pipe
        con.timeout = 10

        i = con.expect([
            '[Pp]assword:',
            '\..+@.+\#',
            'Welcome to a RIS Cluster Machine',
            '^--- JUNOS',
            'Permission denied',
            pexpect.EOF,
            ])
        if i == 0:
            if self.password:
                con.sendline(self.password)
            else:
                raise RuntimeError('login failed: password required but not supplied')
            
            after = con.expect(['JUNOS'] + Cisco._prompts)
            if after == 0:
                # this expects a prompt next
                router = Juniper()
            else:
                router = Cisco()
        elif i == 1 or i == 2:
            router = Quagga()
        elif i == 3:
            # no password required
            router = Juniper()
        else:
            data = con.match.group() if con.match != pexpect.EOF else "NO MATCH"
            raise RuntimeError('login failed: %s: %s' % (self.host, con.before + data))
    
        if not router:
            raise RuntimeError('could not detect vendor: %s' % self.host)

        router.con = con
        router.our_asn = self.asn
        router.connect()
    
        # FIXME: remove hack when all RIS machines are equal
        if i == 2:
            router.prompt()

        return router

    def __enter__(self):
        '''Re-establish the connection if needed. Returns the connection object'''
        if self._socket:
            try:
                self._socket.cmd('')
                log.debug('reusing socket to %s', self.host)
                return self._socket
            except:
                self._socket = None

        log.info('opening socket to %s', self.host)
        try:
            self._socket = self._connect()
            return self._socket
        except Exception, e:
            self.error = e.__class__.__name__
            self._pipe.clear()
            raise

    def __exit__(self, type, value, traceback):
        if value:
            self.error = str(value)
            self._pipe.clear()

    def close(self):
        if self._socket:
            self._socket.close()
        self._socket = None

class Router:
    def cmd(self, cmd):
        '''run commands line-by-line and return the result'''
        result = ''

        cmd = cmd.strip().splitlines()
        if not cmd:
            cmd = [ '' ]

        for line in cmd:
            try:
                # discard remaining data to avoid desyncronization
                self.con.read_nonblocking(size=99999, timeout=0.01)
            except pexpect.TIMEOUT:
                pass # good
            log.debug('typing %r', line.strip())
            self.con.sendline(line.strip())
            result += self.prompt()

        return result
    
    def prompt(self):
        '''wait for a prompt and return what comes before'''
        try:
            self.con.expect(self._prompts)
        except:
            log.error('error waiting for prompt')
            raise

        return self.con.before

    def del_peer(self, group, ip):
        return self._del_peer.format(
                our_asn=self._format_asn(self.our_asn),
                group=group,
                ip=ip)
    
    def add_peer(self, group, ip, asn, desc):
        return self._add_peer.format(
                our_asn=self._format_asn(self.our_asn),
                group=group,
                ip=ip,
                asn=self._format_asn(asn),
                desc=desc)

    def _format_asn(self, asn):
        return str(asn)

class Juniper(Router):
    _prompts = [ '\n\S+@\S+(>|#)' ]
    _add_peer = '''
        edit protocols bgp group {group} neighbor {ip}
        set peer-as {asn}
        set description "{desc}"
    '''
    _del_peer = '''
        delete protocols bgp group {group} neighbor {ip}
    '''
    _setup = '''
        edit system login class rancid
        set permissions [ access admin firewall flow-tap interface network routing secret security snmp system trace view ]
        top
        edit system login user rancid
        set class rancid
        set authentication ssh-rsa "{pubkey}"
    '''

    def connect(self):
        self.prompt()
        self.cmd('set cli screen-length 0')
        self.cmd('set cli screen-width 0')

    def peer_info(self, ip):
        info = {}

        info['ping'] = self.cmd('ping %s count 1 wait 1' % ip),
        info['summary'] = self.cmd('show bgp neighbor %s | match "Peer:|Type:|messages:|Last"' % ip)
        
        tolerant_ip = re.sub('::', ':[0:]*:', str(ip))
       
        info['config'] = self.cmd('show configuration | display set | match %s' % tolerant_ip)
        info['log'] = self.cmd('show log bgp | match %s | last 10' % tolerant_ip)
        info['log2'] = self.cmd('show log messages | match %s | last 10' % tolerant_ip)
        return info
   
    def groups(self):
        return self.cmd('show bgp group brief | match "Name: ."')
       
    def apply_config(self, conf):
        self.cmd("conf")
        self.cmd(conf)
        self.con.sendline("commit and-quit")
        self.con.expect("commit complete", timeout=15)
        self.prompt()

    def peers(self):
        peers = []

        self.con.sendline('show bgp summary | display xml')
        self.con.expect('<rpc-reply.*</rpc-reply>')
        xml = self.con.match.group()
        xml = re.sub('xmlns="[^"]+"', '', xml)
        self.prompt()
        root = ET.fromstring(xml)
        for node in root.findall('*/bgp-peer'):
            peer = utils.Peer()
            peer.ip = node.findtext('peer-address')
            peer.asn = int(node.findtext('peer-as'))
            peer.last_change = node.findtext('elapsed-time')
            peer.state = node.findtext('peer-state')
            
            if node.findall('bgp-rib'):
                peer.ver = 6 if 'inet6' in node.findtext('bgp-rib/name') else 4
                peer.prefixes = node.findtext('bgp-rib/received-prefix-count')

            peers.append(peer)
    
        return peers

    def hardware(self):
        '''
        Example:

        Hardware inventory:
        Item             Version  Part number  Serial number     Description
        Chassis                                J8025             M7I
        Midplane         REV 06   710-008761   AABH6555          M7i Midplane
        '''
        self.con.sendline('show chassis hardware')
        self.con.expect('Chassis\s+(\w+)\s+(\w+)')
        info = {
            'vendor': 'Juniper',
            'model': self.con.match.group(2),
            'serial': self.con.match.group(1),
        }
        self.prompt()
        return info
    
    def setup(self, enable_password=None):
        self.apply_config(self._setup.format(pubkey=config.PUBKEY.strip()))

    def close(self):
        self.con.sendline('exit')
        self.con.expect(pexpect.EOF)

class Quagga(Router):
    _prompts = [
            '\n\S+#', # in vtysh: rrc05.ripe.net# 
            '\n[^ ]*\[\S+@\S+ \S+\]#', # in shell: \x1b]0;...[root@rrc05 ~]#
            ]
    _add_peer = '''
        router bgp {our_asn}
        neighbor {ip} remote-as {asn}
        neighbor {ip} description {desc}
        address-family ipv{ip.version}
        neighbor {ip} peer-group {group}
    '''
    _del_peer = '''
        router bgp {our_asn}
        no neighbor {c.ip}
    '''
    def connect(self):
        pass
    
    def setup(self, enable_password):
        self.con.sendline('enable')
        self.con.expect('Password:')
        self.con.sendline(enable_password)

    def peers(self):
        peers = []
        for line in self.cmd('vtysh -c "show ip bgp summary"').splitlines():
            peers.append(parse_cisco_peer_summary_line(line))
        
        return filter(None, peers) 

    def peer_info(self, ip):
        info = {}
        if ip.version == 6:
            info['ping'] = self.cmd('ping6 -c1 -w1 %s' % ip)
        else:
            info['ping'] = self.cmd('ping -c1 -w1 %s' % ip)
        
        info['summary'] = self.cmd('vtysh -c "show bgp neighbors %s" | egrep "BGP|Desc|Member|Last|Current|prefixes|family"' % ip)
        
        ip = str(ip).replace('::', ':[:0]*:')
        info['config'] = self.cmd('vtysh -c "show running-config" | egrep "%s|address-family"' % ip)
        return info

    def groups(self):
        return self.cmd('vtysh -c "show running-config" | egrep "peer-group$"')
       
    def apply_config(self, conf):
        self.cmd("vtysh")
        self.cmd("conf terminal")
        self.cmd(conf)
        self.cmd("end")
        self.cmd("copy running-config startup-config")
        self.cmd("exit")
    
    def hardware(self):
        return {
                'vendor': 'Quagga',
                'model': 'Linux',
                'serial': '??????',
        }

    def close(self):
        self.con.send('\n~.')
        self.con.expect(pexpect.EOF)

class Cisco(Router):
    _prompts = ['(^|\n)\S+[#>]']
    _add_peer = '''
        router bgp {our_asn}
        address-family ipv{ip.version}
        neighbor {ip} remote-as {asn}
        neighbor {ip} peer-group {group}
        neighbor {ip} description {desc}
        neighbor {ip} activate
    '''
    _del_peer = '''
        router bgp {our_asn}
        address-family ipv{ip.version}
        no neighbor {ip}
    '''
    _setup = '''
        aaa authentication login default local group radius
        aaa authorization exec default local group radius if-authenticated 
       
        username rancid privilage 15 secret 5 $1$M1I6$M9Tgi8ZCUiDbrlrz7PpVx.
        
        privilege router all level 5 address-family
        privilege configure level 5 router
        privilege exec level 5 write
        privilege exec level 5 copy running-config startup-config
        privilege exec level 5 configure terminal
        privilege exec all level 5 ping
    '''
    
    def peers(self):
        peers = []
        for line in self.cmd('show ip bgp summary').splitlines():
            peers.append(parse_cisco_peer_summary_line(line))
        
        return filter(None, peers) 

    def connect(self): 
        self.cmd('terminal length 0')
        self.cmd('terminal no editing')

    def summary(self):
        info = {}
        info['addr'] = self.cmd('show config | i ipv*6* address')
        return info
        
    def peer_info(self, ip):
        info = {}
        info['ping'] = self.cmd('ping %s repeat 1 timeout 1' % ip)
        info['summary'] = self.cmd('show bgp ipv%s unicast neighbors %s | include BGP|Desc|Member|Last|Current' % (ip.version, str(ip).upper()))
        info['config'] = self.cmd('show config | i %s|^ address' % str(ip).upper())
        info['logs'] = self.cmd('show logging | i %s' % str(ip).upper())
        return info

    def setup(self, enable_password):
        self.con.sendline('enable')
        self.con.expect('Password:')
        self.con.sendline(enable_password)
        self.prompt()
        self.apply_config(self._setup)

    def close(self):
        self.con.sendline('exit')
        self.con.expect(pexpect.EOF)

    def apply_config(self, conf):
        self.cmd('configure terminal')
        self.cmd(conf)
        self.con.sendcontrol('z')
        self.prompt()
        self.con.sendline('copy running-config startup-config')
        self.con.expect('Destination filename .*\?')
        self.con.sendline('')
        self.con.expect('OK')
        self.prompt()
    
    def groups(self):
        return self.cmd('show config | i peer-group$')
    
    def hardware(self):
        '''
        Example:

        NAME: "Chassis", DESCR: "Cisco 7301 single-slot chassis"
        PID: Cisco7301         , VID:    , SN: 74852456
        '''
        self.con.sendline('show inventory')
        self.con.expect('PID: (\w*) *, VID: .*, SN: (\w+)')
        info = {
            'vendor': 'Cisco',
            'model': self.con.match.group(1),
            'serial': self.con.match.group(2),
        }
        self.prompt()
        return info

    def _format_asn(self, asn):
        if asn > 65536:
            return "%s.%s" % (197000/65536, 197000%65536)
        else:
            return str(asn)

def parse_cisco_peer_summary_line(line):
    '''
    Example:
    
    Neighbor        V    AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
    12.0.1.63       4  7018 4336594   15901        0    0    0 02w0d16h   469820
    '''
    pattern = '''
        ^([\d.]+)\s+  # Neighbor
        (4|6)\s+      # version
        ([\d.]+)\s+      # AS Number
        (?:\d+\s+){5} # MsgRcvd, MsgSent, TblVer, InQ, OutQ
        ([\w:]+)\s+      # last state change
        (\w+)\s*$     # State/PfxRcd
    '''
    m = re.match(pattern, line, re.VERBOSE)
    if not m:
        return

    peer = utils.Peer()
    peer.ip = m.group(1)
    peer.ver = m.group(2)
    peer.asn = m.group(3)
    peer.last_change = m.group(4)
    try:
        peer.prefixes = int(m.group(5))
        peer.state = 'Established'
    except ValueError:
        peer.state = m.group(5)
    
    return peer

