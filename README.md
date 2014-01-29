# Peertools

peercli is a helper script for managing peerings on our routers.

peerweb is a monitoring component.

## Usage

> pip install peertools
> peercli router.host.name --help
> peerweb -c path/to/config.py

# Examples

> peercli router.host.name 12345 info 1.2.3.4
> peercli router.host.name 77777 summary

## Supported Routers

- Cisco IOS, Juniper JunOS, RHEL+Quagga

## TODO

- better peeringdb integration
- support for adding / removing peers
- configurable name mangling

## Example config.py

```python
'''
Peering Tools Config
'''

# optinally used to setup remote access on Juniper routers
PUBKEY = '''
ssh-rsa AAAA....Dw== name
'''

# tuples of hostname, ASN, optional password
ROUTERS = [
    ('host.fqdn.net', 12345), # no password needed
    ('host2.fqdn.net', 12345, 'password'),
]
```
