"""Privacy-minimized labels derived from client-supplied request metadata."""
import ipaddress


def client_labels(user_agent):
    # Never persist the raw header: it is client-controlled and can contain arbitrary data.
    value = (user_agent or '')[:1024].lower()
    if not value:
        return 'Not provided', 'Not provided'
    if 'ipad' in value or 'tablet' in value:
        device = 'Reported tablet'
    elif any(token in value for token in ('iphone', 'ipod', 'mobile', 'windows phone')) or ('android' in value and 'mobile' in value):
        device = 'Reported mobile'
    elif any(token in value for token in ('windows nt', 'macintosh', 'x11', 'linux')):
        device = 'Reported desktop'
    else:
        device = 'Unknown device'
    if 'edg/' in value:
        browser = 'Microsoft Edge'
    elif 'opr/' in value or 'opera' in value:
        browser = 'Opera'
    elif 'firefox/' in value or 'fxios/' in value:
        browser = 'Firefox'
    elif 'chrome/' in value or 'crios/' in value:
        browser = 'Chrome'
    elif 'safari/' in value:
        browser = 'Safari'
    else:
        browser = 'Unknown browser'
    return device, browser


def approximate_source(value):
    try:
        address = ipaddress.ip_address(value.split('%', 1)[0])
        prefix = 24 if address.version == 4 else 48
        return str(ipaddress.ip_network(f'{address}/{prefix}', strict=False))
    except (AttributeError, ValueError):
        return 'Unavailable'
