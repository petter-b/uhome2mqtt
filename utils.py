import ipaddress
import re


def is_valid_ip(address: str) -> bool:
    """Check if a string is a valid IP address."""
    try:
        ipaddress.ip_address(address)
        return True
    except ValueError:
        return False


def is_valid_fqdn(hostname: str) -> bool:
    """Check if a string is a valid fully-qualified domain name."""
    fqdn_regex = (
        r'^(?=.{1,253}$)((?!-)[A-Za-z0-9-]{1,63}(?<!-)\.)+[A-Za-z]{2,63}$'
    )
    return re.match(fqdn_regex, hostname) is not None

def is_valid_hostname(hostname: str) -> bool:
    """Check if a string is a valid hostname."""
    if hostname == "localhost":
        return True
    return is_valid_fqdn(hostname)

def is_valid_mqtt_topic(topic: str) -> bool:
    """Check if a string is a valid MQTT topic."""
    # MQTT topic rules
    if len(topic) == 0 or len(topic) > 65535:
        return False
    if '+' in topic or '#' in topic:
        return False
    # Check for invalid characters (optional, based on your specific needs)
    invalid_chars = re.compile(r'[\x00-\x1F\x7F]')
    return not invalid_chars.search(topic)