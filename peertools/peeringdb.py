'''
PeeringDB API
'''

import argparse, logging

from prettytable import PrettyTable

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, aliased, backref
from sqlalchemy.sql import func, select, text
from sqlalchemy import Column, Integer, ForeignKey, String, create_engine, or_

#### Globals ####

log = logging.getLogger(__name__)
db = None

def init(dburl, verbose):
    global db
    
    logging.getLogger('sqlalchemy.engine').level = logging.INFO if verbose else logging.WARN

    engine = create_engine(dburl)
    SqlSession = sessionmaker(bind=engine)
    db = SqlSession()
    db.execute("select true");
    log.info('ready dburl=%s', dburl)

#### Schema ####

class Base(declarative_base()):
    '''Base class for ORM with generic printing'''
    __abstract__ = True

    def __repr__(self):
        return "<{} {}>".format(
            self.__class__.__name__, 
            ', '.join(["%s=%r" % i for i in self.__dict__.items() if i[0][0] != '_'])
            )

class Exchange(Base):
    '''An exchange point'''
    __tablename__ = 'mgmtPublics'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    name_long = Column(String)
    tech_email = Column(String)
    policy_email = Column(String)
    website = Column(String)

class Network(Base):
    '''A network at an exchange point: Not Yet Used'''
    __tablename__ = 'mgmtPublicsIPs'

    id = Column(Integer, primary_key=True)
    public = Column(ForeignKey(Exchange.id))
    address = Column(String(128))

    exchange = relationship(Exchange, backref='networks', lazy='joined')

class Peer(Base):
    '''An ASN number'''
    __tablename__ = 'peerParticipants'
    
    id = Column(Integer, primary_key=True)
    asn = Column(Integer)
    name = Column(String)

class Contact(Base):
    '''Peer contacts'''
    __tablename__ = 'peerParticipantsContacts'
    
    id = Column(Integer, primary_key=True)
    peer_id = Column('participant_id', ForeignKey(Peer.id))
    name = Column(String(256))
    role = Column(String)
    email = Column(String)
    
    peer = relationship(Peer, backref=backref('contacts', lazy=True), lazy='joined')

class Router(Base):
    '''One peer's interface at one exchange'''
    __tablename__ = 'peerParticipantsPublics' 

    id = Column(Integer, primary_key=True)
    peer_id = Column('participant_id', ForeignKey(Peer.id))
    public_id = Column(ForeignKey(Exchange.id))
    addr = Column('local_ipaddr', String(32))
    
    # note: this field is always IPv4
    # protocol = Column(String(4))

    @property
    def ipver(self):
        return 6 if ':' in self.addr else 4
    
    exchange = relationship(Exchange, backref=backref('routers', lazy=True), lazy='joined')
    peer = relationship(Peer, backref=backref('routers', lazy=True), lazy='joined')

#### Functions ####

def search(text):
    '''Search for a peer by ASN or free-text search'''

    x = PrettyTable('ASN Name'.split())
    
    for row in db.query(Peer).filter(or_(
        Peer.asn.like('%{}%'.format(text)),
        Peer.name.like('%{}%'.format(text)))):
        x.add_row([row.asn, row.name])
   
    print x.get_string(align="l")

def info(peer):
    '''Show meta-info and routers for a peer'''
    x = PrettyTable('Exchange Address'.split())

    row = db.query(Peer).filter_by(asn=peer).one()
    print 'Name:', row.name
    print 'ASN:', row.asn

    for s in row.routers:
        x.add_row([s.exchange.name, s.addr])
    
    print x.get_string(align="l")

def common(left, right):
    '''find common peering points''' 
    l = aliased(Router)
    r = aliased(Router)
    
    x = PrettyTable(["Exchange", left, right])

    for row in db.query(l, r).filter(
            l.public_id == r.public_id,
            l.peer.has(asn=left),
            r.peer.has(asn=right)):
        if row[0].ipver == row[1].ipver:
            x.add_row([row[0].exchange.name, row[0].addr, row[1].addr])

    print x.get_string(align="l")

def all_possible(asn):
    '''List every possible peering in all our PoPs'''
    x = PrettyTable('exchange ipv4 ipv6'.split())
    x.align = 'l'
  
    q = text('''
        SELECT
            mgmtPublics.name AS "Name",
            SUM(peerParticipantsPublics.local_ipaddr NOT LIKE "%:%") AS "IPv4",
            SUM(peerParticipantsPublics.local_ipaddr LIKE "%:%") AS "IPv6"
        FROM 
            mgmtPublics
        JOIN
            peerParticipantsPublics ON mgmtPublics.id = public_id
        WHERE
            peerParticipantsPublics.local_ipaddr IS NOT NULL
            AND EXISTS (
                SELECT * from peerParticipantsPublics, peerParticipants
                WHERE mgmtPublics.id = public_id AND peerParticipants.id = participant_id AND asn = :asn
            )
        GROUP BY
            mgmtPublics.id
    ''')

    for row in db.execute(q, { 'asn': asn }):
        x.add_row(row)

    print x

def contacts(name):
    '''Get a list of contacts for a given PoP or ASN'''
    x = PrettyTable('thing role email'.split())
    x.align = 'l'
   
    where = or_(
        Peer.asn.like('%{}%'.format(name)),
        Peer.name.like('%{}%'.format(name)),
        Contact.name.like('%{}%'.format(name))
        )

    for row in db.query(Contact).join(Peer).filter(where):
        x.add_row([row.peer.name, row.role, "%s <%s>" % (row.name, row.email)])
    
    where = or_(
        Exchange.name.like('%{}%'.format(name)),
        Exchange.name_long.like('%{}%'.format(name)),
        Exchange.website.like('%{}%'.format(name)),
        )
    
    for row in db.query(Exchange).filter(where):
        x.add_row([row.name, 'tech', row.tech_email])
        x.add_row([row.name, 'policy', row.policy_email])
    
    print x

