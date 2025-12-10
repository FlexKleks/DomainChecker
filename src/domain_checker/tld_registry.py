"""
TLD Registry - Comprehensive list of supported TLDs with RDAP/WHOIS endpoints.

This module contains configurations for 100+ TLDs including:
- Generic TLDs (gTLDs): .com, .net, .org, .info, etc.
- Country Code TLDs (ccTLDs): .de, .uk, .fr, .jp, etc.
- New gTLDs: .app, .dev, .io, .xyz, etc.
"""

from .config import TLDConfig

# RDAP fallback for TLDs without native RDAP
RDAP_FALLBACK = "https://rdap.org/domain/"

# ============================================================================
# GENERIC TLDs (gTLDs)
# ============================================================================
GENERIC_TLDS = [
    TLDConfig(tld="com", rdap_endpoint="https://rdap.verisign.com/com/v1/domain/", whois_server="whois.verisign-grs.com", whois_enabled=True),
    TLDConfig(tld="net", rdap_endpoint="https://rdap.verisign.com/net/v1/domain/", whois_server="whois.verisign-grs.com", whois_enabled=True),
    TLDConfig(tld="org", rdap_endpoint="https://rdap.publicinterestregistry.org/rdap/domain/", whois_server="whois.pir.org", whois_enabled=True),
    TLDConfig(tld="info", rdap_endpoint="https://rdap.afilias.net/rdap/info/domain/", whois_server="whois.afilias.net", whois_enabled=True),
    TLDConfig(tld="biz", rdap_endpoint="https://rdap.nic.biz/domain/", whois_server="whois.nic.biz", whois_enabled=True),
    TLDConfig(tld="name", rdap_endpoint="https://rdap.verisign.com/name/v1/domain/", whois_server="whois.nic.name", whois_enabled=True),
    TLDConfig(tld="mobi", rdap_endpoint="https://rdap.afilias.net/rdap/mobi/domain/", whois_server="whois.afilias.net", whois_enabled=True),
    TLDConfig(tld="pro", rdap_endpoint="https://rdap.afilias.net/rdap/pro/domain/", whois_server="whois.afilias.net", whois_enabled=True),
]


