import os
import dns.query
import dns.zone
import dns.tsigkeyring
from flask import Flask, render_template
from flask_socketio import SocketIO
from pydantic_settings import BaseSettings
import time
import logging
import socket

# Pydantic Settings to load environment variables
class Settings(BaseSettings):
    domain: str
    ns_server: str
    ns_server_port: int
    key_name: str
    key_secret: str

    class Config:
        env_prefix = 'DNS_'  # Environment variable prefix
        env_file = '.env'    # Specify the .env file

# Load settings
settings = Settings()

# Flask app and SocketIO initialization
app = Flask(__name__)
socketio = SocketIO(app)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

def check_dns_resolution(hostname):
    """Check if the hostname can be resolved."""
    try:
        logging.debug(f"Checking DNS resolution for {hostname}.")
        ip_address = socket.gethostbyname(hostname)
        logging.info(f"Successfully resolved {hostname} to {ip_address}.")
        return True
    except socket.gaierror:
        logging.error(f"Failed to resolve {hostname}.")
        return False

def test_dns(host=settings.ns_server, port=settings.ns_server_port, timeout=3):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error as ex:
        print(ex)
        return False

def get_dns_records():
    logging.info("Attempting to fetch DNS records.")
    
    # Create the TSIG keyring using the environment variables
    keyring = dns.tsigkeyring.from_text({
        settings.key_name: settings.key_secret
    })

    # Perform zone transfer using the TSIG key
    try:
        logging.debug(f"Performing zone transfer for {settings.domain} using {settings.ns_server}:{settings.ns_server_port}.")
        zone = dns.zone.from_xfr(
            dns.query.xfr(where=settings.ns_server, zone=settings.domain, port=settings.ns_server_port, keyring=keyring,keyalgorithm='hmac-sha256')
        )
        logging.info("Zone transfer successful.")
    except dns.exception.DNSException as e:
        logging.error(f"DNS error during zone transfer: {e}")
    except Exception as e:
        logging.error(f"General error during zone transfer: {e}")
        return {'error': str(e)}

    # Get all DNS records created by external-dns
    records = []
    for name, node in zone.nodes.items():
        for _record in node.rdatasets:
            for rdata in _record:
                record = {
                    'name': name.to_text(),
                    'type': dns.rdatatype.to_text(_record.rdtype),
                    'data': rdata.to_text(),
                    'rdataset': _record.to_text(),
                    'ttl': _record.ttl
                }
                records.append(record)
                logging.debug(f"Found record: {record}")

    logging.info(f"Total records found: {len(records)}")
    return records

def fetch_and_emit_records():
    while True:
        records = get_dns_records()
        socketio.emit('dns_records', {'records': records})
        logging.info("Emitted DNS records to clients.")
        time.sleep(30)  # Fetch records every 30 seconds

@app.route('/')
def index():
    logging.info("Index route accessed.")
    return render_template('index.html')

if __name__ == "__main__":
    logging.info("Starting the application...")

    # Check if the DNS server and the domain can be resolved at startup
    check_dns_resolution(settings.ns_server)
    check_dns_resolution(settings.domain)

    socketio.start_background_task(target=fetch_and_emit_records)
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