# ============================================================================
# NEW gTLDs - Tech & Startup
# ============================================================================
TECH_TLDS = [
    TLDConfig(tld="io", rdap_endpoint="https://rdap.nic.io/domain/", whois_server="whois.nic.io", whois_enabled=True),
    TLDConfig(tld="co", rdap_endpoint="https://rdap.nic.co/domain/", whois_server="whois.nic.co", whois_enabled=True),
    TLDConfig(tld="app", rdap_endpoint="https://rdap.nic.google/domain/", whois_server="whois.nic.google", whois_enabled=True),
    TLDConfig(tld="dev", rdap_endpoint="https://rdap.nic.google/domain/", whois_server="whois.nic.google", whois_enabled=True),
    TLDConfig(tld="ai", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.nic.ai", whois_enabled=True),
    TLDConfig(tld="tech", rdap_endpoint="https://rdap.centralnic.com/tech/domain/", whois_server="whois.centralnic.com", whois_enabled=True),
    TLDConfig(tld="cloud", rdap_endpoint="https://rdap.nic.cloud/domain/", whois_server="whois.nic.cloud", whois_enabled=True),
    TLDConfig(tld="digital", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="software", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="systems", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="network", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="solutions", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="agency", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="studio", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="design", rdap_endpoint="https://rdap.centralnic.com/design/domain/", whois_server="whois.centralnic.com", whois_enabled=True),
    TLDConfig(tld="media", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
]


# ============================================================================
# NEW gTLDs - Popular & Generic
# ============================================================================
POPULAR_NEW_TLDS = [
    TLDConfig(tld="xyz", rdap_endpoint="https://rdap.nic.xyz/domain/", whois_server="whois.nic.xyz", whois_enabled=True),
    TLDConfig(tld="online", rdap_endpoint="https://rdap.centralnic.com/online/domain/", whois_server="whois.centralnic.com", whois_enabled=True),
    TLDConfig(tld="site", rdap_endpoint="https://rdap.centralnic.com/site/domain/", whois_server="whois.centralnic.com", whois_enabled=True),
    TLDConfig(tld="store", rdap_endpoint="https://rdap.centralnic.com/store/domain/", whois_server="whois.centralnic.com", whois_enabled=True),
    TLDConfig(tld="shop", rdap_endpoint="https://rdap.nic.shop/domain/", whois_server="whois.nic.shop", whois_enabled=True),
    TLDConfig(tld="club", rdap_endpoint="https://rdap.nic.club/domain/", whois_server="whois.nic.club", whois_enabled=True),
    TLDConfig(tld="live", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="life", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="world", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="today", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="space", rdap_endpoint="https://rdap.centralnic.com/space/domain/", whois_server="whois.centralnic.com", whois_enabled=True),
    TLDConfig(tld="fun", rdap_endpoint="https://rdap.centralnic.com/fun/domain/", whois_server="whois.centralnic.com", whois_enabled=True),
    TLDConfig(tld="top", rdap_endpoint="https://rdap.nic.top/domain/", whois_server="whois.nic.top", whois_enabled=True),
    TLDConfig(tld="vip", rdap_endpoint="https://rdap.nic.vip/domain/", whois_server="whois.nic.vip", whois_enabled=True),
    TLDConfig(tld="one", rdap_endpoint="https://rdap.nic.one/domain/", whois_server="whois.nic.one", whois_enabled=True),
    TLDConfig(tld="blog", rdap_endpoint="https://rdap.nic.blog/domain/", whois_server="whois.nic.blog", whois_enabled=True),
    TLDConfig(tld="news", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="email", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="link", rdap_endpoint="https://rdap.uniregistry.net/rdap/domain/", whois_server="whois.uniregistry.net", whois_enabled=True),
    TLDConfig(tld="click", rdap_endpoint="https://rdap.uniregistry.net/rdap/domain/", whois_server="whois.uniregistry.net", whois_enabled=True),
]


# ============================================================================
# EUROPEAN ccTLDs
# ============================================================================
EUROPE_TLDS = [
    TLDConfig(tld="de", rdap_endpoint="https://rdap.denic.de/domain/", whois_server="whois.denic.de", whois_enabled=True),
    TLDConfig(tld="eu", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.eu", whois_enabled=True),
    TLDConfig(tld="at", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.nic.at", whois_enabled=True),
    TLDConfig(tld="ch", rdap_endpoint="https://rdap.nic.ch/domain/", whois_server="whois.nic.ch", whois_enabled=True),
    TLDConfig(tld="li", rdap_endpoint="https://rdap.nic.ch/domain/", whois_server="whois.nic.li", whois_enabled=True),
    TLDConfig(tld="nl", rdap_endpoint="https://rdap.sidn.nl/domain/", whois_server="whois.sidn.nl", whois_enabled=True),
    TLDConfig(tld="be", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.dns.be", whois_enabled=True),
    TLDConfig(tld="fr", rdap_endpoint="https://rdap.nic.fr/domain/", whois_server="whois.nic.fr", whois_enabled=True),
    TLDConfig(tld="it", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.nic.it", whois_enabled=True),
    TLDConfig(tld="es", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.nic.es", whois_enabled=True),
    TLDConfig(tld="pt", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.dns.pt", whois_enabled=True),
    TLDConfig(tld="pl", rdap_endpoint="https://rdap.dns.pl/domain/", whois_server="whois.dns.pl", whois_enabled=True),
    TLDConfig(tld="cz", rdap_endpoint="https://rdap.nic.cz/domain/", whois_server="whois.nic.cz", whois_enabled=True),
    TLDConfig(tld="sk", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.sk-nic.sk", whois_enabled=True),
    TLDConfig(tld="hu", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.nic.hu", whois_enabled=True),
    TLDConfig(tld="ro", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.rotld.ro", whois_enabled=True),
    TLDConfig(tld="bg", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.register.bg", whois_enabled=True),
    TLDConfig(tld="hr", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.dns.hr", whois_enabled=True),
    TLDConfig(tld="si", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.register.si", whois_enabled=True),
    TLDConfig(tld="rs", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.rnids.rs", whois_enabled=True),
    TLDConfig(tld="gr", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.ics.forth.gr", whois_enabled=True),
    TLDConfig(tld="tr", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.nic.tr", whois_enabled=True),
]


# ============================================================================
# NORDIC ccTLDs
# ============================================================================
NORDIC_TLDS = [
    TLDConfig(tld="se", rdap_endpoint="https://rdap.iis.se/domain/", whois_server="whois.iis.se", whois_enabled=True),
    TLDConfig(tld="dk", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.dk-hostmaster.dk", whois_enabled=True),
    TLDConfig(tld="no", rdap_endpoint="https://rdap.norid.no/domain/", whois_server="whois.norid.no", whois_enabled=True),
    TLDConfig(tld="fi", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.fi", whois_enabled=True),
    TLDConfig(tld="is", rdap_endpoint="https://rdap.isnic.is/domain/", whois_server="whois.isnic.is", whois_enabled=True),
]

# ============================================================================
# UK & IRELAND
# ============================================================================
UK_TLDS = [
    TLDConfig(tld="uk", rdap_endpoint="https://rdap.nominet.uk/uk/domain/", whois_server="whois.nic.uk", whois_enabled=True),
    TLDConfig(tld="co.uk", rdap_endpoint="https://rdap.nominet.uk/uk/domain/", whois_server="whois.nic.uk", whois_enabled=True),
    TLDConfig(tld="org.uk", rdap_endpoint="https://rdap.nominet.uk/uk/domain/", whois_server="whois.nic.uk", whois_enabled=True),
    TLDConfig(tld="me.uk", rdap_endpoint="https://rdap.nominet.uk/uk/domain/", whois_server="whois.nic.uk", whois_enabled=True),
    TLDConfig(tld="ie", rdap_endpoint="https://rdap.weare.ie/domain/", whois_server="whois.iedr.ie", whois_enabled=True),
]

# ============================================================================
# AMERICAS
# ============================================================================
AMERICAS_TLDS = [
    TLDConfig(tld="us", rdap_endpoint="https://rdap.nic.us/domain/", whois_server="whois.nic.us", whois_enabled=True),
    TLDConfig(tld="ca", rdap_endpoint="https://rdap.ca.fury.ca/rdap/domain/", whois_server="whois.cira.ca", whois_enabled=True),
    TLDConfig(tld="mx", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.mx", whois_enabled=True),
    TLDConfig(tld="br", rdap_endpoint="https://rdap.registro.br/domain/", whois_server="whois.registro.br", whois_enabled=True),
    TLDConfig(tld="ar", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.nic.ar", whois_enabled=True),
    TLDConfig(tld="cl", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.nic.cl", whois_enabled=True),
    TLDConfig(tld="co", rdap_endpoint="https://rdap.nic.co/domain/", whois_server="whois.nic.co", whois_enabled=True),
    TLDConfig(tld="pe", rdap_endpoint=RDAP_FALLBACK, whois_server="kero.yachay.pe", whois_enabled=True),
]


# ============================================================================
# ASIA PACIFIC
# ============================================================================
ASIA_PACIFIC_TLDS = [
    TLDConfig(tld="au", rdap_endpoint="https://rdap.auda.org.au/domain/", whois_server="whois.auda.org.au", whois_enabled=True),
    TLDConfig(tld="com.au", rdap_endpoint="https://rdap.auda.org.au/domain/", whois_server="whois.auda.org.au", whois_enabled=True),
    TLDConfig(tld="nz", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.srs.net.nz", whois_enabled=True),
    TLDConfig(tld="jp", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.jprs.jp", whois_enabled=True),
    TLDConfig(tld="cn", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.cnnic.cn", whois_enabled=True),
    TLDConfig(tld="hk", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.hkirc.hk", whois_enabled=True),
    TLDConfig(tld="tw", rdap_endpoint="https://rdap.twnic.tw/rdap/domain/", whois_server="whois.twnic.net.tw", whois_enabled=True),
    TLDConfig(tld="kr", rdap_endpoint="https://rdap.kr/rdap/domain/", whois_server="whois.kr", whois_enabled=True),
    TLDConfig(tld="in", rdap_endpoint="https://rdap.registry.in/domain/", whois_server="whois.registry.in", whois_enabled=True),
    TLDConfig(tld="sg", rdap_endpoint="https://rdap.sgnic.sg/domain/", whois_server="whois.sgnic.sg", whois_enabled=True),
    TLDConfig(tld="my", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.mynic.my", whois_enabled=True),
    TLDConfig(tld="th", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.thnic.co.th", whois_enabled=True),
    TLDConfig(tld="id", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.id", whois_enabled=True),
    TLDConfig(tld="ph", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.dot.ph", whois_enabled=True),
    TLDConfig(tld="vn", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.vnnic.vn", whois_enabled=True),
]

# ============================================================================
# MIDDLE EAST & AFRICA
# ============================================================================
MEA_TLDS = [
    TLDConfig(tld="ae", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.aeda.net.ae", whois_enabled=True),
    TLDConfig(tld="sa", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.nic.net.sa", whois_enabled=True),
    TLDConfig(tld="il", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.isoc.org.il", whois_enabled=True),
    TLDConfig(tld="za", rdap_endpoint="https://rdap.registry.net.za/rdap/domain/", whois_server="whois.registry.net.za", whois_enabled=True),
    TLDConfig(tld="ng", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.nic.net.ng", whois_enabled=True),
    TLDConfig(tld="ke", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.kenic.or.ke", whois_enabled=True),
    TLDConfig(tld="eg", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.ripe.net", whois_enabled=True),
    TLDConfig(tld="ma", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.registre.ma", whois_enabled=True),
]


# ============================================================================
# EASTERN EUROPE & CIS
# ============================================================================
CIS_TLDS = [
    TLDConfig(tld="ru", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.tcinet.ru", whois_enabled=True),
    TLDConfig(tld="ua", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.ua", whois_enabled=True),
    TLDConfig(tld="by", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.cctld.by", whois_enabled=True),
    TLDConfig(tld="kz", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.nic.kz", whois_enabled=True),
    TLDConfig(tld="uz", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.cctld.uz", whois_enabled=True),
]

# ============================================================================
# SPECIAL / POPULAR ALTERNATIVE TLDs
# ============================================================================
SPECIAL_TLDS = [
    TLDConfig(tld="me", rdap_endpoint="https://rdap.nic.me/domain/", whois_server="whois.nic.me", whois_enabled=True),
    TLDConfig(tld="tv", rdap_endpoint="https://rdap.verisign.com/tv/v1/domain/", whois_server="whois.nic.tv", whois_enabled=True),
    TLDConfig(tld="cc", rdap_endpoint="https://rdap.verisign.com/cc/v1/domain/", whois_server="ccwhois.verisign-grs.com", whois_enabled=True),
    TLDConfig(tld="ws", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.website.ws", whois_enabled=True),
    TLDConfig(tld="fm", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.nic.fm", whois_enabled=True),
    TLDConfig(tld="gg", rdap_endpoint="https://rdap.gg/domain/", whois_server="whois.gg", whois_enabled=True),
    TLDConfig(tld="to", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.tonic.to", whois_enabled=True),
    TLDConfig(tld="la", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.nic.la", whois_enabled=True),
    TLDConfig(tld="ly", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.nic.ly", whois_enabled=True),
    TLDConfig(tld="vc", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.afilias-grs.info", whois_enabled=True),
    TLDConfig(tld="gl", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.nic.gl", whois_enabled=True),
    TLDConfig(tld="im", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.nic.im", whois_enabled=True),
    TLDConfig(tld="sh", rdap_endpoint="https://rdap.nic.sh/domain/", whois_server="whois.nic.sh", whois_enabled=True),
    TLDConfig(tld="ac", rdap_endpoint="https://rdap.nic.ac/domain/", whois_server="whois.nic.ac", whois_enabled=True),
]


# ============================================================================
# BUSINESS & PROFESSIONAL
# ============================================================================
BUSINESS_TLDS = [
    TLDConfig(tld="company", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="business", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="consulting", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="services", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="group", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="team", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="work", rdap_endpoint="https://rdap.centralnic.com/work/domain/", whois_server="whois.centralnic.com", whois_enabled=True),
    TLDConfig(tld="jobs", rdap_endpoint="https://rdap.nic.jobs/domain/", whois_server="whois.nic.jobs", whois_enabled=True),
    TLDConfig(tld="careers", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="finance", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="money", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="capital", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="ventures", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="holdings", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="partners", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="legal", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="law", rdap_endpoint="https://rdap.nic.law/domain/", whois_server="whois.nic.law", whois_enabled=True),
    TLDConfig(tld="tax", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="accountant", rdap_endpoint="https://rdap.nic.accountant/domain/", whois_server="whois.nic.accountant", whois_enabled=True),
    TLDConfig(tld="insurance", rdap_endpoint="https://rdap.nic.insurance/domain/", whois_server="whois.nic.insurance", whois_enabled=True),
]


# ============================================================================
# LIFESTYLE & ENTERTAINMENT
# ============================================================================
LIFESTYLE_TLDS = [
    TLDConfig(tld="art", rdap_endpoint="https://rdap.nic.art/domain/", whois_server="whois.nic.art", whois_enabled=True),
    TLDConfig(tld="music", rdap_endpoint="https://rdap.nic.music/domain/", whois_server="whois.nic.music", whois_enabled=True),
    TLDConfig(tld="video", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="photo", rdap_endpoint="https://rdap.uniregistry.net/rdap/domain/", whois_server="whois.uniregistry.net", whois_enabled=True),
    TLDConfig(tld="photography", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="gallery", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="fashion", rdap_endpoint="https://rdap.centralnic.com/fashion/domain/", whois_server="whois.centralnic.com", whois_enabled=True),
    TLDConfig(tld="style", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="fitness", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="health", rdap_endpoint="https://rdap.nic.health/domain/", whois_server="whois.nic.health", whois_enabled=True),
    TLDConfig(tld="yoga", rdap_endpoint="https://rdap.centralnic.com/yoga/domain/", whois_server="whois.centralnic.com", whois_enabled=True),
    TLDConfig(tld="travel", rdap_endpoint="https://rdap.nic.travel/domain/", whois_server="whois.nic.travel", whois_enabled=True),
    TLDConfig(tld="holiday", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="restaurant", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="cafe", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="bar", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="beer", rdap_endpoint="https://rdap.centralnic.com/beer/domain/", whois_server="whois.centralnic.com", whois_enabled=True),
    TLDConfig(tld="wine", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="pizza", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="game", rdap_endpoint="https://rdap.uniregistry.net/rdap/domain/", whois_server="whois.uniregistry.net", whois_enabled=True),
    TLDConfig(tld="games", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="casino", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="bet", rdap_endpoint="https://rdap.afilias.net/rdap/bet/domain/", whois_server="whois.afilias.net", whois_enabled=True),
]


# ============================================================================
# REAL ESTATE & PROPERTY
# ============================================================================
REALESTATE_TLDS = [
    TLDConfig(tld="house", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="homes", rdap_endpoint="https://rdap.nic.homes/domain/", whois_server="whois.nic.homes", whois_enabled=True),
    TLDConfig(tld="property", rdap_endpoint="https://rdap.uniregistry.net/rdap/domain/", whois_server="whois.uniregistry.net", whois_enabled=True),
    TLDConfig(tld="properties", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="land", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="estate", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="apartments", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="rent", rdap_endpoint="https://rdap.nic.rent/domain/", whois_server="whois.nic.rent", whois_enabled=True),
]

# ============================================================================
# EDUCATION & COMMUNITY
# ============================================================================
EDUCATION_TLDS = [
    TLDConfig(tld="edu", rdap_endpoint=RDAP_FALLBACK, whois_server="whois.educause.edu", whois_enabled=True),
    TLDConfig(tld="academy", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="school", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="university", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="college", rdap_endpoint="https://rdap.nic.college/domain/", whois_server="whois.nic.college", whois_enabled=True),
    TLDConfig(tld="training", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="courses", rdap_endpoint="https://rdap.nic.courses/domain/", whois_server="whois.nic.courses", whois_enabled=True),
    TLDConfig(tld="community", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="social", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="chat", rdap_endpoint="https://rdap.donuts.co/rdap/domain/", whois_server="whois.donuts.co", whois_enabled=True),
    TLDConfig(tld="forum", rdap_endpoint="https://rdap.nic.forum/domain/", whois_server="whois.nic.forum", whois_enabled=True),
]


# ============================================================================
# GOOGLE TLDs
# ============================================================================
GOOGLE_TLDS = [
    TLDConfig(tld="page", rdap_endpoint="https://rdap.nic.google/domain/", whois_server="whois.nic.google", whois_enabled=True),
    TLDConfig(tld="new", rdap_endpoint="https://rdap.nic.google/domain/", whois_server="whois.nic.google", whois_enabled=True),
    TLDConfig(tld="how", rdap_endpoint="https://rdap.nic.google/domain/", whois_server="whois.nic.google", whois_enabled=True),
    TLDConfig(tld="soy", rdap_endpoint="https://rdap.nic.google/domain/", whois_server="whois.nic.google", whois_enabled=True),
    TLDConfig(tld="foo", rdap_endpoint="https://rdap.nic.google/domain/", whois_server="whois.nic.google", whois_enabled=True),
]

# ============================================================================
# COMBINE ALL TLDs
# ============================================================================
DEFAULT_TLDS = (
    GENERIC_TLDS +
    TECH_TLDS +
    POPULAR_NEW_TLDS +
    EUROPE_TLDS +
    NORDIC_TLDS +
    UK_TLDS +
    AMERICAS_TLDS +
    ASIA_PACIFIC_TLDS +
    MEA_TLDS +
    CIS_TLDS +
    SPECIAL_TLDS +
    BUSINESS_TLDS +
    LIFESTYLE_TLDS +
    REALESTATE_TLDS +
    EDUCATION_TLDS +
    GOOGLE_TLDS
)

# Total count for reference
TLD_COUNT = len(DEFAULT_TLDS)
